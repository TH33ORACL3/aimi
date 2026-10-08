from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import monitor_endpoints as monitor


class FakeResponse:
    def __init__(self, body: dict, status: int = 200) -> None:
        self.status = status
        self.headers = {"content-type": "application/json"}
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class AnthropicMonitorTests(unittest.TestCase):
    def test_missing_key_skips_anthropic_without_recording_a_failed_poll(self) -> None:
        schema = (Path(__file__).resolve().parents[1] / "schema_v2.sql").read_text()
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "aimi.db"
            connection = sqlite3.connect(database)
            connection.executescript(schema)
            connection.commit()
            connection.close()

            output = io.StringIO()
            with patch.object(monitor, "DB", database), patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), contextlib.redirect_stdout(output):
                result = monitor.main(["--provider", "anthropic"])

            self.assertEqual(result, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload[0]["status"], "skipped")
            self.assertIn("ANTHROPIC_API_KEY", payload[0]["error"])
            connection = sqlite3.connect(database)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM monitoring_runs").fetchone()[0], 0)
            connection.close()

    def test_config_uses_official_models_endpoint(self) -> None:
        self.assertEqual(
            monitor.CONFIG["anthropic"],
            ("https://api.anthropic.com/v1/models", "ANTHROPIC_API_KEY", "data"),
        )

    def test_fetch_uses_anthropic_headers_and_collects_every_page(self) -> None:
        responses = [
            {"data": [{"id": "claude-opus-5.5"}], "has_more": True, "last_id": "claude-opus-5.5"},
            {"data": [{"id": "claude-sonnet-5.5"}], "has_more": False, "last_id": "claude-sonnet-5.5"},
        ]
        requests = []

        def fake_urlopen(request, timeout):
            requests.append(request)
            self.assertEqual(timeout, 45)
            return FakeResponse(responses.pop(0))

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-only"}), patch.object(
            monitor.urllib.request, "urlopen", side_effect=fake_urlopen
        ):
            status, raw, _headers = monitor.fetch(
                "anthropic",
                "https://api.anthropic.com/v1/models",
                "ANTHROPIC_API_KEY",
            )

        payload = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in payload["data"]], ["claude-opus-5.5", "claude-sonnet-5.5"])
        self.assertFalse(payload["has_more"])
        self.assertEqual(len(requests), 2)
        for request in requests:
            self.assertEqual(request.get_header("X-api-key"), "test-key-only")
            self.assertEqual(request.get_header("Anthropic-version"), "2023-06-01")
        self.assertEqual(parse_qs(urlparse(requests[0].full_url).query), {"limit": ["1000"]})
        self.assertEqual(
            parse_qs(urlparse(requests[1].full_url).query),
            {"limit": ["1000"], "after_id": ["claude-opus-5.5"]},
        )

    def test_rows_normalize_anthropic_release_limits_and_capabilities(self) -> None:
        payload = {
            "data": [
                {
                    "id": "claude-opus-5.5",
                    "display_name": "Claude Opus 5.5",
                    "created_at": "2026-09-22T12:00:00Z",
                    "max_input_tokens": 1_000_000,
                    "max_tokens": 128_000,
                    "capabilities": {
                        "effort": {
                            "supported": True,
                            "low": {"supported": True},
                            "medium": {"supported": True},
                            "high": {"supported": True},
                            "xhigh": {"supported": True},
                            "max": {"supported": True},
                        },
                        "thinking": {"supported": True},
                        "image_input": {"supported": True},
                        "pdf_input": {"supported": True},
                        "structured_outputs": {"supported": True},
                    },
                }
            ]
        }

        model = monitor.rows("anthropic", payload, "data")["claude-opus-5.5"]

        self.assertEqual(model["provider_created_at"], "2026-09-22T12:00:00Z")
        self.assertEqual(model["context_length"], 1_000_000)
        self.assertEqual(model["max_output"], 128_000)
        self.assertEqual(model["input_modalities"], ["text", "image", "file"])
        self.assertEqual(model["output_modalities"], ["text"])
        self.assertEqual(model["reasoning"], 1)
        self.assertEqual(model["structured_outputs"], 1)
        self.assertEqual(model["reasoning_efforts"], ["low", "medium", "high", "xhigh", "max"])

    def test_anthropic_created_at_is_a_release_event_but_epoch_placeholder_is_not(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.executescript(
            """
            CREATE TABLE model_events (
              provider_model_id INTEGER,
              event_type TEXT,
              event_time TEXT,
              time_precision TEXT,
              evidence_source_id INTEGER,
              evidence_capture_id INTEGER,
              supporting_quote TEXT,
              confidence TEXT,
              details_json TEXT
            );
            """
        )
        source = {"provider_created_at": "2026-09-22T12:00:00+00:00"}
        monitor.record_anthropic_release_event(connection, 9, source, 3, 4)
        monitor.record_anthropic_release_event(connection, 9, source, 3, 4)
        monitor.record_anthropic_release_event(
            connection,
            10,
            {"provider_created_at": "1970-01-01T00:00:00+00:00"},
            3,
            4,
        )

        rows = connection.execute(
            "SELECT provider_model_id,event_type,event_time,confidence FROM model_events"
        ).fetchall()
        self.assertEqual(rows, [(9, "general_release", "2026-09-22T12:00:00+00:00", "single_source")])
        connection.close()


if __name__ == "__main__":
    unittest.main()
