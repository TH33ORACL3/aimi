#!/usr/bin/env python3
"""Tests for DeepSWE benchmark ingestion (ingest_deepswe_scores.py)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema_v2.sql"

SAMPLE = {
    "generated_at": "2026-08-15T00:00:00Z",
    "scope": {},
    "rows": [
        {"model": "gpt-5-6-luna", "harness": "mini-swe-agent", "reasoning_effort": "max",
         "config": "mini_swe_agent_gpt_5_6_luna_max", "pass_at_1": 0.671, "n_tasks": 113, "n_attempted": 444},
        {"model": "gpt-5-6-luna", "harness": "mini-swe-agent", "reasoning_effort": "medium",
         "config": "mini_swe_agent_gpt_5_6_luna_medium", "pass_at_1": 0.50, "n_tasks": 113, "n_attempted": 444},
        {"model": "deepseek-v4-pro", "harness": "mini-swe-agent", "reasoning_effort": "max",
         "config": "mini_swe_agent_deepseek_v4_pro_max", "pass_at_1": 0.628, "n_tasks": 113, "n_attempted": 444},
        {"model": "kimi-k3", "harness": "mini-swe-agent", "reasoning_effort": "max",
         "config": "mini_swe_agent_kimi_k3_max", "pass_at_1": 0.685, "n_tasks": 113, "n_attempted": 444},
    ],
}


class DeepsweIngestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.exe = Path(self.tmp.name) / "aimi.db"
        conn = sqlite3.connect(self.exe)
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.commit()
        conn.close()
        self.env = os.environ.copy()
        self.env["AIMI_DB"] = str(self.exe)
        self.sample = Path(self.tmp.name) / "sample.json"
        self.sample.write_text(json.dumps(SAMPLE))
        self._old_argv = sys.argv
        self._old_env = os.environ
        os.environ["AIMI_DB"] = str(self.exe)

    def tearDown(self) -> None:
        sys.argv = self._old_argv
        os.environ.clear()
        os.environ.update(self._old_env)
        self.tmp.cleanup()

    def _count(self, sql, *args) -> int:
        conn = sqlite3.connect(f"file:{self.exe}?mode=ro", uri=True)
        try:
            return conn.execute(sql, args).fetchone()[0]
        finally:
            conn.close()

    def test_best_config_and_idempotency(self) -> None:
        import ingest_deepswe_scores as m
        sys.argv = ["ingest_deepswe_scores.py", "--input", str(self.sample), "--no-backup"]
        self.assertEqual(m.main(), 0)
        # All four leaderboard rows plus the fixed GLM-5.3 vendor row.
        self.assertEqual(self._count("SELECT COUNT(*) FROM benchmark_scores"), 5)
        # Among gpt-5.6-luna's two effort rows only the max (0.671) is best-config.
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) FROM benchmark_scores b JOIN canonical_models cm USING(canonical_model_id) "
                "WHERE cm.canonical_slug='gpt-5.6-luna' AND b.is_best_config=1"
            ),
            1,
        )
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) FROM benchmark_scores b JOIN canonical_models cm USING(canonical_model_id) "
                "WHERE cm.canonical_slug='gpt-5.6-luna' AND b.is_best_config=1 AND ROUND(b.value,3)=0.671"
            ),
            1,
        )
        # Vendor-reported GLM-5.3 present.
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) FROM benchmark_scores b JOIN canonical_models cm USING(canonical_model_id) "
                "WHERE cm.canonical_slug='glm-5.3' AND b.source_type='vendor'"
            ),
            1,
        )
        # Idempotent re-run does not duplicate rows.
        sys.argv = ["ingest_deepswe_scores.py", "--input", str(self.sample), "--no-backup"]
        self.assertEqual(m.main(), 0)
        self.assertEqual(self._count("SELECT COUNT(*) FROM benchmark_scores"), 5)


class GenericBenchmarkIngestTest(unittest.TestCase):
    """Tests for the generic multi-benchmark ingestor (ingest_benchmark_scores.py)."""

    def test_swebench_and_terminal_bench(self) -> None:
        import tempfile
        import importlib
        import ingest_benchmark_scores
        tmp = tempfile.TemporaryDirectory()
        try:
            exe = Path(tmp.name) / "aimi.db"
            conn = sqlite3.connect(exe)
            conn.executescript(SCHEMA.read_text(encoding="utf-8"))
            conn.commit(); conn.close()
            old = os.environ.get("AIMI_DB")
            os.environ["AIMI_DB"] = str(exe)
            # DB is bound at import time; reload so it points at the temp db.
            importlib.reload(ingest_benchmark_scores)
            m = ingest_benchmark_scores
            payload = {
                "benchmark": "swebench_verified", "benchmark_version": "2026-08",
                "source_url": "https://example.invalid/swebench",
                "rows": [
                    {"canonical_slug": "claude-opus-5", "value": 0.96, "score_date": "2026-08-14"},
                    {"canonical_slug": "claude-opus-5", "value": 0.90, "score_date": "2026-08-14", "config_text": "other"},
                ],
            }
            src = Path(tmp.name) / "s.json"; src.write_text(__import__("json").dumps(payload))
            sys.argv = ["ingest_benchmark_scores.py", "--input", str(src), "--no-backup"]
            self.assertEqual(m.main(), 0)
            cnt = sqlite3.connect(f"file:{exe}?mode=ro", uri=True)
            row = cnt.execute("SELECT COUNT(*) FROM benchmark_scores WHERE benchmark='swebench_verified'").fetchone()[0]
            best = cnt.execute(
                "SELECT COUNT(*) FROM benchmark_scores b JOIN canonical_models cm USING(canonical_model_id) "
                "WHERE b.benchmark='swebench_verified' AND b.is_best_config=1 AND cm.canonical_slug='claude-opus-5'"
            ).fetchone()[0]
            top = cnt.execute(
                "SELECT ROUND(value*100,1) FROM benchmark_scores WHERE benchmark='swebench_verified' AND is_best_config=1"
            ).fetchone()[0]
            self.assertEqual(row, 2)
            self.assertEqual(best, 1)   # single best-config per model
            self.assertEqual(top, 96.0) # picks the higher value
            cnt.close()
            if old is None: os.environ.pop("AIMI_DB", None)
            else: os.environ["AIMI_DB"] = old
        finally:
            tmp.cleanup()

    def test_value_units_roundtrip(self) -> None:
        """Elo/points/count values above 1 are stored with their unit."""
        import tempfile
        import importlib
        import ingest_benchmark_scores
        tmp = tempfile.TemporaryDirectory()
        try:
            exe = Path(tmp.name) / "aimi.db"
            conn = sqlite3.connect(exe)
            conn.executescript(SCHEMA.read_text(encoding="utf-8"))
            conn.commit(); conn.close()
            old = os.environ.get("AIMI_DB")
            os.environ["AIMI_DB"] = str(exe)
            importlib.reload(ingest_benchmark_scores)
            m = ingest_benchmark_scores
            payload = {
                "benchmark": "gdpval_aa", "benchmark_version": "v2",
                "source_url": "https://example.invalid/gdpval",
                "rows": [
                    {"canonical_slug": "claude-opus-5", "value": 1861, "value_unit": "elo", "metric": "elo", "score_date": "2026-07-24"},
                    {"canonical_slug": "gpt-5.6-sol", "value": 80, "value_unit": "points", "metric": "score", "score_date": "2026-07-09"},
                ],
            }
            src = Path(tmp.name) / "u.json"; src.write_text(__import__("json").dumps(payload))
            sys.argv = ["ingest_benchmark_scores.py", "--input", str(src), "--no-backup"]
            self.assertEqual(m.main(), 0)
            cnt = sqlite3.connect(f"file:{exe}?mode=ro", uri=True)
            elo = cnt.execute("SELECT value, value_unit FROM benchmark_scores WHERE metric='elo'").fetchone()
            pts = cnt.execute("SELECT value, value_unit FROM benchmark_scores WHERE metric='score'").fetchone()
            self.assertEqual(elo, (1861.0, "elo"))
            self.assertEqual(pts, (80.0, "points"))
            cnt.close()
            if old is None: os.environ.pop("AIMI_DB", None)
            else: os.environ["AIMI_DB"] = old
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
