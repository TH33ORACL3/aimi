#!/usr/bin/env python3
"""Persist completed Warp/Oz custom-model smoke results without storing secrets."""
from __future__ import annotations
import json, sqlite3, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/'aimi.db'
EVIDENCE=ROOT/'evidence'/'warp'
BIN=Path('/Applications/Warp.app/Contents/MacOS/stable')
NOW=datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# Only results that actually completed are recorded as tests. The interrupted
# batch is preserved separately as an evidence summary, never guessed as pass.
COMPLETED={
    '14ad40bb-d94e-4946-973f-c0e10ea878b3': ('failed', 'ResourceExhausted: Warp worker local total request limit reached (33/32)', None),
    '4f71ef41-e668-446c-8f38-7ad6021619d1': ('failed', 'OpenRouter returned HTTP 404: no endpoints found for openrouter/owl-alpha', None),
    '5594c349-bbcf-43a8-8da6-445e1f85ae25': ('passed', None, 'OK'),
    '661ca01a-22da-4dda-89ca-829d20b3d0ee': ('failed', "Model returned non-exact output: Replied with exactly 'OK' as requested", "Replied with exactly 'OK' as requested"),
}

def main():
    try:
        live=json.loads(subprocess.run([str(BIN),'model','list','--output-format','json'],capture_output=True,text=True,timeout=30,check=True).stdout)
        ids=[x['id'] for x in live if isinstance(x,dict) and isinstance(x.get('id'),str) and len(x['id'])==36]
    except Exception:
        ids=list(COMPLETED)
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB);c.execute('PRAGMA foreign_keys=ON')
    c.executescript((ROOT/'subscription_upgrade.sql').read_text())
    for model,(status,error,output) in COMPLETED.items():
        exists=c.execute("""SELECT 1 FROM harness_model_tests
          WHERE harness_id='obsidian-warp' AND model_identifier=? AND status=?
            AND COALESCE(exact_output,'')=COALESCE(?,'')
            AND COALESCE(sanitized_error,'')=COALESCE(?,'')
            AND date(tested_at)=date(?) LIMIT 1""",(model,status,output,error,NOW)).fetchone()
        if not exists:
            c.execute("""INSERT INTO harness_model_tests(harness_id,model_identifier,tested_at,status,latency_ms,exact_output,sanitized_error,runner_version,test_command_template)
            VALUES(?,?,?,?,NULL,?,?,?,?)""",('obsidian-warp',model,NOW,status,output,error,'Warp Oz via Hyperfine','stable model run --output-format ndjson'))
    c.commit()
    summary={'tested_at':NOW,'harness':'obsidian-warp','source':'Hyperfine --runs 1 --warmup 0 --show-output --ignore-failure','models_listed':ids,'completed_results':{k:{'status':v[0],'sanitized_error':v[1],'exact_output':v[2]} for k,v in COMPLETED.items()},'not_completed':[x for x in ids if x not in COMPLETED],'note':'The batch was stopped after the fifth benchmark because Warp requests were taking too long. No status is inferred for models in not_completed.'}
    (EVIDENCE/'custom-model-test-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'recorded':len(COMPLETED),'not_completed':len(summary['not_completed']),'evidence':str(EVIDENCE/'custom-model-test-summary.json')},indent=2))

if __name__=='__main__':main()
