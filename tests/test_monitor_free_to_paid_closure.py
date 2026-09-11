from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import monitor_endpoints as monitor


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / 'schema_v2.sql').read_text()


class MonitorFreeToPaidClosureTests(unittest.TestCase):
    """Free-to-paid (and paid-to-free) transitions must close the stale offer.

    A model observed with a price must not keep an open genuine_zero_price
    offer, because currently_free_provider_models matches any open free-type
    offer. Regression for ~moonshotai/kimi-latest, ~z-ai/glm-latest and
    nvidia/nemotron-3.5-lightning staying in the free view after the
    OpenRouter endpoint reported paid pricing.
    """

    def make_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        connection.executescript(SCHEMA)
        connection.execute(
            """INSERT INTO providers(
                 provider_id,display_name,official_models_endpoint,base_url,
                 api_style,auth_env_var,pricing_policy,free_definition)
               VALUES('openrouter','OpenRouter',
                 'https://openrouter.ai/api/v1/models',
                 'https://openrouter.ai/api/v1','openai-completions',
                 'AIMI_OPENROUTER_API_KEY','pricing_report',
                 'endpoint reports zero input/output price')"""
        )
        connection.execute(
            """INSERT INTO provider_models_v2(
                 provider_id,model_identifier,display_name,
                 endpoint_first_seen_at,endpoint_last_seen_at)
               VALUES('openrouter','~moonshotai/kimi-latest',
                 'Kimi Latest (alias)',?,?)""",
            ('2026-07-27T18:00:00+00:00', '2026-08-31T20:00:00+00:00'),
        )
        source = connection.execute(
            """INSERT INTO evidence_sources(
                 url,source_type,publisher,title,official,primary_source,
                 retrieved_at,verification_status)
               VALUES(?,?,?,?,1,1,?,'verified')""",
            (
                'https://openrouter.ai/api/v1/models',
                'api_endpoint',
                'openrouter',
                'OpenRouter models endpoint',
                '2026-08-31T20:00:00+00:00',
            ),
        ).lastrowid
        capture = connection.execute(
            """INSERT INTO evidence_captures(
                 evidence_source_id,retrieved_at,content_sha256,
                 extraction_method,http_status)
               VALUES(?,?,?,'endpoint_monitor',200)""",
            (source, '2026-08-31T20:00:00+00:00', 'models-hash'),
        ).lastrowid
        provider_model_id = connection.execute(
            "SELECT provider_model_id FROM provider_models_v2"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO access_offers(
                 provider_model_id,offer_type,first_observed_at,
                 last_observed_at,input_price_per_million_usd,
                 output_price_per_million_usd,terms_summary,evidence_source_id,
                 evidence_capture_id,confidence,last_verified_at)
               VALUES(?, 'genuine_zero_price', ?, ?, '0', '0', ?, ?, ?,
                 'verified', ?)""",
            (
                provider_model_id,
                '2026-07-27T18:00:00+00:00',
                '2026-08-31T20:00:00+00:00',
                'Endpoint reports zero input/output price',
                source,
                capture,
                '2026-08-31T20:00:00+00:00',
            ),
        )
        connection.commit()
        return connection

    def provider_model_id(self, connection: sqlite3.Connection) -> int:
        return connection.execute(
            "SELECT provider_model_id FROM provider_models_v2"
        ).fetchone()[0]

    def test_paid_observation_closes_stale_free_offer(self) -> None:
        connection = self.make_connection()
        provider_model_id = self.provider_model_id(connection)
        source = connection.execute(
            "SELECT evidence_source_id FROM evidence_sources LIMIT 1"
        ).fetchone()[0]
        capture = connection.execute(
            "SELECT evidence_capture_id FROM evidence_captures LIMIT 1"
        ).fetchone()[0]
        monitor.upsert_endpoint_offer(
            connection,
            'openrouter',
            provider_model_id,
            {
                'id': '~moonshotai/kimi-latest',
                'pricing': {'prompt': '0.00000255', 'completion': '0.00001275'},
            },
            source,
            capture,
        )
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM access_offers WHERE ends_at IS NULL"
            ).fetchone()[0],
            1,
        )
        open_offer = connection.execute(
            "SELECT offer_type FROM access_offers WHERE ends_at IS NULL"
        ).fetchone()[0]
        self.assertEqual(open_offer, 'paid')
        self.assertIsNotNone(
            connection.execute(
                "SELECT ends_at FROM access_offers WHERE offer_type='genuine_zero_price'"
            ).fetchone()[0]
        )
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM currently_free_provider_models"
            ).fetchone()[0],
            0,
        )
        connection.close()

    def test_repeated_paid_observations_keep_single_open_offer(self) -> None:
        connection = self.make_connection()
        provider_model_id = self.provider_model_id(connection)
        source = connection.execute(
            "SELECT evidence_source_id FROM evidence_sources LIMIT 1"
        ).fetchone()[0]
        capture = connection.execute(
            "SELECT evidence_capture_id FROM evidence_captures LIMIT 1"
        ).fetchone()[0]
        value = {
            'id': '~moonshotai/kimi-latest',
            'pricing': {'prompt': '0.00000255', 'completion': '0.00001275'},
        }
        monitor.upsert_endpoint_offer(connection, 'openrouter', provider_model_id, value, source, capture)
        monitor.upsert_endpoint_offer(connection, 'openrouter', provider_model_id, value, source, capture)
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM access_offers WHERE offer_type='paid' AND ends_at IS NULL"
            ).fetchone()[0],
            1,
        )
        connection.close()

    def test_free_observation_closes_stale_paid_offer(self) -> None:
        connection = self.make_connection()
        provider_model_id = self.provider_model_id(connection)
        source = connection.execute(
            "SELECT evidence_source_id FROM evidence_sources LIMIT 1"
        ).fetchone()[0]
        capture = connection.execute(
            "SELECT evidence_capture_id FROM evidence_captures LIMIT 1"
        ).fetchone()[0]
        monitor.upsert_endpoint_offer(
            connection,
            'openrouter',
            provider_model_id,
            {
                'id': '~moonshotai/kimi-latest',
                'pricing': {'prompt': '0.00000255', 'completion': '0.00001275'},
            },
            source,
            capture,
        )
        payload = {
            'data': [
                {
                    'id': '~moonshotai/kimi-latest',
                    'pricing': {'prompt': '0', 'completion': '0'},
                }
            ]
        }
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
                    'openrouter',
                    monitor.CONFIG['openrouter'][0],
                    None,
                    monitor.CONFIG['openrouter'][2],
                )
            finally:
                monitor.ROOT, monitor.SNAP, monitor.fetch = old_root, old_snap, old_fetch
        self.assertEqual(result['status'], 'success')
        open_offers = connection.execute(
            "SELECT offer_type FROM access_offers WHERE ends_at IS NULL"
        ).fetchall()
        self.assertEqual([row[0] for row in open_offers], ['genuine_zero_price'])
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM currently_free_provider_models"
            ).fetchone()[0],
            1,
        )
        connection.close()


if __name__ == '__main__':
    unittest.main()
