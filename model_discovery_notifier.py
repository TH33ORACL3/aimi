#!/usr/bin/env python3
"""Hermes no-agent watcher for newly observed AIMI model routes.

The AIMI endpoint monitor is the source of truth for polling and raw evidence.
This wrapper runs that monitor, promotes endpoint-only candidates into the
catalogue's route/event tables, and prints a Telegram notification only when a
new provider route was observed. It does not infer release dates, pricing,
capabilities, or free access from an endpoint listing.

Empty stdout means no Telegram message. A non-zero exit means the scheduler
should surface a provider or ingestion failure.
"""
from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Resolve the project from this file so the repository stays portable and no
# personal home path is committed. The Hermes wrapper invokes this script by
# absolute path, which keeps working under any checkout location.
PROJECT = Path(__file__).resolve().parent
DB = PROJECT / 'aimi.db'
MONITOR = PROJECT / 'monitor_endpoints.py'
INGEST = PROJECT / 'ingest_endpoint_candidates.py'
STATE = Path.home() / '.hermes' / 'cron' / 'model-catalogue-discovery-notifier.json'
LOCK = Path.home() / '.hermes' / 'cron' / 'model-catalogue-discovery-notifier.lock'
VERSION = 'model-catalogue-discovery-notifier/1.1'


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state() -> dict | None:
    if not STATE.exists():
        return None
    try:
        value = json.loads(STATE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f'Invalid watcher state at {STATE}: {exc}') from exc
    if not isinstance(value, dict) or not isinstance(value.get('last_change_id'), int):
        raise RuntimeError(f'Invalid watcher state at {STATE}: expected integer last_change_id')
    return value


def save_state(value: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{STATE.name}.', dir=STATE.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
        os.replace(temp_name, STATE)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def db_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


def max_change_id(connection: sqlite3.Connection) -> int:
    return int(connection.execute('SELECT COALESCE(MAX(endpoint_change_id), 0) FROM endpoint_changes').fetchone()[0])


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
        '/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
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
        raise RuntimeError(
            f'AIMI monitor returned no JSON (exit {result.returncode}): '
            f'{(result.stderr or "").strip()[-500:]}'
        )
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'AIMI monitor returned invalid JSON: {exc}') from exc
    if not isinstance(parsed, list):
        raise RuntimeError('AIMI monitor returned JSON other than a provider result list')
    return parsed


def new_routes(connection: sqlite3.Connection, last_change_id: int) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
          ec.endpoint_change_id,
          ec.provider_id,
          ec.model_identifier,
          ec.detected_at,
          COALESCE(cm.canonical_name, pm.display_name, ec.model_identifier) AS model_name,
          pm.endpoint_first_seen_at,
          pm.context_window_tokens,
          pm.max_output_tokens,
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
        WHERE ec.endpoint_change_id > ?
          AND ec.change_type = 'model_added'
        ORDER BY ec.endpoint_change_id
        """,
        (last_change_id,),
    ).fetchall()


def format_notification(routes: list[sqlite3.Row]) -> str:
    lines = [f'New AI model route discovered in AIMI ({len(routes)}):', '']
    for route in routes:
        lines.extend(
            [
                f"• {route['model_name']}",
                f"  Route: {route['provider_id']}/{route['model_identifier']}",
                f"  Endpoint: {route['endpoint_url']}",
                f"  First seen: {route['detected_at']}",
                f"  Access: {route['access_type']}",
            ]
        )
        if route['context_window_tokens'] is not None:
            lines.append(f"  Context: {route['context_window_tokens']:,} tokens")
        if route['max_output_tokens'] is not None:
            lines.append(f"  Max output: {route['max_output_tokens']:,} tokens")
        lines.append('')
    lines.extend(
        [
            'This is an endpoint observation. AIMI has not treated it as the official release date.',
            'Pricing, capabilities, and free status remain evidence-dependent.',
        ]
    )
    return '\n'.join(lines)


def format_failures(results: list[dict]) -> str:
    failures = [item for item in results if item.get('status') == 'failed']
    if not failures:
        return ''
    lines = ['AIMI model endpoint monitor reported provider failures:', '']
    for item in failures:
        lines.append(f"• {item.get('provider', 'unknown')}: {str(item.get('error', 'unknown error'))[:300]}")
    return '\n'.join(lines)


def main() -> int:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('w') as lock_handle:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # A slow provider batch is still running. Avoid overlapping polls.
            return 0

        return run_locked()


def run_locked() -> int:
    state = load_state()
    connection = db_connection()
    before_poll_max = max_change_id(connection)
    connection.close()

    # On first startup, suppress historical endpoint changes but still alert on
    # additions created by this first poll.
    last_change_id = before_poll_max if state is None else state['last_change_id']

    monitor = run_aimi_script(MONITOR)
    try:
        results = parse_monitor_output(monitor)
    except RuntimeError as exc:
        print(f'AIMI model discovery watcher failed: {exc}')
        return 1

    # Successful provider polls are committed even when another provider is
    # unavailable. Promote endpoint-only candidates before building the alert.
    ingest = run_aimi_script(INGEST)
    if ingest.returncode != 0:
        detail = (ingest.stderr or ingest.stdout or '').strip()[-700:]
        print(f'AIMI endpoint candidate ingestion failed (exit {ingest.returncode}).\n{detail}')
        return 1

    connection = db_connection()
    current_max = max_change_id(connection)
    routes = new_routes(connection, last_change_id)
    connection.close()

    save_state(
        {
            'version': VERSION,
            'last_change_id': current_max,
            'last_poll_at': now(),
            'last_monitor_exit_code': monitor.returncode,
            'last_provider_results': results,
        }
    )

    failure_text = format_failures(results)
    message_parts = [part for part in (format_notification(routes) if routes else '', failure_text) if part]
    if message_parts:
        print('\n\n'.join(message_parts))

    # Provider-level failures should remain visible to Hermes even if another
    # provider produced a useful discovery in the same batch.
    return 1 if monitor.returncode != 0 or failure_text else 0


if __name__ == '__main__':
    raise SystemExit(main())
