#!/usr/bin/env python3
"""Record approved GPT-5.6 context semantics without conflating route limits.

The OpenRouter official models capture reports 1,050,000 tokens for the GPT-5.6
routes. The catalogue presents that family-level advertised value as 1M while
retaining the exact 1,050,000 provider-route values already stored. Codex CLI's
local models cache separately reports a 272,000-token effective context cap.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
EVIDENCE = ROOT / "evidence" / "local" / "codex-gpt56-context-2026-08-04.json"
BACKUP_DIR = ROOT / "backups"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add_claim(conn, subject_type, subject_key, field_name, value, source_id, capture_id, quote, notes):
    conn.execute(
        """INSERT OR IGNORE INTO evidence_claims(
          subject_type,subject_key,field_name,value_json,value_type,
          evidence_source_id,supporting_quote,observed_at,confidence,
          verification_method,source_priority,notes,evidence_capture_id
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            subject_type,
            subject_key,
            field_name,
            json.dumps(value, separators=(",", ":")),
            type(value).__name__,
            source_id,
            quote,
            NOW,
            "corroborated" if source_id == 11 else "verified",
            "official provider endpoint" if source_id == 11 else "local harness observation",
            3 if source_id == 11 else 5,
            notes,
            capture_id,
        ),
    )


def main():
    BACKUP_DIR.mkdir(exist_ok=True)
    backup_path = BACKUP_DIR / f"aimi-pre-gpt56-context-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.db"
    source_hash = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys=ON")
    backup = sqlite3.connect(backup_path)
    with backup:
        conn.backup(backup)
    backup.close()

    try:
        conn.execute("BEGIN")

        openrouter_source = conn.execute(
            "SELECT evidence_source_id FROM evidence_sources WHERE url=?",
            ("https://openrouter.ai/api/v1/models",),
        ).fetchone()
        if not openrouter_source:
            raise RuntimeError("OpenRouter evidence source is missing")
        openrouter_source_id = openrouter_source[0]
        openrouter_capture = conn.execute(
            """SELECT evidence_capture_id FROM evidence_captures
               WHERE evidence_source_id=? ORDER BY datetime(retrieved_at) DESC LIMIT 1""",
            (openrouter_source_id,),
        ).fetchone()
        if not openrouter_capture:
            raise RuntimeError("OpenRouter evidence capture is missing")
        openrouter_capture_id = openrouter_capture[0]

        openrouter_quote = (
            "OpenRouter's official models endpoint reports context_length=1,050,000 "
            "and max_completion_tokens=128,000 for GPT-5.6 routes."
        )
        for slug in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
            add_claim(
                conn,
                "canonical_model",
                slug,
                "context_window_tokens",
                1_000_000,
                openrouter_source_id,
                openrouter_capture_id,
                openrouter_quote,
                "Approved family-level advertised representation: 1M. Exact OpenRouter route value remains 1,050,000 in provider_models_v2.",
            )
            conn.execute(
                "UPDATE canonical_models SET updated_at=? WHERE canonical_slug=?",
                (NOW, slug),
            )

        local_source_url = "file:///Users/TH33_ORACL3/.codex/models_cache.json"
        conn.execute(
            """INSERT OR IGNORE INTO evidence_sources(
              url,source_type,publisher,title,official,primary_source,retrieved_at,
              content_sha256,archived_path,verification_status,trust_priority,notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                local_source_url,
                "local_config",
                "Codex CLI",
                "GPT-5.6 local context observation",
                1,
                1,
                NOW,
                source_hash,
                str(EVIDENCE.relative_to(ROOT)),
                "verified",
                5,
                "Sanitized local observation; does not describe the provider maximum.",
            ),
        )
        local_source_id = conn.execute(
            "SELECT evidence_source_id FROM evidence_sources WHERE url=?",
            (local_source_url,),
        ).fetchone()[0]
        conn.execute(
            """INSERT OR IGNORE INTO evidence_captures(
              evidence_source_id,retrieved_at,content_sha256,archived_path,
              extraction_method,extractor_version,immutable,notes
            ) VALUES(?,?,?,?,?,?,1,?)""",
            (
                local_source_id,
                NOW,
                source_hash,
                str(EVIDENCE.relative_to(ROOT)),
                "sanitized_local_snapshot",
                "aimi/1.2.0",
                "Immutable sanitized capture of the local Codex model cache fields used for this claim.",
            ),
        )
        local_capture_id = conn.execute(
            "SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?",
            (local_source_id, source_hash),
        ).fetchone()[0]

        local_quote = "Codex CLI models_cache.json reports context_window=272000 for this GPT-5.6 model."
        for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
            add_claim(
                conn,
                "provider_model",
                f"openai-codex/{model}",
                "local_effective_context_window_tokens",
                272_000,
                local_source_id,
                local_capture_id,
                local_quote,
                "Codex CLI effective local cap; keep separate from provider/model advertised context.",
            )
            rows = conn.execute(
                """SELECT a.harness_available_model_entry_id,a.metadata_json
                   FROM harness_available_model_entries a
                   JOIN harness_installations i USING(installation_id)
                   WHERE i.harness_id='codex-cli' AND a.provider_name='openai-codex'
                     AND a.model_identifier=?""",
                (model,),
            ).fetchall()
            for entry_id, metadata_json in rows:
                metadata = json.loads(metadata_json or "{}")
                metadata.update(
                    {
                        "context_window_tokens": 272_000,
                        "observation_scope": "Codex CLI local effective limit; not provider maximum",
                    }
                )
                conn.execute(
                    "UPDATE harness_available_model_entries SET metadata_json=?,last_observed_at=? WHERE harness_available_model_entry_id=?",
                    (json.dumps(metadata, sort_keys=True), NOW, entry_id),
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(json.dumps({"backup": str(backup_path), "openrouter_context_claim": 1_000_000, "codex_local_effective_context": 272_000}, indent=2))


if __name__ == "__main__":
    main()
