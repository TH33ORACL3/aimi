#!/usr/bin/env python3
"""Remove change events whose before/after differ only in volatile fields.

Some providers return a `created` value that is really a retrieval timestamp,
so every poll looked like a model change. The monitor now excludes those fields
from its change fingerprint, but rows recorded before that fix remain in the
event log and drown out real changes.

This script reuses the monitor's own volatile-field definition, so the cleanup
can never disagree with the detector. A row is only removed when, after
excluding exactly what the monitor excludes, nothing is left that differs.
Affected monitoring runs have their counts recomputed, and a run left with no
changes at all is corrected to `unchanged`.

Usage:
    python correct_volatile_changes.py            # report only
    python correct_volatile_changes.py --apply    # delete, after backing up
"""
from __future__ import annotations

import argparse
import collections
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"

# Import the monitor's own definitions so the two can never drift apart.
sys.path.insert(0, str(ROOT))
from monitor_endpoints import stable_metadata  # noqa: E402

# The monitor excludes provider_created_at from top-level comparison because it
# is derived from the same volatile provider field.
DERIVED_VOLATILE = {"provider_created_at"}


def is_volatile_only(before: dict, after: dict) -> bool:
    differing = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
    differing -= DERIVED_VOLATILE
    if "raw" in differing and stable_metadata(before.get("raw")) == stable_metadata(after.get("raw")):
        differing.discard("raw")
    return not differing


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove volatile-only change events")
    parser.add_argument("--apply", action="store_true", help="Delete the rows and correct affected runs")
    parser.add_argument("--type", default="model_changed", help="Change type to inspect")
    args = parser.parse_args()

    if not DB.exists():
        print(f"No database at {DB}", file=sys.stderr)
        return 1

    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row

    rows = connection.execute(
        "SELECT endpoint_change_id, monitoring_run_id, provider_id, detected_at, before_json, after_json "
        "FROM endpoint_changes WHERE change_type=?",
        (args.type,),
    ).fetchall()

    victims: list[int] = []
    runs: set[int] = set()
    breakdown: collections.Counter = collections.Counter()
    for row in rows:
        before = json.loads(row["before_json"] or "{}")
        after = json.loads(row["after_json"] or "{}")
        if is_volatile_only(before, after):
            victims.append(row["endpoint_change_id"])
            runs.add(row["monitoring_run_id"])
            breakdown[(row["provider_id"], row["detected_at"][:10])] += 1

    print(f"{args.type} rows inspected : {len(rows)}")
    print(f"volatile-only rows       : {len(victims)}")
    print(f"monitoring runs affected : {len(runs)}")
    for (provider, day), count in breakdown.most_common():
        print(f"   {provider:<16}{day}  {count}")

    if not args.apply:
        print("dry run; re-run with --apply")
        return 0
    if not victims:
        return 0

    backup = DB.with_name(f"{DB.name}.bak.volatile-cleanup-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(DB, backup)
    print(f"Backup: {backup.name}")

    marks = ",".join("?" * len(victims))
    connection.execute(f"DELETE FROM endpoint_changes WHERE endpoint_change_id IN ({marks})", victims)

    corrected = 0
    for run_id in sorted(runs):
        counts = dict.fromkeys(("model_added", "model_removed"), 0)
        remaining = 0
        for change_type, count in connection.execute(
            "SELECT change_type, COUNT(*) FROM endpoint_changes WHERE monitoring_run_id=? GROUP BY 1",
            (run_id,),
        ):
            remaining += count
            if change_type in counts:
                counts[change_type] = count
        changed = remaining - counts["model_added"] - counts["model_removed"]
        status_row = connection.execute(
            "SELECT status FROM monitoring_runs WHERE monitoring_run_id=?", (run_id,)
        ).fetchone()
        if status_row and status_row["status"] in ("changed", "success"):
            status = "changed" if remaining else "unchanged"
            connection.execute(
                "UPDATE monitoring_runs SET status=?, added_count=?, removed_count=?, changed_count=? "
                "WHERE monitoring_run_id=?",
                (status, counts["model_added"], counts["model_removed"], changed, run_id),
            )
            if status == "unchanged":
                corrected += 1

    connection.commit()
    remaining_unreviewed = connection.execute(
        "SELECT COUNT(*) FROM endpoint_changes WHERE reviewed=0"
    ).fetchone()[0]
    connection.close()
    print(f"Deleted {len(victims)} rows, corrected {corrected} runs to unchanged")
    print(f"Unreviewed changes remaining: {remaining_unreviewed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
