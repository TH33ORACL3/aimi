#!/usr/bin/env python3
"""Ingest qwen/qwen-image-3-pro and qwen/qwen-image-3 (OpenRouter images API).

Approved by Aubrey 2026-08-05 (option 3). Records models row, canonical
identity, provider_models_v2 route, pricing evidence from the live
/api/v1/images/models + endpoint detail, and an endpoint_first_seen event.
Backs up aimi.db first.
"""
import re, shutil, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'aimi.db'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
SRC = 'https://openrouter.ai/api/v1/images/models'

def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def created_iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

MODELS = [
    dict(model_id='qwen/qwen-image-3-pro', display='Qwen: Qwen Image 3 Pro',
         desc='Qwen Image 3 Pro is an image generation and editing model from Qwen. It supports precise rendering of text and details as small as 10px, along with richer world knowledge.',
         created=1785894548, family='qwen-image', dev='Qwen',
         input_cost='0.003', output_cost='0.04', output_variants='1K 0.04 / 2K 0.075',
         notes='resolution 1K/2K; aspect ratios 1:1..16:9; n 1-6; input_references 0-4; seed; streaming false'),
    dict(model_id='qwen/qwen-image-3', display='Qwen: Qwen Image 3',
         desc='Qwen Image 3 is an image generation and editing model from Qwen.',
         created=1785894548, family='qwen-image', dev='Qwen',
         input_cost='0.003', output_cost='0.03', output_variants='1K 0.03 / 2K 0.03',
         notes='resolution 1K/2K; n 1-6; input_references 0-4; streaming false'),
]

def main():
    bak = DB.with_name(f"aimi.db.bak.qwen-image-ingest-{NOW[:10].replace('-','')}")
    shutil.copy2(DB, bak)
    print(f"backup: {bak.name}")

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')

    for m in MODELS:
        # canonical identity
        cs = slug(m['family'] + '-' + m['model_id'].split('/')[-1])
        c.execute("""INSERT OR IGNORE INTO canonical_models
            (canonical_slug, developer, family, canonical_name, lifecycle_status, weights_status)
            VALUES (?,?,?,?, 'unknown','unknown')""",
            (cs, m['dev'], m['family'], m['display'].split(': ')[-1]))
        cid = c.execute('SELECT canonical_model_id FROM canonical_models WHERE canonical_slug=?', (cs,)).fetchone()['canonical_model_id']

        # models row
        c.execute("""INSERT OR IGNORE INTO models
            (model_id, provider, free_pricing, display_name, description, discovered_at, last_verified_at,
             pricing_status, pricing_unit, pricing_evidence, source_endpoint, api_style, base_url,
             auth_env_var, model_family, input_modalities, output_modalities, supports_reasoning,
             supports_tools, supports_structured_output, supports_streaming, verification_confidence, category)
            VALUES (?,?,0,?,?,?,?,'paid','per-image',?,?,?,?,?,?,?,?,0,0,0,0,'high','image')""",
            (m['model_id'], 'openrouter', m['display'], m['desc'], NOW, NOW,
             f"OpenRouter {SRC} + endpoint detail, captured 2026-08-05; input_image ${m['input_cost']}/image, output_image ${m['output_variants']}",
             SRC, 'openrouter-images', 'https://openrouter.ai/api/v1', 'AIMI_OPENROUTER_API_KEY',
             m['family'], 'text,image', 'image'))
        mid = c.execute('SELECT id FROM models WHERE model_id=? AND provider="openrouter"', (m['model_id'],)).fetchone()['id']

        # route row
        c.execute("""INSERT OR IGNORE INTO provider_models_v2
            (provider_id, canonical_model_id, model_identifier, display_name, endpoint_status,
             endpoint_first_seen_at, endpoint_last_seen_at, input_modalities_json, output_modalities_json,
             streaming, description, provider_created_at, provider_metadata_json)
            VALUES ('openrouter',?,?,?, 'available', ?, ?, ?, ?, 0, ?, ?, ?)""",
            (cid, m['model_id'], m['display'], NOW, NOW, '["text","image"]', '["image"]',
             m['desc'], created_iso(m['created']),
             f'{{"supported_parameters":{{"resolution":["1K","2K"],"n":{{"min":1,"max":6}}}},"notes":"{m["notes"]}"}}'))

        # pricing evidence
        c.execute("""INSERT INTO pricing_evidence
            (model_id, status, prompt_price, completion_price, currency, billing_unit,
             evidence_type, source_endpoint, captured_at, confidence, notes)
            VALUES (?,'paid',?,?,'USD','image','api_endpoint',?,?,'high',?)""",
            (mid, m['input_cost'], m['output_cost'], f'{SRC}/endpoints', NOW, m['output_variants']))

        # event (needs evidence_source_id)
        c.execute("""INSERT OR IGNORE INTO evidence_sources
            (url, source_type, publisher, title, official, primary_source, retrieved_at, trust_priority)
            VALUES (?,'api_endpoint','OpenRouter','OpenRouter image model catalogue',1,1,?,90)""",
            (SRC, NOW))
        esid = c.execute('SELECT evidence_source_id FROM evidence_sources WHERE url=?', (SRC,)).fetchone()['evidence_source_id']
        pmid = c.execute('SELECT provider_model_id FROM provider_models_v2 WHERE provider_id="openrouter" AND model_identifier=?',
                         (m['model_id'],)).fetchone()['provider_model_id']
        c.execute("""INSERT INTO model_events (provider_model_id, event_type, event_time, time_precision,
            evidence_source_id, supporting_quote, confidence, details_json)
            VALUES (?, 'endpoint_first_seen', ?, 'second', ?, 'First seen on OpenRouter images API catalogue', 'verified', ?)""",
            (pmid, NOW, esid, f'{{"source_endpoint": "{SRC}"}}'))
        print(f"ingested: {m['model_id']}")

    c.commit()
    c.close()
    print("done")

if __name__ == '__main__':
    main()
