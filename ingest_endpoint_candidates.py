#!/usr/bin/env python3
"""Promote reviewed endpoint discoveries into canonical identities.

This records endpoint observation, not a claimed developer release date.
"""
import re, sqlite3, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/'aimi.db'
DEVS={'openrouter':{'anthropic':'Anthropic','inclusionai':'InclusionAI'},'opencode-zen':{'claude':'Anthropic','ling':'InclusionAI'},'mistral':{'voxtral':'Mistral','deepseek':'DeepSeek'},'nvidia-nim':{'nvidia/ising':'NVIDIA'}}
def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def main():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
 candidates=c.execute("""SELECT DISTINCT ec.provider_id,ec.model_identifier,ec.detected_at,ec.after_json,pm.provider_model_id,pm.display_name
 FROM endpoint_changes ec JOIN provider_models_v2 pm ON pm.provider_id=ec.provider_id AND pm.model_identifier=ec.model_identifier
 WHERE ec.change_type='model_added' AND pm.canonical_model_id IS NULL
 ORDER BY ec.detected_at""").fetchall()
 promoted=[]
 for r in candidates:
  mid=r['model_identifier']; display=r['display_name'] or mid
  low=mid.lower(); dev='Unknown'
  for mapping in DEVS.values():
   for needle,name in mapping.items():
    if needle in low: dev=name
  if dev=='Unknown':
   dev=(mid.split('/')[0].replace('-',' ').title() if '/' in mid else r['provider_id'])
  name=display.replace(' (free)','').replace(':free','').strip()
  family=name.split()[0] if name else None
  cs=slug(name) or slug(mid)
  c.execute("INSERT OR IGNORE INTO canonical_models(canonical_slug,developer,family,canonical_name,lifecycle_status,weights_status) VALUES(?,?,?,?, 'active','unknown')",(cs,dev,family,name))
  cid=c.execute('SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?',(cs,)).fetchone()[0]
  c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,r['provider_model_id']))
  # endpoint first-seen is a distinct event and is the only claim made here
  target=c.execute('SELECT url FROM monitoring_targets WHERE provider_id=? AND target_type=\'models_endpoint\'',(r['provider_id'],)).fetchone()
  if target:
   url=target[0]; es=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()
   if es:
    c.execute("INSERT OR IGNORE INTO model_events(canonical_model_id,provider_model_id,event_type,event_time,time_precision,evidence_source_id,supporting_quote,confidence,details_json) VALUES(?,NULL,'endpoint_first_seen',?,'second',?,'Endpoint monitor first observed this provider route.','verified',?)",(cid,r['detected_at'],es[0],json.dumps({'provider':r['provider_id'],'model_identifier':mid})))
  promoted.append({'model':name,'developer':dev,'provider':r['provider_id'],'route':mid,'first_seen':r['detected_at']})
 c.commit(); print(json.dumps({'promoted':promoted,'count':len(promoted)},indent=2))
if __name__=='__main__': main()
