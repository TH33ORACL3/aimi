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

## Quick start

```bash
cd "$HOME/AZ Labs/2 - Testing/AIMI"
./aimi summary
./aimi where deepseek-v4-flash
./aimi recommend --task coding --free
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
| `validate_catalogue.py` | Checks integrity, evidence, pricing, ordering, and secret rules |
| `export_sanitized.py` | Creates a public database export with private state removed |
| `schema_v2.sql` | Core model, provider, evidence, harness, and monitoring schema |
| `evidence/` and `snapshots/` | Local raw evidence and endpoint captures, never committed |

The canonical cross-agent skill remains at:

```text
$HOME/.agents/skills/model-catalogue/SKILL.md
```

AIMI is the project and CLI name. `model-catalogue` is the internal skill name used by the agent tooling.

## CLI examples

### Models and routes

```bash
./aimi summary
./aimi doctor
./aimi latest --limit 20
./aimi free
./aimi free --provider openrouter
./aimi where deepseek-v4-flash
./aimi where deepseek-v4-flash --refresh-harnesses
./aimi recommend --task coding --free
```

`aimi where` returns every matching provider route, its access semantics, known limits, harness matches, freshness, and the latest test outcome when one exists.

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

The database keeps one current status per route and a bounded daily history. NVIDIA NIM developer-tier checks run separately from the regular OpenRouter and OpenCode cycle.

```bash
hyperfine --runs 1 --warmup 0 --show-output \
  -n 'free-model-health' \
  "zsh -lc 'source ~/.zshrc >/dev/null 2>&1; cd \"$HOME/AZ Labs/2 - Testing/AIMI\"; python3 free_model_health.py --workers 4 --timeout 45 --retention-days 30'"

./aimi free-health-summary
./aimi free-health
./aimi free-health --failures-only
```

## Monitoring official endpoints

The endpoint monitor covers OpenRouter, OpenCode Zen, OpenCode Go, NVIDIA NIM, DeepSeek, Mistral, OpenAI, Gemini, Cloudflare Workers AI, and Ollama Cloud. It saves timestamped captures, hashes evidence, normalizes volatile fields, records additions and removals, and updates free-offer windows without storing secrets.

The Hermes job is:

```text
model-catalogue-endpoint-monitor (454c1f94d5fe)
```

Inspect it with:

```bash
hermes cron runs 454c1f94d5fe
```

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
