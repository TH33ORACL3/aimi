#!/usr/bin/env python3
"""Record the Fish Audio public voice library in the AIMI catalogue.

Adds a provider_voices table (new entity type: TTS voices for a provider route),
seeded from the public Fish Audio model API (https://api.fish.audio/model,
paginated, ~1000 voices visible without auth), linked to the already-recorded
fish-audio/s2.1-pro-free:free route (provider_model_id 1096526).

Flags:
- notable=1 for famous/well-known public voices (celebrities, characters,
  announcers) curated from title/description review.
- verified=1 for voices live-tested through the OpenRouter /audio/speech
  endpoint (200 + distinct audio) on 2026-08-07.
- The OpenRouter default base speaker is recorded as voice_id 'alloy' so the
  Hermes default is representable.

Run deliberately, not as a side effect of a query. Takes a timestamped backup.
Idempotent: re-running updates title/description/tags and refreshes observed
timestamps; verified/notable flags are only ever upgraded, never cleared.
"""
import json, shutil, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
NOW_ISO = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
MERGE = ROOT / "evidence" / "fish_audio_voices" / "merged_2026-08-07.json"
ROUTE_ID = 1096526  # fish-audio/s2.1-pro-free:free
PAGE = "https://api.fish.audio/model"

# Voices live-verified through OpenRouter /audio/speech on 2026-08-07 (200 + distinct audio)
VERIFIED = {
    "alloy",                                    # default base speaker (Hermes default)
    "0327fdb5da9e4fd782899a8058c8ae2b",         # Narrator
    "933563129e564b19a115bedd57b7406a",         # Sarah
    "802e3bc2b27e49c2995d23ef70e6ac89",         # Energetic Male
    "03397b4c4be74759b72533b663fbd001",         # Elon Musk(Noise reduction)
    "2a1036d645634680b3cc69aeeb60375b",         # Спокойный женский голос
    "98655a12fa944e26b274c535e5e03842",         # E-girl
    "d8a1340984ee4b63ad1ffae27a6a4339",         # ELITE
}

# Famous/notable public voices, matched by title fragment (case-insensitive)
NOTABLE_PATTERNS = (
    "musk", "trump", "obama", "morgan freeman", "kendrick lamar", "taylor swift",
    "ronaldo", "messi", "arthur morgan", "dexter morgan", "morpheus",
    "rick sanchez", "morty smith", "goku", "naruto", "spongebob",
    "mickey mouse", "sonic the hedgehog", "mortal kombat", "smash bros",
    "cartoon network", "god voice", "real joker", "jesus narrador", "shrek",
)


def notable(title: str) -> bool:
    t = title.lower()
    return any(p in t for p in NOTABLE_PATTERNS)


def main():
    bak = DB.with_name(f"aimi.db.bak.fish-voices-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(DB, bak)
    print(f"backup: {bak.name}")

    items = json.loads(MERGE.read_text())
    print(f"dataset: {len(items)} voices from {MERGE.name}")

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")

    c.execute("""CREATE TABLE IF NOT EXISTS provider_voices (
        voice_id TEXT PRIMARY KEY,
        provider_model_id INTEGER NOT NULL REFERENCES provider_models_v2(provider_model_id),
        title TEXT NOT NULL,
        description TEXT,
        tags_json TEXT,
        notable INTEGER NOT NULL DEFAULT 0,
        verified INTEGER NOT NULL DEFAULT 0,
        evidence_source_id INTEGER REFERENCES evidence_sources(evidence_source_id),
        first_observed_at TEXT,
        last_observed_at TEXT,
        retrieved_at TEXT
    )""")
    print("table provider_voices ensured")

    src = c.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (PAGE,)).fetchone()
    if src:
        sid = src["evidence_source_id"]
        print(f"evidence source already exists (id {sid})")
    else:
        cur = c.execute("""INSERT INTO evidence_sources
            (url, source_type, publisher, title, official, primary_source, retrieved_at, http_status, trust_priority, verification_status)
            VALUES (?, 'api_endpoint', 'Fish Audio', 'Fish Audio public voice model list', 1, 1, ?, 200, 5, 'verified')""",
            (PAGE, NOW_ISO))
        sid = cur.lastrowid
        print(f"evidence source inserted (id {sid})")

    default_row = {
        "voice_id": "alloy", "title": "Default base speaker (alloy)",
        "description": "OpenRouter default voice for fish-audio TTS; maps to the fish S2.1 base speaker. Current Hermes fallback.",
        "tags_json": json.dumps(["default", "multilingual"]),
    }

    upsert = """INSERT INTO provider_voices
        (voice_id, provider_model_id, title, description, tags_json, notable, verified,
         evidence_source_id, first_observed_at, last_observed_at, retrieved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(voice_id) DO UPDATE SET
            title=excluded.title, description=excluded.description,
            tags_json=excluded.tags_json, last_observed_at=excluded.last_observed_at,
            notable=MAX(provider_voices.notable, excluded.notable),
            verified=MAX(provider_voices.verified, excluded.verified)"""

    n_new = n_upd = 0
    for it in items:
        vid, title = it["_id"], it.get("title") or "Untitled"
        desc = it.get("description") or ""
        tags = json.dumps(it.get("tags") or [], ensure_ascii=False)
        fl = (1 if notable(title) else 0, 1 if vid in VERIFIED else 0)
        cur = c.execute(upsert, (vid, ROUTE_ID, title, desc, tags, fl[0], fl[1], sid, NOW_ISO, NOW_ISO, NOW_ISO))
        n_new += max(cur.rowcount, 0) if cur.rowcount == 1 else 0
        n_upd += 1
    # default speaker row
    cur = c.execute(upsert, (default_row["voice_id"], ROUTE_ID, default_row["title"], default_row["description"],
                             default_row["tags_json"], 1, 1, sid, NOW_ISO, NOW_ISO, NOW_ISO))

    c.commit()

    notable_count = c.execute("SELECT COUNT(*) FROM provider_voices WHERE notable=1").fetchone()[0]
    verified_count = c.execute("SELECT COUNT(*) FROM provider_voices WHERE verified=1").fetchone()[0]
    total = c.execute("SELECT COUNT(*) FROM provider_voices").fetchone()[0]
    print(f"inserted/updated {n_upd} voices + default row; total={total}, notable={notable_count}, verified={verified_count}")

    print("notable voices:")
    for r in c.execute("SELECT voice_id, title FROM provider_voices WHERE notable=1 ORDER BY title"):
        print(f"  {r['voice_id']}  {r['title']}")

    c.close()


if __name__ == "__main__":
    main()
