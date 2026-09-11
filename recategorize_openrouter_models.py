#!/usr/bin/env python3
"""Re-categorize all OpenRouter models in AIMI based on verified input/output capabilities.

Scans all currently integrated OpenRouter models from provider_models_v2, models,
and latest snapshots. Replaces misleading 'image' labels with granular capability
tags and accurate categories.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from catalogue_classification import (
    classify_capability_tags,
    classify_input_type,
    classify_model_category,
    classify_output_type,
    extract_modalities,
    normalise_modalities,
)

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "aimi.db"
SNAPSHOT_PATH = ROOT / "snapshots/monitor/openrouter-2026-09-09T003410+0000.json"


def recategorize(dry_run: bool = False) -> dict:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    # Load latest snapshot data to enrich any models with missing architecture
    snapshot_models: dict[str, dict] = {}
    if SNAPSHOT_PATH.exists():
        try:
            with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
                snap = json.load(f)
                for item in snap.get("data", []):
                    mid = item.get("id")
                    if mid:
                        snapshot_models[mid] = item
        except Exception as exc:
            print(f"Warning: Could not read snapshot: {exc}")

    # Backup database if modifying
    if not dry_run:
        bak_path = ROOT / f"aimi.db.bak-recategorize-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        shutil.copy2(DB_PATH, bak_path)
        print(f"Backed up aimi.db to {bak_path.name}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Fetch all openrouter models
    pm_rows = conn.execute(
        """
        SELECT provider_model_id, model_identifier, display_name,
               input_modalities_json, output_modalities_json,
               reasoning, tools, function_calling, structured_outputs, streaming,
               provider_metadata_json
        FROM provider_models_v2
        WHERE provider_id = 'openrouter'
        """
    ).fetchall()

    legacy_rows = {
        row["model_id"]: dict(row)
        for row in conn.execute(
            "SELECT id, model_id, display_name, category, catagory, input_modalities, output_modalities FROM models WHERE provider = 'openrouter'"
        ).fetchall()
    }

    stats = {
        "total_provider_models": len(pm_rows),
        "total_legacy_models": len(legacy_rows),
        "reclassified_from_image_to_vision": [],
        "confirmed_image_output": [],
        "input_types": {},
        "output_types": {},
        "categories": {},
    }

    updates_pm = []
    updates_legacy = []

    for row in pm_rows:
        mid = row["model_identifier"]
        display = row["display_name"] or mid
        snap_item = snapshot_models.get(mid, {})

        # Extract modalities
        in_mod = None
        out_mod = None

        if snap_item:
            in_mod = extract_modalities(snap_item, "input_modalities")
            out_mod = extract_modalities(snap_item, "output_modalities")

        if in_mod is None and row["input_modalities_json"]:
            try:
                in_mod = normalise_modalities(json.loads(row["input_modalities_json"]), "input")
            except Exception:
                in_mod = normalise_modalities(row["input_modalities_json"], "input")

        if out_mod is None and row["output_modalities_json"]:
            try:
                out_mod = normalise_modalities(json.loads(row["output_modalities_json"]), "output")
            except Exception:
                out_mod = normalise_modalities(row["output_modalities_json"], "output")

        # Default fallback if still None
        in_mod = in_mod or ["text"]
        out_mod = out_mod or ["text"]

        in_type = classify_input_type(in_mod)
        out_type = classify_output_type(out_mod)

        meta = {
            "reasoning": row["reasoning"],
            "tools": row["tools"] or row["function_calling"],
            "structured_outputs": row["structured_outputs"],
            "streaming": row["streaming"],
        }
        tags = classify_capability_tags(in_mod, out_mod, meta)
        cat = classify_model_category(mid, display, in_mod, out_mod)

        # Track stats
        stats["input_types"][in_type] = stats["input_types"].get(in_type, 0) + 1
        stats["output_types"][out_type] = stats["output_types"].get(out_type, 0) + 1
        stats["categories"][cat] = stats["categories"].get(cat, 0) + 1

        if out_type == "image-output":
            stats["confirmed_image_output"].append(mid)

        # Check legacy model category
        leg = legacy_rows.get(mid)
        if leg:
            old_cat = leg["category"] or leg["catagory"]
            if old_cat == "image" and cat != "image":
                stats["reclassified_from_image_to_vision"].append({
                    "model_id": mid,
                    "old_category": old_cat,
                    "new_category": cat,
                    "input_type": in_type,
                    "output_type": out_type,
                    "tags": tags,
                })
            updates_legacy.append((
                cat,
                cat,
                json.dumps(in_mod),
                json.dumps(out_mod),
                mid,
            ))

        updates_pm.append((
            json.dumps(in_mod),
            json.dumps(out_mod),
            row["provider_model_id"],
        ))

    if not dry_run:
        # Apply updates to provider_models_v2
        conn.executemany(
            """
            UPDATE provider_models_v2
            SET input_modalities_json = ?, output_modalities_json = ?
            WHERE provider_model_id = ?
            """,
            updates_pm,
        )

        # Apply updates to legacy models
        conn.executemany(
            """
            UPDATE models
            SET category = ?, catagory = ?, input_modalities = ?, output_modalities = ?
            WHERE provider = 'openrouter' AND model_id = ?
            """,
            updates_legacy,
        )

        conn.commit()
        print(f"Applied updates to {len(updates_pm)} provider_models_v2 rows and {len(updates_legacy)} models rows.")

    conn.close()
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Re-categorize OpenRouter models in AIMI")
    parser.add_argument("--dry-run", action="store_true", help="Inspect categorization without writing")
    args = parser.parse_args()

    results = recategorize(dry_run=args.dry_run)
    print("\n=== Model Categorization Audit Summary ===")
    print(f"Total provider_models_v2 evaluated: {results['total_provider_models']}")
    print(f"Total models evaluated: {results['total_legacy_models']}")
    print(f"\nInput Types Distribution:")
    for k, v in sorted(results["input_types"].items(), key=lambda x: -x[1]):
        print(f"  {k:20s}: {v}")
    print(f"\nOutput Types Distribution:")
    for k, v in sorted(results["output_types"].items(), key=lambda x: -x[1]):
        print(f"  {k:20s}: {v}")
    print(f"\nCategory Distribution:")
    for k, v in sorted(results["categories"].items(), key=lambda x: -x[1]):
        print(f"  {k:20s}: {v}")
    print(f"\nModels confirmed with image-output: {len(results['confirmed_image_output'])}")
    for mid in results["confirmed_image_output"][:10]:
        print(f"  - {mid}")
