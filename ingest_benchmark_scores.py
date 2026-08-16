#!/usr/bin/env python3
"""Record scores for any benchmark in AIMI's benchmark_scores table.

Generic ingestor for benchmarks other than DeepSWE (which has its own live
fetch). Reads a structured JSON of benchmark scores and upserts one row per
(canonical model, benchmark, metric, config, score_date). The highest value per
model/benchmark is flagged is_best_config=1 (the "highest score across effort
levels" rule, matching C:1).

The input is an explicit, sourced score table so frontier leaderboards that
offer no clean JSON API (SWE-bench Verified, Terminal-Bench, LiveCodeBench,
Aider Polyglot, tau-bench, ...) are all ingested the same way going forward.

Idempotent. Backs up the catalogue first unless --no-backup is given.

Input JSON shape:
{
  "source_url": "https://...",          # primary leaderboard page
  "source_type": "leaderboard",         # default for rows that omit it
  "rows": [
    {"canonical_slug":"claude-opus-5","benchmark":"swebench_verified",
     "benchmark_version":"2026-08","value":0.96,"metric":"pass_rate",
     "config_text":"SWE-bench Verified","reasoning_effort":null,
     "confidence":"corroborated","score_date":"2026-08-14","notes":""},
    ...
  ]
}

Usage:
    python3 ingest_benchmark_scores.py --input scores.json --no-backup
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("AIMI_DB", ROOT / "aimi.db")).expanduser().resolve()


def backup() -> str:
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    target = ROOT / "backups" / f"aimi.db.bak-benchmark-{stamp}.sqlite"
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return str(target)


def record_evidence(conn: sqlite3.Connection, raw: bytes, source_url: str) -> tuple[int, int]:
    sha = hashlib.sha256(raw).hexdigest()
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    out = ROOT / "evidence" / "benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    path = out / f"benchmark-scores-{stamp}.json"
    path.write_bytes(raw)
    conn.execute(
        "INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,http_status,trust_priority,verification_status) "
        "VALUES(?,?,?,?,1,1,?,?,50,'captured')",
        (source_url, "third_party", None, "Benchmark score table", now, 200),
    )
    sid = conn.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (source_url,)).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version) "
        "VALUES(?,?,?,?,?,?,?)",
        (sid, now, sha, str(path), 200, "benchmark_ingest", "1.0"),
    )
    cap = conn.execute(
        "SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?",
        (sid, sha),
    ).fetchone()[0]
    return sid, cap


def canonical_id(conn: sqlite3.Connection, slug: str) -> int:
    row = conn.execute("SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?", (slug,)).fetchone()
    if row:
        return row[0]
    conn.execute(
        "INSERT OR IGNORE INTO canonical_models(canonical_slug, developer, canonical_name, weights_status, lifecycle_status) "
        "VALUES(?,?,?, 'unknown','active')",
        (slug, slug.split("-")[0], slug),
    )
    return conn.execute("SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?", (slug,)).fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Record scores for any benchmark in AIMI")
    parser.add_argument("--input", type=Path, required=True, help="Structured JSON of benchmark scores")
    parser.add_argument("--no-backup", action="store_true", help="Skip the pre-write catalogue backup")
    args = parser.parse_args()

    payload = json.loads(args.input.read_bytes())
    source_url = payload.get("source_url") or "https://benchlm.ai/"
    default_type = payload.get("source_type") or "leaderboard"

    conn = sqlite3.connect(f"file:{DB}?mode=rw", uri=True, timeout=30)
    backup_path = None
    sid, cap = None, None
    inserted = 0
    keys = []
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        if not args.no_backup:
            backup_path = backup()
        sid, cap = record_evidence(conn, args.input.read_bytes(), source_url)
        for row in payload.get("rows", []):
            bench = row.get("benchmark") or payload.get("benchmark") or "benchmark"
            version = row.get("benchmark_version") or payload.get("benchmark_version") or "2026"
            metric = row.get("metric") or "pass@1"
            unit = row.get("value_unit") or "ratio"
            stype = row.get("source_type") or default_type
            cid = canonical_id(conn, row["canonical_slug"])
            conn.execute(
                "INSERT INTO benchmark_scores(canonical_model_id, benchmark, benchmark_version, metric, value, value_unit, config_text, reasoning_effort, agent_harness, source_type, score_date, confidence, source_url, evidence_source_id, evidence_capture_id, recorded_at, notes) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(canonical_model_id, benchmark, benchmark_version, metric, value_unit, config_text, score_date, source_type) "
                "DO UPDATE SET value=excluded.value, confidence=excluded.confidence, evidence_capture_id=excluded.evidence_capture_id, source_url=excluded.source_url, recorded_at=excluded.recorded_at",
                (
                    cid, bench, version, metric, row["value"], unit,
                    row.get("config_text"), row.get("reasoning_effort"),
                    row.get("agent_harness"), stype,
                    row.get("score_date"), row.get("confidence") or "corroborated",
                    source_url, sid, cap,
                    dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
                    row.get("notes"),
                ),
            )
            keys.append((cid, bench, version, metric, unit))
            inserted += 1
        # Mark the single highest value per (model, benchmark, metric, unit) as best.
        for (cid, bench, version, metric, unit) in set(keys):
            conn.execute(
                "UPDATE benchmark_scores SET is_best_config=0 WHERE canonical_model_id=? AND benchmark=? AND benchmark_version=? AND metric=? AND value_unit=?",
                (cid, bench, version, metric, unit),
            )
            conn.execute(
                "UPDATE benchmark_scores SET is_best_config=1 WHERE benchmark_score_id=("
                "SELECT benchmark_score_id FROM benchmark_scores WHERE canonical_model_id=? AND benchmark=? AND benchmark_version=? AND metric=? AND value_unit=? "
                "ORDER BY value DESC, benchmark_score_id DESC LIMIT 1)",
                (cid, bench, version, metric, unit),
            )
        conn.commit()
    finally:
        conn.close()

    print(json.dumps({"backup": backup_path, "evidence_source_id": sid, "evidence_capture_id": cap,
                      "rows_processed": inserted, "source_url": source_url}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
