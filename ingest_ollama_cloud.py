#!/usr/bin/env python3
"""Ingest an explicitly approved Ollama Cloud API catalogue and Hyperfine test run."""
from __future__ import annotations
import argparse, hashlib, json, shutil, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "model_catalogue.db"
PASS = {
    "nemotron-3-ultra", "minimax-m3", "gemma4:31b", "nemotron-3-super",
    "minimax-m2.5", "nemotron-3-nano:30b", "gpt-oss:20b", "gpt-oss:120b",
}
SUBSCRIPTION = {
    "glm-5.2", "kimi-k2.7-code", "deepseek-v4-pro", "deepseek-v4-flash",
    "glm-5.1", "kimi-k2.6", "minimax-m2.7", "qwen3.5:397b", "kimi-k2.5",
    "mistral-large-3:675b",
}
LABEL_TO_MODEL = {
    "gemma4-31b": "gemma4:31b", "qwen3.5-397b": "qwen3.5:397b",
    "nemotron-3-nano-30b": "nemotron-3-nano:30b",
    "mistral-large-3-675b": "mistral-large-3:675b",
    "gpt-oss-20b": "gpt-oss:20b", "gpt-oss-120b": "gpt-oss:120b",
}
CANONICAL = {
    "glm-5.2": "glm-5.2", "kimi-k2.7-code": "kimi-k2.7-code",
    "minimax-m3": "minimax-m3", "nemotron-3-ultra": "nemotron-3-ultra-550b-a55b",
}

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def capture(c, url, source_type, publisher, title, official, primary, path, method):
    digest = sha(path); now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    c.execute("""INSERT INTO evidence_sources(url,source_type,publisher,title,official,primary_source,retrieved_at,content_sha256,archived_path,http_status,trust_priority,verification_status)
    VALUES(?,?,?,?,?,?,?,?,?,200,?,'verified') ON CONFLICT(url) DO UPDATE SET retrieved_at=excluded.retrieved_at,content_sha256=excluded.content_sha256,archived_path=excluded.archived_path,verification_status='verified'""",
    (url,source_type,publisher,title,official,primary,now,digest,str(path),1 if official else 10))
    sid=c.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?",(url,)).fetchone()[0]
    c.execute("""INSERT OR IGNORE INTO evidence_captures(evidence_source_id,retrieved_at,content_sha256,archived_path,http_status,extraction_method,extractor_version)
    VALUES(?,?,?,?,200,?,'1.0')""",(sid,now,digest,str(path),method))
    cap=c.execute("SELECT evidence_capture_id FROM evidence_captures WHERE evidence_source_id=? AND content_sha256=?",(sid,digest)).fetchone()[0]
    return sid,cap

def main():
    p=argparse.ArgumentParser();p.add_argument('--tags',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--hyperfine',type=Path,required=True);a=p.parse_args()
    now=datetime.now(timezone.utc).replace(microsecond=0).isoformat(); stamp=now.replace(':','').replace('+00:00','Z')
    out=ROOT/'evidence'/'ollama-cloud'/stamp;out.mkdir(parents=True,exist_ok=True)
    tags_path=out/'api-tags.json'; models_path=out/'v1-models.json'; hf_path=out/'hyperfine.json'
    shutil.copy2(a.tags,tags_path);shutil.copy2(a.models,models_path);shutil.copy2(a.hyperfine,hf_path)
    tags={x['model']:x for x in json.loads(tags_path.read_text())['models']}; models=json.loads(models_path.read_text())['data']; hf=json.loads(hf_path.read_text())
    timings={LABEL_TO_MODEL.get(x['command'],x['command']):{'latency_ms':round(x['mean']*1000),'exit_code':x['exit_codes'][0]} for x in hf['results']}
    summary={'tested_at':now,'endpoint':'https://ollama.com','transport':'Ollama CLI with OLLAMA_HOST=https://ollama.com','passed':sorted(PASS),'subscription_required':sorted(SUBSCRIPTION),'timings':timings}
    summary_path=out/'test-summary.json';summary_path.write_text(json.dumps(summary,indent=2)+'\n')
    c=sqlite3.connect(DB);c.execute('PRAGMA foreign_keys=ON');c.execute('BEGIN')
    models_sid,models_cap=capture(c,'https://ollama.com/v1/models','api_endpoint','Ollama','Ollama Cloud OpenAI-compatible models endpoint',1,1,models_path,'curl')
    tags_sid,tags_cap=capture(c,'https://ollama.com/api/tags','api_endpoint','Ollama','Ollama Cloud native model tags endpoint',1,1,tags_path,'curl')
    test_url='file://'+str(summary_path); test_sid,test_cap=capture(c,test_url,'local_observation','AZ Labs','Ollama Cloud Hyperfine runtime tests',0,1,summary_path,'hyperfine')
    c.execute("""INSERT OR IGNORE INTO monitoring_targets(provider_id,target_type,url,schedule_class,enabled,expected_format,parser_name)
    VALUES('ollama-cloud','models_endpoint','https://ollama.com/v1/models','frequent',1,'json','ollama-cloud')""")
    current={x['id'] for x in models}
    for x in models:
        mid=x['id']; canonical_slug=CANONICAL.get(mid); canonical_id=None
        if canonical_slug:
            row=c.execute('SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?',(canonical_slug,)).fetchone();canonical_id=row[0] if row else None
        meta={'id':mid,'object':x.get('object'),'created':x.get('created'),'owned_by':x.get('owned_by'),'native_tag':tags.get(mid)}
        c.execute("""INSERT INTO provider_models_v2(provider_id,canonical_model_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,provider_metadata_json,source_snapshot_id)
        VALUES('ollama-cloud',?,?,?,'available',?,?,?,NULL)
        ON CONFLICT(provider_id,model_identifier) DO UPDATE SET canonical_model_id=COALESCE(excluded.canonical_model_id,provider_models_v2.canonical_model_id),display_name=excluded.display_name,endpoint_status='available',endpoint_last_seen_at=excluded.endpoint_last_seen_at,endpoint_removed_at=NULL,provider_metadata_json=excluded.provider_metadata_json""",
        (canonical_id,mid,mid,now,now,json.dumps(meta,sort_keys=True)))
        pm=c.execute("SELECT provider_model_id,endpoint_first_seen_at FROM provider_models_v2 WHERE provider_id='ollama-cloud' AND model_identifier=?",(mid,)).fetchone();pmid=pm[0]
        c.execute("""INSERT OR IGNORE INTO model_events(provider_model_id,event_type,event_time,time_precision,evidence_source_id,evidence_capture_id,supporting_quote,confidence,details_json)
        VALUES(?,'endpoint_first_seen',?,'second',?,?,?,'verified',?)""",(pmid,now,models_sid,models_cap,'Present in official Ollama Cloud /v1/models endpoint',json.dumps({'provider_created':x.get('created')})))
        result='passed' if mid in PASS else 'unauthorized'
        err=None if result=='passed' else '403 subscription required'
        c.execute("""INSERT INTO handshake_tests(provider_model_id,harness_id,tested_at,test_type,status,latency_ms,observed_features_json,sanitized_error,runner_version)
        VALUES(?,NULL,?,'ollama_cloud_direct_chat',?,?,?,?,?)""",(pmid,now,result,timings[mid]['latency_ms'],json.dumps({'transport':'OLLAMA_HOST=https://ollama.com','exit_code':timings[mid]['exit_code'],'reply':'OK' if result=='passed' else None}),err,'model-catalogue-skill/1.0'))
        if mid in SUBSCRIPTION:
            c.execute("""INSERT INTO access_offers(provider_model_id,offer_type,first_observed_at,last_observed_at,requires_subscription,terms_summary,evidence_source_id,evidence_capture_id,confidence,last_verified_at)
            VALUES(?,'subscription_included',?,?,1,'Runtime returned HTTP 403 and explicitly required an Ollama subscription',?,?, 'verified',?)
            ON CONFLICT(provider_model_id,offer_type,starts_at,evidence_source_id) DO UPDATE SET last_observed_at=excluded.last_observed_at,last_verified_at=excluded.last_verified_at,evidence_capture_id=excluded.evidence_capture_id""",(pmid,now,now,test_sid,test_cap,now))
    # Retain historical rows, but remove stale aliases/routes from active availability.
    c.execute("UPDATE provider_models_v2 SET endpoint_status='removed',endpoint_removed_at=COALESCE(endpoint_removed_at,?) WHERE provider_id='ollama-cloud' AND model_identifier NOT IN (%s)" % ','.join('?'*len(current)),(now,*sorted(current)))
    c.execute("UPDATE provider_models_v2 SET endpoint_status='removed',endpoint_removed_at=COALESCE(endpoint_removed_at,?) WHERE provider_id='ollama'",(now,))
    c.commit()
    print(json.dumps({'provider':'ollama-cloud','official_models':len(current),'passed':len(PASS),'subscription_required':len(SUBSCRIPTION),'historical_ollama_routes_removed':c.execute("SELECT COUNT(*) FROM provider_models_v2 WHERE provider_id='ollama' AND endpoint_status='removed'").fetchone()[0],'evidence_dir':str(out)},indent=2))
if __name__=='__main__':main()
