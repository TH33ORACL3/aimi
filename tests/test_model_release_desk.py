from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import model_release_desk as desk


class ModelReleaseDeskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "aimi.db"
        self.queue_path = self.root / "queue.json"
        self.packages_path = self.root / "packages"
        self.runs_path = self.root / "runs"
        self.assets_path = self.root / "assets"
        self.patches = [
            patch.object(desk, "DB", self.db_path),
            patch.object(desk, "QUEUE", self.queue_path),
            patch.object(desk, "PACKAGES", self.packages_path),
            patch.object(desk, "RUNS", self.runs_path),
            patch.object(desk, "ASSETS", self.assets_path),
        ]
        for item in self.patches:
            item.start()
        self._create_database()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def _create_database(self) -> None:
        connection = sqlite3.connect(self.db_path)
        connection.executescript(
            """
            CREATE TABLE endpoint_changes (
              endpoint_change_id INTEGER PRIMARY KEY,
              provider_id TEXT,
              model_identifier TEXT,
              change_type TEXT,
              detected_at TEXT
            );
            CREATE TABLE provider_models_v2 (
              provider_model_id INTEGER PRIMARY KEY,
              canonical_model_id INTEGER,
              provider_id TEXT,
              model_identifier TEXT,
              display_name TEXT,
              endpoint_first_seen_at TEXT,
              provider_created_at TEXT,
              context_window_tokens INTEGER,
              max_output_tokens INTEGER,
              reasoning INTEGER,
              tools INTEGER,
              function_calling INTEGER,
              structured_outputs INTEGER,
              description TEXT
            );
            CREATE TABLE canonical_models (
              canonical_model_id INTEGER PRIMARY KEY,
              canonical_name TEXT
            );
            CREATE TABLE providers (provider_id TEXT PRIMARY KEY);
            CREATE TABLE subscription_products (
              subscription_product_id INTEGER PRIMARY KEY,
              product_slug TEXT,
              display_name TEXT,
              vendor TEXT,
              product_status TEXT
            );
            CREATE TABLE subscription_model_access (
              subscription_model_access_id INTEGER PRIMARY KEY,
              subscription_product_id INTEGER,
              provider_model_id INTEGER,
              access_type TEXT,
              confidence TEXT,
              notes TEXT
            );
            CREATE TABLE evidence_sources (
              evidence_source_id INTEGER PRIMARY KEY,
              url TEXT
            );
            CREATE TABLE model_events (
              model_event_id INTEGER PRIMARY KEY,
              canonical_model_id INTEGER,
              provider_model_id INTEGER,
              event_type TEXT,
              event_time TEXT,
              time_precision TEXT,
              confidence TEXT,
              supporting_quote TEXT,
              evidence_source_id INTEGER
            );
            """
        )
        _, start_utc, _ = desk.local_day_bounds()
        connection.execute("INSERT INTO providers VALUES ('openrouter')")
        connection.execute(
            """INSERT INTO provider_models_v2 VALUES
               (1, 1, 'openrouter', 'example/new-model', 'Example New Model', ?, ?,
                1000000, 32000, 1, 1, 1, 1, 'Provider description')""",
            (start_utc, start_utc),
        )
        connection.execute("INSERT INTO canonical_models VALUES (1, 'Example New Model')")
        connection.execute("INSERT INTO evidence_sources VALUES (1, 'https://example.invalid/source')")
        connection.execute(
            """INSERT INTO endpoint_changes VALUES
               (15, 'openrouter', 'example/new-model', 'model_added', ?)""",
            (start_utc,),
        )
        connection.execute(
            """INSERT INTO model_events VALUES
               (1, 1, 1, 'endpoint_first_seen', ?, 'second', 'verified', NULL, 1)""",
            (start_utc,),
        )
        connection.commit()
        connection.close()

    def _queue_event(self) -> dict:
        return {
            "endpoint_change_id": 15,
            "provider_id": "openrouter",
            "provider_name": "OpenRouter",
            "model_identifier": "example/new-model",
            "model_name": "Example New Model",
            "detected_at": desk.local_day_bounds()[1],
            "attempts": 0,
        }

    def test_bulk_legacy_queue_entries_are_skipped_without_calling_pi(self) -> None:
        queue = desk.empty_queue()
        detected_at = desk.local_day_bounds()[1]
        queue["pending"] = [
            {
                "endpoint_change_id": 100 + position,
                "monitoring_run_id": 44,
                "monitoring_run_added_count": 6,
                "provider_id": "openai",
                "model_identifier": f"legacy/model-{position}",
                "model_name": f"Legacy Model {position}",
                "detected_at": detected_at,
                "attempts": 0,
            }
            for position in range(6)
        ]
        desk.save_queue(queue)

        with patch.object(desk, "run_pi") as runner:
            result = desk.process_pending()

        self.assertEqual(result, 0)
        runner.assert_not_called()
        saved = desk.load_queue()
        self.assertEqual(saved["pending"], [])
        self.assertEqual(len(saved["processed"]), 6)
        self.assertTrue(
            all(item["status"] == "bulk_endpoint_sync" for item in saved["processed"])
        )

    def test_dry_run_builds_same_day_context_without_consuming_queue(self) -> None:
        queue = desk.empty_queue()
        queue["pending"].append(self._queue_event())
        desk.save_queue(queue)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = desk.process_pending(dry_run=True)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["trigger_candidates"][0]["endpoint_change_id"], 15)
        self.assertEqual(payload["same_day"]["endpoint_additions"][0]["model_identifier"], "example/new-model")
        self.assertEqual(payload["same_day"]["verified_events"], [])
        self.assertTrue(payload["rules"]["x_auto_post_verified_releases"])
        self.assertEqual(len(desk.load_queue()["pending"]), 1)

    def test_complete_batch_moves_event_to_processed(self) -> None:
        item = self._queue_event()
        queue = desk.empty_queue()
        queue["pending"].append(item)
        desk.save_queue(queue)
        package_path = self.packages_path / "package.json"
        package = {"package_id": "package", "status": "candidate_only"}

        desk.complete_batch(queue, [item], package_path, package)

        saved = desk.load_queue()
        self.assertEqual(saved["pending"], [])
        self.assertEqual(saved["processed"][0]["endpoint_change_id"], 15)
        self.assertEqual(saved["processed"][0]["status"], "candidate_only")

    def test_approval_package_requires_a_real_media_file(self) -> None:
        package = {
            "package_id": "package",
            "status": "awaiting_x_approval",
            "models": [],
            "notes": [],
            "article_url": "https://azlabs.ai/news/example",
            "media_path": str(self.assets_path / "package" / "example.png"),
            "x_root_text": "A model arrived.",
            "x_reply_text": "Details: https://azlabs.ai/news/example",
        }
        with self.assertRaisesRegex(RuntimeError, "media is missing"):
            desk.validate_package(package, "package")

        media = Path(package["media_path"])
        media.parent.mkdir(parents=True)
        media.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 1200, 630)
        )
        desk.validate_package(package, "package")

        package["article_url"] = "https://example.com/news/example"
        with self.assertRaisesRegex(RuntimeError, "canonical AZ Labs News URL"):
            desk.validate_package(package, "package")

    def test_rendered_package_has_media_and_numbered_approval(self) -> None:
        package_path = self.packages_path / "package.json"
        media = self.assets_path / "package" / "example.png"
        media.parent.mkdir(parents=True)
        media.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 1200, 630)
        )
        package = {
            "package_id": "package",
            "status": "awaiting_x_approval",
            "article_url": "https://azlabs.ai/news/example",
            "media_path": str(media),
            "same_day_narrative": "Third model today.",
            "x_root_text": "A model arrived.",
            "x_reply_text": "Read more.",
        }
        rendered = desk.render_package(package, package_path)
        self.assertIn(f"MEDIA:{media}", rendered)
        self.assertIn("1. Post this exact visual thread", rendered)
        self.assertIn("3. Skip X", rendered)

    def test_pi_timeout_is_bounded_by_default(self) -> None:
        self.assertEqual(desk.PI_TIMEOUT_SECONDS, desk.DEFAULT_PI_TIMEOUT_SECONDS)
        self.assertEqual(desk.PI_TIMEOUT_SECONDS, 900)

    def test_batch_id_is_stable_across_retries(self) -> None:
        items = [self._queue_event()]
        first = desk.batch_id(items, "2026-08-12")
        second = desk.batch_id(items, "2026-08-12")
        self.assertEqual(first, second)
        self.assertEqual(first, "20260812-e629fa6598")

    def test_approve_requires_explicit_confirmation(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires --confirmed"):
            desk.approve_package("missing", confirmed=False, digest=None)


if __name__ == "__main__":
    unittest.main()
