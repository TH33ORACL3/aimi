#!/usr/bin/env python3
from __future__ import annotations
import json,re,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;DB=ROOT/'aimi.db'
c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
checks=[]
def add(name,passed,value,expected=None):checks.append({'check':name,'passed':bool(passed),'value':value,'expected':expected})
integrity=c.execute('PRAGMA integrity_check').fetchone()[0];add('sqlite_integrity',integrity=='ok',integrity,'ok')
dup=c.execute('SELECT COUNT(*) FROM (SELECT provider_id,model_identifier,COUNT(*) n FROM provider_models_v2 GROUP BY 1,2 HAVING n>1)').fetchone()[0];add('provider_model_uniqueness',dup==0,dup,0)
missing_event_source=c.execute('SELECT COUNT(*) FROM model_events e LEFT JOIN evidence_sources s USING(evidence_source_id) WHERE s.evidence_source_id IS NULL').fetchone()[0];add('event_sources_resolve',missing_event_source==0,missing_event_source,0)
verified_without_capture=c.execute("SELECT COUNT(*) FROM model_events WHERE confidence IN ('verified','corroborated') AND evidence_capture_id IS NULL").fetchone()[0];add('verified_events_have_immutable_capture',verified_without_capture==0,verified_without_capture,0)
free_window_without_capture=c.execute("SELECT COUNT(*) FROM model_events WHERE event_type='free_window_end' AND evidence_capture_id IS NULL").fetchone()[0];add('free_window_end_events_have_capture',free_window_without_capture==0,free_window_without_capture,0)
# A claim asserting confidence must be re-checkable, so it needs a saved copy of
# its source. A claim explicitly marked unverified or inferred is not asserting
# proof, so requiring a capture there would just push people to delete the row.
claims_without_capture=c.execute("SELECT COUNT(*) FROM evidence_claims WHERE evidence_capture_id IS NULL AND confidence IN ('verified','corroborated','single_source')").fetchone()[0];add('confident_claims_have_capture',claims_without_capture==0,claims_without_capture,0)
free_without_evidence=c.execute("SELECT COUNT(*) FROM access_offers WHERE offer_type IN ('genuine_zero_price','temporary_free_window') AND (evidence_source_id IS NULL OR evidence_capture_id IS NULL)").fetchone()[0];add('free_offers_have_evidence',free_without_evidence==0,free_without_evidence,0)
bench_no_capture=c.execute("SELECT COUNT(*) FROM benchmark_scores WHERE confidence IN ('corroborated','verified') AND evidence_capture_id IS NULL").fetchone()[0];add('benchmark_scores_have_immutable_capture',bench_no_capture==0,bench_no_capture,0)
best_dup=c.execute("SELECT COUNT(*) FROM (SELECT canonical_model_id,benchmark,benchmark_version,metric,SUM(is_best_config) c FROM benchmark_scores GROUP BY 1,2,3,4 HAVING c>1)").fetchone()[0];add('benchmark_scores_single_best_per_model',best_dup==0,best_dup,0)
bench_range=c.execute('SELECT COUNT(*) FROM benchmark_scores WHERE value<0').fetchone()[0];add('benchmark_scores_values_nonnegative',bench_range==0,bench_range,0)
expired_active=c.execute("SELECT COUNT(*) FROM currently_free_provider_models WHERE ends_at IS NOT NULL AND datetime(ends_at)<=datetime('now')").fetchone()[0];add('expired_free_offers_not_active',expired_active==0,expired_active,0)
pi_current=[r[0]+'/'+r[1] for r in c.execute("SELECT e.provider_id,e.model_identifier FROM model_order_profile_entries e JOIN model_order_profiles p USING(profile_id) WHERE p.harness_id='pi' AND p.profile_name='current-local-order' ORDER BY e.position")]
pi_pref=[r[0]+'/'+r[1] for r in c.execute("SELECT e.provider_id,e.model_identifier FROM model_order_profile_entries e JOIN model_order_profiles p USING(profile_id) WHERE p.harness_id='pi' AND p.profile_name='aubrey-preferred-order' ORDER BY e.position")]
# The recorded preferred order is a snapshot of what was enabled at one moment,
# not a durable invariant. Aubrey enables and disables models routinely, so a
# differing count or order is normal and must not fail validation. What does
# matter is whether a model Pi is configured to use still exists at its provider.
unknown_routes=[entry for entry in pi_current if c.execute('SELECT COUNT(*) FROM provider_models_v2 WHERE provider_id=? AND model_identifier=? AND endpoint_status NOT IN (?,?)',(entry.split('/',1)[0],entry.split('/',1)[1],'removed','unavailable')).fetchone()[0]==0]
add('pi_enabled_models_exist_at_provider',not unknown_routes,unknown_routes or 0,0)
unreviewed=c.execute('SELECT COUNT(*) FROM endpoint_changes WHERE reviewed=0').fetchone()[0];add('endpoint_changes_reviewed',unreviewed==0,unreviewed,0)
failed_targets=c.execute('SELECT COUNT(*) FROM monitoring_targets WHERE consecutive_failures>0').fetchone()[0];add('monitoring_targets_healthy',failed_targets==0,failed_targets,0)
health_tables=c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name IN ('free_model_probe_status','free_model_probe_daily')").fetchone()[0]
if health_tables==2:
 stale_health=c.execute("SELECT COUNT(*) FROM free_model_probe_status s WHERE s.currently_free=1 AND NOT EXISTS(SELECT 1 FROM currently_free_provider_models f WHERE f.provider_model_id=s.provider_model_id)").fetchone()[0];add('free_health_targets_still_free',stale_health==0,stale_health,0)
 untested_free=c.execute("SELECT COUNT(*) FROM currently_free_provider_models f WHERE NOT EXISTS(SELECT 1 FROM free_model_probe_status s WHERE s.provider_model_id=f.provider_model_id AND s.currently_free=1)").fetchone()[0];add('active_free_routes_have_health_status',untested_free==0,untested_free,0)
 expired_health=c.execute("SELECT COUNT(*) FROM free_model_probe_daily WHERE test_date < date('now','-30 days')").fetchone()[0];add('free_health_history_within_retention',expired_health==0,expired_health,0)
# The schema file is what a fresh install runs. Drift between it and the live
# database silently produces installs whose CLI commands crash on missing tables.
drift=subprocess.run([sys.executable,str(ROOT/'dump_schema.py'),'--check'],capture_output=True,text=True);add('schema_file_matches_database',drift.returncode==0,drift.stderr.strip() or 'in sync','in sync')
# Evidence is only immutable if the referenced capture still exists on disk.
referenced={r[0] for r in c.execute('SELECT DISTINCT snapshot_path FROM monitoring_runs WHERE snapshot_path IS NOT NULL')}|{r[0] for r in c.execute('SELECT DISTINCT raw_snapshot_path FROM model_sources WHERE raw_snapshot_path IS NOT NULL')}
missing_snapshots=sum(1 for p in referenced if not (Path(p) if Path(p).is_absolute() else ROOT/p).exists());add('referenced_snapshots_present',missing_snapshots==0,missing_snapshots,0)
# WAL keeps recent writes outside the main file, so checkpoint before scanning bytes.
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
raw=DB.read_bytes();patterns=[rb'(?<![A-Za-z0-9_-])sk-(?:proj-)?[A-Za-z0-9_-]{24,}',rb'(?<![A-Za-z0-9_-])sk-or-[A-Za-z0-9_-]{20,}',rb'(?<![A-Za-z0-9_-])nvapi-[A-Za-z0-9_-]{20,}',rb'(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{20,}',rb'(?<![A-Za-z0-9_-])cf(?:at|ut)_[A-Za-z0-9_-]{20,}',rb'(?<![A-Za-z0-9_-])Bearer [A-Za-z0-9_-]{30,}'];hits=sum(bool(re.search(p,raw,re.I)) for p in patterns);add('database_secret_scan',hits==0,hits,0)
report={'passed':all(x['passed'] for x in checks),'checks':checks,'metrics':{'provider_routes':c.execute('SELECT COUNT(*) FROM provider_models_v2').fetchone()[0],'canonical_models':c.execute('SELECT COUNT(*) FROM canonical_models').fetchone()[0],'active_free_routes':c.execute('SELECT COUNT(*) FROM currently_free_provider_models').fetchone()[0],'verified_events':c.execute("SELECT COUNT(*) FROM model_events WHERE confidence IN ('verified','corroborated')").fetchone()[0],'evidence_sources':c.execute('SELECT COUNT(*) FROM evidence_sources').fetchone()[0],'claims':c.execute('SELECT COUNT(*) FROM evidence_claims').fetchone()[0],'installed_harnesses':c.execute('SELECT COUNT(*) FROM harness_installations WHERE installed=1').fetchone()[0],'pi_enabled_models':len(pi_current),'pi_snapshot_order_differs':pi_current!=pi_pref,'benchmark_scores':c.execute('SELECT COUNT(*) FROM benchmark_scores').fetchone()[0],'deepswe_scored_models':c.execute('SELECT COUNT(DISTINCT canonical_model_id) FROM benchmark_scores WHERE benchmark="deepswe" AND is_best_config=1').fetchone()[0],'free_health_green':c.execute("SELECT COUNT(*) FROM free_model_probe_status WHERE currently_free=1 AND last_status='ok'").fetchone()[0] if health_tables==2 else 0,'free_health_orange':c.execute("SELECT COUNT(*) FROM free_model_probe_status WHERE currently_free=1 AND last_status='rate_limited'").fetchone()[0] if health_tables==2 else 0,'free_health_red':c.execute("SELECT COUNT(*) FROM free_model_probe_status WHERE currently_free=1 AND last_status NOT IN ('ok','rate_limited')").fetchone()[0] if health_tables==2 else 0,'free_health_daily_rows':c.execute('SELECT COUNT(*) FROM free_model_probe_daily').fetchone()[0] if health_tables==2 else 0}}
(ROOT/'validation-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
