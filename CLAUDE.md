# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

AIMI is an **evidence-first catalogue** of AI models, provider routes, and local agent harnesses. It answers "which model, through which provider, in which harness, at what cost, backed by what evidence?" Core facts: a private SQLite catalogue (`aimi.db`), a single-file Python CLI (`aimi`, ~1050 lines, no package), one installable cross-agent skill, and a set of operational scripts. **AGENTS.md** holds the authoritative build/test/dev commands and coding style; `README.md` holds full CLI docs. This file adds the architecture and the invariants that only become visible by reading several files.

**The most important rule:** the CLI opens the database **read-only** for every command except the few declared writers. A query can never damage the catalogue. Any change to catalogue data goes through a deliberate, preview-first write path.

## Common commands

```bash
python3 install.py                          # init DB + install skill (idempotent)
python3 install.py --upgrade                # apply new schema objects, never loses data
./aimi summary                              # catalogue totals
./aimi commands                             # machine-readable manifest of every command + which write
./aimi where deepseek-v4-flash              # fast all-provider route lookup for a model
./aimi harness-fragment <harness> <provider> <model>  # config fragment for any harness
python3 -m unittest discover -s tests -p 'test_*.py'  # run the suite
./validate_catalogue.py                     # integrity/evidence/pricing/secret audit → validation-report.json
./dump_schema.py --check                    # fail if schema_v2.sql drifted from the live DB
./scan_local_harnesses.py                   # rescan local harness configs into the DB
./export_sanitized.py                       # private→public DB export into dist/
```

`./aimi commands` is the contract — read it instead of guessing the CLI surface. Every `aimi` write command (`pi-register/select/remove`, `aside-register/remove`, `changes-review`, `test`) **previews by default**; `--apply` performs the write and creates a timestamped backup. `changes-review --apply` additionally requires `--note`.

## Architecture

### The schema is the contract

- `schema_v2.sql` is the single source of truth; every statement is `IF NOT EXISTS`. `install.py --upgrade` applies it to a populated DB; `dump_schema.py` regenerates it from a live DB. `validate_catalogue.py` fails on drift (`schema_file_matches_database`). If you change the schema, regenerate the file.
- `aimi.db` (WAL mode) is private runtime data, gitignored. `free_models.db` is a symlink to it. Legacy tables (`models`, typo `catagory`) survive because old tools depend on them — new work uses the v2 tables.
- Set `AIMI_DB` to point the CLI at a copy/export/test DB instead of editing code.

### Identity is layered, evidence is field-level

- **`canonical_models`** = a conceptual developer release (GPT-5.6 Sol). **`provider_models_v2`** = one exact `(provider_id, model_identifier)` route. One canonical model has many routes; a route may stay unlinked until identity is proven.
- **Evidence chain:** `evidence_sources` (stable source identity) → `evidence_captures` (immutable, content-hashed retrievals) → `evidence_claims` (field-level assertions with confidence) and `model_events` (time-specific events). Claims/events/offers point at immutable captures, never at a silently-replaced source. Missing data is *unverified*, never *unsupported*.
- **Access semantics** live in `access_offers`; the `currently_free_provider_models` view is the safe active-free set. `genuine_zero_price` requires official proof — a working key, open weights, free chat, or credits do NOT prove an API route is free. `subscription_included` is deliberately excluded from free views and free health probes. **OpenCode Go and OpenCode Zen are separate products/endpoints** (`opencode-go`/`https://opencode.ai/zen/go/v1` vs `opencode-zen`/`https://opencode.ai/zen/v1`) — never merge their models.

### Harness system

- Live harness config files are authoritative for "right now"; the DB is an audit/cache layer. `scan_local_harnesses.py` reads Pi, Droid, OpenCode, Codex CLI, Cline, Aside, Antigravity, Mistral Vibe, Warp, Grok, and ZCode, synchronizing **configured** entries into `harness_model_entries` and harness-listed models into `harness_available_model_entries` (kept separate on purpose).
- `harness_provider_support` records each (harness, provider) config schema — this drives `aimi harness-fragment`, the single entry point for pointing any harness at any route. Recipes and privacy rules: `skills/references/harness-config.md`.
- **Secrets never enter the catalogue or repo.** Fragments reference a provider's `auth_env_var` *name*, not the value. The one exception: ZCode's `options.apiKey` stores the literal key, substituted at apply time. Keys live only in `~/.config/aimi/credentials.env` (mode 0600) or each harness's own 0600 config.
- **Claude Code** speaks only the Anthropic Messages API. Anthropic-compatible providers set `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_MODEL`. OpenAI-compatible providers (e.g. ClinePass) need the local translation proxy `~/bin/claude-cline-proxy.py` + the `claude-cline` launcher. For ClinePass use the subscription-namespaced id `cline-pass/<model>` — the bare `deepseek/<model>` id hits a free-tier bucket that 429s on its daily cap.

### Monitoring and scheduling

- `monitor_endpoints.py` polls ~10 official model endpoints. `endpoint_changes` is the durable, reviewable change log; `monitoring_runs` is the poll/audit log; raw payload snapshots are content-addressed (byte-identical responses share one capture) and stored under **project-relative** paths via `normalize_paths.py`.
- Scheduling runs through **Hermes**: `model-catalogue-discovery-notifier` (job `f8ff78fe2fb2`, every 15 min) polls endpoints and Telegram-alerts on route add/remove and provider-failure transitions only; delivery is a durable outbox that advances the watermark only after ack. Free-model health (`free_model_health.py`, exact "Reply with exactly OK" probes, green/orange/red) is a separate weekly job (`da87bcef9fc4`) — do not fold health probes into the discovery job, and do not write periodic health checks into `handshake_tests`.
- `aimi changes` (default unreviewed) and `aimi changes-review` are how you inspect and accept the change log. Review them; never bulk-accept just to make validation pass.

## Invariants that trip people up

- **Write-first-and-ask is forbidden.** A finding that differs from the DB is a *candidate*: present current value, proposed value, source, date, confidence, and affected records, then get explicit confirmation. This applies to model facts, free classification, pricing, release dates, and subscription entitlements. Endpoint observation is *not* a release date; endpoint first-seen is labelled as such.
- **Free-route testing is gated.** `aimi test` refuses paid, subscription-only, and unclassified routes unless `--allow-paid`. Never test a route just to see if it responds unless AIMI has verified it as genuinely free.
- **Validation can be legitimately red.** `validate_catalogue.py` is a fail-closed audit: it checks evidence captures exist for confident claims, free offers have evidence, no expired free offers are active, Pi-enabled models still exist at their providers, referenced snapshots exist, and no API-key-shaped bytes in the DB. It also flags *unreviewed* endpoint changes — and there are thousands backlogged, so `endpoint_changes_reviewed` being false is the expected resting state. Red here is a signal to review the change log or repair evidence, not to shortcut.
- **Runtime data must stay out of Git:** `aimi.db`, `snapshots/`, `evidence/`, `.firecrawl/`, `.omo/`, `.learnings/`, harness inventories, and `*.task_plan.md`/`*-findings.md`/`*-progress.md` session files are all gitignored.
- **Tests:** `unittest`, files named `test_*.py`. Use a temporary DB or an `AIMI_DB` copy for writable scenarios, mock external delivery (see `tests/test_model_discovery_notifier.py`), and never make live provider calls or touch paid/unverified routes in tests.
- **Style:** Python 3.11+, stdlib only, `from __future__ import annotations`, type hints, idempotent `IF NOT EXISTS` schema statements, stable JSON output where a command already emits JSON.

## Skill copy

The in-repo `skills/` is the source; `install.py` copies it to `~/.agents/skills/ai-model-index/` and records the checkout's `project-path`. `skills/SKILL.md` (cross-agent usage) and `skills/references/` (schema semantics, operations/SQL cookbook, harness config, workflows) are the deep reference — read the relevant reference before doing evidence, harness, or monitoring work.
