# Personal AI Model Catalogue

An evidence-first SQLite catalogue for discovering, comparing, configuring, ordering, and monitoring AI models across Aubrey's agent harnesses.

The main goal is practical: an agent should be able to answer **which model can I use, through which provider, in which harness, with what configuration, at what cost, and what proof supports those facts?**

## Current state

- **848** provider/model routes
- **11** newest canonical models with primary-source evidence started
- **141** currently no-charge routes: zero-price, temporary-free, or verified free developer-tier
- **42** verified release/API/weights/endpoint events
- **49** evidence sources and **106** immutable captures
- **73** field-level evidence claims
- **56** known harness/tool records
- **11** verified local harness installations
- **88** active local harness/model entries
- **10** official model endpoints monitored every 15 minutes

Run `./modelctl.py summary` for live counts.

## Files

| File | Purpose |
|---|---|
| `model_catalogue.db` | Private, authoritative personal SQLite database |
| `free_models.db` | Compatibility symlink to `model_catalogue.db` |
| `modelctl.py` | Human/agent CLI for search, recommendations, configuration and Pi ordering |
| `~/.agents/skills/model-catalogue/` | Canonical cross-agent skill with safety rules, intent routing, workflows, schema guide and wrapper |
| `monitor_endpoints.py` | Official endpoint polling, snapshots, normalized diffs and free-window detection |
| `free_model_health.py` | Parallel free-only exact-OK probes with bounded current and 30-day daily state |
| `free_model_health.sql` | Bounded health status, daily aggregate and current-health view schema |
| `scan_local_harnesses.py` | Safe local harness/config/credential-presence scanner |
| `refresh_catalog.py` | Full official-endpoint catalogue refresh |
| `ingest_latest_evidence.py` | Initial open-model primary-evidence ingestion |
| `ingest_frontier_evidence.py` | Current frontier-model evidence and pricing ingestion |
| `validate_catalogue.py` | Integrity, evidence, free-offer, ordering and secret checks |
| `export_sanitized.py` | Produces a public database with personal state removed |
| `schema_v2.sql` | Canonical model/evidence/harness/monitoring/subscription schema |
| `evidence_upgrade.sql` | Versioned evidence-capture and offer-window migration |
| `subscription_upgrade.sql` | First-class subscriptions, personal entitlements, covered routes and harness tests |
| `ingest_subscriptions.py` | Evidence-backed subscription/provider ingestion with explicit conflict states |
| `record_warp_tests.py` | Persists completed Warp custom-model smoke results without guessing interrupted tests |
| `snapshots/` | Timestamped official endpoint payloads |
| `evidence/` | Archived primary web/X/local evidence and test results |
| `task_plan.md`, `findings.md`, `progress.md` | Persistent project reasoning and history |

## Core concepts

### Canonical model versus provider route

A model and a place where it can be called are different things.

- `canonical_models`: GPT-5.6 Sol, GLM-5.2, Kimi K2.7 Code, etc.
- `provider_models_v2`: the exact ID exposed by OpenRouter, OpenCode, NVIDIA, Cloudflare, OpenAI, GitHub Copilot, or another provider.

This permits one canonical model to have multiple routes, aliases, quantizations, prices, limits, and free windows.

### Release dates are events, not one ambiguous field

`model_events` distinguishes:

- announcement
- preview release
- general release
- API availability
- model-card publication
- weights release
- endpoint first seen or removed
- free-window start or end
- pricing/capability/context changes
- deprecation and retirement

Every verified event requires an `evidence_source` and immutable `evidence_capture`.

### Pricing semantics

| Status/offer | Meaning |
|---|---|
| `genuine_zero_price` | Official source proves zero price |
| `free_tier_quota` | Limited quota, not universally free |
| `temporary_free_window` | Free now, duration finite or unknown |
| `temporary_discount` | Reduced price, not free |
| `promotional_credit` | Credits offset paid usage |
| `subscription_included` | Included only with a subscription |
| `paid` | Paid API usage |
| `unknown` | No adequate official pricing evidence |

A working key, open weights, or free chat interface is never enough to classify an API route as free. An official free developer/evaluation tier can qualify as `free_tier_quota` when its scope and restrictions are captured explicitly; it must not be presented as permanent `genuine_zero_price`.

## Agent skill

The canonical skill is:

```text
/Users/TH33_ORACL3/.agents/skills/model-catalogue/SKILL.md
```

Pi and other compatible harnesses discover it from `~/.agents/skills`. It triggers for Pi model order, latest/free provider models, model additions/removals, model switching, pricing/capability/release evidence, harness configuration, endpoint monitoring, validation and public exports.

Use it directly in Pi with:

```text
/skill:model-catalogue
```

The bundled wrapper resolves the private project automatically:

```bash
catalogue="$HOME/.agents/skills/model-catalogue/scripts/catalogue"
"$catalogue" pi-order
"$catalogue" monitor
"$catalogue" latest-free --provider openrouter
```

## Subscription and harness inventory

Subscriptions are not free routes. `subscription_included` and the first-class subscription tables record entitlement separately from API pricing and the `currently_free_provider_models` view.

```bash
# All catalogue products, or only Aubrey's active/reported entitlements
./modelctl.py subscriptions
./modelctl.py subscriptions --mine
./modelctl.py subscription opencode-go

# Search canonical maker/model identity across every provider route
./modelctl.py model-info 'gpt-oss'
./modelctl.py maker-models OpenAI

# Warp/Oz's live harness registry. This refreshes Warp's local registry first.
./modelctl.py warp-models
./modelctl.py warp-models --custom
```

Warp custom inference models are represented by the UUID returned by `oz model list --output-format json`. Warp's UI is the authority for the UUID's label and endpoint configuration; the catalogue does not invent names or treat BYOK/custom endpoints as Warp-hosted inference. `record_warp_tests.py` stores only completed tests and preserves interrupted batches as evidence notes.

## `modelctl` experience

```bash
# Overview
./modelctl.py summary
./modelctl.py doctor

# Models and evidence
./modelctl.py free
./modelctl.py free --provider openrouter
./modelctl.py latest --limit 20
./modelctl.py recommend --task coding --free

# Harnesses and local configuration/availability
# These harness commands rescan the harness's actual local model files.
./modelctl.py harnesses
./modelctl.py harness-models pi
./modelctl.py harness-models codex-cli
./modelctl.py harness-models codex-cli --kind configured
./modelctl.py harness-models codex-cli --kind available
./modelctl.py harness-models droid

# Fast provider lookup: one read returns all routes, offers, latest test outcomes,
# cached harness matches and freshness. `last_test` includes what happened, not only when.
# It does not rescan local harness files.
./modelctl.py where glm-5.2
# Add --refresh-harnesses only when current local config is required.
./modelctl.py where glm-5.2 --refresh-harnesses
# Use --no-harnesses for provider routes only.
./modelctl.py where glm-5.2 --no-harnesses

# Every harness model row includes record_type (configured/available) and source_path.
# Examples of live sources: ~/.codex/config.toml + ~/.codex/models_cache.json,
# ~/.pi/agent/settings.json + ~/.pi/agent/models.json, ~/.factory/settings.json,
# ~/.config/opencode/opencode.json, ~/.vibe/config.toml, and other harness files.

# Pi ordering
./modelctl.py order-diff pi

# Generate a secret-free Pi provider fragment
./modelctl.py pi-fragment openrouter 'poolside/laguna-s-2.1:free'
./modelctl.py pi-register openrouter 'poolside/laguna-s-2.1:free' --apply

# Preview moving/selecting a Pi model; no write by default
./modelctl.py pi-select openrouter 'poolside/laguna-s-2.1:free' --position 3

# Apply with automatic timestamped backup
./modelctl.py pi-select openrouter 'poolside/laguna-s-2.1:free' --position 3 --default --apply

# Register and append the newest verified free OpenRouter route
./modelctl.py pi-add-latest-free --provider openrouter --apply

# Endpoint/product maintenance
./modelctl.py monitor-status
./modelctl.py validate
```

Pi ordering is read live from `~/.pi/agent/settings.json`; compare it with the durable preference using `./modelctl.py order-diff pi`. Do not assume the database snapshot is current without running the live command.

## Free-only health checks

Only routes present in `currently_free_provider_models` are eligible. Paid, subscription-only, unknown-pricing and expired-window routes are excluded before any request is sent.

```bash
hyperfine --runs 1 --warmup 0 --show-output \
  -n 'all-verified-free-models-parallel' \
  "zsh -lc 'source ~/.zshrc >/dev/null 2>&1; cd \"$HOME/AZ Labs/2 - Testing/Models\"; python3 free_model_health.py --workers 4 --timeout 45 --retention-days 30'"

./modelctl.py free-health-summary
./modelctl.py free-health
./modelctl.py free-health --failures-only
```

Health uses three clear states:

- **Green:** latest probe returned exact `OK`.
- **Orange:** latest probe was rate-limited, so availability is inconclusive rather than failed.
- **Red:** latest probe failed the exact-OK contract, returned another HTTP error, timed out, or was otherwise unusable.

The detailed probe status, HTTP code, last-tested time and last-OK time are retained alongside the colour.

Storage stays bounded:

- one current upserted status per tested route;
- one compact aggregate per route per UTC day;
- only 30 days of daily aggregates retained;
- `last_ok_at` remains available after later failures;
- recurring probes do not inflate `handshake_tests`.

Hermes job `free-model-health-monitor` (`398046f2facf`) runs OpenRouter/OpenCode checks every 12 hours. NVIDIA NIM's 119-route free developer tier is checked separately every seven days by `nvidia-nim-free-health-monitor` (`2e53805672be`) to avoid unnecessary credit and request usage. Both remain silent unless status changes or the batch fails.

## Monitoring

`monitor_endpoints.py` currently checks:

1. OpenRouter
2. OpenCode Zen
3. OpenCode Go
4. NVIDIA NIM
5. DeepSeek
6. Mistral
7. OpenAI
8. Gemini
9. Cloudflare Workers AI
10. Ollama Cloud (`https://ollama.com/v1/models`; cloud-only, never local by default)

The monitor:

- saves immutable timestamped snapshots;
- hashes every capture;
- normalizes volatile provider fields;
- records additions, removals and meaningful metadata changes;
- starts/updates/closes free offers;
- marks removed provider routes;
- stores run health and errors without secrets.

A Hermes no-agent job is active every 15 minutes:

```text
model-catalogue-endpoint-monitor (454c1f94d5fe)
```

It is silent when nothing changed. Inspect it with:

```bash
hermes cron runs 454c1f94d5fe
```

## Evidence policy

Priority order:

1. successful runtime/API observation
2. official models or pricing endpoint
3. official provider documentation/changelog
4. official model card, repository, technical report or paper
5. official release blog
6. official X announcement
7. trusted third party
8. unverified lead

Different sources can be best for different fields. An API endpoint is strongest for current availability and exact model IDs; a dated official announcement is strongest for announcement/release time; runtime tests are strongest for actual compatibility and enforced limits.

Conflicts are retained as claims with confidence and source priority. They are not silently overwritten.

## Local privacy

The private database may contain local paths, harness ordering, historical preferences, account-ID placeholders, and environment-variable names. It does **not** intentionally store API-key values.

Raw evidence, snapshots and the private DB are gitignored.

Create a public export with:

```bash
./export_sanitized.py
```

The export removes:

- machine installations
- configured model order
- credential inventory
- personal rankings
- local config evidence and paths
- account identifiers

It then runs `VACUUM`, SQLite integrity validation, and a fail-closed secret-pattern scan.

## Refresh and validation

```bash
./refresh_catalog.py
./scan_local_harnesses.py
./monitor_endpoints.py
./validate_catalogue.py
./export_sanitized.py
```

`validation-report.json` is the latest machine-readable audit.

## Important limitations

- Only the newest 11 canonical models have been deeply linked to primary release evidence so far. Historical enrichment remains intentionally incremental.
- Hundreds of provider routes still lack verified context or output limits because many `/models` endpoints do not expose them.
- Five OpenCode `-free` routes have unknown free-window start/end dates. Their current availability is verified; their duration is not.
- Grok 4.5's model ID and API usage are verified, but its exact release date remains intentionally unset pending a dated primary source.
- A null capability means unverified/not exposed, not unsupported.

## Next build priorities

1. Complete official model cards, reports, prices and context/tool metadata for newest models.
2. Link remaining provider routes to canonical models and aliases.
3. Add safe runtime handshake tests for tools, reasoning, images, streaming and structured output.
4. Track model benchmark sources separately from Aubrey's personal rankings.
5. Add task-specific Pi order profiles and usage-based “move this model closer” recommendations.
6. Add reviewed notifications for new free windows, ending windows, removals and deprecations.
7. Expand historical releases after current frontier coverage is complete.
