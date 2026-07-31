#!/usr/bin/env python3
"""Promote endpoint-only observations into placeholder catalogue identities.

This records a route and its endpoint-first-seen event. It does not claim the
model's developer, official release date, pricing, capabilities, or weights.
"""
import re, sqlite3, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent; DB=ROOT/'aimi.db'
def slug(s): return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def main():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
 candidates=c.execute("""SELECT DISTINCT ec.monitoring_run_id,ec.provider_id,ec.model_identifier,ec.detected_at,ec.after_json,pm.provider_model_id,pm.display_name
 FROM endpoint_changes ec JOIN provider_models_v2 pm ON pm.provider_id=ec.provider_id AND pm.model_identifier=ec.model_identifier
 WHERE ec.change_type='model_added' AND pm.canonical_model_id IS NULL
 ORDER BY ec.detected_at""").fetchall()
 promoted=[]
 for r in candidates:
  mid=r['model_identifier']; display=r['display_name'] or mid
  # The endpoint does not prove the maker or lifecycle. Keep those fields
  # explicitly unknown until an evidence-backed ingestion is approved.
  dev='Unknown'
  name=display.replace(' (free)','').replace(':free','').strip()
  family=None
  cs=slug(name) or slug(mid)
  c.execute("INSERT OR IGNORE INTO canonical_models(canonical_slug,developer,family,canonical_name,lifecycle_status,weights_status) VALUES(?,?,?,?, 'unknown','unknown')",(cs,dev,family,name))
  cid=c.execute('SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?',(cs,)).fetchone()[0]
  c.execute('UPDATE provider_models_v2 SET canonical_model_id=? WHERE provider_model_id=?',(cid,r['provider_model_id']))
  # endpoint first-seen is a distinct event and is the only claim made here
  target=c.execute("""SELECT mt.url
   FROM monitoring_runs mr JOIN monitoring_targets mt ON mt.monitoring_target_id=mr.monitoring_target_id
   WHERE mr.monitoring_run_id=?""",(r['monitoring_run_id'],)).fetchone()
  if target:
   url=target[0]; es=c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?',(url,)).fetchone()
   if es:
    capture=c.execute("""SELECT evidence_capture_id FROM evidence_captures
     WHERE evidence_source_id=? AND retrieved_at=?
     ORDER BY evidence_capture_id DESC LIMIT 1""",(es[0],r['detected_at'])).fetchone()
    if not capture:
     capture=c.execute("""SELECT evidence_capture_id FROM evidence_captures
      WHERE evidence_source_id=? ORDER BY evidence_capture_id DESC LIMIT 1""",(es[0],)).fetchone()
    capture_id=capture[0] if capture else None
    c.execute("""INSERT OR IGNORE INTO model_events(
      canonical_model_id,provider_model_id,event_type,event_time,time_precision,
      evidence_source_id,supporting_quote,confidence,details_json,evidence_capture_id)
      VALUES(?,NULL,'endpoint_first_seen',?,'second',?,
      'Endpoint monitor first observed this provider route.','verified',?,?)""",
      (cid,r['detected_at'],es[0],json.dumps({'provider':r['provider_id'],'model_identifier':mid}),capture_id))
    # Repair endpoint-first-seen rows created by older versions of this script.
    c.execute("""UPDATE model_events SET evidence_capture_id=COALESCE(evidence_capture_id,?)
      WHERE canonical_model_id=? AND provider_model_id IS NULL
        AND event_type='endpoint_first_seen' AND event_time=? AND evidence_source_id=?""",
      (capture_id,cid,r['detected_at'],es[0]))
  promoted.append({'model':name,'developer':dev,'provider':r['provider_id'],'route':mid,'first_seen':r['detected_at']})
 # Every verified endpoint-first-seen event must point to an immutable capture.
 # This also repairs events written by the pre-capture version of this script.
 c.execute("""UPDATE model_events SET evidence_capture_id=(
   SELECT ec.evidence_capture_id FROM evidence_captures ec
   WHERE ec.evidence_source_id=model_events.evidence_source_id
   ORDER BY ec.evidence_capture_id DESC LIMIT 1)
 WHERE model_events.event_type='endpoint_first_seen'
   AND model_events.evidence_capture_id IS NULL""")
 c.commit(); print(json.dumps({'promoted':promoted,'count':len(promoted)},indent=2))
if __name__=='__main__': main()
