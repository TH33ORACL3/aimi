#!/usr/bin/env python3
"""Ingest verified Mistral reasoning/compat findings (2026-08-17).

Evidence:
  - Official docs: https://docs.mistral.ai/capabilities/reasoning/  (reasoning_effort = "none"|"high" only)
  - Local API tests 2026-08-17 (Aubrey's MacBook):
      * mistral-medium-3-5 / mistral-medium-latest: reasoning_effort "none" -> 200 (minimal thinking, no chunk)
        "high" -> 200 (full thinking chunk). "low"/"medium" -> HTTP 400.
      * mistral-large-latest / mistral-large-2512: reasoning_effort low/medium/high -> 400,
        thinking {"type":"enabled"} -> 422. No reasoning support yet ("reasoning version coming soon").
      * Pi harness integration (pi --model mistral/...):
        - store:false -> 422  (fix: compat.supportsStore=false)
        - role:developer -> 422 on BOTH models; role:system -> 200 (fix: compat.supportsDeveloperRole=false)
        - max_completion_tokens accepted, but max_tokens used (maxTokensField="max_tokens")
        - streaming with reasoning on: delta.content is a part-array -> rendered as [object Object] by pi-ai (upstream)
      * All tests used MISTRAL_API_KEY against https://api.mistral.ai/v1, Hyperfine --runs 1 --warmup 0, parallel.
"""
from __future__ import annotations
import json, sqlite3, sys, shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'aimi.db'
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
PREVIEW = '--preview' in sys.argv

DOCS = {
    'url': 'https://docs.mistral.ai/capabilities/reasoning/',
    'source_type': 'official_docs',
    'publisher': 'Mistral AI',
    'title': 'Mistral Docs: Reasoning (reasoning_effort parameter)',
    'official': 1, 'primary_source': 1,
    'retrieved_at': '2026-08-17T19:50:00+00:00',
    'verification_status': 'verified',
    'trust_priority': 90,
    'notes': 'Official docs: mistral-small-latest and mistral-medium-3-5 support reasoning_effort; only "high" and "none" documented. "low"/"medium" not listed.',
}

LOCAL_TEST = {
    'url': 'file:///Users/TH33_ORACL3/AZ%20Labs/2%20-%20Testing/AIMI/.session/mistral-reasoning-tests-2026-08-17',
    'source_type': 'local_observation',
    'publisher': 'Aubrey Zemba',
    'title': 'Local Mistral reasoning_effort + Pi harness integration tests (2026-08-17)',
    'official': 0, 'primary_source': 0,
    'retrieved_at': NOW,
    'verification_status': 'verified',
    'trust_priority': 70,
    'notes': 'Hyperfine runs against api.mistral.ai/v1 with MISTRAL_API_KEY; all three Pi scenarios verified (large plain OK, medium none OK, medium high OK).',
}

CLAIMS = [
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-medium-latest',
        'field_name': 'reasoning', 'value_json': 'true',
        'supporting_quote': 'mistral-medium-latest supports reasoning_effort param (verified 200 OK for none and high)',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-medium-3-5',
        'field_name': 'reasoning', 'value_json': 'true',
        'supporting_quote': 'mistral-medium-3-5 supports reasoning_effort param (verified 200 OK for none and high)',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-medium-latest',
        'field_name': 'reasoning_efforts', 'value_json': '["none","high"]',
        'supporting_quote': 'reasoning_effort="none" -> 200 minimal thinking, no chunk; "high" -> 200 full thinking chunk; "low"/"medium" -> HTTP 400',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-medium-3-5',
        'field_name': 'reasoning_efforts', 'value_json': '["none","high"]',
        'supporting_quote': 'reasoning_effort="none" -> 200; "high" -> 200 with thinking chunk; "low"/"medium" -> HTTP 400',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-large-latest',
        'field_name': 'reasoning', 'value_json': 'false',
        'supporting_quote': 'No reasoning support: reasoning_effort low/medium/high all -> HTTP 400; thinking {"type":"enabled"} -> 422. Docs: "reasoning version coming soon"',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-large-2512',
        'field_name': 'reasoning', 'value_json': 'false',
        'supporting_quote': 'No reasoning support via API yet (same model as mistral-large-latest, which returned 400/422)',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model', 'subject_key': 'mistral/mistral-medium-latest',
        'field_name': 'thinking_api',
        'value_json': json.dumps({
            'openai_compatible': {
                'endpoint': 'https://api.mistral.ai/v1/chat/completions',
                'parameters': {'reasoning_effort': 'high'},
                'accepted_values': ['none', 'high'],
                'note': 'low/medium rejected (400). high returns reasoning chunk; none omits it.',
            },
        }),
        'supporting_quote': 'Mistral Medium 3.5 reasoning via OpenAI-compatible reasoning_effort param',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'harness', 'subject_key': 'pi/mistral', 'field_name': 'compat_requirements',
        'value_json': json.dumps({
            'compat': {
                'maxTokensField': 'max_tokens',
                'supportsReasoningEffort': True,
                'supportsStore': False,
                'supportsDeveloperRole': False,
            },
            'thinkingLevelMap': {
                'off': 'none', 'minimal': 'none', 'low': 'none', 'medium': 'none',
                'high': 'high', 'xhigh': 'high', 'max': 'high',
            },
        }),
        'supporting_quote': 'Pi needs supportsStore=false (store:false -> 422) and supportsDeveloperRole=false (developer role -> 422 on both Mistral models). Map every Pi thinking level to none/high.',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
    {
        'subject_type': 'harness', 'subject_key': 'pi/mistral', 'field_name': 'known_issue',
        'value_json': json.dumps({'issue': 'thinking parts rendered as [object Object]',
            'cause': 'Mistral streams reasoning as delta.content part-array; pi-ai does block.text += delta.content',
            'workaround': 'thinking off/none streams clean; upstream pi-ai fix required for clean thinking display'}),
        'supporting_quote': 'Verified: Mistral high-reasoning streaming sends content:[{"type":"thinking",...}]; --thinking off produces clean "OK"',
        'confidence': 'verified', 'verification_method': 'api_test',
    },
]

METADATA_UPDATES = [
    ('mistral', 'mistral-medium-latest'),
    ('mistral', 'mistral-medium-3-5'),
]

COMPAT_SCHEMA = {
    'thinking': {
        'api_backend': 'chat_completions',
        'parameters': {'reasoning_effort': 'high'},
        'reasoning_efforts': ['none', 'high'],
        'thinking_level_map': {'off': 'none', 'minimal': 'none', 'low': 'none', 'medium': 'none', 'high': 'high', 'xhigh': 'high', 'max': 'high'},
        'compat_required': {'maxTokensField': 'max_tokens', 'supportsReasoningEffort': True, 'supportsStore': False, 'supportsDeveloperRole': False},
        'notes': 'Mistral Medium 3.5 reasoning via OpenAI-compatible reasoning_effort (none|high). Pi must send system role (developer -> 422) and omit store (-> 422). Thinking deltas stream as part-arrays; pi-ai renders them as [object Object] (upstream issue).',
    }
}
COMPAT_NOTES = ('Pi + Mistral: use compat {"maxTokensField":"max_tokens","supportsReasoningEffort":true,"supportsStore":false,"supportsDeveloperRole":false}; '
                'medium supports reasoning_effort "none"|"high" only (low/medium -> 400); '
                'large-latest has no reasoning support yet; '
                'developer role & store:false -> 422; '
                'thinking streams as part-arrays -> [object Object] in pi-ai (upstream).')


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.execute('PRAGMA foreign_keys=ON')
    backup = ROOT / f'aimi.db.bak.ingest-mistral-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    if not PREVIEW:
        shutil.copy2(DB, backup)

    conn.execute('BEGIN')
    try:
        for src in (DOCS, LOCAL_TEST):
            conn.execute(
                """INSERT OR IGNORE INTO evidence_sources(url, source_type, publisher, title, official, primary_source, retrieved_at, verification_status, trust_priority, notes)
                VALUES(:url, :source_type, :publisher, :title, :official, :primary_source, :retrieved_at, :verification_status, :trust_priority, :notes)""",
                src,
            )
        docs_id = conn.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (DOCS['url'],)).fetchone()[0]
        test_id = conn.execute("SELECT evidence_source_id FROM evidence_sources WHERE url=?", (LOCAL_TEST['url'],)).fetchone()[0]

        added_claims = 0
        for claim in CLAIMS:
            src_id = docs_id if claim['verification_method'] == 'docs_citation' else test_id
            cur = conn.execute(
                """SELECT 1 FROM evidence_claims WHERE subject_type=? AND subject_key=? AND field_name=? AND value_json=? AND evidence_source_id=?""",
                (claim['subject_type'], claim['subject_key'], claim['field_name'], claim['value_json'], src_id),
            )
            if cur.fetchone():
                print(f"  [skip] claim {claim['subject_key']} {claim['field_name']} (already present)")
                continue
            conn.execute(
                """INSERT INTO evidence_claims(subject_type, subject_key, field_name, value_json, value_type, evidence_source_id, supporting_quote, observed_at, confidence, verification_method, source_priority)
                VALUES(:subject_type, :subject_key, :field_name, :value_json, 'json', :evidence_source_id, :supporting_quote, :observed_at, :confidence, :verification_method, 80)""",
                {**claim, 'evidence_source_id': src_id, 'observed_at': NOW},
            )
            added_claims += 1
            print(f"  + claim {claim['subject_key']} {claim['field_name']} -> {claim['value_json'][:80]}")

        for pid, mid in METADATA_UPDATES:
            row = conn.execute(
                "SELECT provider_model_id, provider_metadata_json FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?",
                (pid, mid),
            ).fetchone()
            if not row:
                print(f"  [warn] route not found: {pid}/{mid}")
                continue
            existing = json.loads(row[1]) if row[1] else {}
            existing.update({'thinking': True, 'reasoning_efforts': ['none', 'high'],
                             'thinking_api': {'openai_compatible': {'endpoint': 'https://api.mistral.ai/v1/chat/completions',
                                                                    'parameters': {'reasoning_effort': 'high'}}}})
            conn.execute(
                "UPDATE provider_models_v2 SET provider_metadata_json=? WHERE provider_model_id=?",
                (json.dumps(existing), row[0]),
            )
            print(f"  + metadata {pid}/{mid}: thinking=True, reasoning_efforts=[none,high]")

        # reasoning flags: enforce verified truth (medium=1, large=0)
        set_reason = [('mistral', 'mistral-medium-latest'), ('mistral', 'mistral-medium-3-5'),
                      ('openrouter', 'mistralai/mistral-medium-3-5')]
        clear_reason = [('mistral', 'mistral-large-latest'), ('mistral', 'mistral-large-2512'),
                        ('openrouter', 'mistralai/mistral-large-2512')]
        for pid, mid in set_reason:
            n = conn.execute("UPDATE provider_models_v2 SET reasoning=1 WHERE provider_id=? AND model_identifier=? AND (reasoning IS NULL OR reasoning=0)", (pid, mid)).rowcount
            print(f"  + reasoning=1 on {pid}/{mid} ({n} row)")
        for pid, mid in clear_reason:
            n = conn.execute("UPDATE provider_models_v2 SET reasoning=0 WHERE provider_id=? AND model_identifier=? AND reasoning=1", (pid, mid)).rowcount
            print(f"  + reasoning=0 on {pid}/{mid} ({n} row)")

        n = conn.execute(
            """UPDATE harness_provider_support SET config_schema_json=?, compatibility_notes=?, last_verified_at=? WHERE harness_id='pi' AND provider_id='mistral'""",
            (json.dumps(COMPAT_SCHEMA), COMPAT_NOTES, NOW),
        ).rowcount
        print(f"  + harness_provider_support pi/mistral updated ({n} row)")

        if PREVIEW:
            conn.execute('ROLLBACK')
            print(json.dumps({'status': 'preview', 'mode': '--preview (no changes applied)',
                              'evidence_sources': 2, 'claims_to_add': added_claims,
                              'metadata_updates': len(METADATA_UPDATES),
                              'harness_note_update': 'pi/mistral'}, indent=2))
        else:
            conn.execute('COMMIT')
            print(json.dumps({'status': 'ok', 'backup': str(backup), 'evidence_sources_added': 2,
                              'evidence_claims_added': added_claims,
                              'metadata_updates': len(METADATA_UPDATES),
                              'harness_provider_support_updated': 'pi/mistral'}, indent=2))
    except Exception as e:
        conn.execute('ROLLBACK')
        print(json.dumps({'status': 'error', 'message': str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()