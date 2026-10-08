from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import model_release_desk as desk
import model_release_worker as worker


class ModelReleaseWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.state_dir = root / "state"
        self.active_file = self.state_dir / "active.json"
        self.lock_file = self.state_dir / "dispatcher.lock"
        self.queue_file = root / "queue.json"
        self.release_lock = root / "release.lock"
        self.worker_runs = root / "worker-runs"
        self.patches = [
            patch.object(worker, "STATE_DIR", self.state_dir),
            patch.object(worker, "ACTIVE_FILE", self.active_file),
            patch.object(worker, "DISPATCH_LOCK", self.lock_file),
            patch.object(worker, "WORKER_RUNS", self.worker_runs),
            patch.object(desk, "QUEUE", self.queue_file),
            patch.object(desk, "LOCK", self.release_lock),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def _queue(self) -> dict:
        queue = desk.empty_queue()
        queue["pending"].append(
            {
                "endpoint_change_id": 15,
                "canonical_model_id": 8,
                "provider_id": "openai",
                "model_identifier": "gpt-6-luna",
                "detected_at": desk.local_day_bounds()[1],
                "attempts": 0,
            }
        )
        desk.save_queue(queue)
        return queue

    def test_dispatch_launches_one_supervised_worker_unit(self) -> None:
        self._queue()
        launched = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch.object(worker.subprocess, "run", return_value=launched) as runner:
            result = worker.dispatch_once()

        self.assertEqual(result, 0)
        runner.assert_called_once()
        command = runner.call_args.args[0]
        self.assertEqual(command[0], "systemd-run")
        self.assertIn("--no-block", command)
        self.assertIn("--collect", command)
        self.assertIn(str(Path(worker.__file__).resolve()), command)
        self.assertIn("worker", command)
        state = json.loads(self.active_file.read_text(encoding="utf-8"))
        self.assertTrue(state["active"]["unit_name"].startswith("aimi-model-release-worker-"))
        self.assertEqual(state["version"], worker.VERSION)

    def test_running_worker_prevents_duplicate_dispatch(self) -> None:
        self._queue()
        worker.write_json(
            self.active_file,
            {
                "version": worker.VERSION,
                "active": {
                    "run_id": "existing-run",
                    "unit_name": "aimi-model-release-worker-existing-run.service",
                    "result_path": str(self.state_dir / "results" / "existing.json"),
                    "log_path": str(self.state_dir / "existing.log"),
                },
            },
        )
        with patch.object(worker, "systemd_unit_active", return_value=True), patch.object(worker.subprocess, "run") as runner:
            self.assertEqual(worker.dispatch_once(), 0)
        runner.assert_not_called()

    def test_legacy_running_worker_is_preserved_during_systemd_migration(self) -> None:
        self._queue()
        worker.write_json(
            self.active_file,
            {
                "version": worker.VERSION,
                "active": {
                    "run_id": "legacy-run",
                    "pid": 4567,
                    "result_path": str(self.state_dir / "results" / "legacy.json"),
                    "log_path": str(self.state_dir / "legacy.log"),
                },
            },
        )
        with patch.object(worker, "process_matches", return_value=True), patch.object(worker, "systemd_unit_active") as systemd_check, patch.object(worker.subprocess, "run") as runner:
            self.assertEqual(worker.dispatch_once(), 0)
        systemd_check.assert_not_called()
        runner.assert_not_called()

    def test_legacy_stale_batch_without_dispatch_state_is_recovered(self) -> None:
        queue = self._queue()
        queue["active_batch"] = {"package_id": "legacy-stale", "endpoint_change_ids": [15]}
        desk.save_queue(queue)

        with patch.object(worker.subprocess, "run") as runner:
            self.assertEqual(worker.dispatch_once(), 0)

        saved = desk.load_queue()
        self.assertNotIn("active_batch", saved)
        self.assertEqual(saved["pending"][0]["attempts"], 1)
        self.assertEqual(saved["pending"][0]["last_error"], "Recovered a stale Hermes release-batch claim before dispatch.")
        runner.assert_not_called()

    def test_dead_worker_recovery_clears_stale_batch_and_applies_backoff(self) -> None:
        queue = self._queue()
        item = queue["pending"][0]
        queue["active_batch"] = {"package_id": "stale", "endpoint_change_ids": [15]}
        desk.save_queue(queue)
        worker.write_json(
            self.active_file,
            {
                "version": worker.VERSION,
                "active": {
                    "run_id": "dead-run",
                    "unit_name": "aimi-model-release-worker-dead-run.service",
                    "result_path": str(self.state_dir / "missing-result.json"),
                    "log_path": str(self.state_dir / "dead.log"),
                },
            },
        )

        with patch.object(worker, "systemd_unit_active", return_value=False), patch.object(worker.subprocess, "run") as runner:
            self.assertEqual(worker.dispatch_once(), 1)

        saved_state = json.loads(self.active_file.read_text(encoding="utf-8"))
        self.assertTrue(saved_state["last_result"]["reported"])
        saved = desk.load_queue()
        self.assertNotIn("active_batch", saved)
        self.assertEqual(saved["pending"][0]["attempts"], 1)
        self.assertIn("exited before writing", saved["pending"][0]["last_error"])
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
