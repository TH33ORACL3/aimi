#!/usr/bin/env python3
"""Create a public SQLite export and fail closed if secret/personal markers remain."""
from __future__ import annotations
import re,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent; SRC=ROOT/'aimi.db'; DIST=ROOT/'dist'; OUT=DIST/'aimi.public.db'
PATTERNS={
 'home_path':rb'/Users/TH33_ORACL3',
 'openai_key':rb'(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{20,}',
 'openrouter_key':rb'(?<![A-Za-z0-9_-])sk-or-[A-Za-z0-9_-]{20,}',
 'nvidia_key':rb'(?<![A-Za-z0-9_-])nvapi-[A-Za-z0-9_-]{20,}',
 'github_token':rb'(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{20,}',
 'cloudflare_token':rb'(?<![A-Za-z0-9_-])cf(?:at|ut)_[A-Za-z0-9_-]{20,}',
 'generic_bearer':rb'(?<![A-Za-z0-9_-])Bearer [A-Za-z0-9_-]{24,}',
 'anthropic_key':rb'(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_-]{20,}',
}
def main():
 DIST.mkdir(exist_ok=True); OUT.unlink(missing_ok=True)
 src=sqlite3.connect(SRC); dst=sqlite3.connect(OUT); src.backup(dst); src.close(); dst.execute('PRAGMA foreign_keys=OFF')
 # Remove personal machine state while preserving reusable harness/provider/model knowledge.
 for table in ('credential_inventory','harness_model_entries','harness_available_model_entries','harness_installations','user_rankings','model_order_profile_entries','model_order_profiles','handshake_tests'):
  dst.execute(f'DELETE FROM {table}')
 # Local files and raw captures are private. Keep official web/API source identities and claims.
 local_ids=[r[0] for r in dst.execute("SELECT evidence_source_id FROM evidence_sources WHERE source_type IN ('local_config','local_observation') OR url LIKE 'file://%'")]
 if local_ids:
  qs=','.join('?'*len(local_ids));dst.execute(f'DELETE FROM evidence_claims WHERE evidence_source_id IN ({qs})',local_ids);dst.execute(f'DELETE FROM model_events WHERE evidence_source_id IN ({qs})',local_ids);dst.execute(f'DELETE FROM evidence_captures WHERE evidence_source_id IN ({qs})',local_ids);dst.execute(f'DELETE FROM evidence_sources WHERE evidence_source_id IN ({qs})',local_ids)
 dst.execute("UPDATE harnesses SET source_note_path=NULL")
 dst.execute("UPDATE evidence_sources SET archived_path=NULL")
 dst.execute("UPDATE evidence_captures SET archived_path=NULL")
 dst.execute("UPDATE model_sources SET raw_snapshot_path=NULL")
 dst.execute("UPDATE monitoring_runs SET snapshot_path=NULL,error_summary=CASE WHEN error_summary IS NULL THEN NULL ELSE '[redacted]' END")
 dst.execute("UPDATE automation_jobs SET external_job_id=NULL,script_name=NULL,workdir=NULL,health_notes=NULL")
 dst.execute("UPDATE providers SET base_url=replace(base_url,'f4bd871c679a4049632dd48cb38b536f','{account_id}'),official_models_endpoint=replace(official_models_endpoint,'f4bd871c679a4049632dd48cb38b536f','{account_id}')")
 dst.commit(); dst.execute('VACUUM'); dst.close()
 raw=OUT.read_bytes();fail=[]
 for name,pat in PATTERNS.items():
  if re.search(pat,raw,re.I):fail.append(name)
 # SQLite integrity is part of export, not an optional follow-up.
 check=subprocess.run(['sqlite3',str(OUT),'PRAGMA integrity_check;'],capture_output=True,text=True)
 if check.stdout.strip()!='ok':fail.append('sqlite_integrity')
 if fail:
  OUT.unlink(missing_ok=True); print('Sanitized export rejected: '+', '.join(fail),file=sys.stderr);return 1
 OUT.chmod(0o644);print(f'Created {OUT} ({OUT.stat().st_size} bytes); integrity=ok; secret_scan=passed');return 0
if __name__=='__main__':raise SystemExit(main())
