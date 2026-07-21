#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/'free_models.db'; NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat()
RELEASES=[
 {'slug':'kimi-k2.7-code','developer':'Moonshot AI','family':'Kimi','name':'Kimi K2.7 Code','weights':'open','license':'unknown','url':'https://x.com/Kimi_Moonshot/status/2065377579130142937','path':ROOT/'evidence/x/kimi-k2.7-code.md','time':'2026-06-12T10:16:02Z','events':['announcement','general_release','api_availability','weights_release'],'quote':'Kimi-K2.7-Code, our latest coding model, is now released and open-sourced! Available today via Kimi API and Kimi Code.','links':[('opencode-go','kimi-k2.7-code'),('cloudflare-ai','@cf/moonshotai/kimi-k2.7-code')]},
 {'slug':'glm-5.2','developer':'Z.ai','family':'GLM','name':'GLM-5.2','weights':'open','license':'MIT','url':'https://x.com/Zai_org/status/2066938937344495629','path':ROOT/'evidence/x/glm-5.2.md','time':'2026-06-16T17:40:19Z','events':['announcement','general_release','weights_release'],'quote':'Introducing GLM-5.2: Frontier Intelligence, Open Weights. Strong long-horizon capabilities with a 1M context window. MIT-licensed open weights.','links':[('opencode-go','glm-5.2'),('nvidia-nim','z-ai/glm-5.2'),('cloudflare-ai','@cf/zai-org/glm-5.2')]},
 {'slug':'minimax-m3','developer':'MiniMax','family':'MiniMax','name':'MiniMax M3','weights':'announced','license':'unknown','url':'https://x.com/MiniMax_AI/status/2061266317815296322','path':ROOT/'evidence/x/minimax-m3.md','time':'2026-06-01T01:59:21Z','events':['announcement','preview_release'],'quote':'Introducing MiniMax M3... MiniMax Sparse Attention scales context to 1M. Natively Multimodal from Step Zero. Weights & Tech Report in ~10 Days.','links':[('opencode-go','minimax-m3'),('nvidia-nim','minimaxai/minimax-m3')]},
 {'slug':'nemotron-3-ultra-550b-a55b','developer':'NVIDIA','family':'Nemotron 3','name':'Nemotron 3 Ultra 550B A55B','weights':'open','license':'OpenMDW-1.1','url':'https://x.com/NVIDIAAI/status/2062521325076299981','path':ROOT/'evidence/x/nemotron-3-ultra.md','time':'2026-06-04T13:06:18Z','events':['announcement','general_release','weights_release'],'quote':'Today we are shipping Nemotron 3 Ultra. A 550B MoE frontier-intelligence open model built for long-running agents.','links':[('nvidia-nim','nvidia/nemotron-3-ultra-550b-a55b'),('openrouter','nvidia/nemotron-3-ultra-550b-a55b:free'),('opencode-zen','nemotron-3-ultra-free')]},
]

def source_capture(c,url,path,publisher,title,pubtime):
 raw=path.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
 c.execute("INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,publication_time,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status) VALUES(?,?,?,?,1,1,?,?,?,?,200,10,'verified')",(url,'official_x',publisher,title,pubtime,NOW,sha,str(path)))
 sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()[0]
 c.execute("INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,publication_time_observed,content_sha256,archived_path,http_status,extraction_method,extractor_version,notes) VALUES(?,?,?,?,?,200,'firecrawl','1.16.0','Official X post extracted by Firecrawl after bird authentication was unavailable.')",(sid,NOW,pubtime,sha,str(path)))
 cap=c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?',(sid,sha)).fetchone()[0]
 return sid,cap

def endpoint_capture(c,provider,path,url):
 raw=path.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
 c.execute("INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status) VALUES(?,?,?,?,1,1,?,?,?,200,1,'verified')",(url,'api_endpoint',provider,f'{provider} official models endpoint',NOW,sha,str(path)))
 sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()[0]
 c.execute("INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version) VALUES(?,?,?,?,200,'official_endpoint_refresh','refresh_catalog.py')",(sid,NOW,sha,str(path)))
 cap=c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?',(sid,sha)).fetchone()[0]
 return sid,cap

def claim(c,typ,key,field,value,sid,cap,quote,confidence='verified',method='primary-source extraction',priority=10):
 c.execute("INSERT OR IGNORE INTO evidence_claims(subject_type,subject_key,field_name,value_json,value_type,evidence_source_id,supporting_quote,observed_at,confidence,verification_method,source_priority,evidence_capture_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(typ,key,field,json.dumps(value),type(value).__name__,sid,quote,NOW,confidence,method,priority,cap))

def main():
 c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON')
 for r in RELEASES:
  sid,cap=source_capture(c,r['url'],r['path'],r['developer'],r['name']+' official release post',r['time'])
  c.execute("""INSERT INTO canonical_models(canonical_slug,developer,family,canonical_name,weights_status,license_spdx,lifecycle_status,updated_at)
   VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(canonical_slug) DO UPDATE SET developer=excluded.developer,family=excluded.family,canonical_name=excluded.canonical_name,weights_status=excluded.weights_status,license_spdx=excluded.license_spdx,lifecycle_status=excluded.lifecycle_status,updated_at=excluded.updated_at""",
   (r['slug'],r['developer'],r['family'],r['name'],r['weights'],r['license'],'active' if 'general_release' in r['events'] else 'preview',NOW))
  cid=c.execute('SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?',(r['slug'],)).fetchone()[0]
  claim(c,'canonical_model',r['slug'],'canonical_name',r['name'],sid,cap,r['quote'])
  claim(c,'canonical_model',r['slug'],'developer',r['developer'],sid,cap,r['quote'])
  claim(c,'canonical_model',r['slug'],'weights_status',r['weights'],sid,cap,r['quote'])
  if r['license']!='unknown':claim(c,'canonical_model',r['slug'],'license',r['license'],sid,cap,r['quote'])
  if r['slug']=='glm-5.2':
   claim(c,'canonical_model',r['slug'],'context_window_tokens',1000000,sid,cap,r['quote']); c.execute('UPDATE canonical_models SET architecture=COALESCE(architecture,?) WHERE canonical_model_id=?',('open-weight long-context model',cid))
  if r['slug']=='minimax-m3':claim(c,'canonical_model',r['slug'],'context_window_tokens',1000000,sid,cap,r['quote'])
  if r['slug']=='nemotron-3-ultra-550b-a55b':
   claim(c,'canonical_model',r['slug'],'total_parameters',550000000000,sid,cap,r['quote']); c.execute('UPDATE canonical_models SET total_parameters=?,architecture=? WHERE canonical_model_id=?',(550000000000,'hybrid Mamba-Transformer MoE',cid))
  for ev in r['events']:
   c.execute("INSERT OR IGNORE INTO model_events(canonical_model_id,event_type,event_time,time_precision,evidence_source_id,supporting_quote,confidence,details_json,evidence_capture_id) VALUES(?,?,?,?,?,?,?,?,?)",(cid,ev,r['time'],'second',sid,r['quote'],'verified',json.dumps({'source':'official X'}),cap))
  for pid,mid in r['links']:
   row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()
   if row:c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,row[0]))
 # MiniMax seven-day 50% discount. End is explicitly marked inferred from "first 7 days".
 r=RELEASES[2]; sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(r['url'],)).fetchone()[0]; cap=c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? ORDER BY evidence_capture_id DESC',(sid,)).fetchone()[0]
 for pid,mid in r['links']:
  row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()
  if row:c.execute("INSERT OR IGNORE INTO access_offers(provider_model_id,offer_type,starts_at,ends_at,announced_at,first_observed_at,last_observed_at,discount_percent,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at) VALUES(?,'temporary_discount','2026-06-01T01:59:21Z','2026-06-08T01:59:21Z','2026-06-01T01:59:22Z',?,?,?,'50% off standard usage up to 512K context during first 7 days',?,?,?,?)",(row[0],NOW,NOW,'50',sid,cap,'inferred',NOW))
 # Current free offers from immutable endpoint snapshots.
 for provider,url in [('openrouter','https://openrouter.ai/api/v1/models'),('opencode-zen','https://opencode.ai/zen/v1/models')]:
  path=ROOT/'snapshots'/f'{provider}-2026-07-21.json'
  sid,cap=endpoint_capture(c,provider,path,url); payload=json.loads(path.read_text()); items=payload.get('data',[])
  for item in items:
   mid=item.get('id'); isfree=(provider=='openrouter' and item.get('pricing',{}).get('prompt')=='0' and item.get('pricing',{}).get('completion')=='0') or (provider=='opencode-zen' and mid.endswith('-free'))
   if not isfree:continue
   row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(provider,mid)).fetchone()
   if not row:continue
   offer='genuine_zero_price' if provider=='openrouter' else 'temporary_free_window'
   terms='Official endpoint reported prompt and completion price 0' if provider=='openrouter' else 'Official endpoint model ID ends in -free; start and end dates are not published'
   c.execute("INSERT OR IGNORE INTO access_offers(provider_model_id,offer_type,starts_at,ends_at,first_observed_at,last_observed_at,input_price_per_million_usd,output_price_per_million_usd,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at) VALUES(?,?,NULL,NULL,?,?,?,?,?,?,?,?,?)",(row[0],offer,NOW,NOW,'0' if provider=='openrouter' else None,'0' if provider=='openrouter' else None,terms,sid,cap,'verified' if provider=='openrouter' else 'single_source',NOW))
   claim(c,'provider_model',f'{provider}/{mid}','current_free_offer',True,sid,cap,terms,'verified' if provider=='openrouter' else 'single_source','official endpoint extraction',1)
 c.commit()
 print(json.dumps({'canonical_models':c.execute('SELECT COUNT(*) FROM canonical_models').fetchone()[0],'release_events':c.execute('SELECT COUNT(*) FROM model_events').fetchone()[0],'evidence_sources':c.execute('SELECT COUNT(*) FROM evidence_sources').fetchone()[0],'evidence_captures':c.execute('SELECT COUNT(*) FROM evidence_captures').fetchone()[0],'claims':c.execute('SELECT COUNT(*) FROM evidence_claims').fetchone()[0],'active_free_offers':c.execute('SELECT COUNT(*) FROM currently_free_provider_models').fetchone()[0]},indent=2))
if __name__=='__main__':main()
