#!/usr/bin/env python3
"""Bounded, free-only model health checks.

Targets only the active `currently_free_provider_models` view, sends one tiny
exact-OK prompt per route, tests concurrently, and stores bounded status/daily
aggregates. It never probes paid, unknown, subscription-only, or expired offers.
"""
from __future__ import annotations
import argparse, concurrent.futures, json, os, socket, sqlite3, time
import urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

from aimi_credentials import load_aimi_credentials

load_aimi_credentials()
ROOT=Path(__file__).resolve().parent
DB=ROOT/'aimi.db'
MIGRATION=ROOT/'free_model_health.sql'
VERSION='free-model-health/1.0'
PROMPT='Reply with exactly OK'

def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c

def targets(c,provider=None,only_failures=False,exclude_provider=None):
 q="""SELECT f.provider_model_id,f.provider_id,f.model_identifier,f.display_name,f.offer_type,f.offer_verified_at
 FROM currently_free_provider_models f LEFT JOIN free_model_probe_status s USING(provider_model_id)
 WHERE (? IS NULL OR f.provider_id=?) AND (? IS NULL OR f.provider_id<>?)
   AND (?=0 OR s.last_status IS NULL OR s.last_status<>'ok')
 GROUP BY f.provider_model_id ORDER BY f.provider_id,f.model_identifier"""
 return [dict(x) for x in c.execute(q,(provider,provider,exclude_provider,exclude_provider,int(only_failures)))]

def provider_config(c):
 return {x['provider_id']:dict(x) for x in c.execute("SELECT provider_id,base_url,api_style,auth_env_var FROM providers")}

def clean_error(body,status):
 try:
  payload=json.loads(body.decode('utf-8','replace'));msg=payload.get('error',{})
  if isinstance(msg,dict):msg=msg.get('message') or msg.get('code') or json.dumps(msg)
  elif not isinstance(msg,str):msg=json.dumps(msg)
  # An empty error object told us nothing. Fall back to other common fields
  # before giving up, so a failure is diagnosable instead of showing '{}'.
  if msg in ('{}','[]','null',''):
   for key in ('detail','message','title','type','status'):
    value=payload.get(key)
    if value:msg=value if isinstance(value,str) else json.dumps(value);break
   else:msg=f'HTTP {status} with an empty error body'
 except Exception:msg=body.decode('utf-8','replace')
 msg=' '.join(str(msg or f'HTTP {status}').split())[:300]
 return msg

def probe(target,config,timeout):
 started=time.perf_counter();tested=now();pid=target['provider_id'];mid=target['model_identifier'];env=config.get('auth_env_var');key=os.getenv(env) if env else None
 base=(config.get('base_url') or '').rstrip('/')
 result={**target,'tested_at':tested,'status':'configuration_error','latency_ms':None,'http_status':None,'error_category':None,'error_message':None}
 if not base:
  result.update(error_category='missing_base_url',error_message='Provider base URL is not configured');return result
 if env and not key:
  result.update(error_category='missing_credential',error_message=f'Missing credential environment variable {env}');return result
 # 128 leaves enough room for providers that consume output budget on hidden reasoning before returning `OK`.
 payload=json.dumps({'model':mid,'messages':[{'role':'user','content':PROMPT}],'max_tokens':128,'temperature':0}).encode()
 headers={'Content-Type':'application/json','User-Agent':'AZ-Labs-free-model-health/1.0'}
 if key:headers['Authorization']='Bearer '+key
 req=urllib.request.Request(base+'/chat/completions',data=payload,headers=headers,method='POST')
 try:
  with urllib.request.urlopen(req,timeout=timeout) as response:
   body=response.read();result['http_status']=response.status
  data=json.loads(body);content=data.get('choices',[{}])[0].get('message',{}).get('content','')
  # Reasoning may be returned separately; only the final visible content is evaluated.
  if str(content).strip()=='OK':result['status']='ok'
  else:result.update(status='unexpected_response',error_category='unexpected_response',error_message='Final response was not exactly OK')
 except urllib.error.HTTPError as e:
  result['http_status']=e.code;message=clean_error(e.read(),e.code)
  if e.code==429:status='rate_limited'
  elif e.code in (401,403):status='unauthorized'
  else:status='http_error'
  result.update(status=status,error_category=f'http_{e.code}',error_message=message)
 except (TimeoutError,socket.timeout):result.update(status='timeout',error_category='timeout',error_message=f'Request exceeded {timeout}s')
 except Exception as e:result.update(status='network_error',error_category=type(e).__name__,error_message=' '.join(str(e).split())[:300])
 result['latency_ms']=round((time.perf_counter()-started)*1000);return result

def record(c,results,retention_days):
 c.executescript(MIGRATION.read_text());previous={x['provider_model_id']:x['last_status'] for x in c.execute('SELECT provider_model_id,last_status FROM free_model_probe_status')}
 # Reconcile every stored route against the live free view, including routes omitted by a partial retry.
 c.execute("""UPDATE free_model_probe_status SET currently_free=CASE WHEN EXISTS(
 SELECT 1 FROM currently_free_provider_models f WHERE f.provider_model_id=free_model_probe_status.provider_model_id
 ) THEN 1 ELSE 0 END""")
 transitions=[]
 for r in results:
  ok=r['status']=='ok';old=previous.get(r['provider_model_id'])
  if old is not None and old!=r['status']:transitions.append({'provider':r['provider_id'],'model':r['model_identifier'],'from':old,'to':r['status']})
  elif old is None:transitions.append({'provider':r['provider_id'],'model':r['model_identifier'],'from':None,'to':r['status']})
  c.execute("""INSERT INTO free_model_probe_status(provider_model_id,provider_id,model_identifier,currently_free,last_tested_at,last_status,last_ok_at,last_failure_at,latency_ms,http_status,consecutive_failures,last_error_category,last_error_message,offer_type,offer_verified_at,runner_version,updated_at)
  VALUES(?,?,?,1,?,?,?,?,?,?,?, ?,?,?,?,?,?)
  ON CONFLICT(provider_model_id) DO UPDATE SET provider_id=excluded.provider_id,model_identifier=excluded.model_identifier,currently_free=1,last_tested_at=excluded.last_tested_at,last_status=excluded.last_status,last_ok_at=CASE WHEN excluded.last_status='ok' THEN excluded.last_tested_at ELSE free_model_probe_status.last_ok_at END,last_failure_at=CASE WHEN excluded.last_status='ok' THEN free_model_probe_status.last_failure_at ELSE excluded.last_tested_at END,latency_ms=excluded.latency_ms,http_status=excluded.http_status,consecutive_failures=CASE WHEN excluded.last_status='ok' THEN 0 ELSE free_model_probe_status.consecutive_failures+1 END,last_error_category=excluded.last_error_category,last_error_message=excluded.last_error_message,offer_type=excluded.offer_type,offer_verified_at=excluded.offer_verified_at,runner_version=excluded.runner_version,updated_at=excluded.updated_at""",
  (r['provider_model_id'],r['provider_id'],r['model_identifier'],r['tested_at'],r['status'],r['tested_at'] if ok else None,None if ok else r['tested_at'],r['latency_ms'],r['http_status'],0 if ok else 1,r['error_category'],r['error_message'],r['offer_type'],r['offer_verified_at'],VERSION,r['tested_at']))
  day=r['tested_at'][:10];lat=r['latency_ms'] or 0
  c.execute("""INSERT INTO free_model_probe_daily(provider_model_id,test_date,first_tested_at,last_tested_at,attempts,ok_count,failure_count,last_status,min_latency_ms,max_latency_ms,total_latency_ms)
  VALUES(?,?,?,?,1,?,?,?,?,?,?)
  ON CONFLICT(provider_model_id,test_date) DO UPDATE SET last_tested_at=excluded.last_tested_at,attempts=free_model_probe_daily.attempts+1,ok_count=free_model_probe_daily.ok_count+excluded.ok_count,failure_count=free_model_probe_daily.failure_count+excluded.failure_count,last_status=excluded.last_status,min_latency_ms=CASE WHEN free_model_probe_daily.min_latency_ms IS NULL THEN excluded.min_latency_ms WHEN excluded.min_latency_ms IS NULL THEN free_model_probe_daily.min_latency_ms ELSE min(free_model_probe_daily.min_latency_ms,excluded.min_latency_ms) END,max_latency_ms=max(COALESCE(free_model_probe_daily.max_latency_ms,0),COALESCE(excluded.max_latency_ms,0)),total_latency_ms=free_model_probe_daily.total_latency_ms+excluded.total_latency_ms""",
  (r['provider_model_id'],day,r['tested_at'],r['tested_at'],1 if ok else 0,0 if ok else 1,r['status'],r['latency_ms'],r['latency_ms'],lat))
 c.execute("DELETE FROM free_model_probe_daily WHERE test_date < date('now',?)",(f'-{retention_days} days',));c.commit();return transitions

def main():
 p=argparse.ArgumentParser();p.add_argument('--provider');p.add_argument('--exclude-provider');p.add_argument('--only-failures',action='store_true');p.add_argument('--workers',type=int,default=4);p.add_argument('--timeout',type=int,default=45);p.add_argument('--openrouter-start-interval',type=float,default=3.2);p.add_argument('--retention-days',type=int,default=30);p.add_argument('--output',type=Path);p.add_argument('--quiet',action='store_true');a=p.parse_args()
 c=connect();c.executescript(MIGRATION.read_text());items=targets(c,a.provider,a.only_failures,a.exclude_provider);configs=provider_config(c)
 if not items:raise SystemExit('No currently verified free routes matched; no requests sent')
 with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(a.workers,8))) as pool:
  futures=[]
  for index,x in enumerate(items):
   futures.append(pool.submit(probe,x,configs[x['provider_id']],a.timeout))
   if x['provider_id']=='openrouter' and index<len(items)-1:time.sleep(max(0,a.openrouter_start_interval))
  results=[f.result() for f in concurrent.futures.as_completed(futures)]
 results.sort(key=lambda x:(x['provider_id'],x['model_identifier']));transitions=record(c,results,a.retention_days)
 green=sum(x['status']=='ok' for x in results);orange=sum(x['status']=='rate_limited' for x in results);red=len(results)-green-orange
 out={'tested_at':now(),'free_only_guard':True,'prompt':PROMPT,'target_count':len(results),'green_ok':green,'orange_rate_limited':orange,'red_failed':red,'retention_days':a.retention_days,'transitions':transitions,'results':results}
 text=json.dumps(out,indent=2)
 if a.output:a.output.write_text(text+'\n')
 if not a.quiet:print(text)
 return 0
if __name__=='__main__':raise SystemExit(main())
