from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import monitor_endpoints as monitor


class ClineMonitorTests(unittest.TestCase):
    def test_cline_catalog_normalization(self) -> None:
        payload = {
            "clinePass": [
                {
                    "id": "cline-pass/deepseek-v4-flash",
                    "name": "cline-pass/deepseek-v4-flash",
                    "description": "Fast and efficient with 1M context window",
                    "tags": [],
                },
                {
                    "id": "cline-pass/qwen3.7-plus",
                    "name": "cline-pass/qwen3.7-plus",
                    "description": "Fast multimodal agent model with vision and video input",
                    "tags": [],
                },
            ]
        }
        rows = monitor.rows("cline", payload, "clinePass")
        flash = rows["cline-pass/deepseek-v4-flash"]
        qwen = rows["cline-pass/qwen3.7-plus"]

        self.assertEqual(monitor.CONFIG["cline"][0], "https://api.cline.bot/api/v1/ai/cline/recommended-models")
        self.assertEqual(monitor.CONFIG["cline"][1], "CLINE_API_KEY")
        self.assertEqual(flash["displayName"], "DeepSeek V4 Flash")
        self.assertEqual(flash["context_length"], 1_000_000)
        self.assertEqual(qwen["input_modalities"], ["text", "image", "video"])
        self.assertEqual(qwen["raw"]["tags"], [])
        self.assertFalse(monitor.is_free("cline", flash))

    def test_poll_persists_evidence_subscription_and_identity_idempotently(self) -> None:
        schema = (Path(__file__).resolve().parents[1] / "schema_v2.sql").read_text()
        payload = {
            "clinePass": [
                {
                    "id": "cline-pass/deepseek-v4-flash",
                    "name": "cline-pass/deepseek-v4-flash",
                    "description": "Fast and efficient with 1M context window",
                    "tags": [],
                },
                {
                    "id": "cline-pass/qwen3.8-max",
                    "name": "cline-pass/qwen3.8-max",
                    "description": "Qwen's New SOTA coding model",
                    "tags": [],
                },
            ]
        }
        raw = json.dumps(payload, sort_keys=True).encode()

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temporary:
            root = Path(temporary)
            database = root / "fixture.db"
            connection = sqlite3.connect(database)
            connection.executescript(schema)
            connection.execute(
                "INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,auth_env_var,pricing_policy,free_definition) VALUES(?,?,?,?,?,?,?,?)",
                (
                    "cline",
                    "Cline",
                    "https://docs.cline.bot/getting-started/clinepass",
                    "https://api.cline.bot/api/v1",
                    "openai-completions",
                    "CLINE_API_KEY",
                    "subscription",
                    "stale",
                ),
            )
            connection.execute(
                "INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,pricing_policy,free_definition) VALUES(?,?,?,?,?,?,?)",
                (
                    "openrouter",
                    "OpenRouter",
                    "https://openrouter.ai/api/v1/models",
                    "https://openrouter.ai/api/v1",
                    "openai-completions",
                    "per-token",
                    "provider-defined",
                ),
            )
            cursor = connection.execute(
                "INSERT INTO canonical_models(canonical_slug,developer,canonical_name) VALUES('qwen-qwen3-8-max','Qwen','Qwen: Qwen3.8 Max')"
            )
            canonical_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO provider_models_v2(provider_id,canonical_model_id,model_identifier,endpoint_first_seen_at,endpoint_last_seen_at) VALUES('openrouter',?,'qwen/qwen3.8-max',?,?)",
                (canonical_id, monitor.NOW, monitor.NOW),
            )
            connection.execute(
                "INSERT INTO subscription_products(product_slug,vendor,display_name,product_type,billing_model,product_status,confidence) VALUES('cline-pass','Cline Bot Inc.','ClinePass','individual','subscription','active','verified')"
            )
            connection.commit()

            old_root, old_snap, old_fetch = monitor.ROOT, monitor.SNAP, monitor.fetch
            monitor.ROOT = root
            monitor.SNAP = root / "snapshots" / "monitor"
            monitor.SNAP.mkdir(parents=True)
            monitor.fetch = lambda pid, url, env: (200, raw, {})
            try:
                first = monitor.poll(
                    connection,
                    "cline",
                    monitor.CONFIG["cline"][0],
                    monitor.CONFIG["cline"][1],
                    monitor.CONFIG["cline"][2],
                )
                second = monitor.poll(
                    connection,
                    "cline",
                    monitor.CONFIG["cline"][0],
                    monitor.CONFIG["cline"][1],
                    monitor.CONFIG["cline"][2],
                )
            finally:
                monitor.ROOT, monitor.SNAP, monitor.fetch = old_root, old_snap, old_fetch

            self.assertEqual(first["status"], "success")
            self.assertEqual(second["status"], "unchanged")
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM provider_models_v2 WHERE provider_id='cline' AND model_identifier LIKE 'cline-pass/%'").fetchone()[0],
                2,
            )
            qwen = connection.execute(
                "SELECT canonical_model_id,source_snapshot_id FROM provider_models_v2 WHERE provider_id='cline' AND model_identifier='cline-pass/qwen3.8-max'"
            ).fetchone()
            self.assertEqual(qwen[0], canonical_id)
            self.assertIsNotNone(qwen[1])
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM evidence_captures").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM access_offers WHERE offer_type='subscription_included'").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM subscription_model_access WHERE access_type='subscription_included'").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM model_events WHERE event_type='endpoint_first_seen'").fetchone()[0], 2)
            endpoint = connection.execute("SELECT official_models_endpoint FROM providers WHERE provider_id='cline'").fetchone()[0]
            self.assertEqual(endpoint, monitor.CONFIG["cline"][0])
            api_paths = dict(connection.execute("SELECT path,endpoint_status FROM provider_api_endpoints WHERE provider_id='cline'").fetchall())
            self.assertEqual(api_paths["/ai/cline/recommended-models"], "available")
            self.assertEqual(api_paths["/models"], "unavailable")
            self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM evidence_claims WHERE subject_key LIKE 'cline/%'").fetchone()[0], 8)
            connection.close()


if __name__ == "__main__":
    unittest.main()
