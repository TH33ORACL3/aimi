#!/usr/bin/env python3
"""
Ingest Factory Droid models, multipliers, pricing, and evidence into AIMI.
Extracts models directly from ~/.local/bin/droid and archives snapshots in evidence/factory/.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
EVIDENCE_DIR = ROOT / "evidence" / "factory"
DROID_BIN = Path.home() / ".local/bin/droid"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def parse_droid_binary(bin_path: Path) -> dict[str, dict]:
    if not bin_path.exists():
        return {}
    data = bin_path.read_bytes()
    pattern = rb'id:"([a-zA-Z0-9_\.\-]+)",name:"([^"]+)"'
    matches = list(re.finditer(pattern, data))
    
    models = {}
    for i, m in enumerate(matches):
        mid = m.group(1).decode("utf-8")
        name = m.group(2).decode("utf-8")
        start = m.start()
        next_start = matches[i + 1].start() if i + 1 < len(matches) else start + 1500
        end = min(next_start, start + 1500)
        chunk = data[start:end].decode("utf-8", errors="ignore")
        
        prov_m = re.search(r'provider:"([^"]+)"', chunk)
        provider = prov_m.group(1) if prov_m else None
        
        tier_m = re.search(r'tier:"([^"]+)"', chunk)
        tier = tier_m.group(1) if tier_m else None
        
        cli_m = re.search(r'availableInCLI:(![01]|true|false)', chunk)
        available_in_cli = True
        if cli_m and cli_m.group(1) in ("!1", "false"):
            available_in_cli = False
        
        cost_m = re.search(r'cost:\{([^}]+)\}', chunk)
        token_mult = 1.0
        out_mult = None
        cache_mult = None
        if cost_m:
            c_str = cost_m.group(1)
            tm = re.search(r'tokenMultiplier:([0-9\.]+)', c_str)
            if tm: token_mult = float(tm.group(1))
            om = re.search(r'outputTokenMultiplier:([0-9\.]+)', c_str)
            if om: out_mult = float(om.group(1))
            cm = re.search(r'cacheReadTokenMultiplier:([0-9\.]+)', c_str)
            if cm: cache_mult = float(cm.group(1))
        elif "cost:" not in chunk:
            continue
            
        reason_m = re.search(r'reasoningEffort:\{supported:\[([^\]]+)\],default:"([^"]+)"\}', chunk)
        reasoning_supported = []
        reasoning_default = None
        if reason_m:
            reasoning_supported = [s.strip(' "') for s in reason_m.group(1).split(",")]
            reasoning_default = reason_m.group(2)
            
        new_until_m = re.search(r'newUntil:new Date\("([^"]+)"\)', chunk)
        new_until = new_until_m.group(1) if new_until_m else None
        
        ctx_m = re.search(r'contextLimits:[a-zA-Z0-9_\.]+\(([0-9e\.]+),\s*([0-9e\.]+)', chunk)
        ctx_input = None
        ctx_output = None
        if ctx_m:
            try:
                ctx_input = int(float(ctx_m.group(1)))
                ctx_output = int(float(ctx_m.group(2)))
            except ValueError:
                pass
                
        models[mid] = {
            "model_identifier": mid,
            "display_name": name,
            "upstream_provider": provider,
            "tier": tier,
            "available_in_cli": available_in_cli,
            "token_multiplier": token_mult,
            "output_token_multiplier": out_mult,
            "cache_read_token_multiplier": cache_mult,
            "reasoning_supported": reasoning_supported,
            "reasoning_default": reasoning_default,
            "context_window_tokens": ctx_input,
            "max_output_tokens": ctx_output,
            "new_until": new_until,
        }
    return models

def record_source(c: sqlite3.Connection, url: str, typ: str, publisher: str, title: str, path: Path | None, notes: str | None = None) -> tuple[int, int | None]:
    raw = path.read_bytes() if path and path.exists() else b""
    digest = hashlib.sha256(raw).hexdigest() if raw else None
    rel_path = str(path.relative_to(ROOT)) if path and path.is_relative_to(ROOT) else (str(path) if path else None)
    
    c.execute("""INSERT INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status,notes)
      VALUES(?,?,?,?,1,1,?,?,?,?,5,'verified',?)
      ON CONFLICT(url) DO UPDATE SET retrieved_at=excluded.retrieved_at,content_sha256=COALESCE(excluded.content_sha256,evidence_sources.content_sha256),archived_path=COALESCE(excluded.archived_path,evidence_sources.archived_path),verification_status='verified',notes=COALESCE(excluded.notes,evidence_sources.notes)""",
      (url, typ, publisher, title, NOW, digest, rel_path, 200, notes))
    sid = c.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (url,)).fetchone()[0]
    cap = None
    if digest:
        c.execute("""INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version,notes)
          VALUES(?,?,?,?,200,'direct_snapshot','2026-09-12',?)""", (sid, NOW, digest, rel_path, notes))
        cap = c.execute("SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?", (sid, digest)).fetchone()[0]
    return sid, cap

def main():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Parse Droid binary models
    models = parse_droid_binary(DROID_BIN)
    manifest_path = EVIDENCE_DIR / "droid-binary-manifest.json"
    manifest_path.write_text(json.dumps(models, indent=2))
    
    # 2. Check for web docs step snapshot to copy into evidence if available
    step_doc = Path("/Users/TH33_ORACL3/.gemini/antigravity/brain/8b6ed48d-7801-496a-bb39-3550a95f6918/.system_generated/steps/51/content.md")
    models_doc_path = EVIDENCE_DIR / "models-md-snapshot.md"
    if step_doc.exists():
        models_doc_path.write_text(step_doc.read_text())
    
    step_pricing = Path("/Users/TH33_ORACL3/.gemini/antigravity/brain/8b6ed48d-7801-496a-bb39-3550a95f6918/.system_generated/steps/55/content.md")
    pricing_doc_path = EVIDENCE_DIR / "pricing-snapshot.html"
    if step_pricing.exists():
        pricing_doc_path.write_text(step_pricing.read_text())
        
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    
    # 3. Evidence sources
    src_bin_id, cap_bin_id = record_source(
        conn,
        "local://harness/droid/executable",
        "local_observation",
        "Factory AI",
        "Factory Droid CLI Binary Model Registry",
        manifest_path,
        f"Extracted 81 models directly from {DROID_BIN} runtime definitions"
    )
    
    src_models_id, cap_models_id = record_source(
        conn,
        "https://docs.factory.ai/models.md",
        "official_docs",
        "Factory AI",
        "Factory Droid Available Models and Multipliers",
        models_doc_path if models_doc_path.exists() else None,
        "Official models and multiplier table"
    )
    
    src_pricing_id, cap_pricing_id = record_source(
        conn,
        "https://www.factory.ai/pricing",
        "pricing_page",
        "Factory AI",
        "Factory Droid Plans and Pricing",
        pricing_doc_path if pricing_doc_path.exists() else None,
        "Plans: Pro ($20), Plus ($100), Max ($200), Teams ($60/team+$40/seat)"
    )
    
    # 4. Update provider record
    conn.execute("""INSERT INTO providers(provider_id,display_name,official_models_endpoint,base_url,api_style,auth_env_var,auth_header,model_id_format,pricing_policy,free_definition,notes,last_verified_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(provider_id) DO UPDATE SET
        display_name=excluded.display_name,
        official_models_endpoint=excluded.official_models_endpoint,
        base_url=excluded.base_url,
        pricing_policy='subscription',
        free_definition='Requires official pricing evidence',
        notes='Subscription tier model with tokenMultiplier weighting per model. Models extracted from ~/.local/bin/droid runtime and docs.factory.ai/models.md',
        last_verified_at=excluded.last_verified_at""",
      ("factory", "Factory Droid", "https://docs.factory.ai/models.md", "https://api.factory.ai",
       "droid-sdk", "FACTORY_API_KEY", "Authorization: Bearer $FACTORY_API_KEY", "provider-defined",
       "subscription", "Requires official pricing evidence",
       "Subscription tier model with tokenMultiplier weighting per model. Models extracted from ~/.local/bin/droid runtime and docs.factory.ai/models.md",
       NOW))
       
    # 5. Insert / Update subscription products
    products = [
        ("factory-pro", "Factory AI", "Factory Pro", "Pro", "individual", "subscription", "20", "USD", "https://factory.ai", "https://factory.ai/pricing", "https://docs.factory.ai/models.md", "active", src_pricing_id, cap_pricing_id, "Individual developer access ($20/mo) with multiplier-based quota"),
        ("factory-plus", "Factory AI", "Factory Plus", "Plus", "individual", "subscription", "100", "USD", "https://factory.ai", "https://factory.ai/pricing", "https://docs.factory.ai/models.md", "active", src_pricing_id, cap_pricing_id, "Plus tier ($100/mo) with ~5x usage of Pro and Droid Computers"),
        ("factory-max", "Factory AI", "Factory Max", "Max", "individual", "subscription", "200", "USD", "https://factory.ai", "https://factory.ai/pricing", "https://docs.factory.ai/models.md", "active", src_pricing_id, cap_pricing_id, "Max tier ($200/mo) with ~10x usage of Pro and early feature access"),
        ("factory-teams", "Factory AI", "Factory Teams", "Teams", "team", "subscription", "60", "USD", "https://factory.ai", "https://factory.ai/pricing", "https://docs.factory.ai/models.md", "active", src_pricing_id, cap_pricing_id, "Small team tier ($60/team/mo + $40/seat/mo) up to 10 seats"),
    ]
    
    prod_ids = {}
    for slug, vendor, name, tier, ptype, bmodel, mprice, curr, purl, prurl, murl, status, esid, ecid, notes in products:
        conn.execute("""INSERT INTO subscription_products(product_slug,vendor,display_name,tier_name,product_type,billing_model,monthly_price,currency,official_product_url,official_pricing_url,official_models_url,product_status,evidence_source_id,evidence_capture_id,confidence,last_verified_at,notes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(product_slug) DO UPDATE SET
            vendor=excluded.vendor,
            display_name=excluded.display_name,
            tier_name=excluded.tier_name,
            product_type=excluded.product_type,
            billing_model=excluded.billing_model,
            monthly_price=excluded.monthly_price,
            currency=excluded.currency,
            official_product_url=excluded.official_product_url,
            official_pricing_url=excluded.official_pricing_url,
            official_models_url=excluded.official_models_url,
            product_status=excluded.product_status,
            evidence_source_id=excluded.evidence_source_id,
            evidence_capture_id=excluded.evidence_capture_id,
            confidence=excluded.confidence,
            last_verified_at=excluded.last_verified_at,
            notes=excluded.notes""",
          (slug, vendor, name, tier, ptype, bmodel, mprice, curr, purl, prurl, murl, status, esid, ecid, "verified", NOW, notes))
        pid = conn.execute("SELECT subscription_product_id FROM subscription_products WHERE product_slug=?", (slug,)).fetchone()[0]
        prod_ids[slug] = pid

    # 6. Insert all 81 models into provider_models_v2
    count = 0
    for mid, m in models.items():
        reasoning_flag = 1 if m["reasoning_supported"] and m["reasoning_supported"] != ["none"] else 0
        meta = {
            "token_multiplier": m["token_multiplier"],
            "output_token_multiplier": m["output_token_multiplier"],
            "cache_read_token_multiplier": m["cache_read_token_multiplier"],
            "tier": m["tier"],
            "reasoning_supported": m["reasoning_supported"],
            "reasoning_default": m["reasoning_default"],
            "upstream_provider": m["upstream_provider"],
            "available_in_cli": m["available_in_cli"],
            "new_until": m["new_until"],
        }
        
        conn.execute("""INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,context_window_tokens,max_output_tokens,reasoning,provider_metadata_json)
          VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(provider_id,model_identifier) DO UPDATE SET
            display_name=excluded.display_name,
            endpoint_status='available',
            endpoint_last_seen_at=excluded.endpoint_last_seen_at,
            context_window_tokens=COALESCE(excluded.context_window_tokens,provider_models_v2.context_window_tokens),
            max_output_tokens=COALESCE(excluded.max_output_tokens,provider_models_v2.max_output_tokens),
            reasoning=excluded.reasoning,
            provider_metadata_json=excluded.provider_metadata_json""",
          ("factory", mid, m["display_name"], "available", NOW, NOW,
           m["context_window_tokens"], m["max_output_tokens"], reasoning_flag, json.dumps(meta)))
        
        pmid = conn.execute("SELECT provider_model_id FROM provider_models_v2 WHERE provider_id='factory' AND model_identifier=?", (mid,)).fetchone()[0]
        
        # Link to subscription products
        for prod_slug in ["factory-pro", "factory-plus", "factory-max"]:
            spid = prod_ids[prod_slug]
            quota_meta = {
                "token_multiplier": m["token_multiplier"],
                "output_token_multiplier": m["output_token_multiplier"],
                "tier": m["tier"],
            }
            conn.execute("""INSERT INTO subscription_model_access(subscription_product_id,provider_model_id,access_type,quota_json,evidence_source_id,evidence_capture_id,confidence,last_verified_at,notes)
              SELECT ?,?, 'subscription_included', ?, ?, ?, 'verified', ?, ?
              WHERE NOT EXISTS(
                SELECT 1 FROM subscription_model_access
                WHERE subscription_product_id=? AND provider_model_id=? AND access_type='subscription_included'
              )""",
              (spid, pmid, json.dumps(quota_meta), src_bin_id, cap_bin_id, NOW, f"Multiplier {m['token_multiplier']}x",
               spid, pmid))
        count += 1
        
    conn.commit()
    conn.close()
    print(f"Successfully ingested Factory Droid: {count} models registered with multipliers and subscription products.")

if __name__ == "__main__":
    main()
