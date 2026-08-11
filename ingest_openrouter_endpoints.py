#!/usr/bin/env python3
"""Record OpenRouter's API v1 endpoint surface in the catalogue.

Adds provider_api_endpoints rows for every endpoint verified live on
2026-08-05 (HTTP probes against https://openrouter.ai/api/v1, plus the
official OpenAPI-generated changelog at
https://openrouter.ai/docs/changelog.md as the authoritative inventory),
registers the images/models and changelog URLs as monitoring targets, and
captures raw catalogue snapshots for images and videos.

Run deliberately, never as a side effect of answering a question.
Takes a timestamped backup of aimi.db first.
"""
import json, re, shutil, sqlite3, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'aimi.db'
SNAPSHOTS = ROOT / 'snapshots'
BASE = 'https://openrouter.ai/api/v1'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
TODAY = NOW[:10]

# (path, method, kind, purpose, input_modalities, output_modalities, auth_required, first_seen, status, notes)
# first_seen: 'new' = first verified in this catalogue today; None = pre-existing route already known to AIMI
ENDPOINTS = [
    ('/api/v1/models', 'GET', 'models_catalogue', 'Text/chat model catalogue (existing AIMI source)', 'text', 'text', 0, None, 'available', 'official_models_endpoint for provider openrouter'),
    ('/api/v1/chat/completions', 'POST', 'chat_completions', 'OpenAI-compatible Chat Completions', 'text', 'text', 1, None, 'available', 'api_style openai-completions'),
    ('/api/v1/messages', 'POST', 'anthropic_messages', 'Anthropic Messages API compatibility', 'text', 'text', 1, 'new', 'available', 'confirmed by OpenAPI changelog 2026-07-28+ and docs'),
    ('/api/v1/responses', 'POST', 'responses', 'OpenAI Responses API (reasoning, tools, web search)', 'text', 'text', 1, None, 'available', 'probe: 401 with dummy auth = live'),
    ('/api/v1/embeddings', 'POST', 'embeddings', 'Vector embeddings from text and images', 'text,image', 'embedding', 1, 'new', 'available', 'probe: 401 with valid shape = live'),
    ('/api/v1/rerank', 'POST', 'rerank', 'Rerank documents against a query', 'text', 'text', 1, 'new', 'available', 'listed in SDK references and OpenAPI changelog'),
    ('/api/v1/images', 'POST', 'images_generate', 'Image generation and editing (text/image in, image out)', 'text,image', 'image', 1, 'new', 'available', 'qwen/qwen-image-3-pro quickstart; 402 insufficient credits with real key = live'),
    ('/api/v1/images/models', 'GET', 'images_models_catalogue', 'Image model catalogue with architecture and parameters', 'text', 'json', 0, 'new', 'available', 'verified live 2026-08-05; 40 models listed'),
    ('/api/v1/images/models/{author}/{slug}/endpoints', 'GET', 'images_endpoint_detail', 'Per-endpoint pricing and provider detail for image models', 'text', 'json', 0, 'new', 'available', 'verified live 2026-08-05'),
    ('/api/v1/generation', 'GET', 'generation_status', 'Generation status and usage metadata lookup (async image jobs)', 'text', 'json', 1, 'new', 'available', 'probe: expected id, returned Generation not found = live'),
    ('/api/v1/audio/speech', 'POST', 'audio_speech', 'Text-to-speech', 'text', 'audio', 1, 'new', 'available', 'probe: 401 with valid shape = live'),
    ('/api/v1/audio/transcriptions', 'POST', 'audio_transcriptions', 'Speech-to-text transcription', 'audio', 'text', 1, 'new', 'available', 'probe: 401 with valid shape = live'),
    ('/api/v1/videos', 'POST', 'videos_generate', 'Video generation', 'text,image', 'video', 1, 'new', 'available', 'listed in OpenAPI changelog'),
    ('/api/v1/videos/models', 'GET', 'videos_models_catalogue', 'Video model catalogue (minimal listing; no pricing detail yet)', 'text', 'json', 0, 'new', 'available', 'verified live 2026-08-05; 21 models listed'),
    ('/api/v1/files', 'POST', 'files_upload', 'Upload files', 'file', 'json', 1, 'new', 'available', 'probe: 401 = live; OpenAPI changelog'),
    ('/api/v1/files', 'GET', 'files_list', 'List files', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/files/{file_id}', 'GET', 'files_get', 'Get file metadata', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/files/{file_id}', 'DELETE', 'files_delete', 'Delete a file', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/files/{file_id}/content', 'GET', 'files_download', 'Download file content', 'text', 'file', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/guardrails', 'POST', 'guardrails_create', 'Create a guardrail', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/guardrails', 'GET', 'guardrails_list', 'List guardrails', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/guardrails/{id}', 'GET', 'guardrails_get', 'Get a guardrail', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/guardrails/{id}', 'PATCH', 'guardrails_update', 'Update a guardrail', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/benchmarks', 'GET', 'benchmarks', 'Benchmark results', 'text', 'json', 0, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/byok', 'GET', 'byok_list', 'List BYOK providers', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/byok', 'POST', 'byok_create', 'Create BYOK provider', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/byok/{id}', 'GET', 'byok_get', 'Get BYOK provider', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/byok/{id}', 'PATCH', 'byok_update', 'Update BYOK provider', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/datasets/rankings-daily', 'GET', 'datasets_rankings_daily', 'Daily rankings dataset', 'text', 'json', 0, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/endpoints/zdr', 'GET', 'zdr_info', 'Zero Data Retention endpoint info', 'text', 'json', 0, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/workspaces/{id}/members', 'GET', 'workspaces_members', 'Workspace members', 'text', 'json', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/presets/{slug}/chat/completions', 'POST', 'presets_chat', 'Run a preset against Chat Completions', 'text', 'text', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/presets/{slug}/messages', 'POST', 'presets_messages', 'Run a preset against Anthropic Messages', 'text', 'text', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/presets/{slug}/responses', 'POST', 'presets_responses', 'Run a preset against OpenAI Responses', 'text', 'text', 1, 'new', 'available', 'OpenAPI changelog'),
    ('/api/v1/keys', 'GET', 'keys', 'API key management', 'text', 'json', 1, 'new', 'available', 'probe: 401 = live'),
    ('/api/v1/credits', 'GET', 'credits', 'Credit balance/limits', 'text', 'json', 1, 'new', 'available', 'probe: 401 = live'),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_api_endpoints (
  endpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL REFERENCES providers(provider_id),
  path TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT 'GET',
  endpoint_kind TEXT NOT NULL,
  purpose TEXT,
  input_modalities TEXT,
  output_modalities TEXT,
  auth_required INTEGER NOT NULL DEFAULT 1,
  endpoint_status TEXT NOT NULL DEFAULT 'available'
    CHECK(endpoint_status IN ('available','unavailable','deprecated','removed','unknown')),
  first_seen_at TEXT,
  last_verified_at TEXT,
  notes TEXT,
  UNIQUE(provider_id, path, method)
);
"""


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'aimi-endpoint-ingest/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    # 1. backup
    bak = DB.with_name(f"aimi.db.bak.openrouter-endpoints-{NOW.replace(':','').replace('-','').replace('T','-')[:15]}")
    shutil.copy2(DB, bak)
    print(f"backup: {bak.name}")

    # 2. raw evidence snapshots
    for label, url, fname in [
        ('images', f'{BASE}/images/models', f'openrouter-images-models-{TODAY}.json'),
        ('videos', f'{BASE}/videos/models', f'openrouter-videos-models-{TODAY}.json'),
        ('changelog', 'https://openrouter.ai/docs/changelog.md', f'openrouter-changelog-{TODAY}.md'),
    ]:
        try:
            raw = fetch(url)
            (SNAPSHOTS / fname).write_bytes(raw)
            print(f"snapshot: {fname} ({len(raw)} bytes)")
        except Exception as e:
            print(f"snapshot FAILED for {label}: {e}")

    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')

    # 3. table
    c.executescript(SCHEMA)

    # 4. endpoint rows
    added = 0
    for path, method, kind, purpose, in_mod, out_mod, auth, first_seen, status, notes in ENDPOINTS:
        fs = NOW if first_seen == 'new' else None
        cur = c.execute("""INSERT OR IGNORE INTO provider_api_endpoints
            (provider_id, path, method, endpoint_kind, purpose, input_modalities, output_modalities,
             auth_required, endpoint_status, first_seen_at, last_verified_at, notes)
            VALUES ('openrouter',?,?,?,?,?,?,?,?,?,?,?)""",
            (path, method, kind, purpose, in_mod, out_mod, auth, status, fs, NOW, notes))
        added += cur.rowcount
    print(f"endpoint rows added: {added}")

    # 5. monitoring targets (images catalogue + OpenAPI-generated changelog)
    mt_added = 0
    for target_type, url, schedule, fmt, parser in [
        ('models_endpoint', f'{BASE}/images/models', 'weekly', 'json', 'openrouter-images'),
        ('changelog', 'https://openrouter.ai/docs/changelog.md', 'weekly', 'markdown', 'openrouter-changelog'),
    ]:
        cur = c.execute("""INSERT OR IGNORE INTO monitoring_targets
            (provider_id, target_type, url, schedule_class, enabled, expected_format, parser_name)
            VALUES ('openrouter',?,?,?,1,?,?)""", (target_type, url, schedule, fmt, parser))
        mt_added += cur.rowcount
    print(f"monitoring targets added: {mt_added}")

    # 6. evidence sources
    es_added = 0
    for url, stype, title in [
        (f'{BASE}/images/models', 'api_endpoint', 'OpenRouter image model catalogue'),
        (f'{BASE}/videos/models', 'api_endpoint', 'OpenRouter video model catalogue'),
        ('https://openrouter.ai/docs/changelog.md', 'official_changelog', 'OpenRouter API changelog (OpenAPI-generated)'),
    ]:
        cur = c.execute("""INSERT OR IGNORE INTO evidence_sources
            (url, source_type, publisher, title, official, primary_source, retrieved_at, trust_priority)
            VALUES (?,?, 'OpenRouter', ?, 1, 1, ?, 90)""", (url, stype, title, NOW))
        es_added += cur.rowcount
    print(f"evidence sources added: {es_added}")

    c.commit()
    n = c.execute('SELECT COUNT(*) FROM provider_api_endpoints WHERE provider_id="openrouter"').fetchone()[0]
    print(f"total openrouter endpoints recorded: {n}")
    c.close()


if __name__ == '__main__':
    main()
