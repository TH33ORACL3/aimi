#!/usr/bin/env python3
"""Normalise evidence file paths stored in the catalogue.

Snapshot and capture paths were recorded as absolute paths. When the project
directory was renamed from `Models` to `AIMI`, 885 evidence references stopped
resolving even though every file still existed. Absolute paths also write the
personal home directory into a database that gets exported.

This script rewrites any path that points inside the project to a
project-relative path, so a future rename or a different checkout location
cannot break the evidence chain again. Paths outside the project are left
untouched and reported.

Usage:
    python normalize_paths.py            # report only
    python normalize_paths.py --apply    # rewrite, after backing up the database
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
# Directory names this project has used. Paths under any of them belong here.
FORMER_NAMES = ("Models", "ai-model-index", "AIMI")
PATH_COLUMNS = (
    ("monitoring_runs", "monitoring_run_id", "snapshot_path"),
    ("model_sources", "source_id", "raw_snapshot_path"),
    ("evidence_captures", "evidence_capture_id", "archived_path"),
    ("evidence_sources", "evidence_source_id", "archived_path"),
)


def candidate_roots() -> list[Path]:
    return [ROOT] + [ROOT.parent / name for name in FORMER_NAMES if (ROOT.parent / name) != ROOT]


def to_relative(value: str) -> str | None:
    """Return a project-relative path, or None when the path is external."""
    if not value or not value.startswith("/"):
        return None
    # Collapse accidental double slashes recorded by earlier writers.
    cleaned = "/" + value.lstrip("/")
    for base in candidate_roots():
        base_str = str(base)
        if cleaned.startswith(base_str + "/"):
            return cleaned[len(base_str) + 1 :]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalise stored evidence paths to project-relative form")
    parser.add_argument("--apply", action="store_true", help="Write the changes")
    args = parser.parse_args()

    if not DB.exists():
        print(f"No database at {DB}", file=sys.stderr)
        return 1

    if args.apply:
        backup = DB.with_name(f"{DB.name}.bak.path-normalize-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(DB, backup)
        print(f"Backup: {backup.name}")

    connection = sqlite3.connect(DB)
    connection.execute("PRAGMA foreign_keys=ON")
    summary: list[dict] = []
    unresolved_total = 0

    for table, key, column in PATH_COLUMNS:
        rows = connection.execute(
            f"SELECT {key}, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} LIKE '/%'"
        ).fetchall()
        updates = []
        external = 0
        for row_id, value in rows:
            relative = to_relative(value)
            if relative is None:
                external += 1
                continue
            if relative != value:
                updates.append((relative, row_id))
        still_missing = sum(1 for _, value in rows if to_relative(value) and not (ROOT / to_relative(value)).exists())
        unresolved_total += still_missing
        if args.apply and updates:
            connection.executemany(f"UPDATE {table} SET {column}=? WHERE {key}=?", updates)
        summary.append(
            {
                "table": f"{table}.{column}",
                "absolute_rows": len(rows),
                "rewritten": len(updates),
                "external_left_alone": external,
                "files_still_missing": still_missing,
            }
        )

    if args.apply:
        connection.commit()
    connection.close()

    width = max(len(item["table"]) for item in summary)
    for item in summary:
        print(
            f"{item['table']:<{width}}  absolute={item['absolute_rows']:<6} "
            f"rewrite={item['rewritten']:<6} external={item['external_left_alone']:<4} "
            f"missing_files={item['files_still_missing']}"
        )
    print("applied" if args.apply else "dry run; re-run with --apply")
    return 1 if unresolved_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
