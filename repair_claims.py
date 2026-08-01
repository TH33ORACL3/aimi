#!/usr/bin/env python3
"""Give evidence claims a real immutable capture, or mark them honestly.

A claim records a fact ("this route supports reasoning"). An evidence *source*
records where it came from. An evidence *capture* is the saved copy of what that
source actually said, hashed, so the claim can be re-checked later even if the
page changes. A claim with a source but no capture cannot be re-verified.

For each claim without a capture this script either:
  - fetches the source and stores a real capture, when the source is a reachable
    URL, or
  - downgrades the claim's confidence and records why, when the source is a
    local file that no longer exists and therefore can never be captured.

It never invents evidence and never upgrades confidence.

Usage:
    python repair_claims.py            # report what it would do
    python repair_claims.py --apply
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
CAPTURES = ROOT / "evidence" / "web"
VERSION = "repair-claims/1.0"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url: str, timeout: int = 30) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "AZ-Labs-aimi-evidence/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Attach captures to claims, or mark them unverifiable")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")

    claims = connection.execute(
        """SELECT ec.claim_id, ec.subject_key, ec.field_name, ec.confidence, ec.notes,
                  ec.evidence_source_id, es.url, es.source_type
           FROM evidence_claims ec
           LEFT JOIN evidence_sources es USING(evidence_source_id)
           WHERE ec.evidence_capture_id IS NULL"""
    ).fetchall()

    if not claims:
        print("Every claim already has an immutable capture.")
        return 0

    capturable: dict[str, list[sqlite3.Row]] = {}
    unverifiable: list[sqlite3.Row] = []
    for claim in claims:
        url = claim["url"] or ""
        if url.startswith(("http://", "https://")):
            capturable.setdefault(url, []).append(claim)
        elif url.startswith("file://"):
            if Path(url[len("file://"):]).exists():
                capturable.setdefault(url, []).append(claim)
            else:
                unverifiable.append(claim)
        else:
            unverifiable.append(claim)

    print(f"claims without a capture : {len(claims)}")
    print(f"  capturable sources     : {sum(len(v) for v in capturable.values())} across {len(capturable)} url(s)")
    for url, rows in capturable.items():
        print(f"      {url}  ({len(rows)} claims)")
    print(f"  source no longer exists: {len(unverifiable)}")
    for claim in unverifiable[:3]:
        print(f"      {claim['subject_key']} / {claim['field_name']}  (currently '{claim['confidence']}')")
    if len(unverifiable) > 3:
        print(f"      ... and {len(unverifiable) - 3} more")

    if not args.apply:
        print("dry run; re-run with --apply")
        return 0

    backup = DB.with_name(f"{DB.name}.bak.claim-repair-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(DB, backup)
    print(f"Backup: {backup.name}")
    CAPTURES.mkdir(parents=True, exist_ok=True)

    captured = 0
    for url, rows in capturable.items():
        try:
            if url.startswith("file://"):
                body = Path(url[len("file://"):]).read_bytes()
                status = None
                method = "local_file"
            else:
                status, body = fetch(url)
                method = "http_fetch"
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            print(f"  could not capture {url}: {str(exc)[:120]}")
            continue

        sha = hashlib.sha256(body).hexdigest()
        name = f"{sha[:16]}-{url.rstrip('/').rsplit('/', 1)[-1][:40] or 'source'}"
        path = CAPTURES / f"{name}.capture"
        path.write_bytes(body)
        relative = str(path.relative_to(ROOT))

        source_id = rows[0]["evidence_source_id"]
        connection.execute(
            """INSERT OR IGNORE INTO evidence_captures
               (evidence_source_id, retrieved_at, content_sha256, archived_path, http_status,
                extraction_method, extractor_version, immutable, notes)
               VALUES(?,?,?,?,?,?,?,1,?)""",
            (source_id, now(), sha, relative, status, method, VERSION,
             "Captured to give existing claims a verifiable copy of their source."),
        )
        capture_id = connection.execute(
            "SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?",
            (source_id, sha),
        ).fetchone()[0]
        for claim in rows:
            connection.execute(
                "UPDATE evidence_claims SET evidence_capture_id=? WHERE claim_id=?",
                (capture_id, claim["claim_id"]),
            )
            captured += 1
        print(f"  captured {url} -> {relative} ({len(body)} bytes, {len(rows)} claims linked)")

    downgraded = 0
    for claim in unverifiable:
        note = (claim["notes"] + " | " if claim["notes"] else "") + (
            f"Confidence lowered from '{claim['confidence']}' on {now()[:10]}: the originating source "
            f"({claim['url']}) no longer exists, so this claim cannot be re-verified. "
            "Re-test the route to restore a verified claim."
        )
        connection.execute(
            "UPDATE evidence_claims SET confidence='unverified', notes=? WHERE claim_id=?",
            (note, claim["claim_id"]),
        )
        downgraded += 1

    connection.commit()
    remaining = connection.execute(
        "SELECT COUNT(*) FROM evidence_claims WHERE evidence_capture_id IS NULL AND confidence<>'unverified'"
    ).fetchone()[0]
    connection.close()
    print(f"Linked {captured} claims to real captures, downgraded {downgraded} to unverified")
    print(f"Claims still lacking a capture while claiming confidence: {remaining}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
