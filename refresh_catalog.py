#!/usr/bin/env python3
"""Refresh the AI model index from official provider model endpoints.

Secrets are read only from environment variables and never written to disk.
The database intentionally distinguishes free pricing from free-tier access.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
SNAPSHOTS = ROOT / "snapshots"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_json(url: str, env_var: str | None = None, headers: dict[str, str] | None = None):
    h = {"User-Agent": "AZ-Labs-aimi/1.0"}
    if env_var and os.getenv(env_var):
        h["Authorization"] = f"Bearer {os.environ[env_var]}"
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
        return json.loads(raw), response.status, raw


def category(model_id: str, name: str = "") -> str:
    s = f"{model_id} {name}".lower()
    if any(x in s for x in ("embed", "embedding")): return "embedding"
    if any(x in s for x in ("image", "imagen", "flux")): return "image"
    if any(x in s for x in ("video", "veo")): return "video"
    if any(x in s for x in ("tts", "audio", "voxtral", "speech", "whisper")): return "audio"
    if any(x in s for x in ("vision", "vl", "scout")): return "vision"
    if any(x in s for x in ("code", "coder", "codestral", "devstral", "fim")): return "code"
    if any(x in s for x in ("reason", "o1", "o3", "o4", "thinking", "magistral")): return "reasoning"
    if any(x in s for x in ("moderation", "guard", "safety")): return "safety"
    return "chat"


def pricing(provider: str, item: dict) -> tuple[str, int, str, str]:
    mid = item.get("id", "")
    if provider == "openrouter":
        p = item.get("pricing", {})
        if p.get("prompt") == "0" and p.get("completion") == "0":
            return "free", 1, "high", "Official OpenRouter pricing.prompt=0 and pricing.completion=0"
        return "paid", 0, "high", "Official OpenRouter pricing is non-zero"
    if provider == "opencode-zen":
        if mid.endswith("-free"):
            return "free", 1, "high", "Official OpenCode Zen model ID explicitly ends in -free"
        return "unknown", 0, "low", "Official model endpoint does not expose pricing"
    if provider == "gemini": return "free_tier", 0, "medium", "Official Gemini model endpoint; quota/free-tier access is model and account dependent"
    if provider == "cloudflare-ai": return "free_tier", 0, "medium", "Official Workers AI catalogue; account quota/pricing must be checked separately"
    if provider in {"openai", "mistral", "deepseek"}: return "paid", 0, "medium", "Official model endpoint does not establish zero-price access"
    if provider == "nvidia-nim": return "unknown", 0, "low", "Official NIM models endpoint does not expose pricing"
    return "unknown", 0, "low", "No pricing evidence"


PROVIDERS = {
    "openrouter": ("https://openrouter.ai/api/v1/models", "OPENROUTER_API_KEY"),
    "opencode-zen": ("https://opencode.ai/zen/v1/models", "OPENCODE_API_KEY"),
    "nvidia-nim": ("https://integrate.api.nvidia.com/v1/models", "NVIDIA_API_KEY"),
    "deepseek": ("https://api.deepseek.com/v1/models", "DEEPSEEK_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1/models", "MISTRAL_API_KEY"),
    "openai": ("https://api.openai.com/v1/models", "OPENAI_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models?key=" + os.getenv("GEMINI_API_KEY", ""), None),
}
if os.getenv("CLOUDFLARE_API_TOKEN_AZLABS_AI_WORKERS") and os.getenv("CLOUDFLARE_ACCOUNT_ID"):
    PROVIDERS["cloudflare-ai"] = (f"https://api.cloudflare.com/client/v4/accounts/{os.environ['CLOUDFLARE_ACCOUNT_ID']}/ai/models/search?per_page=200", "CLOUDFLARE_API_TOKEN_AZLABS_AI_WORKERS")


def normalise(provider: str, payload: dict) -> list[dict]:
    if provider == "cloudflare-ai":
        return payload.get("result", [])
    return payload.get("data", payload.get("models", []))


def main() -> int:
    SNAPSHOTS.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys=ON")
    # Safe compatibility migration for databases created before this script.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(models)")}
    if "category" not in cols:
        conn.execute("ALTER TABLE models ADD COLUMN category TEXT")
        conn.execute("UPDATE models SET category=catagory WHERE category IS NULL")
    failures = []
    total = 0
    for provider, (url, env_var) in PROVIDERS.items():
        if env_var and not os.getenv(env_var):
            failures.append(f"{provider}: missing {env_var}")
            continue
        try:
            payload, status, raw = get_json(url, env_var)
            source_url = url.split('?key=')[0]
            items = normalise(provider, payload)
        except Exception as exc:  # refresh should continue for other providers
            failures.append(f"{provider}: {exc}")
            continue
        digest = hashlib.sha256(raw).hexdigest()
        snap = SNAPSHOTS / f"{provider}-{NOW[:10]}.json"
        snap.write_bytes(raw)
        conn.execute("INSERT INTO model_sources(provider_id,endpoint,fetched_at,http_status,response_sha256,raw_snapshot_path,record_count) VALUES (?,?,?,?,?,?,?)",
                     (provider, source_url, NOW, status, digest, str(snap), len(items)))
        for item in items:
            # Cloudflare's UUID is catalogue metadata; the callable model ID is its name.
            mid = (item.get("name") or item.get("id")) if provider == "cloudflare-ai" else (item.get("id") or item.get("name"))
            if not mid: continue
            name = item.get("name") or item.get("displayName") or mid
            # Gemini names are models/foo; preserve API ID but use readable name.
            display = item.get("display_name") or item.get("displayName") or name
            ctx = item.get("context_length") or item.get("max_context_length") or item.get("inputTokenLimit")
            out = item.get("outputTokenLimit") or item.get("top_provider", {}).get("max_completion_tokens")
            caps = item.get("capabilities", {})
            cat = category(mid, display)
            status_name, free, confidence, evidence = pricing(provider, item)
            base = {
                "openrouter": "https://openrouter.ai/api/v1",
                "opencode-zen": "https://opencode.ai/zen/v1",
                "nvidia-nim": "https://integrate.api.nvidia.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "mistral": "https://api.mistral.ai/v1",
                "openai": "https://api.openai.com/v1",
                "gemini": "https://generativelanguage.googleapis.com/v1beta",
            }.get(provider)
            auth = {"openrouter":"OPENROUTER_API_KEY","opencode-zen":"OPENCODE_API_KEY","nvidia-nim":"NVIDIA_API_KEY","deepseek":"DEEPSEEK_API_KEY","mistral":"MISTRAL_API_KEY","openai":"OPENAI_API_KEY","gemini":"GEMINI_API_KEY"}.get(provider)
            conn.execute("""INSERT INTO models(model_id,provider,free_pricing,context_window,display_name,description,last_verified_at,catagory,category,pricing_status,pricing_unit,pricing_evidence,source_endpoint,api_style,base_url,auth_env_var,max_output_tokens,supports_reasoning,supports_tools,supports_structured_output,supports_streaming,verification_confidence)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(model_id) DO UPDATE SET provider=excluded.provider, free_pricing=excluded.free_pricing, context_window=COALESCE(excluded.context_window,models.context_window), display_name=excluded.display_name, description=excluded.description, last_verified_at=excluded.last_verified_at, catagory=excluded.catagory, category=excluded.category, pricing_status=excluded.pricing_status, pricing_unit=excluded.pricing_unit, pricing_evidence=excluded.pricing_evidence, source_endpoint=excluded.source_endpoint, api_style=excluded.api_style, base_url=excluded.base_url, auth_env_var=excluded.auth_env_var, max_output_tokens=COALESCE(excluded.max_output_tokens,models.max_output_tokens), supports_reasoning=COALESCE(excluded.supports_reasoning,models.supports_reasoning), supports_tools=COALESCE(excluded.supports_tools,models.supports_tools), supports_structured_output=COALESCE(excluded.supports_structured_output,models.supports_structured_output), verification_confidence=excluded.verification_confidence""",
                (mid, provider, free, ctx, display, item.get("description"), NOW, cat, cat, status_name, "per-token" if provider in {"openrouter","openai","mistral","deepseek"} else "provider-defined", evidence, source_url, "google-generative-ai" if provider == "gemini" else "cloudflare-ai" if provider == "cloudflare-ai" else "openai-completions", base, auth, out, int(bool(item.get("thinking") or caps.get("reasoning"))) if (item.get("thinking") is not None or "reasoning" in caps) else None, int(bool(caps.get("function_calling") or caps.get("completion_chat"))) if caps else None, 1 if caps.get("function_calling") else None, 1 if provider != "cloudflare-ai" else None, confidence))
            rowid = conn.execute("SELECT id FROM models WHERE model_id=?", (mid,)).fetchone()[0]
            conn.execute("""INSERT INTO model_capabilities(model_id,context_window_tokens,max_input_tokens,max_output_tokens,input_modalities,output_modalities,reasoning,tools,function_calling,structured_outputs,streaming,vision,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(model_id) DO UPDATE SET context_window_tokens=COALESCE(excluded.context_window_tokens,model_capabilities.context_window_tokens),max_input_tokens=COALESCE(excluded.max_input_tokens,model_capabilities.max_input_tokens),max_output_tokens=COALESCE(excluded.max_output_tokens,model_capabilities.max_output_tokens),reasoning=COALESCE(excluded.reasoning,model_capabilities.reasoning),tools=COALESCE(excluded.tools,model_capabilities.tools),function_calling=COALESCE(excluded.function_calling,model_capabilities.function_calling),vision=COALESCE(excluded.vision,model_capabilities.vision)""",
                         (rowid, ctx, item.get("inputTokenLimit"), out, json.dumps(item.get("architecture", {}).get("input_modalities", ["text"])), json.dumps(item.get("architecture", {}).get("output_modalities", ["text"])), int(bool(item.get("thinking") or caps.get("reasoning"))) if (item.get("thinking") is not None or "reasoning" in caps) else None, int(bool(caps.get("function_calling"))) if caps else None, int(bool(caps.get("function_calling"))) if caps else None, None, 1, int(bool(caps.get("vision"))) if "vision" in caps else None, item.get("deprecation")))
            total += 1
        conn.commit()
    conn.commit()
    print(json.dumps({"refreshed_records": total, "db": str(DB), "failures": failures}, indent=2))
    return 0 if not failures else 2

if __name__ == "__main__":
    raise SystemExit(main())
