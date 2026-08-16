#!/usr/bin/env python3
"""Record DeepSWE (v1.1) benchmark scores in AIMI and backfill coverage.

Fetches the live Datacurve DeepSWE leaderboard JSON, maps every scored model
to its canonical identity, and upserts one row per (model, bench, metric,
config, score_date). The row with the highest pass@1 per model is flagged
is_best_config=1 so callers and display names can surface the single canonical
score ("highest score across effort levels").

Vendor-reported scores (models published by their maker but not on the public
table, e.g. GLM-5.3) are recorded through VENDOR_SCORES with source_type
'vendor'. Models with no recorded benchmark simply get no row - "recorded or
not" is answered by their presence here.

Idempotent. Backs up the catalogue first unless --no-backup is given.

Usage:
    python3 ingest_deepswe_scores.py                      # live fetch + upsert
    python3 ingest_deepswe_scores.py --input file.json    # offline / test
    python3 ingest_deepswe_scores.py --no-backup
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sqlite3
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("AIMI_DB", ROOT / "aimi.db")).expanduser().resolve()
LEADERBOARD_URL = "https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json"
EVIDENCE_DIR = ROOT / "evidence" / "deep-swe-v1.1"
# Explicit DeepSWE model id -> canonical_slug. Version dashes are collapsed to
# dots; the exact map avoids heuristic guesswork for ambiguous ids like gpt-5-5.
MODEL_MAP = {
    "claude-opus-5": "claude-opus-5",
    "gpt-5-6-sol": "gpt-5.6-sol",
    "claude-fable-5": "claude-fable-5",
    "gpt-5-6-terra": "gpt-5.6-terra",
    "kimi-k3": "kimi-k3",
    "grok-4-6": "grok-4.6",
    "gpt-5-6-luna": "gpt-5.6-luna",
    "gpt-5-5": "gpt-5.5",
    "gemini-3-7-flash": "gemini-3.7-flash",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "claude-opus-4-8": "claude-opus-4.8",
    "qwen3-8-max": "qwen3.8-max",
    "muse-spark-1-2": "muse-spark-1.2",
    "claude-sonnet-5": "claude-sonnet-5",
    "grok-4-5": "grok-4.5",
    "muse-spark-1-1": "muse-spark-1.1",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "gpt-5-4": "gpt-5.4",
    "gemini-3-6-flash": "gemini-3.6-flash",
    "glm-5-2": "glm-5.2",
    "gemini-3-5-flash": "gemini-3.5-flash",
    "kimi-k2-7-code": "kimi-k2.7-code",
    "claude-sonnet-4-6": "claude-sonnet-4.6",
    "gemini-3-1-pro-preview": "gemini-3.1-pro-preview",
}
# Vendor-reported scores for models absent from the public table.
# (canonical_slug, score, reasoning/config note, score_date, source_url)
VENDOR_SCORES = [
    {
        "canonical_slug": "glm-5.3",
        "value": 0.669,
        "config_text": "vendor-reported (best available mini-swe-agent configuration)",
        "reasoning_effort": None,
        "score_date": "2026-08-14",
        "source_url": "https://x.com/Zai_org/status/2088132965922476159",
        "notes": "GLM-5.3 official release: DeepSWE 46.2 -> 66.9 after post-training on 743B base.",
    },
]

NOW = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def backup(conn: sqlite3.Connection) -> str:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    target = ROOT / "backups" / f"aimi.db.bak-deepswe-{stamp}.sqlite"
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return str(target)


def fetch_live() -> bytes:
    req = urllib.request.Request(LEADERBOARD_URL, headers={"User-Agent": "aimi-benchmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def record_evidence(conn: sqlite3.Connection, raw: bytes, status: int) -> tuple[int, int]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(raw).hexdigest()
    now = NOW
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    path = EVIDENCE_DIR / f"leaderboard-live-{stamp}.json"
    path.write_bytes(raw)
    conn.execute(
        "INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,http_status,trust_priority,verification_status) "
        "VALUES(?,?,?,?,1,1,?,?,1,'verified')",
        (LEADERBOARD_URL, "official_blog", "datacurve.ai", "DeepSWE live leaderboard", now, status),
    )
    sid = conn.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (LEADERBOARD_URL,)).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version) "
        "VALUES(?,?,?,?,?,?,?)",
        (sid, now, sha, str(path), status, "deepswe_ingest", "1.0"),
    )
    cap = conn.execute(
        "SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?",
        (sid, sha),
    ).fetchone()[0]
    return sid, cap


def ingest(conn: sqlite3.Connection, payload: dict, sid: int, cap: int) -> dict:
    rows = payload.get("rows", [])
    best: dict[str, tuple[float, int]] = {}
    inserted = 0
    for row in rows:
        slug = MODEL_MAP.get(row.get("model", ""))
        if slug is None:
            continue
        cid = conn.execute(
            "SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?", (slug,)
        ).fetchone()
        if cid is None:
            conn.execute(
                "INSERT OR IGNORE INTO canonical_models(canonical_slug, developer, canonical_name, weights_status, lifecycle_status) "
                "VALUES(?,?,?, 'unknown','active')",
                (slug, slug.split("-")[0], slug),
            )
        cid = conn.execute(
            "SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?", (slug,)
        ).fetchone()
        if cid is None:
            continue
        cid = cid[0]
        val = row.get("pass_at_1")
        if val is None:
            continue
        metric = "pass@1"
        effort = row.get("reasoning_effort")
        cfg = row.get("config") or f"mini_swe_agent_{slug}_{effort or 'default'}"
        if slug not in best or val > best[slug][0]:
            best[slug] = (val, cid)
        conn.execute(
            "INSERT INTO benchmark_scores(canonical_model_id, benchmark, benchmark_version, metric, value, value_unit, config_text, reasoning_effort, agent_harness, source_type, score_date, n_tasks, n_attempted, n_tasks_passed_any, n_runs, ci_lo, ci_hi, confidence, source_url, evidence_source_id, evidence_capture_id, recorded_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(canonical_model_id, benchmark, benchmark_version, metric, value_unit, config_text, score_date, source_type) DO UPDATE SET value=excluded.value, recorded_at=excluded.recorded_at",
            (
                cid,
                "deepswe",
                payload.get("scope", {}).get("version", "1.1") if isinstance(payload.get("scope"), dict) else "1.1",
                "pass@1",
                val,
                "ratio",
                cfg,
                effort,
                row.get("harness") or "mini-swe-agent",
                "leaderboard",
                payload.get("generated_at") or NOW,
                row.get("n_tasks"),
                row.get("n_attempted"),
                row.get("n_tasks_passed_any"),
                row.get("n_runs"),
                row.get("ci_lo"),
                row.get("ci_hi"),
                "corroborated",
                LEADERBOARD_URL,
                sid,
                cap,
                NOW,
            ),
        )
        inserted += conn.total_changes
    # Mark the highest-value row per model as the canonical "best config".
    conn.execute("UPDATE benchmark_scores SET is_best_config=0 WHERE benchmark='deepswe' AND benchmark_version='1.1' AND metric='pass@1'")
    for slug, (_, cid) in best.items():
        conn.execute(
            "UPDATE benchmark_scores SET is_best_config=1 WHERE benchmark_score_id=("
            "SELECT benchmark_score_id FROM benchmark_scores WHERE canonical_model_id=? AND benchmark='deepswe' AND benchmark_version='1.1' AND metric='pass@1' ORDER BY value DESC, benchmark_score_id DESC LIMIT 1)",
            (cid,),
        )
    return {"leaderboard_rows": len(rows), "mapped_models": len(best)}


def ingest_vendor(conn: sqlite3.Connection) -> int:
    n = 0
    for vs in VENDOR_SCORES:
        cid = conn.execute(
            "SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?", (vs["canonical_slug"],)
        ).fetchone()
        if cid is None:
            cur = conn.execute(
                "INSERT INTO canonical_models(canonical_slug, developer, canonical_name, weights_status, lifecycle_status) "
                "VALUES(?,?,?, 'unknown','active') ON CONFLICT(canonical_slug) DO NOTHING",
                (vs["canonical_slug"], vs["canonical_slug"].split("-")[0], vs["canonical_slug"]),
            )
            cid = conn.execute(
                "SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?", (vs["canonical_slug"],)
            ).fetchone()[0]
        else:
            cid = cid[0]
        conn.execute(
            "INSERT INTO benchmark_scores(canonical_model_id, benchmark, benchmark_version, metric, value, value_unit, config_text, reasoning_effort, source_type, score_date, confidence, source_url, recorded_at, notes) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(canonical_model_id, benchmark, benchmark_version, metric, value_unit, config_text, score_date, source_type) DO UPDATE SET value=excluded.value, recorded_at=excluded.recorded_at",
            (
                cid, "deepswe", "1.1", "pass@1", vs["value"], "ratio", vs["config_text"],
                vs["reasoning_effort"], "vendor", vs["score_date"], "single_source",
                vs["source_url"], NOW, vs["notes"],
            ),
        )
        conn.execute(
            "UPDATE benchmark_scores SET is_best_config=1 WHERE benchmark_score_id=("
            "SELECT benchmark_score_id FROM benchmark_scores WHERE canonical_model_id=? AND benchmark='deepswe' AND benchmark_version='1.1' AND metric='pass@1' ORDER BY value DESC, benchmark_score_id DESC LIMIT 1)",
            (cid,),
        )
        n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description="Record DeepSWE v1.1 benchmark scores in AIMI")
    parser.add_argument("--input", type=Path, help="Read a leaderboard JSON file instead of fetching live")
    parser.add_argument("--no-backup", action="store_true", help="Skip the pre-write catalogue backup")
    args = parser.parse_args()

    if args.input is not None:
        raw = args.input.read_bytes()
    else:
        raw = fetch_live()

    payload = json.loads(raw)
    sid, cap = None, None
    conn = sqlite3.connect(f"file:{DB}?mode=rw", uri=True, timeout=30)
    backup_path = None
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        if not args.no_backup:
            backup_path = backup(conn)
        sid, cap = record_evidence(conn, raw, 200)
        summary = ingest(conn, payload, sid, cap)
        summary["vendor_scores"] = ingest_vendor(conn)
        conn.commit()
    finally:
        conn.close()

    result = {"backup": backup_path, "evidence_source_id": sid, "evidence_capture_id": cap, **summary}
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
