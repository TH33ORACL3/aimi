#!/usr/bin/env python3
"""Reliable no-agent watcher for newly observed AIMI model routes.

The AIMI endpoint monitor is the source of truth for polling and raw evidence.
This wrapper runs that monitor, promotes endpoint-only candidates into the
catalogue's route/event tables, and sends Telegram notifications for added or
removed provider routes.

Delivery is deliberately at-least-once. A durable pending outbox is written
before sending and the endpoint-change watermark advances only after
``hermes send --json`` succeeds. A crash in the small post-send persistence
window may produce one duplicate alert, but a Telegram outage cannot silently
lose a discovery or removal notification.

Provider failures are reported on transition/change and recovery, not on every
poll. The watcher never infers release dates, pricing, capabilities, or free
access from an endpoint listing and never tests model responses.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Resolve the project from this file so the repository stays portable and no
# personal home path is committed. The Hermes wrapper invokes this script by
# absolute path, which keeps working under any checkout location.
PROJECT = Path(__file__).resolve().parent
DB = PROJECT / 'aimi.db'
MONITOR = PROJECT / 'monitor_endpoints.py'
INGEST = PROJECT / 'ingest_endpoint_candidates.py'
STATE = Path.home() / '.hermes' / 'cron' / 'model-catalogue-discovery-notifier.json'
LOCK = Path.home() / '.hermes' / 'cron' / 'model-catalogue-discovery-notifier.lock'
VERSION = 'model-catalogue-discovery-notifier/2.1'
HERMES_TARGET = os.environ.get('AIMI_TELEGRAM_TARGET', 'telegram:7104596722')
HERMES_TIMEOUT_SECONDS = 60
DELIVERY_ATTEMPTS = 2
MAX_MESSAGE_CHARS = 3900
LOCAL_TIMEZONE_NAME = os.environ.get('AIMI_LOCAL_TIMEZONE', 'Africa/Johannesburg')
try:
    LOCAL_TIMEZONE = ZoneInfo(LOCAL_TIMEZONE_NAME)
except ZoneInfoNotFoundError:
    # A broken optional override must not stop the discovery watcher. The
    # default machine timezone is South Africa, but UTC is a safe fallback.
    LOCAL_TIMEZONE_NAME = 'UTC'
    LOCAL_TIMEZONE = timezone.utc

# Pi and some harnesses use a shortened provider label in their own config.
# Map those onto catalogue provider ids so an impact match is exact rather than
# a fuzzy substring, which produced false alarms during review.
HARNESS_PROVIDER_ALIASES = {
    'opencode': 'opencode-zen',
    'nvidia': 'nvidia-nim',
    'cloudflare-workers-ai': 'cloudflare-ai',
}

# Redact likely credential-shaped values before writing an error into the
# state file or sending it to Telegram. Endpoint errors should be actionable,
# but never become a secret exfiltration path.
SECRET_PATTERNS = (
    re.compile(r'bot\d+:[A-Za-z0-9_-]+'),
    re.compile(r'(?i)\bsk-[A-Za-z0-9_-]+'),
    re.compile(r'(?i)\bAIza[A-Za-z0-9_-]+'),
    re.compile(r'(?i)\bxai-[A-Za-z0-9_-]+'),
)


class DeliveryError(RuntimeError):
    """Telegram delivery failed and the pending outbox must be retried."""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def format_local_time(value: object) -> str:
    """Render an ISO timestamp in Aubrey's configured local timezone."""
    text = str(value or '').strip()
    if not text:
        return 'Unknown'
    normalized = text[:-1] + '+00:00' if text.endswith('Z') else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(LOCAL_TIMEZONE)
    return local.strftime('%d %b %Y, %H:%M:%S %Z')


def safe_error(value: object, limit: int = 700) -> str:
    text = str(value or 'unknown error').strip()
    for pattern in SECRET_PATTERNS:
        text = pattern.sub('<redacted>', text)
    return text[:limit]


def initial_state(last_change_id: int) -> dict:
    return {
        'version': VERSION,
        'last_change_id': int(last_change_id),
        'last_poll_at': None,
        'last_monitor_exit_code': None,
        'last_provider_results': [],
        'provider_failures': {},
        'last_hard_error': None,
        'last_delivery': None,
        'pending_notification': None,
    }


def load_state() -> dict | None:
    if not STATE.exists():
        return None
    try:
        value = json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Invalid watcher state at {STATE}: {safe_error(exc)}') from exc
    if not isinstance(value, dict) or not isinstance(value.get('last_change_id'), int):
        raise RuntimeError(f'Invalid watcher state at {STATE}: expected integer last_change_id')
    if value['last_change_id'] < 0:
        raise RuntimeError(f'Invalid watcher state at {STATE}: last_change_id must be non-negative')
    pending = value.get('pending_notification')
    if pending is not None and not isinstance(pending, dict):
        raise RuntimeError(f'Invalid watcher state at {STATE}: pending_notification must be an object')
    value.setdefault('provider_failures', failure_snapshot(value.get('last_provider_results', [])))
    value.setdefault('last_hard_error', None)
    value.setdefault('last_delivery', None)
    value.setdefault('pending_notification', None)
    return value


def save_state(value: dict) -> None:
    """Atomically replace the state file and keep it private."""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{STATE.name}.', dir=STATE.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
        os.replace(temp_name, STATE)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA busy_timeout=10000')
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


def max_change_id(connection: sqlite3.Connection) -> int:
    return int(
        connection.execute(
            'SELECT COALESCE(MAX(endpoint_change_id), 0) FROM endpoint_changes'
        ).fetchone()[0]
    )


def run_aimi_script(path: Path) -> subprocess.CompletedProcess[str]:
    if not path.exists():
        raise RuntimeError(f'Missing AIMI script: {path}')
    # Hermes starts jobs with a minimal environment. Source Aubrey's exported
    # provider credentials without ever printing the sourced file or values.
    command = (
        "source ~/.zshrc >/dev/null 2>&1; "
        f'exec {json.dumps(sys.executable)} {json.dumps(str(path))}'
    )
    environment = os.environ.copy()
    environment.setdefault(
        'PATH',
        '/Users/TH33_ORACL3/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:'
        '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
    )
    return subprocess.run(
        ['/bin/zsh', '-lc', command],
        cwd=PROJECT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


def parse_monitor_output(result: subprocess.CompletedProcess[str]) -> list[dict]:
    output = (result.stdout or '').strip()
    if not output:
        monitor_detail = (result.stderr or '').strip()[-500:]
        raise RuntimeError(
            f'AIMI monitor returned no JSON (exit {result.returncode}): '
            f'{safe_error(monitor_detail)}'
        )
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'AIMI monitor returned invalid JSON: {safe_error(exc)}') from exc
    if not isinstance(parsed, list):
        raise RuntimeError('AIMI monitor returned JSON other than a provider result list')
    return parsed


def hermes_binary() -> str:
    configured = os.environ.get('AIMI_HERMES_BIN')
    if configured:
        return configured
    return shutil.which('hermes') or str(Path.home() / '.local' / 'bin' / 'hermes')


def parse_delivery_result(stdout: str) -> dict:
    """Extract non-secret delivery metadata without requiring a fixed Hermes schema."""
    if not stdout.strip():
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    candidates = [payload]
    if isinstance(payload, dict) and isinstance(payload.get('payload'), dict):
        candidates.append(payload['payload'])
    candidates = [candidate for candidate in candidates if isinstance(candidate, dict)]
    for candidate in candidates:
        if candidate.get('ok') is False:
            raise DeliveryError(safe_error(candidate.get('error') or candidate))
    for candidate in candidates:
        message_id = candidate.get('messageId') or candidate.get('message_id')
        if message_id is not None:
            return {'message_id': str(message_id)}
    return {}


def send_via_hermes(
    text: str,
    *,
    runner=None,
    sleep_fn=time.sleep,
) -> dict:
    """Send through Hermes' configured Telegram adapter and require success.

    The optional runner/sleep_fn hooks keep this function unit-testable without
    sending a real Telegram message.
    """
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix='.aimi-discovery-', suffix='.txt', dir=STATE.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)

        command = [
            hermes_binary(),
            'send',
            '--to',
            HERMES_TARGET,
            '--file',
            temp_name,
            '--json',
        ]
        environment = os.environ.copy()
        environment.setdefault(
            'PATH',
            '/Users/TH33_ORACL3/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:'
            '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
        )
        invoke = runner or subprocess.run
        errors: list[str] = []
        for attempt in range(DELIVERY_ATTEMPTS):
            try:
                result = invoke(
                    command,
                    cwd=PROJECT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=HERMES_TIMEOUT_SECONDS,
                    check=False,
                )
                if result.returncode == 0:
                    metadata = parse_delivery_result(result.stdout or '')
                    metadata.update({'target': HERMES_TARGET, 'sent_at': now()})
                    return metadata
                delivery_detail = result.stderr or result.stdout or 'no error output'
                errors.append(
                    f'exit {result.returncode}: '
                    f'{safe_error(delivery_detail)}'
                )
            except subprocess.TimeoutExpired:
                errors.append(f'timed out after {HERMES_TIMEOUT_SECONDS}s')
            except OSError as exc:
                errors.append(safe_error(exc))
            except DeliveryError:
                raise
            if attempt + 1 < DELIVERY_ATTEMPTS:
                sleep_fn(3)
        raise DeliveryError('; '.join(errors[-DELIVERY_ATTEMPTS:]))
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def deliver_notification(text: str) -> dict:
    return send_via_hermes(text)


def route_rows(
    connection: sqlite3.Connection,
    last_change_id: int,
    change_type: str,
) -> list[sqlite3.Row]:
    """Endpoint changes of one type newer than the durable watermark."""
    return connection.execute(
        """
        SELECT
          ec.endpoint_change_id,
          ec.provider_id,
          ec.model_identifier,
          ec.detected_at,
          COALESCE(cm.canonical_name, pm.display_name, ec.model_identifier) AS model_name,
          COALESCE(p.display_name, ec.provider_id) AS provider_name,
          pm.endpoint_first_seen_at,
          pm.context_window_tokens,
          pm.max_input_tokens,
          pm.max_output_tokens,
          pm.reasoning,
          pm.tools,
          pm.function_calling,
          pm.structured_outputs,
          pm.streaming,
          pm.input_modalities_json,
          pm.output_modalities_json,
          pm.tokenizer,
          pm.quantization,
          pm.description,
          COALESCE(
            (SELECT ao.offer_type
             FROM access_offers ao
             WHERE ao.provider_model_id = pm.provider_model_id
               AND (ao.ends_at IS NULL OR datetime(ao.ends_at) > datetime('now'))
             ORDER BY CASE ao.offer_type
               WHEN 'genuine_zero_price' THEN 1
               WHEN 'free_tier_quota' THEN 2
               WHEN 'temporary_free_window' THEN 3
               WHEN 'subscription_included' THEN 4
               WHEN 'paid' THEN 5
               ELSE 6 END
             LIMIT 1),
            'not classified'
          ) AS access_type,
          COALESCE(
            (SELECT mt.url
             FROM monitoring_targets mt
             WHERE mt.provider_id = ec.provider_id
               AND mt.target_type = 'models_endpoint'
             ORDER BY mt.monitoring_target_id DESC
             LIMIT 1),
            'endpoint URL unavailable'
          ) AS endpoint_url
        FROM endpoint_changes ec
        LEFT JOIN provider_models_v2 pm
          ON pm.provider_id = ec.provider_id
         AND pm.model_identifier = ec.model_identifier
        LEFT JOIN canonical_models cm ON cm.canonical_model_id = pm.canonical_model_id
        LEFT JOIN providers p ON p.provider_id = ec.provider_id
        WHERE ec.endpoint_change_id > ?
          AND ec.change_type = ?
        ORDER BY ec.endpoint_change_id
        """,
        (last_change_id, change_type),
    ).fetchall()


def configured_models(connection: sqlite3.Connection) -> set[tuple[str, str]]:
    """Every (provider, model) currently enabled in a locally installed harness."""
    pairs: set[tuple[str, str]] = set()
    for provider, model in connection.execute(
        """SELECT e.configured_provider_name, e.configured_model_identifier
           FROM harness_model_entries e
           JOIN harness_installations i USING(installation_id)
           WHERE e.enabled = 1 AND i.installed = 1"""
    ):
        if not provider or not model:
            continue
        pairs.add((HARNESS_PROVIDER_ALIASES.get(provider, provider), model))
    return pairs


def impact(route: sqlite3.Row, configured: set[tuple[str, str]]) -> bool:
    """Exact provider and model match only. Suffix matching produced false alarms."""
    return (route['provider_id'], route['model_identifier']) in configured


# Telegram truncates long messages, and a provider withdrawing a whole family can
# produce dozens of routes in one poll. Detail the first few, then summarise.
DETAIL_LIMIT = 4

PROVIDER_LABELS = {
    'cloudflare-ai': 'Cloudflare Workers AI',
    'nvidia-nim': 'NVIDIA NIM',
    'ollama-cloud': 'Ollama Cloud',
    'opencode-go': 'OpenCode Go',
    'opencode-zen': 'OpenCode Zen',
    'openrouter': 'OpenRouter',
}


def route_value(route: sqlite3.Row, key: str, default=None):
    """Read optional route fields while keeping old test fixtures compatible."""
    try:
        if key not in route.keys():
            return default
        return route[key]
    except (AttributeError, IndexError, KeyError):
        return default


def provider_label(route: sqlite3.Row) -> str:
    provider = str(route_value(route, 'provider_id', 'unknown'))
    return str(route_value(route, 'provider_name') or PROVIDER_LABELS.get(provider, provider))


def inline_code(value: object) -> str:
    text = 'Unknown' if value is None else str(value)
    text = text.replace('`', "'").replace('\n', ' ')
    return f'`{text}`'


def format_tokens(value: object) -> str:
    if value is None or value == '':
        return 'Unknown'
    try:
        return f'{int(value):,} tokens'
    except (TypeError, ValueError):
        return str(value)


def format_tristate(value: object) -> str:
    if value is None:
        return 'Unknown'
    try:
        return 'Yes' if int(value) else 'No'
    except (TypeError, ValueError):
        return str(value)


def format_json_list(value: object) -> str:
    if value is None or value == '':
        return 'Unknown'
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
    if isinstance(parsed, list):
        items = []
        for item in parsed:
            if isinstance(item, dict):
                item = item.get('id') or item.get('type') or item.get('name') or item
            items.append(str(item))
        return ', '.join(items) if items else 'Unknown'
    if isinstance(parsed, dict):
        return ', '.join(str(key) for key in parsed) or 'Unknown'
    return str(parsed)


def format_access(value: object) -> str:
    labels = {
        'free_tier_quota': 'Free developer/evaluation quota',
        'genuine_zero_price': 'Genuinely zero-price',
        'temporary_free_window': 'Temporary free window',
        'subscription_included': 'Subscription access',
        'paid': 'Paid',
        'not classified': 'Not classified',
        'unknown': 'Unknown',
    }
    text = str(value or 'unknown')
    return labels.get(text, text.replace('_', ' ').capitalize())


def format_metadata(route: sqlite3.Row) -> list[str]:
    context_window = route_value(route, 'context_window_tokens')
    max_input = route_value(route, 'max_input_tokens')
    max_output = route_value(route, 'max_output_tokens')
    lines = [
        f'• Context window: {format_tokens(context_window)}',
        f'• Max input: {format_tokens(max_input)}',
        f'• Max output: {format_tokens(max_output)}',
    ]
    capability_keys = ('reasoning', 'tools', 'function_calling', 'structured_outputs', 'streaming')
    if any(route_value(route, key) is not None for key in capability_keys):
        labels = {
            'reasoning': 'reasoning',
            'tools': 'tools',
            'function_calling': 'function calling',
            'structured_outputs': 'structured output',
            'streaming': 'streaming',
        }
        capabilities = ' · '.join(
            f"{labels[key]}: {format_tristate(route_value(route, key))}"
            for key in capability_keys
        )
        lines.append(f'• Capabilities: {capabilities}')
    else:
        lines.append('• Capabilities: Unknown')

    input_modalities = format_json_list(route_value(route, 'input_modalities_json'))
    output_modalities = format_json_list(route_value(route, 'output_modalities_json'))
    if input_modalities != 'Unknown' or output_modalities != 'Unknown':
        lines.append(f'• Modalities: input {input_modalities} · output {output_modalities}')
    else:
        lines.append('• Modalities: Unknown')

    tokenizer = route_value(route, 'tokenizer')
    quantization = route_value(route, 'quantization')
    if tokenizer is not None:
        lines.append(f'• Tokenizer: {tokenizer}')
    if quantization is not None:
        lines.append(f'• Quantization: {quantization}')
    return lines


def format_route_card(route: sqlite3.Row, position: int, *, removed: bool, configured: set[tuple[str, str]]) -> list[str]:
    provider = str(route_value(route, 'provider_id', 'unknown'))
    model = str(route_value(route, 'model_identifier', 'unknown'))
    name = str(route_value(route, 'model_name', model))
    route_id = f'{provider}/{model}'
    endpoint = route_value(route, 'endpoint_url', 'Unknown')
    marker = '⚠️' if removed else '🆕'
    lines = [
        f'**{position}. {marker} {provider_label(route)}**',
        f'**Model:** {inline_code(name)}',
        f'**Route:** {inline_code(route_id)}',
        f'**Endpoint:** {inline_code(endpoint)}',
    ]
    if removed:
        last_listed = format_local_time(route_value(route, 'detected_at'))
        lines.append(f'**Last listed:** {last_listed}')
        if impact(route, configured):
            lines.append('🚨 **Still enabled locally.**')
    else:
        first_seen = format_local_time(route_value(route, 'detected_at'))
        access = format_access(route_value(route, 'access_type'))
        lines.extend(
            [
                f'**First seen:** {first_seen}',
                f'**Access:** {access}',
                '**Metadata**',
                *format_metadata(route),
            ]
        )
        description = str(route_value(route, 'description') or '').strip()
        if description:
            description = ' '.join(description.split())
            if len(description) > 240:
                description = description[:237].rstrip() + '...'
            lines.append(f'**Description:** {description}')
    lines.append('')
    return lines


def overflow(routes: list[sqlite3.Row], noun: str) -> list[str]:
    extra = routes[DETAIL_LIMIT:]
    if not extra:
        return []
    by_provider: dict[str, int] = {}
    for route in extra:
        by_provider[route['provider_id']] = by_provider.get(route['provider_id'], 0) + 1
    summary = ', '.join(f'{provider} {count}' for provider, count in sorted(by_provider.items()))
    return [f'...and {len(extra)} more {noun}(s): {summary}', '']


def bound_message(text: str) -> str:
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return text[: MAX_MESSAGE_CHARS - 80].rstrip() + '\n\n...message truncated; inspect AIMI endpoint_changes for the full list.'


def format_notification(
    added: list[sqlite3.Row],
    removed: list[sqlite3.Row],
    configured: set[tuple[str, str]],
) -> str:
    lines: list[str] = []

    if added:
        lines.extend(
            [
                f'🆕 **New AI model routes discovered ({len(added)})**',
                '_AIMI endpoint monitor · local time_',
                '',
            ]
        )
        for position, route in enumerate(added[:DETAIL_LIMIT], start=1):
            lines.extend(format_route_card(route, position, removed=False, configured=configured))
        lines.extend(overflow(added, 'addition'))

    if removed:
        # A provider withdrawing a whole family produces a long list. Show the
        # routes that actually affect a locally configured model first, so the
        # actionable ones survive the detail limit.
        ordered = sorted(removed, key=lambda route: not impact(route, configured))
        affected = [route for route in removed if impact(route, configured)]
        if lines:
            lines.append('')
        lines.extend(
            [
                f'⚠️ **Model routes removed from their provider ({len(removed)})**',
                '_AIMI endpoint monitor · local time_',
                '',
            ]
        )
        for position, route in enumerate(ordered[:DETAIL_LIMIT], start=1):
            lines.extend(format_route_card(route, position, removed=True, configured=configured))
        lines.extend(overflow(ordered, 'removal'))
        if affected:
            lines.append(
                f'🚨 **{len(affected)} removed route(s) are still enabled locally and may now fail.**'
            )
            lines.append('')

    lines.extend(
        [
            'ℹ️ _Endpoint observation only. AIMI has not treated this as an official release or retirement date._',
            '_Pricing, capabilities, and free status remain evidence-dependent._',
        ]
    )
    return bound_message('\n'.join(lines))


def failure_snapshot(results: list[dict] | None) -> dict[str, str]:
    failures: dict[str, str] = {}
    for item in results or []:
        if not isinstance(item, dict) or item.get('status') != 'failed':
            continue
        provider = str(item.get('provider') or 'unknown')
        failures[provider] = safe_error(item.get('error', 'unknown error'))
    return failures


def provider_statuses(results: list[dict] | None) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for item in results or []:
        if not isinstance(item, dict) or not item.get('provider'):
            continue
        statuses[str(item['provider'])] = str(item.get('status') or 'unknown')
    return statuses


def failure_transitions(
    previous_failures: dict[str, str] | None,
    results: list[dict] | None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Return new/changed failures and confirmed provider recoveries."""
    previous = previous_failures or {}
    current = failure_snapshot(results)
    statuses = provider_statuses(results)
    new = sorted((provider, error) for provider, error in current.items() if previous.get(provider) != error)
    recovered = sorted(
        provider
        for provider in previous
        if provider in statuses and statuses[provider] != 'failed' and provider not in current
    )
    return new, recovered


def format_failure_transitions(
    new_failures: list[tuple[str, str]],
    recovered: list[str],
) -> str:
    if not new_failures and not recovered:
        return ''
    lines = ['AIMI model endpoint monitor status changed:', '']
    for provider, error in new_failures:
        lines.append(f'• {provider} failed: {error}')
    for provider in recovered:
        lines.append(f'• {provider} recovered')
    return '\n'.join(lines)


def format_hard_failure(error: str) -> str:
    return bound_message(
        'AIMI model discovery monitor failed:\n\n'
        f'• {safe_error(error)}\n\n'
        'The pending state will be retried on the next scheduled run.'
    )


def format_hard_recovery(previous_error: str | None) -> str:
    if not previous_error:
        return ''
    return 'AIMI model discovery monitor recovered after a watcher failure:\n\n' f'• {safe_error(previous_error)}'


def pending_record(body: str, up_to_change_id: int, kind: str) -> dict:
    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()[:16]
    return {
        'id': f'{kind}-{up_to_change_id}-{digest}',
        'kind': kind,
        'body': body,
        'up_to_change_id': int(up_to_change_id),
        'created_at': now(),
        'attempts': 0,
        'last_attempt_at': None,
        'last_error': None,
    }


def deliver_pending(state: dict) -> dict | None:
    """Retry one durable notification; only then advance its watermark."""
    pending = state.get('pending_notification')
    if not pending:
        return None
    try:
        result = deliver_notification(str(pending['body']))
    except Exception as exc:
        pending['attempts'] = int(pending.get('attempts') or 0) + 1
        pending['last_attempt_at'] = now()
        pending['last_error'] = safe_error(exc)
        save_state(state)
        if isinstance(exc, DeliveryError):
            raise
        raise DeliveryError(safe_error(exc)) from exc

    state['pending_notification'] = None
    state['last_change_id'] = max(
        int(state.get('last_change_id', 0)),
        int(pending.get('up_to_change_id', state.get('last_change_id', 0))),
    )
    state['last_delivery'] = {
        'notification_id': pending.get('id'),
        'kind': pending.get('kind'),
        **(result or {}),
    }
    save_state(state)
    return result or {}


def queue_and_deliver(state: dict, body: str, up_to_change_id: int, kind: str) -> dict:
    """Persist an outbox item before attempting delivery."""
    state['pending_notification'] = pending_record(body, up_to_change_id, kind)
    save_state(state)
    return deliver_pending(state) or {}


def report_delivery_failure(exc: Exception) -> None:
    # This stdout is intentionally a fallback for the outer Hermes job's
    # existing `deliver: telegram` path. The discovery body is not printed, so
    # a successful fallback cannot duplicate the actual discovery alert.
    print(
        'AIMI model discovery notification delivery failed; '
        f'the alert is retained for retry. {safe_error(exc)}'
    )


def handle_hard_failure(state: dict, last_change_id: int, error: Exception) -> int:
    message = safe_error(error)
    state['last_poll_at'] = now()
    state['last_monitor_exit_code'] = None
    if state.get('last_hard_error') == message:
        # The transition was already reported. Keep the scheduler healthy and
        # avoid sending the same persistent outage every 15 minutes.
        save_state(state)
        return 0

    state['last_hard_error'] = message
    # Never move the discovery watermark while the monitor/ingestion path is
    # unhealthy. The monitor may have committed some endpoint_changes before
    # failing; leaving the old watermark guarantees those routes are revisited
    # and included after the next successful poll.
    pending_watermark = int(state.get('last_change_id', last_change_id))
    try:
        queue_and_deliver(state, format_hard_failure(message), pending_watermark, 'hard-failure')
    except DeliveryError as exc:
        report_delivery_failure(exc)
        return 1
    return 0


def main() -> int:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('w', encoding='utf-8') as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # A slow provider batch is still running. Avoid overlapping polls.
            return 0

        try:
            return run_locked()
        except Exception as exc:  # pragma: no cover - final scheduler guard
            print(f'AIMI model discovery watcher crashed: {safe_error(exc)}')
            return 1


def run_locked() -> int:
    state = load_state()

    # Retry an outbox item before polling again. This prevents a Telegram
    # outage from allowing the endpoint watermark to move past an undelivered
    # alert. Once it is acknowledged, the same run can continue polling.
    if state is not None and state.get('pending_notification'):
        try:
            deliver_pending(state)
        except DeliveryError as exc:
            report_delivery_failure(exc)
            return 1

    try:
        connection = db_connection()
        before_poll_max = max_change_id(connection)
        connection.close()
    except Exception as exc:
        baseline = int(state.get('last_change_id', 0)) if state else 0
        if state is None:
            state = initial_state(baseline)
        return handle_hard_failure(state, baseline, exc)

    # On first startup, suppress historical endpoint changes but still alert on
    # additions created by this first poll.
    if state is None:
        state = initial_state(before_poll_max)
    last_change_id = int(state['last_change_id'])
    previous_failures = state.get('provider_failures') or failure_snapshot(
        state.get('last_provider_results', [])
    )
    previous_hard_error = state.get('last_hard_error')

    try:
        monitor = run_aimi_script(MONITOR)
        results = parse_monitor_output(monitor)

        # Successful provider polls are committed even when another provider
        # is unavailable. Promote endpoint-only candidates before building the
        # alert. A hard ingestion failure leaves the watermark unchanged.
        ingest = run_aimi_script(INGEST)
        if ingest.returncode != 0:
            detail = (ingest.stderr or ingest.stdout or '').strip()[-700:]
            raise RuntimeError(
                f'AIMI endpoint candidate ingestion failed (exit {ingest.returncode}): '
                f'{safe_error(detail)}'
            )
    except Exception as exc:
        return handle_hard_failure(state, last_change_id, exc)

    try:
        connection = db_connection()
        current_max = max_change_id(connection)
        added = route_rows(connection, last_change_id, 'model_added')
        removed = route_rows(connection, last_change_id, 'model_removed')
        configured = configured_models(connection)
        connection.close()
    except Exception as exc:
        return handle_hard_failure(state, last_change_id, exc)

    current_failures = failure_snapshot(results)
    new_failures, recovered_failures = failure_transitions(previous_failures, results)
    state.update(
        {
            'version': VERSION,
            'last_poll_at': now(),
            'last_monitor_exit_code': monitor.returncode,
            'last_provider_results': results,
            'provider_failures': current_failures,
            'last_hard_error': None,
        }
    )

    message_parts: list[str] = []
    if added or removed:
        message_parts.append(format_notification(added, removed, configured))
    failure_text = format_failure_transitions(new_failures, recovered_failures)
    if failure_text:
        message_parts.append(bound_message(failure_text))
    hard_recovery = format_hard_recovery(previous_hard_error)
    if hard_recovery:
        message_parts.append(bound_message(hard_recovery))

    if message_parts:
        body = bound_message('\n\n'.join(message_parts))
        kind = 'discovery' if added or removed else 'health-transition'
        try:
            queue_and_deliver(state, body, current_max, kind)
        except DeliveryError as exc:
            report_delivery_failure(exc)
            return 1
    else:
        # No user-visible notification was needed. It is safe to advance past
        # all observed endpoint changes because there is no message to lose.
        state['last_change_id'] = max(last_change_id, current_max)
        save_state(state)

    # Provider-level failures are represented in state and transition alerts,
    # not as a non-zero scheduler result. This lets healthy providers continue
    # to deliver discoveries while a single provider (currently Gemini) is
    # unavailable.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
