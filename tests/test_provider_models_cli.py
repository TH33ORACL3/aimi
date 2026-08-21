from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("aimi_cli_for_test", str(ROOT / "aimi"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None and SPEC.loader is not None
AIMI = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(AIMI)


class ProviderModelsCommandTests(unittest.TestCase):
    def test_detected_routes_are_visible_and_unlinked_access_stays_explicit(self) -> None:
        schema = (ROOT / "schema_v2.sql").read_text()
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            connection = sqlite3.connect(Path(temporary) / "fixture.db")
            connection.row_factory = sqlite3.Row
            connection.executescript(schema)
            connection.execute(
                "INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,pricing_policy,free_definition) VALUES(?,?,?,?,?,?,?)",
                (
                    "opencode-go",
                    "OpenCode Go",
                    "https://opencode.ai/zen/go/v1/models",
                    "https://opencode.ai/zen/go/v1",
                    "openai-completions",
                    "subscription",
                    "Requires official pricing evidence",
                ),
            )
            connection.execute(
                "INSERT INTO monitoring_targets(provider_id,target_type,url,schedule_class,enabled,expected_format,parser_name,last_checked_at,last_success_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    "opencode-go",
                    "models_endpoint",
                    "https://opencode.ai/zen/go/v1/models",
                    "frequent",
                    1,
                    "json",
                    "opencode-go",
                    "2026-08-19T12:56:33+00:00",
                    "2026-08-19T12:56:33+00:00",
                ),
            )
            product_id = connection.execute(
                "INSERT INTO subscription_products(product_slug,vendor,display_name,product_type,billing_model,product_status,confidence) VALUES(?,?,?,?,?,?,?)",
                ("opencode-go", "OpenCode", "OpenCode Go", "individual", "subscription", "active", "verified"),
            ).lastrowid
            covered_id = connection.execute(
                "INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_first_seen_at,endpoint_last_seen_at) VALUES(?,?,?,?,?)",
                ("opencode-go", "known-model", "Known Model", "2026-08-01T00:00:00Z", "2026-08-19T12:56:33Z"),
            ).lastrowid
            detected_id = connection.execute(
                "INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_first_seen_at,endpoint_last_seen_at) VALUES(?,?,?,?,?)",
                ("opencode-go", "muse-spark-1.2-contributor", "Muse Spark 1.2 Contributor", "2026-08-19T06:34:41Z", "2026-08-19T12:56:33Z"),
            ).lastrowid
            connection.execute(
                "INSERT INTO subscription_model_access(subscription_product_id,provider_model_id,access_type,confidence,last_verified_at) VALUES(?,?,?,?,?)",
                (product_id, covered_id, "subscription_included", "verified", "2026-07-21T21:26:24Z"),
            )
            target_id = connection.execute(
                "SELECT monitoring_target_id FROM monitoring_targets WHERE provider_id='opencode-go'"
            ).fetchone()[0]
            run_id = connection.execute(
                "INSERT INTO monitoring_runs(monitoring_target_id,started_at,status) VALUES(?,?,?)",
                (target_id, "2026-08-19T06:34:41Z", "changed"),
            ).lastrowid
            connection.execute(
                "INSERT INTO endpoint_changes(monitoring_run_id,provider_id,change_type,model_identifier,detected_at) VALUES(?,?,?,?,?)",
                (run_id, "opencode-go", "model_added", "muse-spark-1.2-contributor", "2026-08-19T06:34:41Z"),
            )
            connection.commit()

            payload = AIMI._provider_models_payload(connection, "opencode-go")

            self.assertEqual(payload["model_count"], 2)
            models = {row["model_identifier"]: row for row in payload["models"]}
            self.assertEqual(models["known-model"]["subscription_access"][0]["access_type"], "subscription_included")
            self.assertEqual(models["muse-spark-1.2-contributor"]["subscription_access"], [])
            self.assertTrue(models["muse-spark-1.2-contributor"]["detected_in_endpoint_changes"])
            self.assertEqual(payload["official_models_endpoint"], "https://opencode.ai/zen/go/v1/models")

            pi_fragment = AIMI.pi_provider_fragment(connection, "opencode-go", "muse-spark-1.2-contributor")
            pi_model = pi_fragment["models"][0]
            self.assertEqual(pi_model["api"], "openai-responses")
            self.assertTrue(pi_model["reasoning"])

            parser, _ = AIMI.build_parser()
            args = parser.parse_args(["provider-models", "opencode-go"])
            self.assertEqual(args.provider, "opencode-go")
            self.assertFalse(args.include_removed)
            connection.close()


if __name__ == "__main__":
    unittest.main()
