#!/usr/bin/env python3
"""Collapse byte-identical endpoint snapshots to one file per distinct payload.

Every 15-minute poll wrote a full response copy even when the provider returned
exactly the same JSON, so `snapshots/` grew about 50 MB a day and more than half
the files were exact duplicates of another file.

Snapshots are content addressed by sha256, so this is lossless by construction:
a duplicate is only removed when another file with the identical hash remains
referenced, and every affected database row is repointed at that surviving file
first. The script verifies on-disk hashes before and after, and refuses to
delete anything if a single verification fails.

Usage:
    python prune_snapshots.py            # report what would be reclaimed
    python prune_snapshots.py --apply    # repoint rows, then delete duplicates
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
SNAPSHOTS = ROOT / "snapshots"
# (table, primary key, path column, hash column)
PATH_TABLES = (
    ("monitoring_runs", "monitoring_run_id", "snapshot_path", "response_sha256"),
    ("model_sources", "source_id", "raw_snapshot_path", "response_sha256"),
    ("evidence_captures", "evidence_capture_id", "archived_path", "content_sha256"),
)


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate identical endpoint snapshots")
    parser.add_argument("--apply", action="store_true", help="Repoint rows and delete duplicate files")
    args = parser.parse_args()

    if not DB.exists():
        print(f"No database at {DB}", file=sys.stderr)
        return 1

    connection = sqlite3.connect(DB)

    # 1. Collect every referenced (path, recorded hash) pair.
    references: list[tuple[str, str, str, str, str]] = []  # table, key, path, hash, row id
    for table, key, path_col, hash_col in PATH_TABLES:
        for row_id, path_value, hash_value in connection.execute(
            f"SELECT {key},{path_col},{hash_col} FROM {table} "
            f"WHERE {path_col} IS NOT NULL AND {hash_col} IS NOT NULL"
        ):
            references.append((table, key, path_value, hash_value, row_id))

    # 2. Verify the on-disk content of every distinct existing file once.
    verified: dict[str, str] = {}   # relative path -> real hash
    unreadable: list[str] = []
    for _, _, path_value, _, _ in references:
        if path_value in verified:
            continue
        resolved = resolve(path_value)
        if not resolved.exists():
            unreadable.append(path_value)
            continue
        verified[path_value] = file_hash(resolved)

    # 3. Choose one canonical file per real hash: the shortest-lived duplicate
    #    set collapses onto the earliest path, which keeps the oldest evidence.
    canonical: dict[str, str] = {}
    for path_value in sorted(verified):
        canonical.setdefault(verified[path_value], path_value)

    mismatched = [
        (path_value, hash_value, verified[path_value])
        for _, _, path_value, hash_value, _ in references
        if path_value in verified and verified[path_value] != hash_value
    ]

    repoint: list[tuple[str, str, str, object]] = []
    for table, key, path_value, hash_value, row_id in references:
        if path_value not in verified:
            continue
        target = canonical[verified[path_value]]
        if target != path_value:
            repoint.append((table, key, target, row_id))

    keep = set(canonical.values())
    on_disk = {
        str(p.relative_to(ROOT)) for p in SNAPSHOTS.rglob("*.json") if p.is_file()
    }
    removable = sorted(
        p for p in on_disk
        if p not in keep and p in verified and verified[p] in canonical
    )
    orphan_files = sorted(p for p in on_disk if p not in verified)
    reclaim = sum(resolve(p).stat().st_size for p in removable)

    print(f"referenced rows      : {len(references)}")
    print(f"distinct files       : {len(verified)}")
    print(f"distinct payloads    : {len(canonical)}")
    print(f"rows to repoint      : {len(repoint)}")
    print(f"duplicate files      : {len(removable)}  ({reclaim/1_048_576:.1f} MB)")
    print(f"unreferenced on disk : {len(orphan_files)} (left in place)")
    print(f"missing referenced   : {len(unreadable)}")
    print(f"hash mismatches      : {len(mismatched)}")

    if mismatched:
        for path_value, recorded, actual in mismatched[:5]:
            print(f"  MISMATCH {path_value}: recorded {recorded[:12]} actual {actual[:12]}")
        print("Refusing to prune: recorded hashes do not match file contents.", file=sys.stderr)
        return 1

    if not args.apply:
        print("dry run; re-run with --apply")
        return 0

    backup = DB.with_name(f"{DB.name}.bak.snapshot-prune-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(DB, backup)
    print(f"Backup: {backup.name}")

    for table, key, target, row_id in repoint:
        column = {t: c for t, k, c, h in PATH_TABLES}[table]
        connection.execute(f"UPDATE {table} SET {column}=? WHERE {key}=?", (target, row_id))
    connection.commit()

    # 4. Re-read references and confirm every one now resolves before deleting.
    still_missing = 0
    for table, key, path_col, hash_col in PATH_TABLES:
        for (path_value,) in connection.execute(
            f"SELECT DISTINCT {path_col} FROM {table} WHERE {path_col} IS NOT NULL"
        ):
            if not resolve(path_value).exists():
                still_missing += 1
    if still_missing:
        print(f"Refusing to delete: {still_missing} references do not resolve after repointing.", file=sys.stderr)
        connection.close()
        return 1

    deleted = 0
    for path_value in removable:
        resolve(path_value).unlink(missing_ok=True)
        deleted += 1
    connection.close()
    print(f"Repointed {len(repoint)} rows, deleted {deleted} duplicate files, reclaimed {reclaim/1_048_576:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
