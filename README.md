<div align="center">

# AIMI

### AI Model Inventory

An evidence-first catalogue for discovering, comparing, configuring, and monitoring AI models across providers and agent harnesses.

<p>
  <a href="https://github.com/TH33ORACL3/aimi"><img src="https://img.shields.io/badge/status-active-7c3aed?style=flat-square" alt="Status: active"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/storage-SQLite-003b57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite"></a>
  <a href="https://x.com/TH33_ORACL3"><img src="https://img.shields.io/badge/follow-TH33ORACL3-000000?style=flat-square&logo=x&logoColor=white" alt="Follow TH33_ORACL3 on X"></a>
</p>

<p>
  <strong>Built and maintained by <a href="https://x.com/TH33_ORACL3">Aubrey Zemba</a></strong><br>
  <a href="https://x.com/TH33_ORACL3">Follow me on X / Twitter</a>
</p>

</div>

---

## What AIMI does

AIMI answers a practical question:

> Which model can I use, through which provider, in which harness, with what limits, at what cost, and what evidence supports that answer?

It keeps canonical models separate from provider routes, records evidence at field level, tracks access semantics such as genuinely free and subscription-included, and monitors official provider endpoints for changes.

## Installation (agent-first, macOS, Windows, and Linux)

A human does not need to install AIMI manually. An agent should clone or copy this repository, then run the portable installer from the repository root:

```text
python install.py
```

Use `py install.py` on Windows when `python` is not the registered command. The installer:

1. Requires Python 3.11 or newer.
2. Creates the private local `aimi.db` from `schema_v2.sql` when it does not exist.
3. Installs the repository's bundled skill to `~/.agents/skills/ai-model-index/` using the platform's home directory.
4. Enables WAL journalling so the scheduled endpoint monitor and an agent reading the catalogue never block each other.
4. Prints the exact database, skill, and CLI paths after completion.

The installer has no third-party Python dependencies. It uses only the Python standard library and SQLite. API keys are optional for local inspection; provider refreshes and health checks require the relevant environment variables.

Verify the installation:

```text
python aimi summary
python validate_catalogue.py
```

On Windows, use `py` instead of `python` if required. The Python CLI is the portable entry point on every operating system. The optional `skills/scripts/catalogue` wrapper is provided for POSIX shells only; Windows agents should invoke `python aimi` and the Python maintenance scripts directly.

### Platform notes

- **Windows:** Python 3.11+, SQLite via Python, and PowerShell or another agent shell are sufficient for the core CLI, database, validation, export, and catalogue scripts. Windows-specific harness paths are detected when available; missing harnesses are reported rather than invented.
- **macOS/Linux:** Python 3.11+ is sufficient for the core CLI. `skills/scripts/catalogue` can be used from a POSIX shell. `hyperfine`, `zsh`, and Hermes are optional integrations used only by the relevant monitoring workflows.
- **Provider access:** install the provider's own CLI or credentials only when you want to scan or test that provider. AIMI does not silently install agent harnesses or create API keys.

### Quick start

```text
python aimi summary
python aimi where deepseek-v4-flash
python aimi recommend --task coding --free
```

The main CLI is called `aimi`. It can search routes, compare providers, inspect harness configuration, show free-model health, and manage Pi model ordering.

## Project layout

| Path | Purpose |
|---|---|
| `aimi` | CLI for search, recommendations, configuration, and Pi ordering |
| `aimi.db` | Private authoritative SQLite database, kept out of Git |
| `free_models.db` | Compatibility symlink to `aimi.db` |
| `monitor_endpoints.py` | Polls official provider model endpoints and records changes |
| `free_model_health.py` | Runs bounded exact-OK health checks against eligible no-charge routes |
| `scan_local_harnesses.py` | Scans local harness configuration and availability |
| `refresh_catalog.py` | Refreshes provider routes from official endpoints |
| `validate_catalogue.py` | Checks integrity, evidence, pricing, ordering, schema drift, and secret rules |
| `dump_schema.py` | Regenerates `schema_v2.sql` from the live database so fresh installs match |
| `normalize_paths.py` | Rewrites stored evidence paths to project-relative form |
| `prune_snapshots.py` | Collapses byte-identical endpoint snapshots, verified by sha256 |
| `correct_volatile_changes.py` | Removes change events that differ only in volatile provider timestamps |
| `repair_claims.py` | Captures a claim's source, or marks the claim unverified when the source is gone |
| `handshake.py` | One sanitized provider handshake, used by `aimi test` |
| `export_sanitized.py` | Creates a public database export with private state removed |
| `schema_v2.sql` | Core model, provider, evidence, harness, and monitoring schema |
| `evidence/` and `snapshots/` | Local raw evidence and endpoint captures, never committed |

The canonical cross-agent skill remains at:

```text
$HOME/.agents/skills/ai-model-index/SKILL.md
```

AIMI is the project and CLI name. `ai-model-index` is the skill name that agents load. Installing the skill under any other directory name creates a second competing copy, so `install.py` always targets this path.

Run `python install.py --upgrade` on an existing checkout to apply new schema objects to a populated database without touching data. Every statement in `schema_v2.sql` is `IF NOT EXISTS`.

## CLI examples

### Models and routes

```bash
./aimi summary
./aimi doctor
./aimi version
./aimi commands
./aimi latest --limit 20
./aimi free
./aimi free --provider openrouter
./aimi where deepseek-v4-flash
./aimi where deepseek-v4-flash --refresh-harnesses
./aimi recommend --task coding --free
```

`aimi where` returns every matching provider route, its access semantics, known limits, harness matches, freshness, and the latest test outcome when one exists.

`aimi commands` returns a machine-readable manifest of every command, its arguments, and whether it writes. Agents should read that instead of guessing the surface.

### Testing a route

```bash
./aimi test openrouter 'poolside/laguna-s-2.1:free'
./aimi test nvidia-nim 'deepseek-ai/deepseek-v4-flash'
./aimi test openai gpt-5.6-sol --allow-paid
```

One small handshake, classified green/orange/red, recorded in `handshake_tests` with the exact reply, HTTP status, latency and token counts. Paid, subscription-only and unclassified routes are refused unless `--allow-paid` is given, so a test cannot quietly spend money or subscription quota. Credentials, request headers and raw provider bodies are never stored, and any token-shaped text is redacted from errors.

The CLI opens the database **read-only** for every command except `changes-review`, so a query can never damage the catalogue or block the endpoint monitor. Set `AIMI_DB` to point the CLI at a copy or an export.

### Harness inventory

```bash
./aimi harnesses
./aimi harness-models pi
./aimi harness-models droid
./aimi harness-models codex-cli --kind configured
./aimi harness-models codex-cli --kind available
```

The scanner reads the local sources used by each harness, including Pi, Droid, OpenCode, Codex CLI, Cline, Aside, Antigravity, and Mistral Vibe where present.

### Pi model ordering

```bash
./aimi order-diff pi
./aimi pi-fragment openrouter 'poolside/laguna-s-2.1:free'
./aimi pi-register openrouter 'poolside/laguna-s-2.1:free'
./aimi pi-select openrouter 'poolside/laguna-s-2.1:free' --position 3
```

Writes preview by default. Applying a change creates a timestamped backup, then the local configuration is rescanned and validated.

### Subscriptions and harness-specific access

```bash
./aimi subscriptions
./aimi subscriptions --mine
./aimi subscription opencode-go
./aimi warp-models
./aimi warp-models --custom
```

Subscription access is tracked separately from genuinely free API access. OpenCode Go and OpenCode Zen are separate products with separate endpoints. Warp BYOK and custom inference endpoints are recorded separately from Warp-hosted inference.

## Evidence and pricing rules

AIMI treats these as different access categories:

| Offer type | Meaning |
|---|---|
| `genuine_zero_price` | Official source proves that the route has no charge |
| `free_tier_quota` | Official developer or evaluation quota with explicit limits |
| `temporary_free_window` | Free for a window whose dates may be finite or unknown |
| `subscription_included` | Available through a subscription, not classified as free |
| `paid` | Paid API usage |
| `unknown` | Not enough evidence to classify the route |

A working API key, open weights, free chat access, or free credits does not prove that an API route is free. Missing capability or context data means unverified, not unsupported.

AIMI keeps announcement, general availability, API availability, model-card, weights-release, endpoint-first-seen, and free-window events separate. Claims point to immutable evidence captures rather than silently replacing conflicting sources.

## Health monitoring

Only routes currently verified as no-charge are eligible for free-model health probes. The probe contract is exact:

```text
Reply with exactly OK
```

Results use three states:

- **Green:** exact `OK` returned.
- **Orange:** rate limited, so availability is inconclusive.
- **Red:** failed, unauthorized, timed out, or returned something other than exact `OK`.

The database keeps one current status per route and a bounded daily history. Free-model health runs on the weekly Hermes job below, covering every verified no-charge route including NVIDIA NIM's developer tier. The scripts can also be run manually at any time.

```bash
hyperfine --runs 1 --warmup 0 --show-output \
  -n 'free-model-health' \
  "zsh -lc 'source ~/.zshrc >/dev/null 2>&1; cd \"$HOME/AZ Labs/2 - Testing/AIMI\"; python3 free_model_health.py --workers 4 --timeout 45 --retention-days 30'"

./aimi free-health-summary
./aimi free-health
./aimi free-health --failures-only
```

## Monitoring official endpoints

The endpoint monitor covers OpenRouter, OpenCode Zen, OpenCode Go, NVIDIA NIM, DeepSeek, Mistral, OpenAI, Gemini, Cloudflare Workers AI, and Ollama Cloud. It saves timestamped captures, hashes evidence, retains the complete sanitised per-model provider payload, normalizes context/limits/capabilities/modalities/aliases where supplied, records additions and removals, and updates free-offer windows without storing secrets. Every poll is retained in `monitoring_runs` and `model_sources`; every detected route/metadata/pricing change is retained in `endpoint_changes` with the monitoring run, endpoint URL, timestamp, and before/after JSON. Provider-supplied aliases are stored in `provider_model_aliases`. Endpoint-reported paid prices are stored in `access_offers`, and explicit lifecycle date fields are recorded as evidence-linked model events without confusing provider-created timestamps with release dates. Transient provider errors are retried, and one provider failure cannot discard successful discoveries from the other providers.

The consolidated Hermes discovery job is:

```text
model-catalogue-discovery-notifier (f8ff78fe2fb2)
```

It runs every 15 minutes, polls all ten endpoints, updates endpoint routes and endpoint-first-seen events through the existing AIMI scripts, and delivers a Telegram notification when a route is **added or removed at any provider**. Removals that match a model still enabled in a local harness are listed first and flagged, because those are the ones that will start failing. Long provider sweeps are summarised so the message stays within Telegram's limit. It keeps a first-run watermark at `~/.hermes/cron/model-catalogue-discovery-notifier.json` so existing history is not replayed.

Free-model health runs weekly:

```text
aimi-free-model-health-weekly (da87bcef9fc4)
```

One weekly pass over every route the catalogue verifies as no-charge, including NVIDIA NIM's developer tier. It reports the green/orange/red counts and any status transitions since the previous run.

Inspect it with:

```bash
hermes cron runs f8ff78fe2fb2
```

The former standalone endpoint monitor and the two older health jobs (12-hourly free health, weekly NVIDIA NIM) were consolidated into the two jobs above: one 15-minute discovery notifier and one weekly health pass.

Query the complete change history without writing SQL:

```bash
# Every detected change, including reviewed entries
./aimi changes --all --since 2026-07-24 --until 2026-07-25

# Only new API routes, with exact before/after payloads
./aimi changes --all --type model_added --diff --limit 100

# Search one provider or model family
./aimi changes --all --provider openrouter --model opus --diff

# Every endpoint poll, including unchanged and failed checks
./aimi monitor-runs --since 2026-07-25 --limit 200
./aimi monitor-runs --provider openai --status failed
```

`endpoint_changes` is the durable event log. `monitoring_runs` is the poll/audit log. A provider outage is therefore queryable separately from a model removal or addition, and the raw response snapshot is linked by `snapshot_path` and `response_sha256`.

Snapshots are content addressed. When an endpoint returns a byte-identical payload the run is linked to the existing capture instead of writing a duplicate file, so `snapshots/` grows with real change rather than with poll frequency. `prune_snapshots.py` applies the same rule retroactively and refuses to delete anything when a recorded hash does not match the file on disk.

Stored evidence paths are project-relative. A rename or a different checkout location cannot break the evidence chain, and `validate_catalogue.py` fails when a referenced capture is missing.

### Reviewing changes

Detected changes stay unreviewed until someone accepts them:

```bash
# Preview exactly what would be accepted
./aimi changes-review --provider openrouter --type pricing_changed

# Accept that set, recording why
./aimi changes-review --provider openrouter --type pricing_changed \
  --note 'Reviewed 2026-08-01: OpenRouter price refresh' --apply
```

The command previews by default and refuses to write without `--note`. Bulk-accepting the log purely to make validation pass defeats the point of the event log.

## Public export

The private database, raw endpoint captures, local harness state, personal rankings, account identifiers, and credential inventory stay local. To produce a sanitized database for review or publication:

```bash
./export_sanitized.py
```

The exporter removes private state, runs SQLite integrity validation, and performs a fail-closed secret-pattern scan before writing the public export under `dist/`.

## Development checks

```bash
./scan_local_harnesses.py
./validate_catalogue.py
./dump_schema.py --check
./export_sanitized.py
```

The latest machine-readable validation result is stored in `validation-report.json`.

## Privacy

AIMI is designed around a private local catalogue with a safe public export. API-key values are not stored in the database. Raw evidence, snapshots, local configuration inventories, and the private database are excluded from the Git repository.

## Roadmap

- Link more provider routes to canonical model identities and aliases.
- Add reviewed capability and benchmark evidence for newer models.
- Expand safe runtime tests for tools, reasoning, images, streaming, and structured output.
- Add task-specific Pi order profiles and usage-based recommendations.
- Improve notifications for new free windows, removals, and deprecations.

---

<div align="center">

Made by <a href="https://x.com/TH33_ORACL3">Aubrey Zemba</a> · <a href="https://x.com/TH33_ORACL3">@TH33_ORACL3 on X</a>

</div>
