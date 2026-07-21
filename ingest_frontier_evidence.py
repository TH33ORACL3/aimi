#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/'free_models.db'; WEB=ROOT/'evidence/web'; NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def src(c,url,path,publisher,title,stype='official_blog',pub=None,priority=10):
 raw=Path(path).read_bytes(); h=hashlib.sha256(raw).hexdigest()
 c.execute("INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,publication_time,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status) VALUES(?,?,?,?,1,1,?,?,?,?,200,?,'verified')",(url,stype,publisher,title,pub,NOW,h,str(path),priority))
 sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()[0]
 c.execute("INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,publication_time_observed,content_sha256,archived_path,http_status,extraction_method,extractor_version) VALUES(?,?,?,?,?,200,'firecrawl','1.16.0')",(sid,NOW,pub,h,str(path)))
 return sid,c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?',(sid,h)).fetchone()[0]
def canonical(c,slug,dev,family,name,status='active'):
 c.execute("INSERT INTO canonical_models(canonical_slug,developer,family,canonical_name,weights_status,lifecycle_status,updated_at) VALUES(?,?,?,?,'closed',?,?) ON CONFLICT(canonical_slug) DO UPDATE SET developer=excluded.developer,family=excluded.family,canonical_name=excluded.canonical_name,lifecycle_status=excluded.lifecycle_status,updated_at=excluded.updated_at",(slug,dev,family,name,status,NOW)); return c.execute('SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?',(slug,)).fetchone()[0]
def pm(c,pid,mid,cid,name=None,ctx=None,out=None):
 c.execute("INSERT INTO provider_models_v2(provider_id,canonical_model_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,context_window_tokens,max_output_tokens) VALUES(?,?,?,?,'available',?,?,?,?) ON CONFLICT(provider_id,model_identifier) DO UPDATE SET canonical_model_id=excluded.canonical_model_id,display_name=COALESCE(excluded.display_name,provider_models_v2.display_name),context_window_tokens=COALESCE(excluded.context_window_tokens,provider_models_v2.context_window_tokens),max_output_tokens=COALESCE(excluded.max_output_tokens,provider_models_v2.max_output_tokens),endpoint_status='available',endpoint_last_seen_at=excluded.endpoint_last_seen_at",(pid,cid,mid,name,NOW,NOW,ctx,out))
 return c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()[0]
def claim(c,typ,key,field,value,sid,cap,quote,confidence='verified',method='official primary source',priority=10):
 c.execute("INSERT OR IGNORE INTO evidence_claims(subject_type,subject_key,field_name,value_json,value_type,evidence_source_id,supporting_quote,observed_at,confidence,verification_method,source_priority,evidence_capture_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(typ,key,field,json.dumps(value),type(value).__name__,sid,quote,NOW,confidence,method,priority,cap))
def event(c,cid,typ,time,sid,cap,quote,precision='day'):
 c.execute("INSERT OR IGNORE INTO model_events(canonical_model_id,event_type,event_time,time_precision,evidence_source_id,supporting_quote,confidence,evidence_capture_id) VALUES(?,?,?,?,?,?,?,?)",(cid,typ,time,precision,sid,quote,'verified',cap))
def offer(c,pmid,typ,sid,cap,start=None,end=None,inp=None,out=None,discount=None,terms='',confidence='verified'):
 c.execute("INSERT OR IGNORE INTO access_offers(provider_model_id,offer_type,starts_at,ends_at,announced_at,first_observed_at,last_observed_at,input_price_per_million_usd,output_price_per_million_usd,discount_percent,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pmid,typ,start,end,start,NOW,NOW,inp,out,discount,terms,sid,cap,confidence,NOW))
def main():
 c=sqlite3.connect(DB); c.execute('PRAGMA foreign_keys=ON')
 # OpenAI GPT-5.6 family, GA 2026-07-09.
 u='https://openai.com/index/gpt-5-6/'; sid,cap=src(c,u,WEB/'openai-gpt-5.6.md','OpenAI','GPT-5.6 launch','official_blog','2026-07-09')
 quote='GPT-5.6 is available starting today across ChatGPT, Codex, and the OpenAI API.'
 for tier,pricein,priceout in [('sol','5','30'),('terra','2.5','15'),('luna','1','6')]:
  slug=f'gpt-5.6-{tier}'; name=f'GPT-5.6 {tier.title()}'; cid=canonical(c,slug,'OpenAI','GPT-5.6',name)
  event(c,cid,'general_release','2026-07-09',sid,cap,quote); event(c,cid,'api_availability','2026-07-09',sid,cap,quote)
  claim(c,'canonical_model',slug,'release_date','2026-07-09',sid,cap,quote); claim(c,'canonical_model',slug,'pricing_usd_per_million',{'input':pricein,'output':priceout},sid,cap,'GPT-5.6 is priced per 1M tokens across three model sizes: Sol is $5 input / $30 output; Terra is $2.50 input / $15 output; and Luna is $1 input / $6 output.')
  p=pm(c,'openai',slug,cid,name); offer(c,p,'paid',sid,cap,start='2026-07-09',inp=pricein,out=priceout,terms='Standard OpenAI API pricing at launch')
  for pid in ('openai-codex','github-copilot'):
   row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,slug)).fetchone()
   if row:c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,row[0]))
 # Anthropic Sonnet 5 release plus exact technical docs and temporary launch price.
 au='https://www.anthropic.com/news/claude-sonnet-5'; asid,acap=src(c,au,WEB/'anthropic-claude-sonnet-5.md','Anthropic','Introducing Claude Sonnet 5','official_blog','2026-06-30')
 du='https://docs.anthropic.com/en/docs/about-claude/models/whats-new-sonnet-5'; dsid,dcap=src(c,du,WEB/'anthropic-sonnet-5-docs.md','Anthropic','Sonnet 5 model documentation','official_docs','2026-06-30',5)
 cid=canonical(c,'claude-sonnet-5','Anthropic','Claude Sonnet','Claude Sonnet 5'); q='From today, Claude Sonnet 5 is available across all plans... Developers can use `claude-sonnet-5` via the Claude API.'
 event(c,cid,'general_release','2026-06-30',asid,acap,q); event(c,cid,'api_availability','2026-06-30',asid,acap,q)
 claim(c,'canonical_model','claude-sonnet-5','context_window_tokens',1000000,dsid,dcap,'Claude Sonnet 5 supports the 1M token context window by default.'); claim(c,'canonical_model','claude-sonnet-5','max_output_tokens',128000,dsid,dcap,'128k max output tokens'); claim(c,'canonical_model','claude-sonnet-5','reasoning_type','adaptive_thinking',dsid,dcap,'adaptive thinking')
 p=pm(c,'anthropic','claude-sonnet-5',cid,'Claude Sonnet 5',1000000,128000); offer(c,p,'temporary_discount',asid,acap,'2026-06-30','2026-09-01','2','10',None,'Introductory pricing through August 31, 2026'); offer(c,p,'paid',asid,acap,'2026-09-01',None,'3','15',None,'Standard pricing after introductory window')
 for pid in ('github-copilot','opencode-zen'):
  row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,'claude-sonnet-5')).fetchone()
  if row:c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,row[0]))
 # Anthropic Opus 4.8.
 ou='https://www.anthropic.com/news/claude-opus-4-8'; osid,ocap=src(c,ou,WEB/'anthropic-claude-opus-4.8.md','Anthropic','Introducing Claude Opus 4.8','official_blog','2026-05-28')
 od='https://docs.anthropic.com/en/docs/about-claude/models/whats-new-claude-4-8'; odsid,odcap=src(c,od,WEB/'anthropic-opus-4.8-docs.md','Anthropic','Opus 4.8 model documentation','official_docs','2026-05-28',5)
 cid=canonical(c,'claude-opus-4.8','Anthropic','Claude Opus','Claude Opus 4.8'); q='Claude Opus 4.8... is available today for the same price.'
 event(c,cid,'general_release','2026-05-28',osid,ocap,q); event(c,cid,'api_availability','2026-05-28',osid,ocap,q); claim(c,'canonical_model','claude-opus-4.8','context_window_tokens',1000000,odsid,odcap,'Claude Opus 4.8 supports the 1M token context window by default.'); claim(c,'canonical_model','claude-opus-4.8','max_output_tokens',128000,odsid,odcap,'128k max output tokens')
 p=pm(c,'anthropic','claude-opus-4.8',cid,'Claude Opus 4.8',1000000,128000); offer(c,p,'paid',osid,ocap,'2026-05-28',None,'5','25',None,'Regular usage pricing')
 for pid in ('github-copilot','opencode-zen'):
  row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,'claude-opus-4-8' if pid=='opencode-zen' else 'claude-opus-4.8')).fetchone()
  if row:c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,row[0]))
 # Gemini 3.6 Flash GA and endpoint limits.
 gu='https://ai.google.dev/gemini-api/docs/changelog'; gsid,gcap=src(c,gu,WEB/'google-gemini-api-changelog.md','Google','Gemini API changelog','official_changelog','2026-07-21',3)
 gm='https://deepmind.google/models/gemini/flash/'; msid,mcap=src(c,gm,WEB/'google-gemini-3.6-model.md','Google DeepMind','Gemini 3.6 Flash model page','official_docs','2026-07-21',5)
 cid=canonical(c,'gemini-3.6-flash','Google DeepMind','Gemini','Gemini 3.6 Flash'); q='Gemini 3.6 Flash and Gemini 3.5 Flash-Lite generally available (GA).'
 event(c,cid,'general_release','2026-07-21',gsid,gcap,q); event(c,cid,'api_availability','2026-07-21',gsid,gcap,q); claim(c,'canonical_model','gemini-3.6-flash','context_window_tokens',1048576,gsid,gcap,'Official Gemini endpoint reports inputTokenLimit 1048576.'); claim(c,'canonical_model','gemini-3.6-flash','max_output_tokens',65536,gsid,gcap,'Official Gemini endpoint reports outputTokenLimit 65536.'); claim(c,'canonical_model','gemini-3.6-flash','pricing_usd_per_million',{'input':'1.50','output':'7.50'},msid,mcap,'Input price $1.50; output price $7.50 per 1M tokens.')
 p=pm(c,'gemini','models/gemini-3.6-flash',cid,'Gemini 3.6 Flash',1048576,65536); offer(c,p,'paid',msid,mcap,'2026-07-21',None,'1.50','7.50',None,'Published standard API pricing; separate free-tier eligibility requires pricing-page evidence')
 # Grok 4.5: official model and API evidence, but no release date is asserted until a primary dated source is captured.
 xu='https://docs.x.ai/developers/grok-4-5'; xsid,xcap=src(c,xu,WEB/'xai-grok-4.5-docs.md','xAI','Grok 4.5 developer documentation','official_docs',None,5)
 cid=canonical(c,'grok-4.5','xAI','Grok','Grok 4.5'); claim(c,'canonical_model','grok-4.5','api_model_id','grok-4.5',xsid,xcap,"model: xai.responses('grok-4.5')"); claim(c,'canonical_model','grok-4.5','api_base_url','https://api.x.ai/v1',xsid,xcap,"baseURL: 'https://api.x.ai/v1'")
 p=pm(c,'xai','grok-4.5',cid,'Grok 4.5');
 for pid in ('xai-subscription','opencode-go','opencode-zen'):
  row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,'grok-4.5')).fetchone()
  if row:c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,row[0]))
 # Corroborate OpenRouter free semantics with official documentation.
 ru='https://openrouter.ai/docs/guides/routing/routers/free-router'; rsid,rcap=src(c,ru,WEB/'openrouter-free-router.md','OpenRouter','Free Models Router documentation','official_docs',None,3)
 for row in c.execute("SELECT provider_model_id,model_identifier FROM provider_models_v2 WHERE provider_id='openrouter' AND provider_model_id IN (SELECT provider_model_id FROM access_offers WHERE offer_type='genuine_zero_price')").fetchall():
  claim(c,'provider_model','openrouter/'+row[1],'free_semantics','zero-cost inference',rsid,rcap,'The Free Models Router is completely free. There is no charge for requests routed to free models.','corroborated')
 c.commit(); print(json.dumps({'canonical_models':c.execute('SELECT COUNT(*) FROM canonical_models').fetchone()[0],'verified_events':c.execute("SELECT COUNT(*) FROM model_events WHERE confidence='verified'").fetchone()[0],'claims':c.execute('SELECT COUNT(*) FROM evidence_claims').fetchone()[0],'offers':c.execute('SELECT COUNT(*) FROM access_offers').fetchone()[0]},indent=2))
if __name__=='__main__':main()
