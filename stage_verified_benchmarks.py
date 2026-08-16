#!/usr/bin/env python3
"""Stage verified frontier benchmark rows for AIMI ingestion (2026-08-15).

Values are transcribed from official maker pages, official PDFs, official X
screenshots, and provider-linked BenchLM dossiers that cite a maker source.
Percentages are normalized to ratio (0-1); Elo/points/counts keep raw values
with their unit. source_type marks official_maker / official_benchmark /
provider_linked. This script only writes the JSON; ingestion is separate.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "benchmark_sources" / "verified_2026-08-15.json"

rows = []


def add(slug, benchmark, version, metric, value, unit="ratio", config=None,
        stype="official_maker", conf="verified", date=None, url=None, notes=None):
    rows.append({
        "canonical_slug": slug,
        "benchmark": benchmark,
        "benchmark_version": version,
        "metric": metric,
        "value": value,
        "value_unit": unit,
        "config_text": config,
        "source_type": stype,
        "confidence": conf,
        "score_date": date,
        "source_url": url,
        "notes": notes,
    })


# ---- OpenAI GPT-5.6 (official page) ----
OAI = "https://openai.com/index/gpt-5-6/"
for slug, swep, dsw, tb, bc, os, gpqa, ale, fm13, fm4, mmmu, ab, ta, eb, hb, bcb, gdp, aaci, aaii, bfb in [
    ("gpt-5.6-sol", 0.646, 0.727, 0.888, 0.904, 0.626, 0.946, 0.527, 0.89, 0.83, 0.83, 0.181, 0.58, 0.735, 0.605, 0.706, 1747.8, 80, 58.9, 0.53),
    ("gpt-5.6-terra", 0.634, 0.696, 0.874, 0.875, 0.502, 0.929, 0.504, 0.849, 0.683, 0.807, 0.152, 0.531, 0.529, 0.577, 0.623, 1593, 77.4, 55, 0.51),
    ("gpt-5.6-luna", 0.627, 0.672, 0.847, 0.833, 0.456, 0.923, 0.503, 0.786, 0.585, 0.784, 0.149, 0.534, 0.332, 0.557, 0.631, 1591.8, 74.6, 51.2, 0.36),
]:
    add(slug, "swebench_pro", "2026-07", "pass@1", swep, url=OAI, date="2026-07-09")
    add(slug, "deepswe", "1.1", "pass@1", dsw, config="OpenAI official table", url=OAI, date="2026-07-09")
    add(slug, "terminal_bench", "2.1", "pass@1", tb, url=OAI, date="2026-07-09")
    add(slug, "osworld_2", "2026", "pass@1", os, url=OAI, date="2026-07-09")
    add(slug, "browsecomp", "2026", "pass@1", bc, url=OAI, date="2026-07-09")
    add(slug, "gpqa_diamond", "2026", "pass@1", gpqa, url=OAI, date="2026-07-09")
    add(slug, "agents_last_exam", "2026", "pass@1", ale, url=OAI, date="2026-07-09")
    add(slug, "frontiermath_t1_3", "v2", "pass@1", fm13, url=OAI, date="2026-07-09")
    add(slug, "frontiermath_t4", "v2", "pass@1", fm4, url=OAI, date="2026-07-09")
    add(slug, "mmmu_pro", "2026", "pass@1", mmmu, url=OAI, date="2026-07-09")
    add(slug, "automationbench", "2026", "pass@1", ab, url=OAI, date="2026-07-09")
    add(slug, "toolathlon", "2026", "pass@1", ta, url=OAI, date="2026-07-09")
    add(slug, "exploitbench", "2026", "pass@1", eb, url=OAI, date="2026-07-09")
    add(slug, "healthbench", "2026", "pass@1", hb, url=OAI, date="2026-07-09")
    add(slug, "benchcad", "2026", "pass@1", bcb, url=OAI, date="2026-07-09")
    add(slug, "gdpval_aa", "v2", "elo", gdp, unit="elo", url=OAI, date="2026-07-09")
    add(slug, "aa_coding_agent_index", "v1.1", "score", aaci, unit="points", url=OAI, date="2026-07-09")
    add(slug, "aa_intelligence_index", "v4.1", "score", aaii, unit="points", url=OAI, date="2026-07-09")
    add(slug, "big_finance_bench", "2026", "pass@1", bfb, url=OAI, date="2026-07-09")

# ---- Anthropic Claude Opus 5 system card ----
OPUS = "https://www-cdn.anthropic.com/c5fbac3f0b1280a933ebd26d3cb8bb9f5bdeaf48/Claude%20Opus%205%20System%20Card.pdf"
add("claude-opus-5", "swebench_pro", "2026", "pass@1", 0.792, url=OPUS, date="2026-07-24")
add("claude-opus-5", "swebench_multilingual", "2026", "pass@1", 0.895, url=OPUS, date="2026-07-24")
add("claude-opus-5", "swebench_multimodal", "2026", "pass@1", 0.594, url=OPUS, date="2026-07-24")
add("claude-opus-5", "deepswe", "1.1", "pass@1", 0.688, config="Anthropic system card", url=OPUS, date="2026-07-24")
add("claude-opus-5", "frontiercode", "1.1", "pass@1", 0.534, config="Main", url=OPUS, date="2026-07-24")
add("claude-opus-5", "frontierbench", "v0.1", "pass@1", 0.433, url=OPUS, date="2026-07-24")
add("claude-opus-5", "browsecomp", "2026", "pass@1", 0.908, url=OPUS, date="2026-07-24")
add("claude-opus-5", "hle", "2026", "pass@1", 0.563, config="no tools", url=OPUS, date="2026-07-24")
add("claude-opus-5", "hle_tools", "2026", "pass@1", 0.647, url=OPUS, date="2026-07-24")
add("claude-opus-5", "osworld_2", "2026", "pass@1", 0.706, url=OPUS, date="2026-07-24")
add("claude-opus-5", "healthbench", "2026", "pass@1", 0.598, url=OPUS, date="2026-07-24")
add("claude-opus-5", "gdpval_aa", "v2", "elo", 1861, unit="elo", url=OPUS, date="2026-07-24")
add("claude-opus-5", "aa_briefcase", "2026", "elo", 1720, unit="elo", url=OPUS, date="2026-07-24")
add("claude-opus-5", "automationbench", "2026", "pass@1", 0.26, url=OPUS, date="2026-07-24")
add("claude-opus-5", "arc_agi_1", "2026", "pass@1", 0.975, url=OPUS, date="2026-07-24")

# ---- Anthropic Claude Sonnet 5 system card ----
SON = "https://www-cdn.anthropic.com/d9bb04416ffe1352af84721476c1fa9994c07fde/Claude%20Sonnet%205%20System%20Card.pdf"
add("claude-sonnet-5", "swebench_verified", "2026", "pass@1", 0.852, url=SON, date="2026-06-30")
add("claude-sonnet-5", "swebench_pro", "2026", "pass@1", 0.632, url=SON, date="2026-06-30")
add("claude-sonnet-5", "swebench_multilingual", "2026", "pass@1", 0.783, url=SON, date="2026-06-30")
add("claude-sonnet-5", "swebench_multimodal", "2026", "pass@1", 0.281, url=SON, date="2026-06-30")
add("claude-sonnet-5", "terminal_bench", "2.1", "pass@1", 0.804, url=SON, date="2026-06-30")
add("claude-sonnet-5", "browsecomp", "2026", "pass@1", 0.847, config="single agent", url=SON, date="2026-06-30")
add("claude-sonnet-5", "browsecomp", "2026", "pass@1", 0.866, config="multi agent", url=SON, date="2026-06-30")
add("claude-sonnet-5", "hle", "2026", "pass@1", 0.432, config="no tools", url=SON, date="2026-06-30")
add("claude-sonnet-5", "hle_tools", "2026", "pass@1", 0.574, url=SON, date="2026-06-30")
add("claude-sonnet-5", "osworld_verified", "2026", "pass@1", 0.812, url=SON, date="2026-06-30")
add("claude-sonnet-5", "frontiercode", "v1", "pass@1", 0.388, url=SON, date="2026-06-30")
add("claude-sonnet-5", "gdpval_aa", "v2", "elo", 1609, unit="elo", url=SON, date="2026-06-30")
add("claude-sonnet-5", "automationbench", "2026", "pass@1", 0.135, url=SON, date="2026-06-30")
add("claude-sonnet-5", "legal_agent_benchmark", "2026", "pass@1", 0.089, config="Full Public Set", url=SON, date="2026-06-30")

# ---- Z.ai GLM-5.2 / GLM-5.1 (official page) ----
GLM52 = "https://z.ai/blog/glm-5.2"
glm52 = {
    "swebench_pro": 0.621, "terminal_bench": 0.81, "deepswe": 0.462, "frontier_swe": 0.744,
    "posttrainbench": 0.343, "swe_marathon": 0.13, "nl2repo": 0.489, "programbench": 0.637,
    "mcp_atlas": 0.768, "tool_decathlon": 0.482, "hle_tools": 0.547, "aime_2026": 0.992,
    "gpqa_diamond": 0.912, "hmmt_2026_feb": 0.925, "imo_answerbench": 0.91,
}
glm51 = {
    "swebench_pro": 0.584, "terminal_bench": 0.635, "deepswe": 0.18, "frontier_swe": 0.305,
    "posttrainbench": 0.201, "swe_marathon": 0.01, "nl2repo": 0.427, "programbench": 0.509,
    "mcp_atlas": 0.718, "tool_decathlon": 0.407, "hle_tools": 0.523, "aime_2026": 0.953,
    "gpqa_diamond": 0.862, "hmmt_2026_feb": 0.826, "imo_answerbench": 0.838,
}
for b, v in glm52.items():
    add("glm-5.2", b, "2026", "pass@1", v, url=GLM52, date="2026-06-16")
for b, v in glm51.items():
    add("glm-5.1", b, "2026", "pass@1", v, url=GLM52, date="2026-06-16")

# ---- Z.ai GLM-5.3 (official page + X image) ----
GLM53 = "https://z.ai/blog/glm-5.3"
add("glm-5.3", "terminal_bench", "2.1", "pass@1", 0.882, url=GLM53, date="2026-08-14")
add("glm-5.3", "terminal_bench_3", "3.0", "pass@1", 0.283, url=GLM53, date="2026-08-14")
add("glm-5.3", "deepswe", "1.1", "pass@1", 0.669, url=GLM53, date="2026-08-14")
add("glm-5.3", "nl2repo", "2026", "pass@1", 0.58, url=GLM53, date="2026-08-14")
add("glm-5.3", "programbench_almost_solved", "2026", "pass@1", 0.19, url=GLM53, date="2026-08-14")
add("glm-5.3", "posttrainbench", "2026", "pass@1", 0.398, url=GLM53, date="2026-08-14")
add("glm-5.3", "cybergym", "2026", "pass@1", 0.845, url=GLM53, date="2026-08-14")
add("glm-5.3", "exploitbench", "2026", "pass@1", 0.544, url=GLM53, date="2026-08-14")
add("glm-5.3", "toolathlon", "2026", "pass@1", 0.73, url=GLM53, date="2026-08-14")
add("glm-5.3", "automationbench", "1.0.6", "pass@1", 0.482, url=GLM53, date="2026-08-14")
add("glm-5.3", "agents_last_exam", "2026", "pass@1", 0.285, url=GLM53, date="2026-08-14")
add("glm-5.3", "hle_tools", "2026", "pass@1", 0.625, url=GLM53, date="2026-08-14")
add("glm-5.3", "gdpval_aa", "v2", "elo", 1769, unit="elo", url=GLM53, date="2026-08-14")
add("glm-5.3", "exploitgym", "2h", "count", 105, unit="count", url=GLM53, date="2026-08-14")
add("glm-5.3", "exploitgym", "6h", "count", 130, unit="count", url=GLM53, date="2026-08-14")

# ---- Qwen3.8-Max (official page) ----
QW38 = "https://qwen.ai/blog?id=qwen3.8"
qw38 = {
    "terminal_bench": 0.866, "swebench_pro": 0.677, "deepswe": 0.566, "nl2repo": 0.559,
    "frontier_swe": 0.735, "mls_bench_lite": 0.41, "paperbench": 0.93, "androidbench": 0.751,
    "qwenswebench": 0.807, "qwenqoderbench": 0.584, "coworkbench": 0.748, "workspacebench": 0.677,
    "jobbench": 0.534, "skillsbench": 0.702, "automationbench": 0.273, "toolathlon": 0.725,
    "widesearch": 0.819, "hle_tools": 0.562, "gpqa_diamond": 0.926, "hle": 0.436,
    "ifbench": 0.828, "healthbench": 0.602, "plawbench": 0.732, "prbench_legal": 0.576,
    "prbench_finance": 0.583, "mrcr_v2_256k": 0.929, "longbench_v2": 0.663,
}
for b, v in qw38.items():
    add("qwen3.8-max", b, "2026", "pass@1", v, url=QW38, date="2026-08-02")
add("qwen3.8-max", "qwenreactbench", "2026", "elo", 1724, unit="elo", url=QW38, date="2026-08-02")
add("qwen3.8-max", "qwensvgbench", "2026", "elo", 1713, unit="elo", url=QW38, date="2026-08-02")
add("qwen3.8-max", "agents_last_exam", "2026", "score", 52.4, unit="points", url=QW38, date="2026-08-02")

# ---- Qwen3.7-Max (official page) ----
QW37 = "https://qwen.ai/blog?id=qwen3.7"
qw37 = {
    "terminal_bench": 0.697, "swebench_verified": 0.804, "swebench_pro": 0.606,
    "swebench_multilingual": 0.783, "nl2repo": 0.472, "bfcl": 0.75, "mcp_mark": 0.608,
    "mcp_atlas": 0.764, "gpqa_diamond": 0.924, "hle": 0.414, "livecodebench": 0.916,
    "hmmt_2026_feb": 0.971, "imo_answerbench": 0.90,
}
for b, v in qw37.items():
    add("qwen3.7-max", b, "2026", "pass@1", v, url=QW37, date="2026-08-01")

# ---- Qwen3.7-Plus (official Alibaba page + image) ----
QW37P = "https://www.alibabacloud.com/blog/qwen3-7-plus-multimodal-agent-intelligence_603206"
qw37p = {
    "swebench_verified": 0.777, "swebench_pro": 0.576, "terminal_bench": 0.703,
    "livecodebench": 0.896, "bfcl": 0.729, "mcp_atlas": 0.732, "gpqa_diamond": 0.903,
    "osworld_verified": 0.733, "swebench_multilingual": 0.758,
}
for b, v in qw37p.items():
    add("qwen3.7-plus", b, "2026", "pass@1", v, url=QW37P, date="2026-07-01")

# ---- Qwen3.6-Plus (official page) ----
QW36 = "https://qwen.ai/blog?id=qwen3.6"
qw36 = {
    "swebench_verified": 0.788, "swebench_pro": 0.566, "swebench_multilingual": 0.738,
    "terminal_bench": 0.616, "livecodebench": 0.871, "mcp_atlas": 0.741, "gpqa_diamond": 0.904,
    "mcp_tasks": 0.741, "claw_eval": 0.588,
}
for b, v in qw36.items():
    add("qwen3.6-plus", b, "2026", "pass@1", v, url=QW36, date="2026-06-01")

# ---- Kimi K3 (official page + images) ----
K3 = "https://www.kimi.com/blog/kimi-k3"
add("kimi-k3", "deepswe", "1.1", "pass@1", 0.675, url=K3, date="2026-07-16")
add("kimi-k3", "terminal_bench", "2.1", "pass@1", 0.883, url=K3, date="2026-07-16")
add("kimi-k3", "frontier_swe", "2026", "pass@1", 0.812, url=K3, date="2026-07-16")
add("kimi-k3", "kimi_code_bench", "2.0", "pass@1", 0.729, url=K3, date="2026-07-16")
add("kimi-k3", "programbench", "2026", "pass@1", 0.778, url=K3, date="2026-07-16")
add("kimi-k3", "swe_marathon", "2026", "pass@1", 0.42, url=K3, date="2026-07-16")
add("kimi-k3", "gdpval_aa", "v2", "elo", 1668, unit="elo", url=K3, date="2026-07-16")
add("kimi-k3", "aa_briefcase", "2026", "elo", 1548, unit="elo", url=K3, date="2026-07-16")
add("kimi-k3", "jobbench", "2026", "pass@1", 0.529, url=K3, date="2026-07-16")
add("kimi-k3", "spreadsheetbench_2", "2026", "pass@1", 0.348, url=K3, date="2026-07-16")
add("kimi-k3", "automationbench", "2026", "pass@1", 0.308, url=K3, date="2026-07-16")
add("kimi-k3", "browsecomp", "2026", "pass@1", 0.912, url=K3, date="2026-07-16")
add("kimi-k3", "charxiv_rq_tool", "2026", "pass@1", 0.913, url=K3, date="2026-07-16")
add("kimi-k3", "zerobench_tool", "2026", "pass@5", 0.41, url=K3, date="2026-07-16")

# ---- Kimi K2.5 / K2.6 / K2.7-Code (official HF cards) ----
K25 = "https://huggingface.co/moonshotai/Kimi-K2.5"
add("kimi-k2.5", "swebench_verified", "2026", "pass@1", 0.768, url=K25, date="2026-02-02")
add("kimi-k2.5", "swebench_pro", "2026", "pass@1", 0.507, url=K25, date="2026-02-02")
add("kimi-k2.5", "swebench_multilingual", "2026", "pass@1", 0.73, url=K25, date="2026-02-02")
add("kimi-k2.5", "terminal_bench", "2.0", "pass@1", 0.508, url=K25, date="2026-02-02")
add("kimi-k2.5", "livecodebench", "v6", "pass@1", 0.85, url=K25, date="2026-02-02")
add("kimi-k2.5", "browsecomp", "2026", "pass@1", 0.606, url=K25, date="2026-02-02")
add("kimi-k2.5", "imo_answerbench", "2026", "pass@1", 0.818, url=K25, date="2026-02-02")

K26 = "https://huggingface.co/moonshotai/Kimi-K2.6"
k26 = {
    "swebench_verified": 0.802, "swebench_pro": 0.586, "swebench_multilingual": 0.767,
    "terminal_bench": 0.667, "livecodebench": 0.896, "browsecomp": 0.832,
    "deepsearchqa": 0.925, "widesearch": 0.808, "mcp_mark": 0.559, "claw_eval": 0.623,
    "apex_agents": 0.279, "osworld_verified": 0.731, "scicode": 0.522, "ojbench": 0.606,
    "aime_2026": 0.964, "hmmt_2026_feb": 0.927, "imo_answerbench": 0.86, "gpqa_diamond": 0.905,
    "mmmu_pro": 0.794, "charxiv_rq_tool": 0.867, "mathvision_tool": 0.932,
}
for b, v in k26.items():
    add("kimi-k2.6", b, "2026", "pass@1", v, url=K26, date="2026-04-20")

K27 = "https://huggingface.co/moonshotai/Kimi-K2.7-Code"
add("kimi-k2.7-code", "kimi_code_bench", "v2", "pass@1", 0.62, url=K27, date="2026-06-12")
add("kimi-k2.7-code", "programbench", "2026", "pass@1", 0.536, url=K27, date="2026-06-12")
add("kimi-k2.7-code", "mls_bench_lite", "2026", "pass@1", 0.351, url=K27, date="2026-06-12")
add("kimi-k2.7-code", "kimi_claw_24_7", "2026", "pass@1", 0.469, url=K27, date="2026-06-12")
add("kimi-k2.7-code", "mcp_atlas", "2026", "pass@1", 0.76, url=K27, date="2026-06-12")
add("kimi-k2.7-code", "mcp_mark_verified", "2026", "pass@1", 0.811, url=K27, date="2026-06-12")

# ---- MiniMax official pages ----
M25 = "https://www.minimax.io/news/minimax-m25"
add("minimax-m2.5", "swebench_verified", "2026", "pass@1", 0.802, url=M25, date="2026-02-12")
add("minimax-m2.5", "multi_swe_bench", "2026", "pass@1", 0.513, url=M25, date="2026-02-12")
add("minimax-m2.5", "browsecomp", "2026", "pass@1", 0.763, url=M25, date="2026-02-12")

M27 = "https://www.minimax.io/news/minimax-m27-en"
add("minimax-m2.7", "swebench_pro", "2026", "pass@1", 0.5622, url=M27, date="2026-03-20")
add("minimax-m2.7", "vibe_pro", "2026", "pass@1", 0.556, url=M27, date="2026-03-20")
add("minimax-m2.7", "terminal_bench", "2.0", "pass@1", 0.57, url=M27, date="2026-03-20")
add("minimax-m2.7", "swebench_multilingual", "2026", "pass@1", 0.765, url=M27, date="2026-03-20")
add("minimax-m2.7", "multi_swe_bench", "2026", "pass@1", 0.527, url=M27, date="2026-03-20")
add("minimax-m2.7", "nl2repo", "2026", "pass@1", 0.398, url=M27, date="2026-03-20")

M3 = "https://www.minimax.io/blog/minimax-m3"
add("minimax-m3", "swebench_pro", "2026", "pass@1", 0.59, url=M3, date="2026-06-22")
add("minimax-m3", "terminal_bench", "2.1", "pass@1", 0.66, url=M3, date="2026-06-22")
add("minimax-m3", "swe_fficiency", "2026", "pass@1", 0.348, url=M3, date="2026-06-22")
add("minimax-m3", "kernelbench_hard", "2026", "pass@1", 0.288, url=M3, date="2026-06-22")

# ---- Xiaomi MiMo official pages + image ----
MIMO25 = "https://mimo.xiaomi.com/mimo-v2-5"
add("mimo-v2.5", "mimo_coding_bench", "2026", "pass@1", 0.623, url=MIMO25, date="2026-08-01")
add("mimo-v2.5", "claw_eval", "2026", "pass@1", 0.658, url=MIMO25, date="2026-08-01")
add("mimo-v2.5", "terminal_bench", "2.0", "pass@1", 0.561, url=MIMO25, date="2026-08-01")

MIMOP = "https://mimo.xiaomi.com/mimo-v2-5-pro"
add("mimo-v2.5-pro", "swebench_pro", "2026", "pass@1", 0.572, url=MIMOP, date="2026-08-01")
add("mimo-v2.5-pro", "mimo_coding_bench", "2026", "pass@1", 0.737, url=MIMOP, date="2026-08-01")
add("mimo-v2.5-pro", "terminal_bench", "2.0", "pass@1", 0.684, url=MIMOP, date="2026-08-01")
add("mimo-v2.5-pro", "gdpval_aa", "v2", "elo", 1581, unit="elo", url=MIMOP, date="2026-08-01")
add("mimo-v2.5-pro", "tau3_bench", "2026", "pass@1", 0.729, url=MIMOP, date="2026-08-01")
add("mimo-v2.5-pro", "claw_eval", "2026", "pass@1", 0.638, url=MIMOP, date="2026-08-01")

# ---- Tencent Hunyuan official pages + images ----
HY3 = "https://github.com/Tencent-Hunyuan/Hy3"
hy3 = {
    "swebench_multilingual": 0.758, "swebench_verified": 0.78, "swebench_pro": 0.579,
    "terminal_bench": 0.717, "nl2repo": 0.456, "deepswe": 0.28, "browsecomp": 0.842,
    "widesearch": 0.764, "deepsearchqa": 0.91, "mcp_atlas": 0.791, "toolathlon": 0.485,
    "apex_agents": 0.256, "claw_eval": 0.685, "wildclawbench": 0.536, "skillsbench": 0.553,
    "hle_tools": 0.532, "gpqa_diamond": 0.904, "usamo_2026": 0.72, "imo_answerbench": 0.90,
    "frontier_science_olympiad": 0.748, "cl_bench": 0.238, "cl_bench_life": 0.17, "aa_lcr": 0.734,
}
for b, v in hy3.items():
    add("hy3", b, "2026", "pass@1", v, url=HY3, date="2026-07-06")

HY3P = "https://github.com/Tencent-Hunyuan/Hy3-preview"
add("hy3-preview", "swebench_verified", "2026", "pass@1", 0.744, url=HY3P, date="2026-04-01")
add("hy3-preview", "terminal_bench", "2.0", "pass@1", 0.544, url=HY3P, date="2026-04-01")
add("hy3-preview", "browsecomp", "2026", "pass@1", 0.671, url=HY3P, date="2026-04-01")
add("hy3-preview", "widesearch", "2026", "pass@1", 0.702, url=HY3P, date="2026-04-01")
add("hy3-preview", "livecodebench", "v6", "pass@1", 0.3486, url=HY3P, date="2026-04-01")
add("hy3-preview", "gsm8k", "2026", "pass@1", 0.9537, url=HY3P, date="2026-04-01")
add("hy3-preview", "math", "2026", "pass@1", 0.7628, url=HY3P, date="2026-04-01")
add("hy3-preview", "cruxeval_i", "2026", "pass@1", 0.7119, url=HY3P, date="2026-04-01")

# ---- Provider-linked BenchLM rows (cite maker source) ----
def pl(slug, benchmark, version, metric, value, unit="ratio", config=None, url=None, notes=None, date=None):
    add(slug, benchmark, version, metric, value, unit=unit, config=config,
        stype="provider_linked", conf="corroborated", url=url, notes=notes, date=date)

# DeepSeek V4 Flash / Pro (BenchLM cites DeepSeek-V4 technical report + API update)
DSF = "https://benchlm.ai/models/deepseek-v4-flash-0731"
pl("deepseek-v4-flash", "swebench_verified", "2026", "pass@1", 0.79, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "swebench_pro", "2026", "pass@1", 0.526, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "livecodebench", "v6", "pass@1", 0.916, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "swebench_multilingual", "2026", "pass@1", 0.733, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "terminal_bench", "2.0", "pass@1", 0.569, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "terminal_bench", "2.1", "pass@1", 0.827, config="provider run", url=DSF, notes="DeepSeek V4 Flash 0731 update")
pl("deepseek-v4-flash", "browsecomp", "2026", "pass@1", 0.732, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "mcp_atlas", "2026", "pass@1", 0.69, url=DSF, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-flash", "gpqa_diamond", "2026", "pass@1", 0.881, url=DSF, notes="DeepSeek-V4 technical report")

DSP = "https://benchlm.ai/models/deepseek-v4-pro-0813"
pl("deepseek-v4-pro", "swebench_verified", "2026", "pass@1", 0.806, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "swebench_pro", "2026", "pass@1", 0.554, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "livecodebench", "v6", "pass@1", 0.935, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "swebench_multilingual", "2026", "pass@1", 0.762, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "terminal_bench", "2.0", "pass@1", 0.679, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "terminal_bench", "2.1", "pass@1", 0.879, config="provider run", url=DSP, notes="DeepSeek V4 Pro 0813 API update")
pl("deepseek-v4-pro", "browsecomp", "2026", "pass@1", 0.834, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "mcp_atlas", "2026", "pass@1", 0.736, url=DSP, notes="DeepSeek-V4 technical report")
pl("deepseek-v4-pro", "gpqa_diamond", "2026", "pass@1", 0.901, url=DSP, notes="DeepSeek-V4 technical report")

# Grok 4.5 (BenchLM cites xAI launch post)
GR = "https://benchlm.ai/models/grok-4-5"
pl("grok-4.5", "swebench_pro", "2026", "pass@1", 0.647, url=GR, notes="xAI Grok 4.5 launch post")
pl("grok-4.5", "swebench_multilingual", "2026", "pass@1", 0.78, url=GR, notes="Cursor Grok 4.5 launch post")
pl("grok-4.5", "terminal_bench", "2.0", "pass@1", 0.833, url=GR, notes="xAI Grok 4.5 launch post")

# MiniMax M3 extras (BenchLM cites MiniMax M3 blog)
M3B = "https://benchlm.ai/models/minimax-m3"
pl("minimax-m3", "swebench_verified", "2026", "pass@1", 0.805, url=M3B, notes="MiniMax M3 blog")
pl("minimax-m3", "osworld_verified", "2026", "pass@1", 0.701, url=M3B, notes="MiniMax M3 blog")
pl("minimax-m3", "browsecomp", "2026", "pass@1", 0.835, url=M3B, notes="MiniMax M3 blog")
pl("minimax-m3", "mcp_atlas", "2026", "pass@1", 0.742, url=M3B, notes="MiniMax M3 blog")
pl("minimax-m3", "claw_eval", "2026", "pass@1", 0.745, url=M3B, notes="MiniMax M3 blog")

# MiMo V2 Omni / V2 Pro (BenchLM reported rows)
pl("mimo-v2-omni", "swebench_verified", "2026", "pass@1", 0.748, url="https://benchlm.ai/models/mimo-v2-omni", notes="Reported upstream source")
pl("mimo-v2-omni", "claw_eval", "2026", "pass@1", 0.452, url="https://benchlm.ai/models/mimo-v2-omni", notes="Claw-Eval leaderboard")
pl("mimo-v2-pro", "swebench_verified", "2026", "pass@1", 0.78, url="https://benchlm.ai/models/mimo-v2-pro", notes="Reported upstream source")
pl("mimo-v2-pro", "claw_eval", "2026", "pass@1", 0.578, url="https://benchlm.ai/models/mimo-v2-pro", notes="Claw-Eval leaderboard")

# Qwen3.5 Plus (BenchLM rows)
pl("qwen3.5-plus", "vibe_code_bench", "v1.1", "pass@1", 0.1574, url="https://benchlm.ai/models/qwen3-5-plus", notes="Vals AI Vibe Code Bench")
pl("qwen3.5-plus", "jobbench", "2026", "pass@1", 0.185, url="https://benchlm.ai/models/qwen3-5-plus", notes="JobBench paper")
pl("qwen3.5-plus", "frontiermath_t1_3", "v2", "pass@1", 0.21034, url="https://benchlm.ai/models/qwen3-5-plus", notes="Epoch AI FrontierMath v2")

# GLM-5 (BenchLM cites Z.AI docs)
pl("glm-5", "swebench_verified", "2026", "pass@1", 0.778, url="https://benchlm.ai/models/glm-5", notes="Z.AI GLM-5 docs")
pl("glm-5", "swebench_pro", "2026", "pass@1", 0.551, url="https://benchlm.ai/models/glm-5", notes="Qwen3.6-Plus comparison table")
pl("glm-5", "terminal_bench", "2.0", "pass@1", 0.562, url="https://benchlm.ai/models/glm-5", notes="Z.AI GLM-5 docs")
pl("glm-5", "gpqa_diamond", "2026", "pass@1", 0.86, url="https://benchlm.ai/models/glm-5", notes="Qwen3.6-Plus comparison table")

payload = {
    "source_url": "https://benchlm.ai/models",
    "source_type": "official_maker",
    "rows": rows,
}
OUT.write_text(json.dumps(payload, indent=2))
print(f"wrote {OUT} with {len(rows)} rows")
