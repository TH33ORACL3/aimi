# tests/test_factory_droid_drift.py
from __future__ import annotations
import json
import re
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "aimi.db"
EVIDENCE_FACTORY = ROOT / "evidence" / "factory"

class TestFactoryDroidDrift(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(DB)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()

    def test_factory_provider_and_pricing_policy(self) -> None:
        row = self.conn.execute("SELECT provider_id, display_name, pricing_policy, official_models_endpoint FROM providers WHERE provider_id='factory'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["pricing_policy"], "subscription")
        self.assertEqual(row["official_models_endpoint"], "https://docs.factory.ai/models.md")

    def test_factory_subscription_tiers(self) -> None:
        rows = {r["product_slug"]: r for r in self.conn.execute("SELECT product_slug, monthly_price, billing_model FROM subscription_products WHERE vendor='Factory AI'")}
        self.assertIn("factory-pro", rows)
        self.assertIn("factory-plus", rows)
        self.assertIn("factory-max", rows)
        self.assertEqual(rows["factory-pro"]["monthly_price"], "20")
        self.assertEqual(rows["factory-plus"]["monthly_price"], "100")
        self.assertEqual(rows["factory-max"]["monthly_price"], "200")
        self.assertEqual(rows["factory-pro"]["billing_model"], "subscription")

    def test_astra_and_gemini_38_multipliers(self) -> None:
        # GPT-6 Astra
        row_astra = self.conn.execute(
            "SELECT model_identifier, display_name, reasoning, provider_metadata_json FROM provider_models_v2 WHERE provider_id='factory' AND model_identifier='gpt-6-astra'"
        ).fetchone()
        self.assertIsNotNone(row_astra, "gpt-6-astra must be registered in provider_models_v2 under factory")
        meta_astra = json.loads(row_astra["provider_metadata_json"])
        self.assertEqual(meta_astra.get("token_multiplier"), 4.0)
        self.assertEqual(meta_astra.get("output_token_multiplier"), 5.0)
        self.assertEqual(meta_astra.get("tier"), "premium")

        # Gemini 3.8 Flash
        row_gemini = self.conn.execute(
            "SELECT model_identifier, display_name, reasoning, context_window_tokens, max_output_tokens, provider_metadata_json FROM provider_models_v2 WHERE provider_id='factory' AND model_identifier='gemini-3.8-flash'"
        ).fetchone()
        self.assertIsNotNone(row_gemini, "gemini-3.8-flash must be registered in provider_models_v2 under factory")
        meta_gemini = json.loads(row_gemini["provider_metadata_json"])
        self.assertEqual(meta_gemini.get("token_multiplier"), 0.6)
        self.assertEqual(meta_gemini.get("output_token_multiplier"), 5.0)
        self.assertEqual(row_gemini["context_window_tokens"], 1000000)
        self.assertEqual(row_gemini["max_output_tokens"], 65536)

    def test_harness_available_models_for_droid(self) -> None:
        avail_count = self.conn.execute(
            "SELECT COUNT(*) FROM harness_available_model_entries WHERE provider_name='factory'"
        ).fetchone()[0]
        self.assertGreaterEqual(avail_count, 80, "Droid harness must have all native models available")

    def test_detect_web_docs_vs_binary_drift(self) -> None:
        manifest_path = EVIDENCE_FACTORY / "droid-binary-manifest.json"
        docs_path = EVIDENCE_FACTORY / "models-md-snapshot.md"
        self.assertTrue(manifest_path.exists(), "Binary manifest must be archived in evidence/factory/")
        self.assertTrue(docs_path.exists(), "Web docs snapshot must be archived in evidence/factory/")

        binary_manifest = json.loads(manifest_path.read_text())
        docs_text = docs_path.read_text()

        # Models documented in web docs
        web_models = set(re.findall(r'\|\s*`([^`]+)`\s*\|', docs_text))

        # Check drift
        binary_models = set(binary_manifest.keys())
        unannounced_or_cli_only = binary_models - web_models

        # Astra and Gemini 3.8 Flash are in binary but missing from static web docs
        self.assertIn("gpt-6-astra", unannounced_or_cli_only)
        self.assertIn("gemini-3.8-flash", unannounced_or_cli_only)

        # Verify drift metadata identifies newUntil flags
        new_models = {mid: m for mid, m in binary_manifest.items() if m.get("new_until")}
        self.assertIn("gpt-6-astra", new_models)
        self.assertIn("gemini-3.8-flash", new_models)

if __name__ == "__main__":
    unittest.main()
