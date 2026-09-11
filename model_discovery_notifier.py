#!/usr/bin/env python3
"""Reliable no-agent watcher for newly observed AIMI model routes.

The AIMI endpoint monitor is the source of truth for polling and raw evidence.
This wrapper runs that monitor, promotes endpoint-only candidates into the
catalogue's route/event tables, and sends Telegram notifications for added or
removed provider routes and provider-confirmed free-window closures. A shared
news gate keeps bulk synchronisations and unverified origin-provider additions
out of the website/X editorial queue.

Delivery is deliberately at-least-once. A durable pending outbox is written
before sending and the endpoint-change watermark advances only after every
bounded Telegram part receives a successful ``hermes send --json`` response. A
crash in the small post-send persistence window may produce one duplicate alert,
but a Telegram outage cannot silently lose a discovery or removal notification.

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

from model_news_eligibility import filter_news_candidates

# Resolve the project from this file so the repository stays portable and no
# personal home path is committed. The Hermes wrapper invokes this script by
# absolute path, which keeps working under any checkout location.
PROJECT = Path(__file__).resolve().parent
DB = PROJECT / 'aimi.db'
MONITOR = PROJECT / 'monitor_endpoints.py'
INGEST = PROJECT / 'ingest_endpoint_candidates.py'
STATE = Path.home() / '.hermes' / 'cron' / 'model-catalogue-discovery-notifier.json'
LOCK = Path.home() / '.hermes' / 'cron' / 'model-catalogue-discovery-notifier.lock'
RELEASE_QUEUE = Path.home() / '.hermes' / 'cron' / 'model-release-desk-queue.json'
VERSION = 'model-catalogue-discovery-notifier/2.5'
RELEASE_QUEUE_VERSION = 1
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


def initial_state(last_change_id: int, last_free_window_event_id: int = 0) -> dict:
    return {
        'version': VERSION,
        'last_change_id': int(last_change_id),
        'last_free_window_event_id': int(last_free_window_event_id),
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
    # Older watcher state predates free-window closure notifications. A None
    # marker lets run_locked establish a safe baseline without replaying old
    # closure events on the first upgraded run.
    value.setdefault('last_free_window_event_id', None)
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


def empty_release_queue() -> dict:
    return {
        'version': RELEASE_QUEUE_VERSION,
        'pending': [],
        'processed': [],
        'updated_at': None,
    }


def load_release_queue() -> dict:
    if not RELEASE_QUEUE.exists():
        return empty_release_queue()
    try:
        value = json.loads(RELEASE_QUEUE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Invalid release-desk queue at {RELEASE_QUEUE}: {safe_error(exc)}') from exc
    if not isinstance(value, dict) or not isinstance(value.get('pending'), list):
        raise RuntimeError(f'Invalid release-desk queue at {RELEASE_QUEUE}: expected pending list')
    value.setdefault('version', RELEASE_QUEUE_VERSION)
    value.setdefault('processed', [])
    value.setdefault('updated_at', None)
    return value


def save_release_queue(value: dict) -> None:
    RELEASE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    value['version'] = RELEASE_QUEUE_VERSION
    value['updated_at'] = now()
    fd, temp_name = tempfile.mkstemp(prefix=f'.{RELEASE_QUEUE.name}.', dir=RELEASE_QUEUE.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
        os.replace(temp_name, RELEASE_QUEUE)
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


def max_free_window_event_id(connection: sqlite3.Connection) -> int:
    return int(
        connection.execute(
            """SELECT COALESCE(MAX(model_event_id), 0)
               FROM model_events WHERE event_type='free_window_end'"""
        ).fetchone()[0]
    )


def free_window_event_id_at_or_before(
    connection: sqlite3.Connection,
    observed_at: str | None,
) -> int:
    if not observed_at:
        return max_free_window_event_id(connection)
    return int(
        connection.execute(
            """SELECT COALESCE(MAX(model_event_id), 0)
               FROM model_events
               WHERE event_type='free_window_end'
                 AND datetime(event_time)<=datetime(?)""",
            (observed_at,),
        ).fetchone()[0]
    )


def run_aimi_script(path: Path) -> subprocess.CompletedProcess[str]:
    if not path.exists():
        raise RuntimeError(f'Missing AIMI script: {path}')
    # Hermes starts jobs with a minimal environment. Source the host's
    # protected service env without ever printing the sourced file or values.
    env_candidates = [
        os.environ.get('AIMI_ENV_FILE', ''),
        str(Path.home() / '.zshrc'),
        str(Path.home() / '.env'),
    ]
    env_file = next((candidate for candidate in env_candidates if candidate and Path(candidate).is_file()), '')
    source = f'if [ -r {json.dumps(env_file)} ]; then set -a; . {json.dumps(env_file)} >/dev/null 2>&1; set +a; fi; '
    command = source + f'exec {json.dumps(sys.executable)} {json.dumps(str(path))}'
    environment = os.environ.copy()
    environment.setdefault(
        'PATH',
        os.pathsep.join(
            str(candidate)
            for candidate in (
                Path.home() / '.local' / 'bin',
                Path.home() / 'bin',
                Path('/usr/local/bin'),
                Path('/usr/bin'),
                Path('/bin'),
            )
        ),
    )
    shell = '/bin/zsh' if Path('/bin/zsh').exists() else '/bin/bash'
    return subprocess.run(
        [shell, '-lc', command],
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
            os.pathsep.join(
                str(candidate)
                for candidate in (
                    Path.home() / '.local' / 'bin',
                    Path.home() / 'bin',
                    Path('/usr/local/bin'),
                    Path('/usr/bin'),
                    Path('/bin'),
                )
            ),
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
          ec.monitoring_run_id,
          ec.provider_id,
          ec.model_identifier,
          ec.detected_at,
          pm.provider_model_id,
          pm.canonical_model_id,
          pm.provider_created_at,
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


def free_window_closure_rows(
    connection: sqlite3.Connection,
    last_event_id: int,
) -> list[sqlite3.Row]:
    """Return authoritative free-window closure events after the watermark."""
    return connection.execute(
        """SELECT
             me.model_event_id AS free_window_event_id,
             me.provider_model_id,
             me.event_time AS detected_at,
             me.supporting_quote,
             pm.provider_id,
             pm.model_identifier,
             COALESCE(cm.canonical_name, pm.display_name, pm.model_identifier) AS model_name,
             COALESCE(p.display_name, pm.provider_id) AS provider_name,
             COALESCE(
               (SELECT mt.url FROM monitoring_targets mt
                WHERE mt.provider_id=pm.provider_id
                  AND mt.target_type='models_endpoint'
                ORDER BY mt.monitoring_target_id DESC LIMIT 1),
               'runtime endpoint unavailable'
             ) AS endpoint_url
           FROM model_events me
           JOIN provider_models_v2 pm ON pm.provider_model_id=me.provider_model_id
           LEFT JOIN canonical_models cm ON cm.canonical_model_id=pm.canonical_model_id
           LEFT JOIN providers p ON p.provider_id=pm.provider_id
           WHERE me.event_type='free_window_end' AND me.model_event_id>?
           ORDER BY me.model_event_id""",
        (int(last_event_id),),
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
    'cline': 'Cline',
    'deepseek': 'DeepSeek',
    'gemini': 'Google Gemini',
    'kilo': 'Kilo',
    'mistral': 'Mistral',
    'nvidia-nim': 'NVIDIA NIM',
    'ollama-cloud': 'Ollama Cloud',
    'openai': 'OpenAI',
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


def enqueue_release_candidates(
    routes: list[sqlite3.Row],
    *,
    connection: sqlite3.Connection | None = None,
    prefiltered: bool = False,
) -> int:
    """Persist only news-eligible additions for the editorial release desk.

    Endpoint additions are observations, not release claims. Bulk catalogue
    synchronisations and origin-provider backfills stay out of the website/X
    queue; the release desk independently re-checks legacy queue records.
    """
    if not routes:
        return 0
    if prefiltered:
        eligible = [
            route for route in routes
            if route_value(route, 'news_eligible', False)
        ]
    else:
        eligible, _suppressed = filter_news_candidates(routes, connection=connection)
    if not eligible:
        return 0
    queue = load_release_queue()
    pending = queue['pending']
    known_ids = {
        int(item['endpoint_change_id'])
        for item in pending
        if isinstance(item, dict) and item.get('endpoint_change_id') is not None
    }
    known_ids.update(
        int(item['endpoint_change_id'])
        for item in queue.get('processed', [])
        if isinstance(item, dict) and item.get('endpoint_change_id') is not None
    )
    added_count = 0
    for route in eligible:
        change_id = int(route_value(route, 'endpoint_change_id', 0))
        if not change_id or change_id in known_ids:
            continue
        pending.append(
            {
                'endpoint_change_id': change_id,
                'monitoring_run_id': route_value(route, 'monitoring_run_id'),
                'monitoring_run_added_count': route_value(route, 'monitoring_run_added_count'),
                'provider_model_id': route_value(route, 'provider_model_id'),
                'canonical_model_id': route_value(route, 'canonical_model_id'),
                'news_eligibility_reason': route_value(
                    route, 'news_eligibility_reason', 'aggregator_route_added'
                ),
                'same_day_official_release': route_value(
                    route, 'same_day_official_release', False
                ),
                'discovery_group_size': route_value(route, 'discovery_group_size'),
                'provider_id': str(route_value(route, 'provider_id', 'unknown')),
                'provider_name': str(route_value(route, 'provider_name', 'unknown')),
                'model_identifier': str(route_value(route, 'model_identifier', 'unknown')),
                'model_name': str(
                    route_value(route, 'model_name')
                    or route_value(route, 'model_identifier', 'unknown')
                ),
                'detected_at': str(route_value(route, 'detected_at', now())),
                'access_type': str(route_value(route, 'access_type', 'not classified')),
                'endpoint_url': str(route_value(route, 'endpoint_url', 'endpoint URL unavailable')),
                'description': str(route_value(route, 'description', '') or ''),
                'attempts': 0,
                'last_error': None,
                'queued_at': now(),
            }
        )
        known_ids.add(change_id)
        added_count += 1
    if added_count:
        save_release_queue(queue)
    return added_count


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
    marker = '🗑️ REMOVED' if removed else '🆕 ADDED'
    lines = [
        f'**{position}. {marker} · {provider_label(route)}**',
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


def overflow(routes: list[sqlite3.Row] | list[dict], noun: str) -> list[str]:
    extra = routes[DETAIL_LIMIT:]
    if not extra:
        return []
    by_provider: dict[str, int] = {}
    for route in extra:
        provider = str(route_value(route, 'provider_id', 'unknown'))
        by_provider[provider] = by_provider.get(provider, 0) + 1
    summary = ', '.join(f'{provider} {count}' for provider, count in sorted(by_provider.items()))
    return [f'...and {len(extra)} more {noun}(s): {summary}', '']


def bound_message(text: str) -> str:
    if len(text) <= MAX_MESSAGE_CHARS:
        return text
    return text[: MAX_MESSAGE_CHARS - 80].rstrip() + '\n\n...message truncated; inspect AIMI endpoint_changes for the full list.'


def _hard_split(text: str, limit: int) -> list[str]:
    """Split one oversized paragraph without dropping its content."""
    pieces: list[str] = []
    remainder = text.strip()
    while len(remainder) > limit:
        newline = remainder.rfind('\n', 0, limit + 1)
        space = remainder.rfind(' ', 0, limit + 1)
        cut = max(newline, space)
        if cut < 1:
            cut = limit
        pieces.append(remainder[:cut].rstrip())
        remainder = remainder[cut:].lstrip()
    if remainder:
        pieces.append(remainder)
    return pieces


def split_message(text: str, limit: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split a notification into bounded logical parts instead of truncating it."""
    value = str(text or '').strip()
    if not value:
        return []
    if len(value) <= limit:
        return [value]

    # Reserve room for the part header so every delivered Telegram message
    # remains under the platform limit, including large part numbers.
    body_limit = max(1, limit - 80)
    paragraphs = [paragraph.strip() for paragraph in value.split('\n\n') if paragraph.strip()]
    chunks: list[str] = []
    current = ''
    for paragraph in paragraphs:
        pieces = _hard_split(paragraph, body_limit) if len(paragraph) > body_limit else [paragraph]
        for piece in pieces:
            candidate = piece if not current else f'{current}\n\n{piece}'
            if len(candidate) <= body_limit:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = piece
    if current:
        chunks.append(current)

    total = len(chunks)
    return [
        f'📨 **AIMI model update · part {position}/{total}**\n\n{chunk}'
        for position, chunk in enumerate(chunks, start=1)
    ]


def format_free_window_closure_notification(
    closures: list[sqlite3.Row],
    configured: set[tuple[str, str]],
) -> str:
    """Format provider-confirmed free-window withdrawals for Telegram."""
    if not closures:
        return ''
    lines = [
        f'⏰ **FREE ACCESS ENDED: Free model access ended ({len(closures)})**',
        '_AIMI runtime probe · local time_',
        '',
    ]
    for position, route in enumerate(closures[:DETAIL_LIMIT], start=1):
        provider = str(route_value(route, 'provider_id', 'unknown'))
        model = str(route_value(route, 'model_identifier', 'unknown'))
        name = str(route_value(route, 'model_name', model))
        lines.extend(
            [
                f'{position}. ⏰ FREE ACCESS ENDED · {provider_label(route)}',
                f'Model: {inline_code(name)}',
                f'Route: {inline_code(f"{provider}/{model}")}',
                f'Closed: {format_local_time(route_value(route, "detected_at"))}',
                f'Reason: {safe_error(route_value(route, "supporting_quote", "Provider ended the free promotion."), 300)}',
            ]
        )
        if impact(route, configured):
            lines.append('Still enabled locally.')
        lines.append('')
    if len(closures) > DETAIL_LIMIT:
        lines.append(f'...and {len(closures) - DETAIL_LIMIT} more closure(s).')
        lines.append('')
    lines.append('The route may still be available through paid or subscription access.')
    return '\n'.join(lines)


def route_change_id(route: sqlite3.Row | dict) -> int | None:
    value = route_value(route, 'endpoint_change_id')
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def provider_summary(routes: list[sqlite3.Row] | list[dict]) -> str:
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    for route in routes:
        provider = str(route_value(route, 'provider_id', 'unknown'))
        counts[provider] = counts.get(provider, 0) + 1
        labels[provider] = provider_label(route)
    return ', '.join(
        f'{labels[provider]} {counts[provider]}'
        for provider in sorted(counts)
    )


def format_suppressed_summary(suppressed: list[sqlite3.Row] | list[dict]) -> list[str]:
    """Explain withheld additions without presenting them as new releases."""
    grouped: dict[str, list[sqlite3.Row] | list[dict]] = {}
    for route in suppressed:
        reason = str(route_value(route, 'news_eligibility_reason', 'suppressed'))
        grouped.setdefault(reason, []).append(route)

    lines: list[str] = []
    reason_order = ('bulk_endpoint_sync', 'endpoint_observation_without_release')
    ordered_reasons = [reason for reason in reason_order if reason in grouped]
    ordered_reasons.extend(reason for reason in grouped if reason not in ordered_reasons)
    for reason in ordered_reasons:
        routes = grouped[reason]
        total = len(routes)
        providers = provider_summary(routes)
        if lines:
            lines.append('')
        if reason == 'bulk_endpoint_sync':
            lines.extend(
                [
                    f'🔄 **RESYNC: Bulk model catalogue sync ({total} routes; no editorial candidates)**',
                    f'Provider(s): {providers}',
                    'Existing provider routes were re-listed after a catalogue refresh. These are not new model releases.',
                    '',
                ]
            )
            continue
        if reason == 'endpoint_observation_without_release':
            heading = f'📡 **ROUTE OBSERVATION: Endpoint-only additions ({total})**'
            explanation = 'These routes were observed, but no verified release evidence was attached.'
        else:
            heading = f'ℹ️ **ROUTES WITHHELD: {reason.replace("_", " ").capitalize()} ({total})**'
            explanation = 'These routes remain technical observations, not public release claims.'
        lines.extend([heading, f'Provider(s): {providers}', explanation, ''])
        for position, route in enumerate(routes[:DETAIL_LIMIT], start=1):
            provider = str(route_value(route, 'provider_id', 'unknown'))
            model = str(route_value(route, 'model_identifier', 'unknown'))
            lines.append(f'• {inline_code(f"{provider}/{model}")}')
        lines.extend(overflow(routes, 'observation'))
    return lines


def format_notification(
    added: list[sqlite3.Row],
    removed: list[sqlite3.Row],
    configured: set[tuple[str, str]],
    suppressed: list[sqlite3.Row] | list[dict] | None = None,
) -> str:
    lines: list[str] = []
    suppressed = suppressed or []
    suppressed_ids = {
        change_id for change_id in (route_change_id(route) for route in suppressed)
        if change_id is not None
    }
    visible_added = [
        route for route in added
        if route_change_id(route) not in suppressed_ids
    ]

    if visible_added:
        lines.extend(
            [
                f'🆕 **ADDED: New AI model routes discovered ({len(visible_added)})**',
                '_AIMI endpoint monitor · local time_',
                '',
            ]
        )
        for position, route in enumerate(visible_added[:DETAIL_LIMIT], start=1):
            lines.extend(format_route_card(route, position, removed=False, configured=configured))
        lines.extend(overflow(visible_added, 'addition'))

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
                f'🗑️ **REMOVED: Model routes removed from their provider ({len(removed)})**',
                '_AIMI endpoint monitor · local time_',
                '',
            ]
        )
        if affected:
            affected_routes = ', '.join(
                inline_code(
                    f"{route_value(route, 'provider_id', 'unknown')}/"
                    f"{route_value(route, 'model_identifier', 'unknown')}"
                )
                for route in affected
            )
            lines.extend(
                [
                    f'🚨 **ACTION NEEDED: {len(affected)} removed route(s) are still enabled locally and may now fail.**',
                    f'Route(s): {affected_routes}',
                    'Review the local harness configuration before replacing or removing the route.',
                    '',
                ]
            )
        for position, route in enumerate(ordered[:DETAIL_LIMIT], start=1):
            lines.extend(format_route_card(route, position, removed=True, configured=configured))
        lines.extend(overflow(ordered, 'removal'))

    if suppressed:
        if lines:
            lines.append('')
        lines.extend(format_suppressed_summary(suppressed))
        lines.extend(
            [
                f'ℹ️ **{len(suppressed)} route(s) withheld from the website/X news queue.**',
                '_Bulk synchronisations and endpoint-only observations are not public release news._',
                '',
            ]
        )
    lines.extend(
        [
            'ℹ️ _Endpoint observation only. AIMI has not treated this as an official release or retirement date._',
            '_Pricing, capabilities, and free status remain evidence-dependent._',
        ]
    )
    return '\n'.join(lines)


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
    lines = ['⚠️ **PROVIDER STATUS CHANGED**', '']
    for provider, error in new_failures:
        lines.append(f'• ⚠️ **PROVIDER UNAVAILABLE:** {provider} · {safe_error(error)}')
    for provider in recovered:
        lines.append(f'• ✅ **PROVIDER RECOVERED:** {provider}')
    return '\n'.join(lines)


def format_hard_failure(error: str) -> str:
    return bound_message(
        '⚠️ **PROVIDER FAILURE: AIMI discovery monitor failed**\n\n'
        f'• {safe_error(error)}\n\n'
        'The pending state will be retried on the next scheduled run.'
    )


def format_hard_recovery(previous_error: str | None) -> str:
    if not previous_error:
        return ''
    return '✅ **AIMI discovery monitor recovered**\n\n' f'• Previous failure: {safe_error(previous_error)}'


def pending_record(
    body: str | list[str] | tuple[str, ...],
    up_to_change_id: int,
    kind: str,
    up_to_free_window_event_id: int | None = None,
) -> dict:
    raw_parts = [body] if isinstance(body, str) else list(body)
    parts: list[str] = []
    for part in raw_parts:
        parts.extend(split_message(str(part)))
    if not parts:
        raise ValueError('A pending notification must contain at least one message part')
    digest = hashlib.sha256('\n\n'.join(parts).encode('utf-8')).hexdigest()[:16]
    return {
        'id': f'{kind}-{up_to_change_id}-{digest}',
        'kind': kind,
        # `body` remains the current part for compatibility with existing
        # state readers. `parts` and `part_index` make follow-up delivery
        # restartable without advancing the endpoint watermark early.
        'body': parts[0],
        'parts': parts,
        'part_index': 0,
        'up_to_change_id': int(up_to_change_id),
        'up_to_free_window_event_id': (
            int(up_to_free_window_event_id)
            if up_to_free_window_event_id is not None else None
        ),
        'created_at': now(),
        'attempts': 0,
        'last_attempt_at': None,
        'last_error': None,
    }


def pending_parts(pending: dict) -> list[str]:
    parts = pending.get('parts')
    if isinstance(parts, list) and parts:
        return [str(part) for part in parts]
    body = pending.get('body')
    return split_message(str(body)) if body else []


def deliver_pending(state: dict) -> dict | None:
    """Deliver every pending part before advancing its durable watermark."""
    pending = state.get('pending_notification')
    if not pending:
        return None
    parts = pending_parts(pending)
    if not parts:
        raise DeliveryError('Pending notification has no message parts')
    pending['parts'] = parts
    try:
        part_index = int(pending.get('part_index') or 0)
    except (TypeError, ValueError) as exc:
        raise DeliveryError('Pending notification has an invalid part index') from exc
    if part_index < 0 or part_index >= len(parts):
        raise DeliveryError('Pending notification part index is out of range')

    message_ids: list[str] = []
    result: dict = {}
    while part_index < len(parts):
        body = parts[part_index]
        pending['body'] = body
        pending['part_index'] = part_index
        try:
            result = deliver_notification(body) or {}
        except Exception as exc:
            pending['attempts'] = int(pending.get('attempts') or 0) + 1
            pending['last_attempt_at'] = now()
            pending['last_error'] = safe_error(exc)
            save_state(state)
            if isinstance(exc, DeliveryError):
                raise
            raise DeliveryError(safe_error(exc)) from exc

        message_id = result.get('message_id')
        if message_id is not None:
            message_ids.append(str(message_id))
        part_index += 1
        pending['part_index'] = part_index
        # Persist progress after every accepted part. A crash between the
        # Hermes acknowledgement and this write can duplicate one part, but
        # can never skip an undelivered part or advance the watermark early.
        if part_index < len(parts):
            pending['body'] = parts[part_index]
            save_state(state)

    state['pending_notification'] = None
    state['last_change_id'] = max(
        int(state.get('last_change_id', 0)),
        int(pending.get('up_to_change_id', state.get('last_change_id', 0))),
    )
    if pending.get('up_to_free_window_event_id') is not None:
        state['last_free_window_event_id'] = max(
            int(state.get('last_free_window_event_id') or 0),
            int(pending['up_to_free_window_event_id']),
        )
    delivery = {
        'notification_id': pending.get('id'),
        'kind': pending.get('kind'),
        'part_count': len(parts),
        **result,
    }
    if message_ids:
        delivery['message_ids'] = message_ids
    state['last_delivery'] = delivery
    save_state(state)
    return result


def queue_and_deliver(
    state: dict,
    body: str | list[str] | tuple[str, ...],
    up_to_change_id: int,
    kind: str,
    up_to_free_window_event_id: int | None = None,
) -> dict:
    """Persist an outbox item before attempting delivery."""
    state['pending_notification'] = pending_record(
        body, up_to_change_id, kind, up_to_free_window_event_id
    )
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
        before_free_window_max = max_free_window_event_id(connection)
        legacy_free_window_baseline = (
            free_window_event_id_at_or_before(
                connection,
                state.get('last_poll_at') if state else None,
            )
            if state else before_free_window_max
        )
        connection.close()
    except Exception as exc:
        baseline = int(state.get('last_change_id', 0)) if state else 0
        if state is None:
            state = initial_state(baseline)
        return handle_hard_failure(state, baseline, exc)

    # On first startup, suppress historical endpoint changes but still alert on
    # additions created by this first poll.
    if state is None:
        state = initial_state(before_poll_max, before_free_window_max)
    elif state.get('last_free_window_event_id') is None:
        # Migrate legacy watcher state without replaying old closures, while
        # retaining events created after the last successful watcher poll.
        state['last_free_window_event_id'] = legacy_free_window_baseline
        save_state(state)
    last_change_id = int(state['last_change_id'])
    last_free_window_event_id = int(state.get('last_free_window_event_id') or 0)
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
        current_free_window_max = max_free_window_event_id(connection)
        added = route_rows(connection, last_change_id, 'model_added')
        removed = route_rows(connection, last_change_id, 'model_removed')
        closures = free_window_closure_rows(connection, last_free_window_event_id)
        configured = configured_models(connection)
        eligible_added, suppressed_added = filter_news_candidates(
            added,
            connection=connection,
        )
        connection.close()
    except Exception as exc:
        return handle_hard_failure(state, last_change_id, exc)

    try:
        enqueue_release_candidates(eligible_added, prefiltered=True)
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
        message_parts.append(
            format_notification(
                added,
                removed,
                configured,
                suppressed=suppressed_added,
            )
        )
    if closures:
        message_parts.append(format_free_window_closure_notification(closures, configured))
    failure_text = format_failure_transitions(new_failures, recovered_failures)
    if failure_text:
        message_parts.append(bound_message(failure_text))
    hard_recovery = format_hard_recovery(previous_hard_error)
    if hard_recovery:
        message_parts.append(bound_message(hard_recovery))

    if message_parts:
        bodies = split_message('\n\n'.join(message_parts))
        if added or removed:
            kind = 'discovery'
        elif closures:
            kind = 'free-window-closed'
        else:
            kind = 'health-transition'
        try:
            queue_and_deliver(
                state,
                bodies,
                current_max,
                kind,
                current_free_window_max if closures else None,
            )
        except DeliveryError as exc:
            report_delivery_failure(exc)
            return 1
    else:
        # No user-visible notification was needed. It is safe to advance past
        # all observed endpoint changes because there is no message to lose.
        state['last_change_id'] = max(last_change_id, current_max)
        state['last_free_window_event_id'] = max(
            last_free_window_event_id, current_free_window_max
        )
        save_state(state)

    # Provider-level failures are represented in state and transition alerts,
    # not as a non-zero scheduler result. This lets healthy providers continue
    # to deliver discoveries while a single provider (currently Gemini) is
    # unavailable.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
