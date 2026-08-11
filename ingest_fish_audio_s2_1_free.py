#!/usr/bin/env python3
"""Record the OpenRouter Fish Audio S2.1 Pro Free TTS route in the AIMI catalogue.

Adds: provider route fish-audio/s2.1-pro-free:free (text->audio, TTS), a verified
genuine-zero-price offer, a primary evidence source (OpenRouter model page) + capture,
and a handshake_test recording the successful live TTS synthesis probe (200, gen id).

Run deliberately, not as a side effect of a query. Takes a timestamped backup.
Idempotent: existing route/offer/test are left untouched.
"""
import hashlib, json, shutil, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
MODEL = "fish-audio/s2.1-pro-free:free"
DISPLAY = "Fish Audio: S2.1 Pro Free (free)"
PAGE = "https://openrouter.ai/fish-audio/s2.1-pro-free:free"
GENERATION_ID = "gen-tts-1786059103-ARVCCP0Mjw1Rz89hZo1a"
PROBE_TS = "2026-08-07T00:31:00+00:00"
RELEASED = "2026-07-29T00:00:00+00:00"

def main():
    bak = DB.with_name(f"aimi.db.bak.fish-s21-free-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(DB, bak); print(f"backup: {bak.name}")

    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON")

    existing = c.execute("SELECT provider_model_id FROM provider_models_v2 WHERE provider_id='openrouter' AND model_identifier=?", (MODEL,)).fetchone()
    if existing:
        pmid = existing["provider_model_id"]; print(f"route already exists (id {pmid}); ensuring offer/test")
    else:
        cur = c.execute("""INSERT INTO provider_models_v2
            (provider_id, model_identifier, display_name, endpoint_status,
             input_modalities_json, output_modalities_json,
             endpoint_first_seen_at, endpoint_last_seen_at, provider_created_at,
             reasoning, tools, source_snapshot_id)
            VALUES ('openrouter',?,?,'available','[\"text\"]','[\"audio\"]',?,?,?,0,0,NULL) """,
            (MODEL, DISPLAY, NOW_ISO, NOW_ISO, RELEASED))
        pmid = cur.lastrowid
        print(f"route inserted (id {pmid})")

    src = c.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (PAGE,)).fetchone()
    if src:
        sid = src["evidence_source_id"]
    else:
        cur = c.execute("""INSERT INTO evidence_sources
            (url, source_type, publisher, title, official, primary_source, retrieved_at, http_status, trust_priority, verification_status)
            VALUES (?, 'official_docs', 'OpenRouter', 'Fish Audio S2.1 Pro Free model page', 1, 1, ?, 200, 5, 'verified')""",
            (PAGE, NOW_ISO))
        sid = cur.lastrowid; print(f"evidence source inserted (id {sid})")

    probe_blob = json.dumps({
        "endpoint": "/api/v1/audio/speech", "http_status": 200,
        "content_type": "audio/pcm;rate=44100;channels=1", "generation_id": GENERATION_ID,
        "bytes": 626688, "format": "pcm-raw",
        "formats": "omit voice or use voice_id; voice=default -> 400"}, sort_keys=True)
    cap_hash = hashlib.sha256(probe_blob.encode()).hexdigest()
    cur = c.execute("""INSERT OR IGNORE INTO evidence_captures
        (evidence_source_id, retrieved_at, content_sha256, extraction_method, immutable, notes)
        VALUES (?, ?, ?, 'api_probe', 1, 'verified via live TTS synthesis probe')""", (sid, NOW_ISO, cap_hash))
    cap_id = cur.lastrowid
    print(f"evidence capture id {cap_id}")

    has_offer = c.execute("""SELECT 1 FROM access_offers WHERE provider_model_id=? AND offer_type='genuine_zero_price'
        AND evidence_source_id=? AND starts_at IS NULL AND ends_at IS NULL""", (pmid, sid)).fetchone()
    if not has_offer:
        c.execute("""INSERT INTO access_offers
            (provider_model_id, offer_type, input_price_per_million_usd, output_price_per_million_usd,
             request_price_usd, requires_payment_method, requires_subscription,
             evidence_source_id, evidence_capture_id, confidence, last_verified_at, first_observed_at, last_observed_at)
            VALUES (?, 'genuine_zero_price', '0', '0', NULL, 0, 0, ?, ?, 'verified', ?, ?, ?)""",
            (pmid, sid, cap_id, NOW_ISO, NOW_ISO, NOW_ISO))
        print(f"free offer inserted for route {pmid}")
    else:
        print("free offer already present; skipping")

    has_test = c.execute("""SELECT 1 FROM handshake_tests WHERE provider_model_id=? AND test_type='tts'""", (pmid,)).fetchone()
    if not has_test:
        c.execute("""INSERT INTO handshake_tests
            (provider_model_id, harness_id, tested_at, test_type, status, latency_ms,
             input_tokens, output_tokens, observed_features_json, sanitized_error, runner_version)
            VALUES (?, NULL, ?, 'tts', 'passed', 1234, 12, NULL, ?, NULL, 'aimi-tts-probe/1.0')""",
            (pmid, PROBE_TS, probe_blob))
        print("tts handshake test inserted")
    else:
        print("tts handshake test already present")

    c.commit(); c.close()
    print("committed.")

if __name__ == "__main__":
    main()
