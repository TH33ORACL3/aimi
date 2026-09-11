from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import verify_grok_build as verifier


class VerifyGrokBuildTests(unittest.TestCase):
    def test_redaction_preserves_limits_and_environment_references(self) -> None:
        value = {
            "api_key": "xai-12345678901234567890",
            "max_completion_tokens": 8192,
            "env_key": "OPENROUTER_API_KEY",
            "env_http_headers": {"X-Tenant": "TENANT_TOKEN"},
            "extra_headers": {
                "anthropic-version": "2023-06-01",
                "Authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
            },
        }

        redacted = verifier.redact(value, home=Path("/home/test/.grok"))

        self.assertEqual(redacted["api_key"], "<redacted>")
        self.assertEqual(redacted["max_completion_tokens"], 8192)
        self.assertEqual(redacted["env_key"], "OPENROUTER_API_KEY")
        self.assertEqual(redacted["env_http_headers"]["X-Tenant"], "TENANT_TOKEN")
        self.assertEqual(redacted["extra_headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(redacted["extra_headers"]["Authorization"], "<redacted>")

    def test_parse_models_output_captures_order_and_default(self) -> None:
        output = """You are logged in with grok.com.

Default model: github-copilot-gpt-5-6-luna

Available models:
  - grok-4.6
  * github-copilot-gpt-5-6-luna (default)
"""

        parsed = verifier.parse_models_output(output)

        self.assertTrue(parsed["logged_in"])
        self.assertEqual(parsed["default"], "github-copilot-gpt-5-6-luna")
        self.assertEqual(parsed["available"], ["grok-4.6", "github-copilot-gpt-5-6-luna"])

    def test_compare_ignores_platform_metadata_but_checks_portable_config_and_assets(self) -> None:
        base = {
            "version": "1.0.13",
            "models": {"default": "route-a", "available": ["route-a"]},
            "config_layers": {"config.toml": {"exists": True, "mode": "0o644", "data": {"models": {"default": "route-a"}}}},
            "environment_reference_names": ["OPENROUTER_API_KEY"],
            "assets": [{"path": "rules/global-instructions.md", "bytes": 4, "sha256": "abcd", "link": "platform-specific"}],
            "inspect": {"grokVersion": "1.0.13", "configSources": {"layers": [{"path": "$HOME/.grok/config.toml", "role": "user"}]}, "skills": []},
        }
        changed = json.loads(json.dumps(base))
        changed["host"] = {"platform": "win32"}
        changed["config_layers"]["config.toml"]["mode"] = "0o600"
        changed["assets"][0]["link"] = "different-platform-link"

        self.assertEqual(verifier.diff_values(verifier.comparable_manifest(base), verifier.comparable_manifest(changed)), [])

        changed["config_layers"]["config.toml"]["data"]["models"]["default"] = "route-b"
        self.assertTrue(verifier.diff_values(verifier.comparable_manifest(base), verifier.comparable_manifest(changed)))

    def test_secret_scan_rejects_secret_shaped_manifest_values(self) -> None:
        self.assertEqual(verifier.secret_hits({"env_key": "OPENROUTER_API_KEY"}), [])
        self.assertTrue(verifier.secret_hits({"value": "sk-or-12345678901234567890"}))

    def test_normalise_string_makes_windows_home_paths_comparable(self) -> None:
        home = Path("C:/Users/test/.grok")
        self.assertEqual(
            verifier.normalise_string(r"C:\Users\test\.grok\config.toml", home),
            "$HOME/.grok/config.toml",
        )

    def test_dependency_inventory_records_names_without_reading_credential_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / ".grok"
            (root / "bin").mkdir(parents=True)
            (root / ".config" / "azlabs").mkdir(parents=True)
            (root / ".pi" / "agent").mkdir(parents=True)
            (root / "bin" / "github-copilot-bridge.py").write_text("bridge", encoding="utf-8")
            (root / ".config" / "azlabs" / "aura-worker.env").write_text("OPENROUTER_API_KEY=secret\n", encoding="utf-8")
            (root / ".pi" / "agent" / "auth.json").write_text("{\"access\":\"secret\"}", encoding="utf-8")

            inventory = verifier.dependency_inventory(home)

            bridge = next(item for item in inventory if item["path"].endswith("bin/github-copilot-bridge.py"))
            env_file = next(item for item in inventory if item["path"].endswith("aura-worker.env"))
            auth_file = next(item for item in inventory if item["path"].endswith(".pi/agent/auth.json"))
            self.assertIn("sha256", bridge)
            self.assertEqual(env_file["environment_names"], ["OPENROUTER_API_KEY"])
            self.assertTrue(auth_file["credential_store"])
            self.assertNotIn("secret", json.dumps(inventory))

    def test_effective_config_merge_preserves_source_settings_and_applies_overlay(self) -> None:
        self.assertEqual(
            verifier.deep_merge(
                {"models": {"default": "old", "nested": {"keep": True}}},
                {"models": {"default": "new", "nested": {"add": 1}}},
            ),
            {"models": {"default": "new", "nested": {"keep": True, "add": 1}}},
        )

    def test_version_parser_reduces_platform_build_to_semver(self) -> None:
        self.assertEqual(verifier.parse_version("grok 1.0.13 (5e9a58528b76)"), "1.0.13")
        self.assertIsNone(verifier.parse_version("not grok"))

    def test_command_capture_decodes_utf8_output_on_all_hosts(self) -> None:
        result = verifier.run_command([verifier.sys.executable, "-c", "print('✓')"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("✓", result["stdout"])

    def test_shipped_verifier_invokes_real_cli_entry_points(self) -> None:
        source = Path(verifier.__file__).read_text(encoding="utf-8")
        for marker in ('"--version"', '"models"', '"inspect"', '"-m"', '"-p"', "subprocess.run"):
            self.assertIn(marker, source)

    def test_manifest_round_trip_stays_secret_safe(self) -> None:
        manifest = {
            "schema": verifier.SCHEMA,
            "version": "1.0.13",
            "models": {"default": "route-a", "available": ["route-a"]},
            "config_layers": {"config.toml": {"exists": True, "data": {"models": {"default": "route-a"}}}},
            "environment_reference_names": ["OPENROUTER_API_KEY"],
            "assets": [],
            "inspect": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(verifier.load_manifest(path)["version"], "1.0.13")


if __name__ == "__main__":
    unittest.main()
