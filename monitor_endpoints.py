#!/usr/bin/env python3
"""Poll official model endpoints, preserve snapshots, and record meaningful diffs.

Designed for a future scheduler. It stores credential names, never credential values.
First run establishes a baseline. Later runs emit added/removed/metadata/pricing changes.
"""
from __future__ import annotations
import hashlib,json,os,sqlite3,urllib.request,urllib.error
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/'aimi.db'; SNAP=ROOT/'snapshots'/'monitor'; SNAP.mkdir(parents=True,exist_ok=True)
NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); STAMP=NOW.replace(':','').replace('+00:00','Z')
CONFIG={
 'openrouter':('https://openrouter.ai/api/v1/models','OPENROUTER_API_KEY','data'),
 'opencode-zen':('https://opencode.ai/zen/v1/models','OPENCODE_API_KEY','data'),
 'opencode-go':('https://opencode.ai/zen/go/v1/models','OPENCODE_API_KEY','data'),
 'nvidia-nim':('https://integrate.api.nvidia.com/v1/models','NVIDIA_API_KEY','data'),
 'deepseek':('https://api.deepseek.com/v1/models','DEEPSEEK_API_KEY','data'),
 'mistral':('https://api.mistral.ai/v1/models','MISTRAL_API_KEY','data'),
 'openai':('https://api.openai.com/v1/models','OPENAI_API_KEY','data'),
 'gemini':('https://generativelanguage.googleapis.com/v1beta/models','GEMINI_API_KEY','models'),
 'cloudflare-ai':(f"https://api.cloudflare.com/client/v4/accounts/{os.getenv('CLOUDFLARE_ACCOUNT_ID','{account_id}')}/ai/models/search?per_page=200",'CLOUDFLARE_API_TOKEN_AZLABS_AI_WORKERS','result'),
 'ollama-cloud':('https://ollama.com/v1/models',None,'data'),
}

def safe_url(pid,url):
 return 'https://generativelanguage.googleapis.com/v1beta/models' if pid=='gemini' else url.replace(os.getenv('CLOUDFLARE_ACCOUNT_ID','__NO_ACCOUNT__'),'{account_id}')

def fetch(pid,url,env):
 key=os.getenv(env) if env else None; headers={'User-Agent':'AZ-Labs-model-monitor/1.0'}
 if env and not key: raise RuntimeError(f'missing {env}')
 if pid=='gemini': url=url+'?key='+key
 elif key: headers['Authorization']='Bearer '+key
 req=urllib.request.Request(url,headers=headers)
 with urllib.request.urlopen(req,timeout=45) as r:return r.status,r.read(),dict(r.headers)

def rows(pid,payload,key):
 out={}
 for x in payload.get(key,[]):
  mid=(x.get('name') or x.get('id')) if pid=='cloudflare-ai' else (x.get('id') or x.get('name'))
  if not mid:continue
  view={'id':mid}
  if pid=='openrouter':
   view.update({'name':x.get('name'),'created':x.get('created'),'context_length':x.get('context_length'),'max_output':x.get('top_provider',{}).get('max_completion_tokens'),'pricing':x.get('pricing'),'input_modalities':x.get('architecture',{}).get('input_modalities'),'output_modalities':x.get('architecture',{}).get('output_modalities')})
  elif pid=='gemini':view.update({'displayName':x.get('displayName'),'inputTokenLimit':x.get('inputTokenLimit'),'outputTokenLimit':x.get('outputTokenLimit'),'methods':x.get('supportedGenerationMethods'),'thinking':x.get('thinking')})
  elif pid=='mistral':view.update({'name':x.get('name'),'context':x.get('max_context_length'),'capabilities':x.get('capabilities'),'aliases':x.get('aliases'),'deprecation':x.get('deprecation'),'replacement':x.get('deprecation_replacement_model')})
  else:
   stable_fields=('name','displayName','owned_by','description') + (('created',) if pid in ('openai','ollama-cloud') else ())
   view.update({k:x.get(k) for k in stable_fields if k in x})
  out[mid]=view
 return out

def is_free(pid,x):
 if pid=='openrouter':return x.get('pricing',{}).get('prompt')=='0' and x.get('pricing',{}).get('completion')=='0'
 if pid=='opencode-zen':return x['id'].endswith('-free')
 return False

def source_capture(c,pid,url,raw,path,status):
 clean=safe_url(pid,url); sha=hashlib.sha256(raw).hexdigest()
 c.execute("INSERT OR IGNORE INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,http_status,trust_priority,verification_status) VALUES(?,?,?, ?,1,1,?,?,1,'verified')",(clean,'api_endpoint',pid,f'{pid} official models endpoint',NOW,status))
 sid=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(clean,)).fetchone()[0]
 c.execute("INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version) VALUES(?,?,?,?,?,'endpoint_monitor','1.0')",(sid,NOW,sha,str(path),status))
 cap=c.execute('SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?',(sid,sha)).fetchone()[0]
 return sid,cap,sha

def ensure_target(c,pid,url):
 clean=safe_url(pid,url)
 c.execute("INSERT OR IGNORE INTO monitoring_targets(provider_id,target_type,url,schedule_class,enabled,expected_format,parser_name) VALUES(?,'models_endpoint',?,'frequent',1,'json',?)",(pid,clean,pid))
 return c.execute("SELECT monitoring_target_id FROM monitoring_targets WHERE target_type='models_endpoint' AND url=?",(clean,)).fetchone()[0]

def ensure_pm(c,pid,mid,x,source_id):
 context=x.get('context_length') or x.get('inputTokenLimit') or x.get('context')
 out=x.get('max_output') or x.get('outputTokenLimit')
 c.execute("""INSERT INTO provider_models_v2(provider_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,context_window_tokens,max_output_tokens,provider_metadata_json,source_snapshot_id)
 VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(provider_id,model_identifier) DO UPDATE SET display_name=COALESCE(excluded.display_name,provider_models_v2.display_name),endpoint_status='available',endpoint_last_seen_at=excluded.endpoint_last_seen_at,endpoint_removed_at=NULL,context_window_tokens=COALESCE(excluded.context_window_tokens,provider_models_v2.context_window_tokens),max_output_tokens=COALESCE(excluded.max_output_tokens,provider_models_v2.max_output_tokens),provider_metadata_json=excluded.provider_metadata_json""",
 (pid,mid,x.get('name') or x.get('displayName') or mid,'available',NOW,NOW,context,out,json.dumps(x,sort_keys=True),None))
 return c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()[0]

def poll(c,pid,url,env,key):
 target=ensure_target(c,pid,url); c.execute("INSERT INTO monitoring_runs(monitoring_target_id,started_at,status) VALUES(?,?,'running')",(target,NOW)); run=c.execute('SELECT last_insert_rowid()').fetchone()[0]
 try:status,raw,headers=fetch(pid,url,env); payload=json.loads(raw); current=rows(pid,payload,key)
 except Exception as e:
  c.execute("UPDATE monitoring_runs SET finished_at=?,status='failed',error_summary=? WHERE monitoring_run_id=?",(NOW,str(e)[:500],run)); c.execute("UPDATE monitoring_targets SET last_checked_at=?,consecutive_failures=consecutive_failures+1 WHERE monitoring_target_id=?",(NOW,target)); c.commit(); return {'provider':pid,'status':'failed','error':str(e)}
 path=SNAP/f'{pid}-{STAMP}.json'; path.write_bytes(raw); sid,cap,sha=source_capture(c,pid,url,raw,path,status)
 prior=c.execute("SELECT monitoring_run_id,snapshot_path,response_sha256 FROM monitoring_runs WHERE monitoring_target_id=? AND monitoring_run_id<>? AND status IN ('success','unchanged','changed') ORDER BY monitoring_run_id DESC LIMIT 1",(target,run)).fetchone()
 previous={}
 if prior and prior[1] and Path(prior[1]).exists():
  old=json.loads(Path(prior[1]).read_text()); previous=rows(pid,old,key)
 added=sorted(set(current)-set(previous)); removed=sorted(set(previous)-set(current)); changed=sorted(k for k in set(current)&set(previous) if current[k]!=previous[k])
 baseline=prior is None
 if baseline:added=[];removed=[];changed=[]
 for mid,x in current.items():
  pm=ensure_pm(c,pid,mid,x,sid)
  if is_free(pid,x):
   typ='genuine_zero_price' if pid=='openrouter' else 'temporary_free_window'; terms='Endpoint reports zero input/output price' if pid=='openrouter' else 'Official model ID ends in -free; duration unpublished'
   existing=c.execute("SELECT access_offer_id FROM access_offers WHERE provider_model_id=? AND offer_type=? AND ends_at IS NULL",(pm,typ)).fetchone()
   if existing:c.execute('UPDATE access_offers SET last_observed_at=?,last_verified_at=?,evidence_source_id=?,evidence_capture_id=? WHERE access_offer_id=?',(NOW,NOW,sid,cap,existing[0]))
   else:c.execute("INSERT INTO access_offers(provider_model_id,offer_type,first_observed_at,last_observed_at,input_price_per_million_usd,output_price_per_million_usd,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(pm,typ,NOW,NOW,'0' if pid=='openrouter' else None,'0' if pid=='openrouter' else None,terms,sid,cap,'verified' if pid=='openrouter' else 'single_source',NOW))
 for mid in removed:
  row=c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?',(pid,mid)).fetchone()
  if row:
   c.execute("UPDATE provider_models_v2 SET endpoint_status='removed',endpoint_removed_at=? WHERE provider_model_id=?",(NOW,row[0])); c.execute("UPDATE access_offers SET ends_at=COALESCE(ends_at,?),last_observed_at=? WHERE provider_model_id=? AND ends_at IS NULL",(NOW,NOW,row[0]))
 for typ,ids in [('model_added',added),('model_removed',removed),('model_changed',changed)]:
  for mid in ids:c.execute("INSERT INTO endpoint_changes(monitoring_run_id,provider_id,change_type,model_identifier,before_json,after_json,detected_at) VALUES(?,?,?,?,?,?,?)",(run,pid,typ,mid,json.dumps(previous.get(mid),sort_keys=True) if mid in previous else None,json.dumps(current.get(mid),sort_keys=True) if mid in current else None,NOW))
 # Raw payload hashes may change because of volatile timestamps, ordering, or provider metadata.
 # User-visible change status is based on normalized model additions/removals/field changes.
 state=('changed' if (added or removed or changed) else 'unchanged') if prior else 'success'
 c.execute("UPDATE monitoring_runs SET finished_at=?,status=?,http_status=?,response_sha256=?,snapshot_path=?,added_count=?,removed_count=?,changed_count=? WHERE monitoring_run_id=?",(NOW,state,status,sha,str(path),len(added),len(removed),len(changed),run))
 c.execute("UPDATE monitoring_targets SET last_checked_at=?,last_success_at=?,last_changed_at=CASE WHEN ?='changed' THEN ? ELSE last_changed_at END,consecutive_failures=0 WHERE monitoring_target_id=?",(NOW,NOW,state,NOW,target)); c.commit()
 return {'provider':pid,'status':state,'models':len(current),'added':len(added),'removed':len(removed),'changed':len(changed)}

def main():
 c=sqlite3.connect(DB);c.execute('PRAGMA foreign_keys=ON'); results=[]
 for pid,(url,env,key) in CONFIG.items():results.append(poll(c,pid,url,env,key))
 print(json.dumps(results,indent=2)); return 1 if any(x['status']=='failed' for x in results) else 0
if __name__=='__main__':raise SystemExit(main())
