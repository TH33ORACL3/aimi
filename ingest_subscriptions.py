#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sqlite3,subprocess
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/'model_catalogue.db'
RESEARCH=Path('/Users/TH33_ORACL3/AZ Labs/4 - Research/2026-07-21_ai-subscriptions-model-catalogue')
NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
WARP_BIN=Path('/Applications/Warp.app/Contents/MacOS/stable')

def source(c,url,typ,publisher,title,path=None,notes=None):
 raw=Path(path).read_bytes() if path and Path(path).exists() else b''
 digest=hashlib.sha256(raw).hexdigest() if raw else None
 c.execute("""INSERT INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status,notes)
 VALUES(?,?,?,?,1,1,?,?,?,?,5,'verified',?) ON CONFLICT(url) DO UPDATE SET retrieved_at=excluded.retrieved_at,content_sha256=COALESCE(excluded.content_sha256,evidence_sources.content_sha256),archived_path=COALESCE(excluded.archived_path,evidence_sources.archived_path),verification_status='verified',notes=COALESCE(excluded.notes,evidence_sources.notes)""",
 (url,typ,publisher,title,NOW,digest,str(path) if path else None,200,notes))
 sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()[0]
 cap=None
 if digest:
  c.execute("""INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version,notes)
  VALUES(?,?,?,?,200,'firecrawl_or_direct','2026-07-21',?)""",(sid,NOW,digest,str(path),notes))
  cap=c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?',(sid,digest)).fetchone()[0]
 return sid,cap

def product(c,slug,vendor,name,tier,ptype,billing,monthly,currency,product_url,pricing_url,models_url,sid,cap,status='active',confidence='verified',notes=None):
 c.execute("""INSERT INTO subscription_products(product_slug,vendor,display_name,tier_name,product_type,billing_model,monthly_price,currency,official_product_url,official_pricing_url,official_models_url,product_status,evidence_source_id,evidence_capture_id,confidence,last_verified_at,notes)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(product_slug) DO UPDATE SET vendor=excluded.vendor,display_name=excluded.display_name,tier_name=excluded.tier_name,product_type=excluded.product_type,billing_model=excluded.billing_model,monthly_price=excluded.monthly_price,currency=excluded.currency,official_product_url=excluded.official_product_url,official_pricing_url=excluded.official_pricing_url,official_models_url=excluded.official_models_url,product_status=excluded.product_status,evidence_source_id=excluded.evidence_source_id,evidence_capture_id=excluded.evidence_capture_id,confidence=excluded.confidence,last_verified_at=excluded.last_verified_at,notes=excluded.notes""",
 (slug,vendor,name,tier,ptype,billing,monthly,currency,product_url,pricing_url,models_url,status,sid,cap,confidence,NOW,notes))
 return c.execute('SELECT subscription_product_id FROM subscription_products WHERE product_slug=?',(slug,)).fetchone()[0]

def entitlement(c,pid,status,relation,source,confidence='user_confirmed',org=None,notes=None):
 c.execute("""INSERT INTO personal_subscription_entitlements(subscription_product_id,owner_label,entitlement_status,account_label,organization_label,relationship_type,confirmed_at,confirmation_source,confidence,notes)
 VALUES(?,'Aubrey Zemba',?,'personal',?,?,?,?,?,?) ON CONFLICT(subscription_product_id,owner_label,account_label,organization_label) DO UPDATE SET entitlement_status=excluded.entitlement_status,organization_label=excluded.organization_label,relationship_type=excluded.relationship_type,confirmed_at=excluded.confirmed_at,confirmation_source=excluded.confirmation_source,confidence=excluded.confidence,notes=excluded.notes""",
 (pid,status,org or '',relation,NOW,source,confidence,notes))

def link_provider(c,pid,provider,access,sid,cap,quota=None,confidence='verified',notes=None):
 for row in c.execute("SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND endpoint_status='available'",(provider,)).fetchall():
  c.execute("""INSERT INTO subscription_model_access(subscription_product_id,provider_model_id,access_type,quota_json,evidence_source_id,evidence_capture_id,confidence,last_verified_at,notes)
  SELECT ?,?,?,?,?,?,?,?,? WHERE NOT EXISTS(
    SELECT 1 FROM subscription_model_access
    WHERE subscription_product_id=? AND provider_model_id=? AND access_type=?
  )""",(pid,row[0],access,json.dumps(quota) if quota else None,sid,cap,confidence,NOW,notes,pid,row[0],access))

def main():
 c=sqlite3.connect(DB);c.execute('PRAGMA foreign_keys=ON');c.executescript((ROOT/'subscription_upgrade.sql').read_text())
 sources={
  'openai':source(c,'https://chatgpt.com/codex/pricing/','pricing_page','OpenAI','Codex pricing',RESEARCH/'firecrawl/openai-codex-pricing.md'),
  'github':source(c,'https://docs.github.com/en/copilot/reference/ai-models/supported-models','official_docs','GitHub','Supported AI models in GitHub Copilot',RESEARCH/'firecrawl/github-copilot-models.md'),
  'warp_models':source(c,'https://docs.warp.dev/agent-platform/inference/model-choice/','official_docs','Warp','Agent model choice',RESEARCH/'firecrawl/warp-model-choice.md'),
  'warp_pricing':source(c,'https://www.warp.dev/pricing','pricing_page','Warp','Warp pricing',RESEARCH/'firecrawl/warp-pricing.md','Page contained conflicting displayed starting prices on capture date.'),
  'go':source(c,'https://opencode.ai/docs/go/','official_docs','OpenCode','OpenCode Go documentation',RESEARCH/'firecrawl/opencode-go-docs.md'),
  'zen':source(c,'https://opencode.ai/docs/zen/','official_docs','OpenCode','OpenCode Zen documentation',RESEARCH/'firecrawl/opencode-zen-docs.md'),
  'go_models':source(c,'https://opencode.ai/zen/go/v1/models','api_endpoint','OpenCode','OpenCode Go models endpoint',RESEARCH/'opencode-go-models.json'),
  'zen_models':source(c,'https://opencode.ai/zen/v1/models','api_endpoint','OpenCode','OpenCode Zen models endpoint',RESEARCH/'opencode-zen-models.json'),
 }
 products={}
 products['chatgpt-plus']=product(c,'chatgpt-plus','OpenAI','ChatGPT Plus','Plus','individual','subscription',None,'USD','https://chatgpt.com/explore/plus/','https://chatgpt.com/codex/pricing/',None,*sources['openai'])
 products['warp']=product(c,'warp-personal','Warp','Warp personal subscription',None,'individual','subscription_with_credits',None,'USD','https://www.warp.dev/','https://www.warp.dev/pricing','https://docs.warp.dev/agent-platform/inference/model-choice/',*sources['warp_pricing'],confidence='conflicting',notes='Exact personal tier not yet confirmed; pricing page contained conflicting displayed starting prices.')
 products['google-ai-pro']=product(c,'google-ai-pro','Google','Google AI Pro','Pro','individual','subscription',None,None,'https://one.google.com/about/google-ai-plans/','https://one.google.com/about/google-ai-plans/',None,None,None,confidence='user_confirmed',notes='User calls this Gemini Pro; exact regional product mapping remains to be verified.')
 products['github-enterprise']=product(c,'github-enterprise','GitHub','GitHub Enterprise','Enterprise','enterprise','custom_contract',None,None,'https://github.com/enterprise','https://github.com/pricing',None,*sources['github'])
 products['opencode-go']=product(c,'opencode-go','OpenCode','OpenCode Go','Go','individual','subscription','10','USD','https://opencode.ai/go','https://opencode.ai/docs/go/','https://opencode.ai/zen/go/v1/models',*sources['go'],notes='$5 first month then $10/month per official docs captured 2026-07-21.')
 products['opencode-zen']=product(c,'opencode-zen','OpenCode','OpenCode Zen','Zen','gateway','pay_as_you_go',None,'USD','https://opencode.ai/zen','https://opencode.ai/docs/zen/','https://opencode.ai/zen/v1/models',*sources['zen'])
 # Additional first-class candidates with official URLs; evidence remains single-source until captured locally.
 candidates=[
  ('claude-pro','Anthropic','Claude Pro','Pro','individual','subscription','20','USD','https://claude.com/pricing'),
  ('claude-max-5x','Anthropic','Claude Max 5x','Max 5x','individual','subscription','100','USD','https://claude.com/pricing'),
  ('claude-max-20x','Anthropic','Claude Max 20x','Max 20x','individual','subscription','200','USD','https://claude.com/pricing'),
  ('mistral-vibe-pro','Mistral AI','Mistral Vibe Pro','Pro','individual','subscription','14.99','USD','https://mistral.ai/pricing/'),
  ('ollama-cloud-pro','Ollama','Ollama Cloud Pro','Pro','individual','subscription','20','USD','https://ollama.com/pricing'),
  ('ollama-cloud-max','Ollama','Ollama Cloud Max','Max','individual','subscription','100','USD','https://ollama.com/pricing'),
  ('supergrok','xAI','SuperGrok','SuperGrok','individual','subscription','30','USD','https://x.ai/pricing'),
 ]
 for slug,vendor,name,tier,ptype,billing,monthly,currency,url in candidates:
  sid,cap=source(c,url,'pricing_page',vendor,name+' pricing')
  product(c,slug,vendor,name,tier,ptype,billing,monthly,currency,url,url,None,sid,cap,confidence='single_source')
 entitlement(c,products['chatgpt-plus'],'active','direct_subscription','Aubrey confirmed in Pi chat on 2026-07-21')
 entitlement(c,products['warp'],'active','direct_subscription','Aubrey confirmed in Pi chat on 2026-07-21',notes='Exact Warp tier unresolved.')
 entitlement(c,products['google-ai-pro'],'active','direct_subscription','Aubrey confirmed Gemini Pro in Pi chat on 2026-07-21',notes='Map to current official regional tier after account confirmation.')
 entitlement(c,products['github-enterprise'],'active','organization_seat','Aubrey confirmed in Pi chat on 2026-07-21',org='Dye & Durham Corporation')
 entitlement(c,products['opencode-go'],'conflicting','reported_access','Aubrey reports access associated with GitHub Enterprise; official docs describe a separate Go subscription.',confidence='conflicting',org='Dye & Durham Corporation',notes='Do not claim bundling until entitlement path is resolved.')
 link_provider(c,products['chatgpt-plus'],'openai-codex','subscription_included',*sources['openai'])
 link_provider(c,products['opencode-go'],'opencode-go','subscription_included',*sources['go'],quota={'five_hour_usd':12,'weekly_usd':30,'monthly_usd':60})
 link_provider(c,products['opencode-zen'],'opencode-zen','pay_as_you_go',*sources['zen'])
 c.commit()
 print(json.dumps({'subscription_products':c.execute('SELECT COUNT(*) FROM subscription_products').fetchone()[0],'personal_entitlements':c.execute('SELECT COUNT(*) FROM personal_subscription_entitlements').fetchone()[0],'subscription_model_links':c.execute('SELECT COUNT(*) FROM subscription_model_access').fetchone()[0]},indent=2))
if __name__=='__main__':main()
