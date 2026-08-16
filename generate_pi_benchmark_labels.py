#!/usr/bin/env python3
"""Generate the Pi footer benchmark-labels file.

Produces ~/.pi/agent/model-benchmarks.json so the Pi footer extension can show
the active model's top benchmark scores. Display rule (Aubrey's preference):
DeepSWE first, Terminal-Bench second, then other SWE-bench variants, then any
software-engineering / terminal / browser benchmark. The top 2 available per
model are emitted, already priority-ordered.

Output shape:
{
  "generated_at": "...",
  "models": [
    {"model": "openai-codex/gpt-5.6-luna", "benchmarks": [
       {"bench":"deepswe","label":"DeepSWE","value":0.672,"value_unit":"ratio","version":"1.1","source_type":"official_maker"},
       {"bench":"terminal_bench","label":"Terminal-Bench 2.1","value":0.847,"value_unit":"ratio","version":"2.1","source_type":"official_maker"}
    ]}
  ]
}
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = Path(__file__).resolve().parent / "aimi.db"
OUT = Path.home() / ".pi" / "agent" / "model-benchmarks.json"
MODELS_JSON = Path.home() / ".pi" / "agent" / "models.json"
BACKUP_DIR = Path.home() / ".pi" / "backups"

# Priority order. Lower index = preferred. Terminal-Bench prefers 2.1 -> 2.0 -> 3.0.
BENCH_ORDER = [
    "deepswe",
    "terminal_bench", "terminal_bench_3",
    "swebench_pro", "swebench_verified", "swebench_multilingual", "swebench_multimodal",
    "livecodebench", "frontier_swe", "programbench", "swe_marathon", "nl2repo",
    "swe_fficiency", "swe_rebench",
    "mcp_atlas", "mcp_mark", "mcp_mark_verified", "mcp_tasks",
    "browsecomp", "widesearch", "deepsearchqa",
    "osworld_verified", "osworld_2",
    "claw_eval", "toolathlon", "automationbench", "kernelbench_hard",
]
ORDER_INDEX = {b: i for i, b in enumerate(BENCH_ORDER)}
FALLBACK_INDEX = len(BENCH_ORDER)

LABELS = {
    "deepswe": "DeepSWE",
    "terminal_bench": "Terminal-Bench",
    "terminal_bench_3": "Terminal-Bench 3.0",
    "swebench_pro": "SWE-Bench Pro",
    "swebench_verified": "SWE-Bench Verified",
    "swebench_multilingual": "SWE-Bench Multilingual",
    "swebench_multimodal": "SWE-Bench Multimodal",
    "livecodebench": "LiveCodeBench",
    "frontier_swe": "FrontierSWE",
    "programbench": "ProgramBench",
    "swe_marathon": "SWE-Marathon",
    "nl2repo": "NL2Repo",
    "swe_fficiency": "SWE-fficiency",
    "swe_rebench": "SWE-Rebench",
    "mcp_atlas": "MCP-Atlas",
    "mcp_mark": "MCP-Mark",
    "mcp_mark_verified": "MCPMark-Verified",
    "mcp_tasks": "MCP-Tasks",
    "browsecomp": "BrowseComp",
    "widesearch": "WideSearch",
    "deepsearchqa": "DeepSearchQA",
    "osworld_verified": "OSWorld-Verified",
    "osworld_2": "OSWorld 2.0",
    "claw_eval": "Claw-Eval",
    "toolathlon": "Toolathlon",
    "automationbench": "AutomationBench",
    "kernelbench_hard": "KernelBench-Hard",
}

# terminal version preference: NEWEST first (3.0 > 2.1 > 2.0)
TERMINAL_VERSION_PREF = ["3.0", "2.1", "2.0"]


def terminal_version(row: dict) -> str:
    """Normalize a terminal row to its benchmark version string."""
    if row.get("benchmark") == "terminal_bench_3":
        return "3.0"
    v = (row.get("benchmark_version") or "").strip()
    return v if v in ("2.0", "2.1", "3.0") else "2.0"

# base display name per canonical model (what shows before the benchmarks)
BASE_NAMES = {
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gpt-5.6-terra": "GPT-5.6 Terra",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "claude-opus-5": "Claude Opus 5",
    "claude-sonnet-5": "Claude Sonnet 5",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "kimi-k3": "Kimi K3",
    "glm-5.3": "GLM-5.3",
    "qwen3.8-max": "Qwen3.8 Max",
}


def fmt_value(value: float, unit: str) -> str:
    if unit in ("elo", "points", "count"):
        return f"{value:g}"
    if unit == "percent":
        return f"{value:.1f}%"
    return f"{value * 100:.1f}%"


def label_string(benchmarks: list[dict]) -> str:
    return " · ".join(f"{e['label']} {fmt_value(e['value'], e['value_unit'])}" for e in benchmarks)


def write_pi_display_names(models_out: list[dict]) -> None:
    """Update ~/.pi/agent/models.json display names with the top-2 benchmarks."""
    if not MODELS_JSON.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(MODELS_JSON, BACKUP_DIR / f"models.json.bak-final-deepswe-{stamp}")
    data = json.loads(MODELS_JSON.read_text())
    providers = data.setdefault("providers", {})
    for m in models_out:
        mid = m["model"]
        benchmarks = m.get("benchmarks", [])
        if not benchmarks:
            continue
        provider, _, model_key = mid.partition("/")
        slug = canonical_slug_from_mid(mid)
        base = BASE_NAMES.get(slug or "", model_key)
        new_name = f"{base} · {label_string(benchmarks)}"
        prov = providers.get(provider)
        if not prov:
            continue
        if provider == "cline":
            for md in prov.get("models", []):
                if md.get("id") == model_key:
                    md["name"] = new_name
        else:
            ov = prov.get("modelOverrides")
            if ov and model_key in ov:
                ov[model_key]["name"] = new_name
    MODELS_JSON.write_text(json.dumps(data, indent=2))
    print(f"updated display names in {MODELS_JSON}")


def canonical_slug_from_mid(model_id: str) -> str | None:
    """Quick canonical lookup for a full provider/model id (no DB needed)."""
    m = model_id.split("/", 1)[1]
    for pre in ("cline-pass/", "deepseek/", "opencode-go/", "opencode-zen/", "codex/"):
        if m.startswith(pre):
            m = m[len(pre):]
    return m if m in BASE_NAMES else None


def canonical_slug(conn: sqlite3.Connection, model_id: str) -> str | None:
    pid, _, m = model_id.partition("/")
    cands = [m]
    for pre in ("cline-pass/", "deepseek/", "opencode-go/", "opencode-zen/", "codex/"):
        if m.startswith(pre):
            cands.append(m[len(pre):])
    for cand in cands:
        row = conn.execute("SELECT canonical_slug FROM canonical_models WHERE canonical_slug=?", (cand,)).fetchone()
        if row:
            return row[0]
    # provider-join fallback
    row = conn.execute(
        "SELECT cm.canonical_slug FROM provider_models_v2 pm JOIN canonical_models cm USING(canonical_model_id) "
        "WHERE pm.provider_id=? AND pm.model_identifier=? LIMIT 1", (pid, m),
    ).fetchone()
    return row[0] if row else None


def terminal_choice(rows: list[dict]) -> dict | None:
    """Pick the newest-version terminal row (3.0 > 2.1 > 2.0)."""
    def key(r: dict) -> int:
        v = terminal_version(r)
        try:
            return TERMINAL_VERSION_PREF.index(v)
        except ValueError:
            return len(TERMINAL_VERSION_PREF)
    return min(rows, key=key) if rows else None


def main() -> int:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        enabled = json.loads((Path.home() / ".pi" / "agent" / "settings.json").read_text()).get("enabledModels", [])
        models_out = []
        for mid in enabled:
            slug = canonical_slug(conn, mid)
            if not slug:
                models_out.append({"model": mid, "benchmarks": []})
                continue
            rows = conn.execute(
                "SELECT b.benchmark, b.benchmark_version, b.value, b.value_unit, b.source_type, b.benchmark_score_id "
                "FROM benchmark_scores b JOIN canonical_models cm USING(canonical_model_id) "
                "WHERE cm.canonical_slug=? AND b.is_best_config=1", (slug,),
            ).fetchall()
            by_bench: dict[str, dict] = {}
            for r in rows:
                b = r["benchmark"]
                d = dict(r)
                if b == "terminal_bench" or b == "terminal_bench_3":
                    prev = by_bench.get("terminal")
                    if prev is None:
                        by_bench["terminal"] = d
                    else:
                        by_bench["terminal"] = terminal_choice([prev, d]) or prev
                else:
                    prev = by_bench.get(b)
                    if prev is None or d["value"] > prev["value"]:
                        by_bench[b] = d
            # sort available benchmarks by priority
            avail = []
            for b, d in by_bench.items():
                if b == "terminal":
                    bench = "terminal_bench"
                    ver = terminal_version(d)
                    label = f"Terminal-Bench {ver}"
                elif b == "deepswe":
                    bench = "deepswe"
                    ver = d["benchmark_version"] or "1.1"
                    label = f"DeepSWE {ver}"
                elif b == "livecodebench":
                    bench = b
                    ver = d["benchmark_version"] or ""
                    label = "LiveCodeBench" + (f" {ver}" if ver else "")
                else:
                    bench = b
                    ver = d["benchmark_version"]
                    label = LABELS.get(bench, bench.replace("_", " ").title())
                idx = ORDER_INDEX.get(bench, FALLBACK_INDEX)
                # terminal_bench_3 is same family; treat as terminal priority
                if bench == "terminal_bench_3":
                    idx = ORDER_INDEX["terminal_bench"]
                avail.append({
                    "bench": bench,
                    "label": label,
                    "value": d["value"],
                    "value_unit": d["value_unit"],
                    "version": ver,
                    "source_type": d["source_type"],
                    "_idx": idx,
                })
            # stable sort: priority first, then fallback alphabetical
            avail.sort(key=lambda x: (x["_idx"], x["label"]))
            for a in avail:
                a.pop("_idx", None)
            models_out.append({"model": mid, "benchmarks": avail[:2]})
    finally:
        conn.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": models_out,
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"wrote {OUT} with {len(models_out)} models")
    try:
        write_pi_display_names(models_out)
    except Exception as e:  # never let a display-name failure break label generation
        print(f"display-name update skipped: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
