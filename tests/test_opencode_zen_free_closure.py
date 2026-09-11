from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import free_model_health as health
import model_discovery_notifier as notifier
import monitor_endpoints as monitor
from free_offer_reconciliation import reconcile_active_temporary_free_windows


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / 'schema_v2.sql').read_text()


class OpenCodeZenFreeClosureTests(unittest.TestCase):
    def make_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        connection.execute(
            """INSERT INTO providers(
                 provider_id,display_name,official_models_endpoint,base_url,
                 api_style,auth_env_var,pricing_policy,free_definition)
               VALUES('opencode-zen','OpenCode Zen',
                 'https://opencode.ai/zen/v1/models',
                 'https://opencode.ai/zen/v1','openai-completions',
                 'OPENCODE_API_KEY','explicit_free_suffix',
                 'official model ID ends in -free')"""
        )
        connection.execute(
            """INSERT INTO provider_models_v2(
                 provider_id,model_identifier,display_name,
                 endpoint_first_seen_at,endpoint_last_seen_at)
               VALUES('opencode-zen','deepseek-v4-flash-free',
                 'DeepSeek V4 Flash Free',?,?)""",
            ('2026-08-18T00:00:00+00:00', '2026-08-20T23:00:00+00:00'),
        )
        source = connection.execute(
            """INSERT INTO evidence_sources(
                 url,source_type,publisher,title,official,primary_source,
                 retrieved_at,verification_status)
               VALUES(?,?,?,?,1,1,?,'verified')""",
            (
                'https://opencode.ai/zen/v1/models',
                'api_endpoint',
                'opencode-zen',
                'OpenCode Zen models endpoint',
                '2026-08-20T23:00:00+00:00',
            ),
        ).lastrowid
        capture = connection.execute(
            """INSERT INTO evidence_captures(
                 evidence_source_id,retrieved_at,content_sha256,
                 extraction_method,http_status)
               VALUES(?,?,?,'endpoint_monitor',200)""",
            (source, '2026-08-20T23:00:00+00:00', 'models-hash'),
        ).lastrowid
        provider_model_id = connection.execute(
            "SELECT provider_model_id FROM provider_models_v2"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO access_offers(
                 provider_model_id,offer_type,first_observed_at,
                 last_observed_at,terms_summary,evidence_source_id,
                 evidence_capture_id,confidence,last_verified_at)
               VALUES(?, 'temporary_free_window', ?, ?, ?, ?, ?,
                 'single_source', ?)""",
            (
                provider_model_id,
                '2026-08-18T00:00:00+00:00',
                '2026-08-20T23:00:00+00:00',
                'Official model ID ends in -free; duration unpublished',
                source,
                capture,
                '2026-08-20T23:00:00+00:00',
            ),
        )
        connection.commit()
        return connection

    def result(self, connection: sqlite3.Connection, **overrides: object) -> dict:
        provider_model_id = connection.execute(
            "SELECT provider_model_id FROM provider_models_v2"
        ).fetchone()[0]
        value = {
            'provider_model_id': provider_model_id,
            'provider_id': 'opencode-zen',
            'model_identifier': 'deepseek-v4-flash-free',
            'display_name': 'DeepSeek V4 Flash Free',
            'offer_type': 'temporary_free_window',
            'offer_verified_at': '2026-08-20T23:00:00+00:00',
            'tested_at': '2026-08-20T23:30:00+00:00',
            'status': 'unauthorized',
            'latency_ms': 100,
            'http_status': 401,
            'error_category': 'free_promotion_ended',
            'error_message': 'Free promotion has ended for DeepSeek V4 Flash Free',
            'promotion_ended': True,
            'promotion_ended_body': 'Free promotion has ended for DeepSeek V4 Flash Free',
        }
        value.update(overrides)
        return value

    def test_signal_ignores_generic_auth_and_rate_limit_errors(self) -> None:
        self.assertTrue(
            health.is_opencode_zen_promotion_ended(
                'opencode-zen',
                401,
                '{"error":{"message":"Free promotion has ended for this model"}}',
            )
        )
        self.assertFalse(
            health.is_opencode_zen_promotion_ended(
                'opencode-zen', 401, '{"error":{"message":"Invalid API key"}}'
            )
        )
        self.assertFalse(
            health.is_opencode_zen_promotion_ended(
                'opencode-zen', 429, '{"error":{"message":"Free promotion has ended"}}'
            )
        )
        self.assertFalse(
            health.is_opencode_zen_promotion_ended(
                'openrouter', 401, '{"error":{"message":"Free promotion has ended"}}'
            )
        )

    def test_probe_marks_explicit_promotion_ended(self) -> None:
        body = b'{"error":{"message":"Free promotion has ended for DeepSeek V4 Flash Free"}}'

        def fail(*_args, **_kwargs):
            raise HTTPError(
                'https://opencode.ai/zen/v1/chat/completions',
                401,
                'Unauthorized',
                {},
                __import__('io').BytesIO(body),
            )

        target = {
            'provider_model_id': 1,
            'provider_id': 'opencode-zen',
            'model_identifier': 'deepseek-v4-flash-free',
        }
        config = {'base_url': 'https://opencode.ai/zen/v1', 'auth_env_var': None}
        with patch.object(health.urllib.request, 'urlopen', fail):
            result = health.probe(target, config, 1)
        self.assertTrue(result['promotion_ended'])
        self.assertEqual(result['error_category'], 'free_promotion_ended')
        self.assertEqual(result['status'], 'unauthorized')

    def test_record_closes_offer_and_persists_evidence_and_event(self) -> None:
        connection = self.make_connection()
        with tempfile.TemporaryDirectory() as temporary:
            old_root, old_migration = health.ROOT, health.MIGRATION
            health.ROOT = Path(temporary)
            health.MIGRATION = ROOT / 'free_model_health.sql'
            try:
                health.record(connection, [self.result(connection)], 30)
            finally:
                health.ROOT, health.MIGRATION = old_root, old_migration

        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM currently_free_provider_models"
            ).fetchone()[0],
            0,
        )
        offer = connection.execute(
            "SELECT ends_at FROM access_offers"
        ).fetchone()
        self.assertEqual(offer[0], '2026-08-20T23:30:00+00:00')
        event = connection.execute(
            "SELECT event_type,evidence_capture_id FROM model_events"
        ).fetchone()
        self.assertEqual(event[0], 'free_window_end')
        self.assertIsNotNone(event[1])
        status = connection.execute(
            "SELECT currently_free,last_error_category FROM free_model_probe_status"
        ).fetchone()
        self.assertEqual(tuple(status), (0, 'free_promotion_ended'))
        self.assertEqual(
            connection.execute("SELECT COUNT(*) FROM evidence_captures").fetchone()[0],
            2,
        )
        connection.close()

    def test_generic_unauthorized_record_does_not_close_offer(self) -> None:
        connection = self.make_connection()
        result = self.result(
            connection,
            error_category='http_401',
            error_message='Invalid API key',
            promotion_ended=False,
            promotion_ended_body=None,
        )
        health.record(connection, [result], 30)
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM currently_free_provider_models"
            ).fetchone()[0],
            1,
        )
        self.assertIsNone(
            connection.execute("SELECT ends_at FROM access_offers").fetchone()[0]
        )
        connection.close()

    def test_health_connection_waits_for_sqlite_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            old_db = health.DB
            health.DB = Path(temporary) / 'health.db'
            try:
                connection = health.connect()
                self.assertEqual(
                    connection.execute('PRAGMA busy_timeout').fetchone()[0],
                    30000,
                )
                self.assertEqual(
                    connection.execute('PRAGMA foreign_keys').fetchone()[0],
                    1,
                )
                connection.close()
            finally:
                health.DB = old_db

    def test_retry_locked_retries_transient_database_lock(self) -> None:
        connection = sqlite3.connect(':memory:')
        calls: list[int] = []

        def operation() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise sqlite3.OperationalError('database is locked')
            return 'ok'

        with patch.object(health.time, 'sleep') as sleeper:
            self.assertEqual(
                health.retry_locked(operation, rollback=connection.rollback),
                'ok',
            )
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeper.call_count, 2)
        connection.close()

    def test_monitor_does_not_reopen_closed_route(self) -> None:
        connection = self.make_connection()
        provider_model_id = connection.execute(
            "SELECT provider_model_id FROM provider_models_v2"
        ).fetchone()[0]
        source = connection.execute(
            "SELECT evidence_source_id FROM evidence_sources LIMIT 1"
        ).fetchone()[0]
        capture = connection.execute(
            "SELECT evidence_capture_id FROM evidence_captures LIMIT 1"
        ).fetchone()[0]
        connection.execute(
            "UPDATE access_offers SET ends_at='2026-08-20T23:30:00+00:00'"
        )
        connection.execute(
            """INSERT INTO model_events(
                 provider_model_id,event_type,event_time,time_precision,
                 evidence_source_id,supporting_quote,confidence,evidence_capture_id)
               VALUES(?, 'free_window_end', ?, 'second', ?, ?, 'verified', ?)""",
            (
                provider_model_id,
                '2026-08-20T23:30:00+00:00',
                source,
                'Free promotion has ended',
                capture,
            ),
        )
        connection.commit()
        payload = {'data': [{'id': 'deepseek-v4-flash-free'}]}
        raw = json.dumps(payload, sort_keys=True).encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old_root, old_snap, old_fetch = monitor.ROOT, monitor.SNAP, monitor.fetch
            monitor.ROOT = root
            monitor.SNAP = root / 'snapshots' / 'monitor'
            monitor.SNAP.mkdir(parents=True)
            monitor.fetch = lambda *_args: (200, raw, {})
            try:
                result = monitor.poll(
                    connection,
                    'opencode-zen',
                    monitor.CONFIG['opencode-zen'][0],
                    None,
                    monitor.CONFIG['opencode-zen'][2],
                )
            finally:
                monitor.ROOT, monitor.SNAP, monitor.fetch = old_root, old_snap, old_fetch
        self.assertEqual(result['status'], 'success')
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM access_offers WHERE ends_at IS NULL"
            ).fetchone()[0],
            0,
        )
        connection.close()

    def test_notifier_formats_closure_and_exact_local_impact(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """SELECT 4 AS free_window_event_id,
                      'opencode-zen' AS provider_id,
                      'deepseek-v4-flash-free' AS model_identifier,
                      'DeepSeek V4 Flash Free' AS model_name,
                      'OpenCode Zen' AS provider_name,
                      '2026-08-20T23:30:00+00:00' AS detected_at,
                      'Free promotion has ended for this model' AS supporting_quote,
                      'https://opencode.ai/zen/v1/models' AS endpoint_url"""
        ).fetchone()
        body = notifier.format_free_window_closure_notification(
            [row], {('opencode-zen', 'deepseek-v4-flash-free')}
        )
        self.assertIn('⏰ **FREE ACCESS ENDED:', body)
        self.assertIn('Free model access ended (1)', body)
        self.assertIn('⏰ FREE ACCESS ENDED', body)
        self.assertIn('Still enabled locally.', body)
        body_without_impact = notifier.format_free_window_closure_notification(
            [row], {('opencode', 'deepseek-v4-flash-free')}
        )
        self.assertNotIn('Still enabled locally.', body_without_impact)
        connection.close()

    def test_closure_notification_has_separate_durable_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_path = Path(temporary) / 'watcher-state.json'
            with patch.object(notifier, 'STATE', state_path), patch.object(
                notifier, 'deliver_notification', return_value={'message_id': 'closure-1'}
            ):
                state = notifier.initial_state(10, 3)
                state['pending_notification'] = notifier.pending_record(
                    'closure body', 15, 'free-window-closed', 4
                )
                notifier.save_state(state)
                notifier.deliver_pending(state)
                saved = json.loads(state_path.read_text())
        self.assertEqual(saved['last_change_id'], 15)
        self.assertEqual(saved['last_free_window_event_id'], 4)
        self.assertIsNone(saved['pending_notification'])

    def test_duplicate_active_windows_are_collapsed_before_indexing(self) -> None:
        connection = sqlite3.connect(':memory:')
        connection.executescript(
            """CREATE TABLE access_offers(
                 access_offer_id INTEGER PRIMARY KEY,
                 provider_model_id INTEGER NOT NULL,
                 offer_type TEXT NOT NULL,
                 starts_at TEXT,
                 ends_at TEXT,
                 first_observed_at TEXT,
                 last_observed_at TEXT,
                 last_verified_at TEXT,
                 evidence_source_id INTEGER,
                 evidence_capture_id INTEGER);
               CREATE TABLE model_events(
                 model_event_id INTEGER PRIMARY KEY,
                 provider_model_id INTEGER,
                 event_type TEXT,
                 event_time TEXT);"""
        )
        connection.executemany(
            """INSERT INTO access_offers(
                 access_offer_id,provider_model_id,offer_type,
                 first_observed_at,last_verified_at)
               VALUES(?,?,?,?,?)""",
            [
                (1, 7, 'temporary_free_window', '2026-08-01', '2026-08-02'),
                (2, 7, 'temporary_free_window', '2026-08-01', '2026-08-03'),
            ],
        )
        self.assertEqual(
            reconcile_active_temporary_free_windows(
                connection, detected_at='2026-08-20T23:30:00+00:00'
            ),
            1,
        )
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM access_offers WHERE ends_at IS NULL"
            ).fetchone()[0],
            1,
        )
        connection.close()


if __name__ == '__main__':
    unittest.main()
