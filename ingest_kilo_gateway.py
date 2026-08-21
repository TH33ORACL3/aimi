#!/usr/bin/env python3
"""Deliberately wire the Kilo AI Gateway provider and its verified free model routes into AIMI.

Aubrey-approved 2026-08-17: test every gateway model that shows as free, then
catalogue the free chat routes. 14 routes verified green (HTTP 200, exact "OK",
$0 cost) and 1 orange (upstream 429) via parallel hyperfine probes. The Google
Lyria audio models list $0/$0 but bill per song (402) and are excluded.

Free routes are genuine_zero_price on the gateway itself (no subscription, no
BYOK required). This script takes a timestamped backup, records evidence, and
writes provider, routes, offers, health rows, credential inventory, and the
monitoring target.
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
EVID = ROOT / "evidence" / "kilo"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
TODAY = NOW[:10]

# Models that showed free pricing ($0/$0 or :free) in the official gateway
# /models listing and were live-probed. Lyria audio models excluded (per-song
# billing surfaced as 402, not genuinely free).
FREE_CHAT_MODELS = [
    "kilo-auto/free",
    "stepfun/step-3.7-flash:free",
    "poolside/laguna-s-2.1:free",
    "tencent/hy3:free",
    "dots-studio/dots-3-note-preview:free",
    "liquid/lfm-2.5-2.6b:free",
    "nvidia/nemotron-3.5-lightning:free",
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
    "z-ai/glm-5.2:free",
    "nvidia/nemotron-3.5-content-safety:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/free",
]

DOCS = EVID / "kilo-gateway-docs.md"
SNAPSHOT = EVID / f"kilo-gateway-models-{TODAY}.json"
TESTS = EVID / f"kilo-gateway-free-tests-{TODAY}.json"

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
    target = BACKUP_DIR / f"aimi.db.bak-kilo-{stamp}.sqlite"
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
        (sid, NOW, h, str(path), "firecrawl" if stype == "official_docs" else "curl-https", "1.0"),
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

    docs_sid, docs_cap = add_source(c, "https://kilo.ai/docs/gateway", "official_docs", "Kilo",
                                    "Kilo AI Gateway: unified OpenAI-compatible API", 1, 1, DOCS, 1)
    snap_sid, snap_cap = add_source(c, "https://api.kilo.ai/api/gateway/models", "api_endpoint", "Kilo",
                                    "Kilo AI Gateway official models listing snapshot", 1, 1, SNAPSHOT, 1)
    test_sid, test_cap = add_source(c, f"file://{TESTS}", "local_observation", "AZ Labs",
                                    "Kilo AI Gateway 17-route parallel hyperfine exact-OK test", 0, 1, TESTS, 10)

    # Provider row.
    c.execute(
        """INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,auth_env_var,auth_header,model_id_format,pricing_policy,free_definition,notes,last_verified_at)
           VALUES('kilo','Kilo AI Gateway','https://api.kilo.ai/api/gateway/models','https://api.kilo.ai/api/gateway','openai-completions','KILO_API_KEY',NULL,'{provider}/{model}', 'genuinely free routes plus credit-paid and BYOK models',
                  'Free routes return HTTP 200 with $0 cost (verified live 2026-08-17); paid models need gateway credits or a BYOK provider key.',
                  'Unified OpenAI-compatible gateway. 362 models in listing; 15 chat routes show free pricing, of which 14 verified green and 1 orange (upstream 429). Google Lyria audio models list $0/$0 but bill per song (402) and are not free.',?)""",
        (NOW,),
    )
    c.execute(
        """INSERT INTO credential_inventory(provider_id,machine_id,env_var_name,present,source_type,last_checked_at,notes)
           VALUES('kilo','macbook','KILO_API_KEY',1,'config_reference',?, 'Key lives in ~/.config/aimi/credentials.env (mode 0600); value never stored in SQLite. JWT valid to 2031-08-16.')
           ON CONFLICT(provider_id,machine_id,env_var_name) DO UPDATE SET present=1,last_checked_at=excluded.last_checked_at""",
        (NOW,),
    )

    # Models snapshot record.
    snap_json = json.loads(SNAPSHOT.read_text())
    n_models = len(snap_json.get("data", []))
    c.execute(
        """INSERT INTO model_sources(provider_id,endpoint,fetched_at,http_status,response_sha256,raw_snapshot_path,record_count,notes)
           VALUES('kilo','https://api.kilo.ai/api/gateway/models',?,200,?,?,?, 'official listing; free flags per route pricing fields')""",
        (NOW, digest(SNAPSHOT), str(SNAPSHOT), n_models),
    )
    snap_id = c.execute(
        "SELECT source_id FROM model_sources WHERE provider_id='kilo' AND endpoint='https://api.kilo.ai/api/gateway/models' ORDER BY fetched_at DESC LIMIT 1"
    ).fetchone()[0]

    listing = {m["id"]: m for m in snap_json.get("data", [])}
    tests = {r["model"]: r for r in json.loads(TESTS.read_text())["results"]}

    # Routes, offers, health.
    for mid in FREE_CHAT_MODELS:
        info = listing.get(mid, {})
        result = tests[mid]
        c.execute(
            """INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,context_window_tokens,max_output_tokens,reasoning,description,provider_metadata_json,source_snapshot_id,provider_created_at)
               VALUES('kilo',?,?, 'available',?,?,?,?,?,?,?,?, NULL)
               ON CONFLICT(provider_id,model_identifier) DO UPDATE SET display_name=excluded.display_name,endpoint_last_seen_at=excluded.endpoint_last_seen_at,context_window_tokens=excluded.context_window_tokens,provider_metadata_json=excluded.provider_metadata_json,source_snapshot_id=excluded.source_snapshot_id""",
            (
                mid,
                info.get("display_name") or info.get("name"),
                NOW, NOW,
                info.get("context_length"),
                info.get("top_provider", {}).get("max_completion_tokens"),
                info.get("architecture", {}).get("modalities") and None,
                (info.get("description") or "")[:400],
                json.dumps({"pricing": info.get("pricing"), "top_provider": info.get("top_provider")}, sort_keys=True),
                snap_id,
            ),
        )
        pmid = c.execute(
            "SELECT provider_model_id FROM provider_models_v2 WHERE provider_id='kilo' AND model_identifier=?", (mid,)
        ).fetchone()[0]

        terms = ("Kilo AI Gateway free model route; verified zero-cost live handshake 2026-08-17 "
                 "(HTTP 200, exact OK, cost 0). Upstream shared-pool rate limits may apply (orange 429 seen on z-ai/glm-5.2:free).")
        c.execute(
            """INSERT INTO access_offers(provider_model_id,offer_type,first_observed_at,last_observed_at,requires_payment_method,requires_subscription,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at)
               VALUES(?,'genuine_zero_price',?,?,0,0,?,?,?,'verified',?)
               ON CONFLICT(provider_model_id,offer_type,starts_at,evidence_source_id) DO UPDATE SET last_observed_at=excluded.last_observed_at,last_verified_at=excluded.last_verified_at""",
            (pmid, NOW, NOW, terms, docs_sid, docs_cap, NOW),
        )

        colour = result["status_colour"]
        status = "ok" if colour == "green" else "rate_limited" if colour == "orange" else "http_error"
        tested = "2026-08-17T20:10:00Z"
        attempts = 3 if mid == "z-ai/glm-5.2:free" else 1
        ok_count = 1 if status == "ok" else 0
        c.execute(
            """INSERT INTO free_model_probe_status(provider_model_id,provider_id,model_identifier,currently_free,last_tested_at,last_status,last_ok_at,last_failure_at,latency_ms,http_status,consecutive_failures,last_error_category,last_error_message,offer_type,offer_verified_at,runner_version,updated_at)
               VALUES(?, 'kilo', ?,1,?,?,?,?,?,?,?,?,?,'genuine_zero_price',?, 'kilo-gateway-hyperfine/1.0',?)
               ON CONFLICT(provider_model_id) DO UPDATE SET currently_free=1,last_tested_at=excluded.last_tested_at,last_status=excluded.last_status,
                 last_ok_at=CASE WHEN excluded.last_status='ok' THEN excluded.last_tested_at ELSE free_model_probe_status.last_ok_at END,
                 last_failure_at=CASE WHEN excluded.last_status='ok' THEN free_model_probe_status.last_failure_at ELSE excluded.last_tested_at END,
                 latency_ms=excluded.latency_ms,http_status=excluded.http_status,
                 consecutive_failures=CASE WHEN excluded.last_status='ok' THEN 0 ELSE free_model_probe_status.consecutive_failures+1 END,
                 last_error_category=excluded.last_error_category,last_error_message=excluded.last_error_message,
                 offer_type=excluded.offer_type,offer_verified_at=excluded.offer_verified_at,runner_version=excluded.runner_version,updated_at=excluded.updated_at""",
            (pmid, mid, tested, status, tested if status == "ok" else None, None if status == "ok" else tested,
             result["latency_ms"], result["http_status"], 0 if status == "ok" else 1,
             "rate_limited" if status == "rate_limited" else None,
             result["error_message"], NOW, tested),
        )
        day = tested[:10]
        c.execute(
            """INSERT INTO free_model_probe_daily(provider_model_id,test_date,first_tested_at,last_tested_at,attempts,ok_count,failure_count,last_status,min_latency_ms,max_latency_ms,total_latency_ms)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(provider_model_id,test_date) DO UPDATE SET last_tested_at=excluded.last_tested_at,attempts=free_model_probe_daily.attempts+excluded.attempts,
                 ok_count=free_model_probe_daily.ok_count+excluded.ok_count,failure_count=free_model_probe_daily.failure_count+excluded.failure_count,
                 last_status=excluded.last_status,min_latency_ms=min(free_model_probe_daily.min_latency_ms,excluded.min_latency_ms),
                 max_latency_ms=max(free_model_probe_daily.max_latency_ms,excluded.max_latency_ms),total_latency_ms=free_model_probe_daily.total_latency_ms+excluded.total_latency_ms""",
            (pmid, day, tested, tested, attempts, ok_count, attempts - ok_count, status,
             result["latency_ms"], result["latency_ms"], result["latency_ms"] or 0),
        )

    # Monitoring target so the endpoint monitor polls the authenticated listing.
    c.execute(
        """INSERT INTO monitoring_targets(provider_id,target_type,url,schedule_class,enabled,expected_format,parser_name)
           VALUES('kilo','models_endpoint','https://api.kilo.ai/api/gateway/models','frequent',1,'json','kilo')
           ON CONFLICT(target_type,url) DO UPDATE SET enabled=1""",
    )

    # Rebuild the active-free view (same definition as the NVIDIA NIM ingest) and derived health views.
    c.execute("DROP VIEW IF EXISTS currently_free_provider_models")
    c.execute(
        """CREATE VIEW currently_free_provider_models AS
           SELECT pm.*,ao.offer_type,ao.starts_at,ao.ends_at,ao.quota_json,ao.rate_limits_json,ao.last_verified_at AS offer_verified_at
           FROM provider_models_v2 pm
           JOIN access_offers ao ON ao.provider_model_id=pm.provider_model_id
           WHERE ao.offer_type IN ('genuine_zero_price','temporary_free_window','free_tier_quota')
             AND (ao.starts_at IS NULL OR datetime(ao.starts_at)<=datetime('now'))
             AND (ao.ends_at IS NULL OR datetime(ao.ends_at)>datetime('now'))
             AND pm.endpoint_status='available'"""
    )
    c.executescript((ROOT / "free_model_health.sql").read_text())
    c.execute("DELETE FROM free_model_probe_daily WHERE test_date < date('now','-30 days')")
    c.commit()

    count = c.execute("SELECT COUNT(*) FROM provider_models_v2 WHERE provider_id='kilo'").fetchone()[0]
    free_count = c.execute(
        "SELECT COUNT(*) FROM currently_free_provider_models WHERE provider_id='kilo'"
    ).fetchone()[0]
    green = c.execute(
        "SELECT COUNT(*) FROM free_model_probe_status WHERE provider_id='kilo' AND last_status='ok'"
    ).fetchone()[0]
    orange = c.execute(
        "SELECT COUNT(*) FROM free_model_probe_status WHERE provider_id='kilo' AND last_status='rate_limited'"
    ).fetchone()[0]
    c.close()
    print(json.dumps({
        "backup": str(backup_path),
        "provider": "kilo",
        "routes_ingested": count,
        "free_routes": free_count,
        "green": green,
        "orange": orange,
        "evidence_sources": ["https://kilo.ai/docs/gateway", "https://api.kilo.ai/api/gateway/models", str(TESTS)],
    }, indent=2))


if __name__ == "__main__":
    main()
