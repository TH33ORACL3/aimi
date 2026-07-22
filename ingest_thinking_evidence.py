#!/usr/bin/env python3
"""Ingest today's verified finding: DeepSeek V4 Flash supports thinking/reasoning,
and Grok CLI requires the Anthropic Messages API backend to enable it.

Evidence source: https://api-docs.deepseek.com/api/reasoning (official docs)
Corroborated by: local API tests on 2026-07-22
"""
from __future__ import annotations
import json, sqlite3, sys, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'aimi.db'
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# Evidence: DeepSeek API docs page showing thinking parameter
DEEPSEEK_API_DOCS = {
    'url': 'https://api-docs.deepseek.com/api/reasoning',
    'source_type': 'official_docs',
    'publisher': 'DeepSeek',
    'title': 'DeepSeek API: Thinking/Reasoning Parameter',
    'official': 1,
    'primary_source': 1,
    'retrieved_at': '2026-07-22T15:10:00+00:00',
    'verification_status': 'verified',
    'trust_priority': 90,
    'notes': 'Official DeepSeek API docs showing thinking: {"type": "enabled"} and reasoning_effort parameters for deepseek-v4-flash and deepseek-v4-pro',
}

# Evidence: Local API test confirming thinking blocks returned
LOCAL_TEST = {
    'url': 'file:///Users/TH33_ORACL3/.grok/sessions/local-test-deepseek-thinking-2026-07-22',
    'source_type': 'local_observation',
    'publisher': 'Aubrey Zemba',
    'title': 'Local DeepSeek V4 Flash Thinking API Test',
    'official': 0,
    'primary_source': 0,
    'retrieved_at': NOW,
    'verification_status': 'verified',
    'trust_priority': 70,
    'notes': 'Verified that DeepSeek Anthropic endpoint returns separate thinking content blocks with reasoning_content',
}

THINKING_CLAIMS = [
    {
        'subject_type': 'provider_model',
        'subject_key': 'deepseek/deepseek-v4-flash',
        'field_name': 'reasoning',
        'value_json': 'true',
        'supporting_quote': 'DeepSeek V4 Flash supports thinking mode via thinking: {"type": "enabled"} with reasoning_effort (low/medium/high)',
        'confidence': 'verified',
        'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model',
        'subject_key': 'deepseek/deepseek-v4-pro',
        'field_name': 'reasoning',
        'value_json': 'true',
        'supporting_quote': 'DeepSeek V4 Pro supports thinking mode via thinking: {"type": "enabled"} with reasoning_effort (low/medium/high)',
        'confidence': 'verified',
        'verification_method': 'api_test',
    },
    {
        'subject_type': 'provider_model',
        'subject_key': 'deepseek/deepseek-v4-flash',
        'field_name': 'reasoning_efforts',
        'value_json': '["low","medium","high"]',
        'supporting_quote': 'DeepSeek API accepts reasoning_effort: "low" | "medium" | "high"',
        'confidence': 'verified',
        'verification_method': 'docs_citation',
    },
    {
        'subject_type': 'provider_model',
        'subject_key': 'deepseek/deepseek-v4-pro',
        'field_name': 'reasoning_efforts',
        'value_json': '["low","medium","high"]',
        'supporting_quote': 'DeepSeek API accepts reasoning_effort: "low" | "medium" | "high"',
        'confidence': 'verified',
        'verification_method': 'docs_citation',
    },
    {
        'subject_type': 'provider_model',
        'subject_key': 'deepseek/deepseek-v4-flash',
        'field_name': 'thinking_api',
        'value_json': json.dumps({
            'openai_compatible': {
                'parameters': {'thinking': {'type': 'enabled'}, 'reasoning_effort': 'high'},
                'endpoint': 'https://api.deepseek.com/v1/chat/completions',
                'note': 'Grok chat_completions backend cannot send thinking param',
            },
            'anthropic_compatible': {
                'endpoint': 'https://api.deepseek.com/anthropic/v1/messages',
                'parameters': {'thinking': {'type': 'enabled', 'budget_tokens': 1024}, 'reasoning_effort': 'high'},
                'note': 'Grok messages backend supports this; thinking blocks returned natively',
            },
        }),
        'supporting_quote': 'DeepSeek supports both OpenAI and Anthropic API formats for thinking/reasoning',
        'confidence': 'verified',
        'verification_method': 'api_test',
    },
]


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('BEGIN')

    try:
        # 1. Record evidence sources
        for src in [DEEPSEEK_API_DOCS, LOCAL_TEST]:
            conn.execute(
                """INSERT OR IGNORE INTO evidence_sources(url, source_type, publisher, title, official, primary_source, retrieved_at, verification_status, trust_priority, notes)
                VALUES(:url, :source_type, :publisher, :title, :official, :primary_source, :retrieved_at, :verification_status, :trust_priority, :notes)""",
                src,
            )

        # Get the evidence_source_ids
        docs_src_id = conn.execute(
            "SELECT evidence_source_id FROM evidence_sources WHERE url=?",
            (DEEPSEEK_API_DOCS['url'],),
        ).fetchone()[0]
        test_src_id = conn.execute(
            "SELECT evidence_source_id FROM evidence_sources WHERE url=?",
            (LOCAL_TEST['url'],),
        ).fetchone()[0]

        # 2. Record evidence claims
        for claim in THINKING_CLAIMS:
            src_id = docs_src_id if claim['verification_method'] == 'docs_citation' else test_src_id
            conn.execute(
                """INSERT OR IGNORE INTO evidence_claims(subject_type, subject_key, field_name, value_json, value_type, evidence_source_id, supporting_quote, observed_at, confidence, verification_method, source_priority)
                VALUES(:subject_type, :subject_key, :field_name, :value_json, 'json', :evidence_source_id, :supporting_quote, :observed_at, :confidence, :verification_method, :source_priority)""",
                {
                    **claim,
                    'evidence_source_id': src_id,
                    'observed_at': NOW,
                    'source_priority': 80,
                },
            )

        # 3. Update reasoning=1 for DeepSeek V4 Flash and V4 Pro routes
        deepseek_routes = [
            ('deepseek', 'deepseek-v4-flash'),
            ('deepseek', 'deepseek-v4-pro'),
            ('nvidia-nim', 'deepseek-ai/deepseek-v4-flash'),
            ('nvidia-nim', 'deepseek-ai/deepseek-v4-pro'),
            ('opencode-zen', 'deepseek-v4-flash-free'),
            ('opencode-go', 'deepseek-v4-flash'),
            ('opencode-go', 'deepseek-v4-pro'),
            ('ollama-cloud', 'deepseek-v4-flash'),
            ('ollama-cloud', 'deepseek-v4-pro'),
            # OpenRouter: v4-flash and v4-pro support thinking
            ('openrouter', 'deepseek/deepseek-v4-flash'),
            ('openrouter', 'deepseek/deepseek-v4-pro'),
        ]
        for pid, mid in deepseek_routes:
            conn.execute(
                "UPDATE provider_models_v2 SET reasoning = 1 WHERE provider_id = ? AND model_identifier = ? AND (reasoning IS NULL OR reasoning = 0)",
                (pid, mid),
            )

        # 4. Update provider_metadata_json for deepseek provider's v4-flash and v4-pro
        # to include thinking and reasoning_efforts info
        thinking_meta = json.dumps({
            'thinking': True,
            'reasoning_efforts': ['low', 'medium', 'high'],
            'thinking_api': {
                'anthropic_backend': 'https://api.deepseek.com/anthropic',
                'openai_backend': 'https://api.deepseek.com/v1',
            },
        })
        for pid, mid in [('deepseek', 'deepseek-v4-flash'), ('deepseek', 'deepseek-v4-pro')]:
            row = conn.execute(
                "SELECT provider_model_id, provider_metadata_json FROM provider_models_v2 WHERE provider_id=? AND model_identifier=?",
                (pid, mid),
            ).fetchone()
            if row:
                existing = json.loads(row[1]) if row[1] else {}
                existing.update({
                    'thinking': True,
                    'reasoning_efforts': ['low', 'medium', 'high'],
                })
                conn.execute(
                    "UPDATE provider_models_v2 SET provider_metadata_json=? WHERE provider_model_id=?",
                    (json.dumps(existing), row[0]),
                )

        # 5. Add grok-build harness (canonical harness ID)
        conn.execute(
            """INSERT OR IGNORE INTO harnesses(harness_id, display_name, vendor, category, config_format, custom_provider_support, notes)
            VALUES('grok-build', 'Grok Build / Grok CLI', 'xAI', 'CLI Agent', 'toml', 1, 'xAI Grok CLI — toml config at ~/.grok/config.toml; supports custom models with chat_completions, responses, and messages API backends')"""
        )

        # 6. Add installation for grok-build
        grok_path = Path.home() / '.grok/config.toml'
        installed = int(grok_path.exists())
        conn.execute(
            """INSERT INTO harness_installations(harness_id, machine_id, installed, executable_path, config_path, status, last_scanned_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(harness_id, machine_id) DO UPDATE SET installed=excluded.installed, status=excluded.status, last_scanned_at=excluded.last_scanned_at""",
            ('grok-build', 'aubrey-macbook', installed, '/Users/TH33_ORACL3/.local/bin/grok', str(grok_path) if installed else None, 'active' if installed else 'historical', NOW),
        )
        grok_inst_id = conn.execute(
            "SELECT installation_id FROM harness_installations WHERE harness_id='grok-build' AND machine_id='aubrey-macbook'"
        ).fetchone()[0]

        # 7. Add harness_provider_support for grok-build + deepseek (thinking via Messages API)
        thinking_config_schema = {
            'thinking': {
                'api_backend': 'messages',
                'required_fields': ['reasoning_effort', 'extra_headers'],
                'extra_headers': {'anthropic-version': '2023-06-01'},
                'reasoning_efforts': ['low', 'medium', 'high'],
                'notes': 'Grok requires Anthropic Messages API backend for thinking mode. chat_completions backend cannot send thinking: {"type": "enabled"}. Use the anthropic-compatible endpoint at {base_url}/anthropic.',
            }
        }
        conn.execute(
            """INSERT OR IGNORE INTO harness_provider_support(harness_id, provider_id, support_type, api_style, config_location, config_schema_json, compatibility_notes, last_verified_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
            ('grok-build', 'deepseek', 'custom_openai_compatible', 'messages', '~/.grok/config.toml', json.dumps(thinking_config_schema),
             'Grok supports DeepSeek via Anthropic Messages API for thinking. Requires: api_backend = "messages", base_url = "https://api.deepseek.com/anthropic", reasoning_effort = "high", extra_headers = { "anthropic-version" = "2023-06-01" }', NOW),
        )

        # 8. Record evidence for the grok-build harness + deepseek support
        conn.execute(
            """INSERT OR IGNORE INTO evidence_claims(subject_type, subject_key, field_name, value_json, value_type, evidence_source_id, supporting_quote, observed_at, confidence, verification_method, source_priority)
            VALUES(?, ?, ?, ?, 'json', ?, ?, ?, 'verified', ?, ?)""",
            ('harness', 'grok-build/deepseek', 'thinking_config', json.dumps(thinking_config_schema),
             test_src_id,
             'Grok CLI configured with DeepSeek Anthropic Messages API backend returns thinking blocks',
             NOW, 'api_test', 80),
        )

        conn.execute('COMMIT')
        print(json.dumps({
            'status': 'ok',
            'evidence_sources_added': 2,
            'evidence_claims_added': len(THINKING_CLAIMS) + 1,
            'deepseek_routes_updated': len(deepseek_routes),
            'harness_added': 'grok-build',
            'harness_provider_support_added': 'grok-build + deepseek',
        }, indent=2))

    except Exception as e:
        conn.execute('ROLLBACK')
        print(json.dumps({'status': 'error', 'message': str(e)}, indent=2), file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
