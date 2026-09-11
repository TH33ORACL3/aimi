#!/usr/bin/env python3
"""Deliberately wire the Merge Gateway provider and ONE model route into AIMI.

Aubrey-approved 2026-08-27: add provider `merge-gateway` and only the route
`deepseek/deepseek-v4-flash`; test only that model; register it in Pi on the
MacBook, then replicate key + config to AJ and Pal and fully test there.

Evidence: official docs (docs.merge.dev/merge-gateway), authenticated /v1/models
snapshot (276 models, 24 providers, HTTP 200), and one green smoke test
(HTTP 200, exact "OK", ~$0.00000217) via /v1/chat/completions.

Access semantics: the mg_ key comes from the Merge Gateway dashboard developer
account (free-tier budget with 402 when exhausted, per documented error
semantics). Not verified zero price => offer classified `paid`, tested with
--allow-paid. Only this single route is ingested; the other 275 models are NOT
added, per explicit instruction.

This script takes a timestamped backup, records evidence, and writes provider,
route, access offer, credential inventory, model_sources and the monitoring
target. It does not touch free-only views (no free route here).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("AIMI_DB", ROOT / "aimi.db")).expanduser().resolve()
EVID = ROOT / "evidence" / "merge"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
TODAY = NOW[:10]

DOCS = EVID / "merge-gateway-docs.md"
SNAPSHOT = EVID / f"merge-gateway-models-{TODAY}.json"
TESTS = EVID / f"merge-gateway-smoke-tests-{TODAY}.json"

PROVIDER_ID = "merge-gateway"
MODEL_ID = "deepseek/deepseek-v4-flash"  # the ONLY model added, per instruction

BACKUP_DIR = ROOT / "backups"
BACKUP_INVENTORY = Path.home() / ".agents" / "backup-inventory.md"


def backup_policy() -> dict:
    text = BACKUP_INVENTORY.read_text(encoding="utf-8")
    match = re.search(r"## CONFIG.*?```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        raise RuntimeError(f"Cannot parse backup inventory: {BACKUP_INVENTORY}")
    config = json.loads(match.group(1))
    for item in config.get("locations", []):
        if Path(item["path"]).expanduser() == BACKUP_DIR:
            return item
    raise RuntimeError(f"AIMI backup directory is not registered: {BACKUP_DIR}")


def create_backup() -> Path:
    policy = backup_policy()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"aimi.db.bak-merge-gateway-{stamp}.sqlite"
    source = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        destination.execute("PRAGMA journal_mode=DELETE")
    finally:
        destination.close()
        source.close()
    Path(f"{target}-wal").unlink(missing_ok=True)
    Path(f"{target}-shm").unlink(missing_ok=True)
    os.chmod(target, 0o600)
    check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("AIMI backup integrity check failed")
    finally:
        check.close()
    backups = sorted(BACKUP_DIR.glob(policy["pattern"]), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[int(policy["keep"]):]:
        old.unlink()
    return target


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_source(c: sqlite3.Connection, url: str, stype: str, publisher: str, title: str,
               official: int, primary: int, path: Path, priority: int) -> tuple[int, int]:
    h = digest(path)
    c.execute(
        """INSERT INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status)
           VALUES(?,?,?,?,?,?,?,?,?,200,?,'verified')
           ON CONFLICT(url) DO UPDATE SET retrieved_at=excluded.retrieved_at,content_sha256=excluded.content_sha256,archived_path=excluded.archived_path,verification_status='verified'""",
        (url, stype, publisher, title, official, primary, NOW, h, str(path), priority),
    )
    sid = c.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (url,)).fetchone()[0]
    c.execute(
        """INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version)
           VALUES(?,?,?,?,200,?,?)""",
        (sid, NOW, h, str(path), "curl-https", "1.0"),
    )
    cap = c.execute(
        "SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?",
        (sid, h),
    ).fetchone()[0]
    return sid, cap


def main() -> None:
    backup_path = create_backup()
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("BEGIN")

    docs_sid, docs_cap = add_source(c, "https://docs.merge.dev/merge-gateway", "official_docs", "Merge",
                                    "Merge Gateway: get started — unified API for every LLM", 1, 1, DOCS, 1)
    snap_sid, snap_cap = add_source(c, "https://api-gateway.merge.dev/v1/models", "api_endpoint", "Merge",
                                    "Merge Gateway official models listing snapshot (276 models, 24 providers)", 1, 1, SNAPSHOT, 1)
    test_sid, test_cap = add_source(c, f"file://{TESTS}", "local_observation", "AZ Labs",
                                    "Merge Gateway single-route smoke test (deepseek/deepseek-v4-flash), green HTTP 200 exact OK", 0, 1, TESTS, 10)

    # Provider row.
    c.execute(
        """INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,auth_env_var,auth_header,model_id_format,pricing_policy,free_definition,notes,last_verified_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (PROVIDER_ID, 'Merge Gateway', 'https://api-gateway.merge.dev/v1/models',
         'https://api-gateway.merge.dev/v1', 'openai-completions', 'MERGE_API_KEY', None,
         '{provider}/{model}',
         'Developer API key with free-tier budget; 402 when budget exhausted; usage billed per token',
         'No verified zero-price offer on record; mg_ developer key carries a free-tier budget per documented 402 semantics but this is not verified zero-price.',
         'Unified multi-LLM gateway. 276 models in authenticated listing across 24 providers (openai, qwen, google, zai, mistral, moonshot, deepseek, anthropic, minimax, meta, xai, nvidia, bytedance, amazon, cohere, morph, xiaomimimo, writer, sakana, ai21, thinkingmachines, bland, arcee-ai, alibaba). Only deepseek/deepseek-v4-flash ingested (explicit instruction). Model IDs are provider-prefixed. Supports /v1/chat/completions (verified) and /v1/responses (SDK default).', NOW),
    )
    c.execute(
        """INSERT INTO credential_inventory(provider_id,machine_id,env_var_name,present,source_type,last_checked_at,notes)
           VALUES(?,?,?,1,'config_reference',?, 'MERGE_API_KEY exported in ~/.zshrc (MacBook); value never stored in SQLite.')
           ON CONFLICT(provider_id,machine_id,env_var_name) DO UPDATE SET present=1,last_checked_at=excluded.last_checked_at""",
        (PROVIDER_ID, 'macbook', 'MERGE_API_KEY', NOW),
    )

    # Models snapshot record.
    snap_json = json.loads(SNAPSHOT.read_text())
    n_models = len(snap_json)
    c.execute(
        """INSERT INTO model_sources(provider_id,endpoint,fetched_at,http_status,response_sha256,raw_snapshot_path,record_count,notes)
           VALUES(?,?,?,200,?,?,?, 'authenticated listing; 5 cursor pages; only one model ingested per instruction')""",
        (PROVIDER_ID, 'https://api-gateway.merge.dev/v1/models', NOW, digest(SNAPSHOT), str(SNAPSHOT), n_models),
    )
    snap_id = c.execute(
        "SELECT source_id FROM model_sources WHERE provider_id=? AND endpoint='https://api-gateway.merge.dev/v1/models' ORDER BY fetched_at DESC LIMIT 1",
        (PROVIDER_ID,),
    ).fetchone()[0]

    info = next((m for m in snap_json if m.get("model") == MODEL_ID), None)
    if not info:
        raise SystemExit(f"{MODEL_ID} not found in snapshot")
    vendor = info.get("vendors", {}).get("deepseek", {})
    caps = vendor.get("capabilities", {})
    pricing = vendor.get("pricing", {})
    ctx = vendor.get("context_window")
    max_out = vendor.get("max_output_tokens")

    # The single route.
    c.execute(
        """INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,context_window_tokens,max_output_tokens,reasoning,tools,function_calling,structured_outputs,streaming,input_modalities_json,description,provider_metadata_json,source_snapshot_id,provider_created_at)
           VALUES(?,?,?, 'available',?,?,?,?,?,?,?,?,?,?,?,?,?, ?)""",
        (
            PROVIDER_ID, MODEL_ID, info.get("display_name") or MODEL_ID,
            NOW, NOW, ctx, max_out,
            1 if caps.get("supports_reasoning") else 0,
            1 if caps.get("supports_tool_calling") else 0,
            1 if caps.get("supports_tool_calling") else 0,
            1 if caps.get("supports_structured_outputs") else 0,
            1 if caps.get("streaming") else 0,
            json.dumps(caps.get("input", ["text"])),
            (info.get("display_name") or "")[:400],
            json.dumps({
                "vendors": {k: {"launch_date": v.get("launch_date"), "context_window": v.get("context_window"),
                                "max_output_tokens": v.get("max_output_tokens"), "pricing": v.get("pricing")}
                            for k, v in info.get("vendors", {}).items()},
                "capabilities": caps, "aliases": info.get("aliases"),
            }, sort_keys=True),
            snap_id,
            vendor.get("launch_date"),
        ),
    )
    pmid = c.execute(
        "SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?",
        (PROVIDER_ID, MODEL_ID),
    ).fetchone()[0]

    terms = ("Merge Gateway key-based developer access; pay-per-token pricing (input $0.22/M, output $0.66/M at deepseek "
             "vendor rates; peak windows 2x); free-tier budget per docs with 402 when exhausted; not verified zero price.")
    c.execute(
        """INSERT INTO access_offers(provider_model_id,offer_type,first_observed_at,last_observed_at,requires_payment_method,requires_subscription,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at)
           VALUES(?,'paid',?,?,0,0,?,?,?,'verified',?)
           ON CONFLICT(provider_model_id,offer_type,starts_at,evidence_source_id) DO UPDATE SET last_observed_at=excluded.last_observed_at,last_verified_at=excluded.last_verified_at""",
        (pmid, NOW, NOW, terms, docs_sid, docs_cap, NOW),
    )

    # Monitoring target so a future monitor pass can poll the authenticated listing.
    c.execute(
        """INSERT INTO monitoring_targets(provider_id,target_type,url,schedule_class,enabled,expected_format,parser_name)
           VALUES(?,?,?,'frequent',1,'json','merge-gateway')
           ON CONFLICT(target_type,url) DO UPDATE SET enabled=1""",
        (PROVIDER_ID, 'models_endpoint', 'https://api-gateway.merge.dev/v1/models'),
    )

    c.commit()
    c.close()
    print(json.dumps({
        "backup": str(backup_path),
        "provider": PROVIDER_ID,
        "models_ingested": [MODEL_ID],
        "other_models_skipped": n_models - 1,
        "evidence_sources": ["https://docs.merge.dev/merge-gateway", "https://api-gateway.merge.dev/v1/models", str(TESTS)],
    }, indent=2))


if __name__ == "__main__":
    main()