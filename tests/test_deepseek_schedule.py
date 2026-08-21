from __future__ import annotations

from importlib.machinery import SourceFileLoader
import importlib.util
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import deepseek_schedule


class DeepSeekScheduleTests(unittest.TestCase):
    def test_peak_boundaries_are_exclusive_at_end(self) -> None:
        self.assertEqual(
            deepseek_schedule.status_at(
                "2026-08-17T01:00:00Z", "UTC"
            )["period"],
            "peak",
        )
        self.assertEqual(
            deepseek_schedule.status_at(
                "2026-08-17T04:00:00Z", "UTC"
            )["period"],
            "off_peak",
        )
        self.assertEqual(
            deepseek_schedule.status_at(
                "2026-08-17T06:00:00Z", "UTC"
            )["period"],
            "peak",
        )
        self.assertEqual(
            deepseek_schedule.status_at(
                "2026-08-17T10:00:00Z", "UTC"
            )["period"],
            "off_peak",
        )

    def test_south_africa_conversion_uses_am_pm_and_local_windows(self) -> None:
        result = deepseek_schedule.status_at(
            "2026-08-16T23:19:00Z",
            "Africa/Johannesburg",
        )
        self.assertEqual(result["timezone"], "Africa/Johannesburg")
        self.assertEqual(result["local_time"], "17 Aug 2026, 1:19 AM SAST")
        self.assertTrue(result["is_off_peak"])
        self.assertEqual(
            result["answer"],
            "Yes, you are currently in an off-peak period.",
        )
        self.assertEqual(
            [(x["start"], x["end"]) for x in result["peak_windows_today"]],
            [("3:00 AM", "6:00 AM"), ("8:00 AM", "12:00 PM")],
        )
        self.assertEqual(
            [(x["start"], x["end"]) for x in result["off_peak_windows_today"]],
            [
                ("12:00 AM", "3:00 AM"),
                ("6:00 AM", "8:00 AM"),
                ("12:00 PM", "12:00 AM"),
            ],
        )

    def test_next_transition_is_reported_in_local_time(self) -> None:
        result = deepseek_schedule.status_at(
            "2026-08-17T00:59:00Z",
            "Africa/Johannesburg",
        )
        self.assertEqual(result["next_transition"]["period_after_transition"], "peak")
        self.assertEqual(
            result["next_transition"]["local_time"],
            "17 Aug 2026, 3:00 AM",
        )

    def test_invalid_timezone_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown IANA timezone"):
            deepseek_schedule.status_at(
                "2026-08-17T00:00:00Z",
                "Not/A-Timezone",
            )

    def test_cli_manifest_and_handler_expose_command(self) -> None:
        cli_path = Path(__file__).resolve().parents[1] / "aimi"
        loader = SourceFileLoader("aimi_cli", str(cli_path))
        spec = importlib.util.spec_from_loader("aimi_cli", loader)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        parser, subparsers = cli.build_parser()
        args = parser.parse_args(
            [
                "deepseek-status",
                "--timezone",
                "Africa/Johannesburg",
                "--at",
                "2026-08-16T23:19:00Z",
            ]
        )
        output = io.StringIO()
        with redirect_stdout(output):
            args.fn(None, args)
        payload = json.loads(output.getvalue())
        self.assertTrue(payload["is_off_peak"])
        self.assertIn("deepseek-status", subparsers.choices)


if __name__ == "__main__":
    unittest.main()
