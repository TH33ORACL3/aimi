---
name: ai-model-index
description: Comprehensive personal AI model index operations for Aubrey. Use for listing Pi models in their exact live order; finding the newest or free model on OpenRouter, OpenCode, NVIDIA, Cloudflare, DeepSeek, Gemini, Mistral, OpenAI or other providers; adding, moving, removing or selecting Pi models; model/provider pricing, free windows, context limits, capabilities, aliases, release dates and evidence; harness/IDE availability and configuration for Pi, Droid, OpenCode, Codex, Copilot, Aside, Cline, Antigravity or Vibe; model recommendations; endpoint changes; model monitoring; index validation; and sanitized exports. Always use this skill for requests mentioning the model index, model database, aimi, Pi model order, enabledModels, latest free models, or adding/swapping models in an agent harness.
compatibility: Windows, macOS, and Linux; requires Python 3.11+ and SQLite. POSIX shell tooling (bash/zsh, jq, and optional Hermes/Hyperfine) is only required for the corresponding optional workflows.
metadata:
  version: "1.1.0"
  owner: Aubrey Zemba
---

# Personal AI Model Index

## Source of truth

- Project: `/Users/TH33_ORACL3/AZ Labs/2 - Testing/AIMI`
- Private database: `aimi.db`
- CLI: `aimi` (invoke as `python aimi` on Windows)
- Skill wrapper: `scripts/catalogue`
- Pi live settings: `~/.pi/agent/settings.json`
- Pi custom providers: `~/.pi/agent/models.json`
- Durable Pi order: `~/.pi/agent/AGENTS.md`

## OpenCode subscription providers

OpenCode Go and OpenCode Zen are separate subscription products created by the OpenCode harness. They must be treated as separate providers, not as two names for the same service:

| Product | Catalogue provider ID | Official models endpoint | Access semantics |
|---|---|---|---|
| OpenCode Go | `opencode-go` | `https://opencode.ai/zen/go/v1` | Subscription access; not free |
| OpenCode Zen | `opencode-zen` | `https://opencode.ai/zen/v1` | Separate Zen gateway with pay-as-you-go credits; classify subscription access only when an entitlement is evidenced |

When Aubrey asks for OpenCode Go models, query only `opencode-go` and its Go endpoint. When he asks for OpenCode Zen models, query only `opencode-zen` and its Zen endpoint. Do not answer either request from the other provider or from the generic OpenCode harness config alone. Official docs currently describe Go as a standalone optional subscription and Zen as pay-as-you-go, so preserve Aubrey's reported entitlement path as a user claim until verified.

## Subscription catalogue model

Track subscriptions separately from providers and model routes:

- **Subscription product**: vendor, product/tier, billing semantics, region, official pricing URL, and verification timestamp.
- **Personal entitlement**: whether Aubrey reports or evidence proves active access, the account/organisation relationship, confirmation source, start/end or review dates, and confidence.
- **Covered routes**: many-to-many links from a subscription/entitlement to exact provider/model routes or harness model IDs, with `subscription_included`, usage/credit limits, client restrictions, and evidence per link.
- **Harness-only models**: record model IDs from an official harness registry even when the vendor exposes no public `/models` endpoint. Do not invent a provider API route for them.
- **BYOK/custom endpoints**: record separately from subscription-included vendor inference. A Warp BYOK Anthropic/OpenAI/Google route is not a Warp-hosted model.

Known first-class subscription/harness candidates include ChatGPT Plus/Codex, Claude Pro/Max/Team/Enterprise and Claude Code, Google AI plans/Gemini, GitHub Copilot/Enterprise, OpenCode Go/Zen, and Warp. Expand this set when an official subscription covers a provider/model already in the catalogue.

Warp is a first-class harness, not a provider endpoint. Use its official model-choice documentation and local `oz model list --output-format json`. UUID entries are preserved exactly when Warp exposes no public name. Warp Settings is the authority for changing custom inference endpoints; BYOK and custom OpenAI-compatible endpoints must be labelled separately from Warp-hosted inference.

**Grok Build / Grok CLI** is the xAI agent harness used in this session. Custom models are configured in `~/.grok/config.toml` (TOML format). Grok supports three API backends:
- `chat_completions` — OpenAI Chat Completions (`/v1/chat/completions`)
- `responses` — OpenAI Responses (`/v1/responses`)
- `messages` — Anthropic Messages (`/v1/messages`)

### Thinking/Reasoning in Grok

For models with thinking/reasoning support, Grok **requires** the `messages` backend (Anthropic-compatible endpoint) because the `chat_completions` backend cannot send `thinking: {"type": "enabled"}`. Use the `aimi grok-config` command to generate the correct config block:

```bash
aimi grok-config <provider> <model>
```

This command:
- Looks up the model's `reasoning` flag and available `reasoning_efforts`
- Reads the `harness_provider_support` table for grok-build + that provider
- Generates a `[model.<key>]` block with `api_backend = "messages"`, the correct Anthropic-compatible `base_url`, `reasoning_effort`, and `extra_headers`
- Falls back to basic config if the provider/harness support data is not yet recorded

The generated block can be pasted directly into `~/.grok/config.toml`. Both the original model entry (non-thinking, `chat_completions` backend) and the thinking variant (with `messages` backend) can coexist, allowing `/model` switching in the TUI.

### Applying thinking to any agent

The same pattern applies to any agent/harness that supports custom API backends:

| Agent | Thinking config approach |
|---|---|
| **Grok CLI** | Use `api_backend = "messages"` with the provider's Anthropic-compatible endpoint + `reasoning_effort` + `extra_headers` |
| **Pi CLI** | Set `reasoning: true` in the provider model config; Pi sends `reasoning_effort` natively via OpenAI format |
| **Droid** | Set `reasoningEffort` in session default settings; Droid passes it through to the API |
| **Aside** | Set `reasoning: true` in the model config block |
| **OpenCode** | Configure via provider model settings; OpenCode passes reasoning params through |
| **Codex CLI** | Use `--model-reasoning-effort` flag or config equivalent |

The database stores this in `harness_provider_support.config_schema_json` per (harness, provider) pair, with the `thinking` key containing the exact parameters needed.

Resolve all relative skill paths against this skill directory. Use the wrapper instead of rebuilding SQL or config logic by hand.

```bash
SKILL="$HOME/.agents/skills/model-catalogue"
"$SKILL/scripts/catalogue" summary
```

On Windows, use the portable Python entry point from the AIMI project instead:

```powershell
py aimi summary
```

Install or refresh the skill and initialise the database with `python install.py` (or `py install.py`).

## Non-negotiable rules

1. **Live configuration wins for “right now.”** Read Pi's order with `catalogue pi-order`; do not answer from a stale database row or AGENTS.md.
2. **Check freshness without silently ingesting chat discoveries.** Before answering “latest,” “currently free,” “newly available,” or current endpoint-availability questions, use the fast composite command when applicable. `catalogue where '<model>'` returns provider routes, access offers, cached harness matches, and freshness metadata in one read, so do not run separate `monitor-status`, `route`, raw SQLite, or harness-scan commands for a simple provider lookup. The command does not rescan local harnesses unless `--refresh-harnesses` is explicitly requested. If live checking in the chat finds information not already represented, present it as a candidate and obtain Aubrey's confirmation before running any ingestion or authoritative update.
3. **Free means proven no-charge access with precise semantics.** Require an active `genuine_zero_price`, `temporary_free_window`, or officially evidenced `free_tier_quota`. API access, open weights, free chat access, or an API key alone do not prove a free route. Always distinguish permanent zero-price from temporary windows and free developer/evaluation quotas.
3a. **Subscription access is a separate category.** Use `subscription_included` / subscription-access classification for models included with an Aubrey-held subscription. Subscription inclusion is not `free`, must not appear in free-only results, and must not be tested by the free-model health job. Track genuinely free routes separately, including free models available through the Zen endpoint.
3b. **Keep OpenCode Go and Zen endpoint-specific.** Use provider ID `opencode-go` with `https://opencode.ai/zen/go/v1` for Go, and provider ID `opencode-zen` with `https://opencode.ai/zen/v1` for Zen. Never merge their model lists, pricing/access offers, endpoint telemetry, or health results.
4. **Name the date semantics.** Provider `created` time, endpoint first-seen, announcement, GA, API availability, model-card publication, and weights release are different dates. Never collapse them into one release date.
5. **Null means unknown.** Missing capability/context/output data is unverified, not unsupported.
6. **Never expose secrets.** Do not print environment variables, complete config files, auth headers, tokens, or literal keys. Generated configuration must use `$ENV_VAR` references.
7. **Preview risky writes.** Model changes preview by default. An explicit user request such as “add it,” “move it,” “remove it,” or “make it default” authorizes that exact write. Otherwise show the preview and request approval.
8. **Preserve order by default.** If the user says only “add,” append the model. Move or set default only when requested. Never rewrite Aubrey's durable preferred order in AGENTS.md unless he explicitly asks to change that policy.
9. **Back up and verify.** Pi writes must use `aimi`, which creates timestamped backups. After applying, run `catalogue scan`, `catalogue pi-order`, `catalogue order-diff pi`, and `catalogue validate`.
10. **Test before enabling a newly discovered route.** Make one small sanitized API handshake when credentials are available. Record the result in `handshake_tests`; never store response secrets or full request headers.
11. **Never silently persist newly discovered information.** If an agent finds new model, provider, pricing, release, capability, harness, ranking, or availability information in any chat, treat it as a candidate finding only. Show Aubrey the evidence and ask for explicit confirmation before adding it to or changing it in the database. This is mandatory when the finding differs from, conflicts with, or would supersede existing database information. Do not suggest that the database was already updated, and do not write first and ask afterwards.
12. **Make conflicts explicit before approval.** Present the current database value, proposed new value, source URL/type, evidence date, confidence, and affected records. Ask a short numbered confirmation such as: `1. Add/update it  2. Keep the database unchanged  3. Save as an unverified candidate only.` Only option 1 authorizes changing verified data. Option 3 may create an explicitly unverified candidate claim but must not alter the current authoritative value.
13. **Do not auto-apply endpoint changes.** New endpoint records and free-window changes must be reviewed and confirmed by Aubrey before broad database or configuration changes.
14. **Use current time for time claims.** Run `date` before "today," "newest," expiry, or age statements.

15. **Identify models by maker, not provider.** When Aubrey asks for models from a company or model family (for example, “OpenAI models”), search the canonical model identity/developer, display name, model identifier, and aliases across every harness and provider. Do not restrict the answer to providers whose name contains that company. For OpenAI, this must surface routes such as `openrouter/openai/gpt-oss-120b:free` even though the provider is OpenRouter, and any NVIDIA/OpenCode/Cloudflare/other route for the same OpenAI model.
16. **Show every provider route for the same model.** When answering questions about a specific model — "latest free", "newest", "what's available" — always list **every provider route** (OpenRouter, OpenCode Zen, NVIDIA NIM, Cloudflare, etc.) for that model, not just the top result. Duplicate models across providers are relevant information and must be shown with their distinct evidence, pricing, and date semantics.
16. **Ollama means cloud-only for Aubrey.** Use provider `ollama-cloud` and the official cloud endpoints `https://ollama.com/api/tags` or `https://ollama.com/v1/models`. For runtime tests, force `OLLAMA_HOST=https://ollama.com`. Do not catalogue, recommend, pull, benchmark, or configure locally hosted Ollama models unless Aubrey explicitly reverses this preference.
17. **Periodic health probes are free-only and bounded.** Select targets exclusively from `currently_free_provider_models`; never probe paid, subscription-only, unknown-pricing, expired-window, or merely open-weight models. Use the exact prompt `Reply with exactly OK`, parallel bounded workers, and Hyperfine around the batch. Persist one upserted current status per route plus one compact daily aggregate per route, retaining only 30 days. Preserve `last_ok_at` even after later failures.
18. **Use three health colours without conflating rate limits with failure.** `green` means the latest probe returned exact `OK`; `orange` means the latest probe was rate-limited (normally HTTP 429), so availability is inconclusive rather than failed; `red` means the latest probe was reachable but failed the exact-OK contract, returned another HTTP error, timed out, was unauthorized, or was otherwise unusable. Always show the detailed `last_status`, HTTP code, human-readable `result_description`, last-tested time, and last-OK time alongside the colour.
19. **NVIDIA NIM uses an official free developer/evaluation tier.** Direct `nvidia-nim` routes are `free_tier_quota`, backed by NVIDIA's “free access ... for unlimited prototyping” and “Free serverless APIs for development” statements. Do not call this permanent zero-price production access. Preserve each route's detailed health result; test NVIDIA NIM weekly rather than every 12 hours to limit unnecessary evaluation usage.

## Intent routing

| User intent | Required workflow |
|---|---|
| “List all Pi models in order right now” | `catalogue pi-order` |
| “What is free on OpenRouter?” | `catalogue monitor-status`, then `catalogue free --provider openrouter`; if stale, disclose that before any proposed refresh |
| “What OpenCode Go models are available?” | Query the live `opencode-go` provider and `https://opencode.ai/zen/go/v1`; report subscription access separately from free routes |
| “What OpenCode Zen models are available?” | Query the live `opencode-zen` provider and `https://opencode.ai/zen/v1`; report subscription-included and genuinely free routes separately |
| “What is the latest free OpenRouter model?” | `catalogue monitor-status`, then `catalogue latest-free --provider openrouter --limit 5`; identify ordering as provider-created time. Treat externally discovered differences as candidates pending approval |
| “Add the latest free OpenRouter model to Pi” | Follow [Latest-free-to-Pi workflow](references/workflows.md#latest-free-provider-model-to-pi) |
| “Where can I use model X?” | Run one fast read: `catalogue where '<model>'`. It returns every available provider route, offers/pricing semantics, cached harness matches, and freshness metadata. Use `--refresh-harnesses` only when current local config rather than cached config is specifically required. |
| “What models are in any installed harness?” | `catalogue harness-models <harness>`; it performs a live local rescan. Use `--kind configured` or `--kind available` to narrow the answer |
| “Which model should I use?” | `catalogue recommend --task <task>` with free/provider filters requested |
| “What models are in any installed harness?” | `catalogue harness-models <harness>`; it performs a live local rescan. Use `--kind configured` or `--kind available` to narrow the answer |
| “Which model should I use?” | `catalogue recommend --task <task>` with free/provider filters requested |
| “How do I configure model X with thinking in Grok?” | Run `catalogue grok-config <provider> <model>`. It returns a TOML `[model.*]` block for `~/.grok/config.toml` with the correct `api_backend = "messages"`, `reasoning_effort`, `base_url` (Anthropic endpoint), and `extra_headers`. Uses `harness_provider_support` data to match the correct backend per provider. |
| “Which free models are working/last returned OK?” | `catalogue free-health-summary`, then `catalogue free-health`; use `--failures-only` when appropriate |
| “Test all free models” | Run `free_model_health.py` through Hyperfine; targets must come only from `currently_free_provider_models` |
| “What changed?” | `catalogue changes` and `catalogue monitor-status` |
| “Check database health” | `catalogue validate` and `catalogue doctor` |
| “Prepare GitHub version” | `catalogue export`; report generated path and scan status |
| Release date, pricing or capability claim | Query route/latest, then inspect evidence claims; cite primary source and date semantics. If new/different, present the conflict and obtain approval before any database write |

## Core commands

```bash
# Live Pi state
catalogue pi-order
catalogue order-diff pi

# Provider/model discovery
catalogue providers
catalogue subscriptions --mine
catalogue subscription opencode-go
catalogue model-info 'gpt-oss'
catalogue maker-models OpenAI
catalogue warp-models --custom
catalogue free --provider openrouter
catalogue latest-free --provider openrouter --limit 10
catalogue free-health-summary
catalogue free-health
catalogue free-health --failures-only
catalogue latest --limit 20
catalogue route openrouter 'poolside/laguna-s-2.1:free'
# Fast all-provider lookup: routes + offers + cached harnesses + freshness
catalogue where 'laguna-s-2.1'
# Only rescan local harness files when that freshness is required
catalogue where 'laguna-s-2.1' --refresh-harnesses
catalogue recommend --task coding --free --limit 10

# Grok CLI thinking config: generates TOML for ~/.grok/config.toml
catalogue grok-config deepseek deepseek-v4-flash
catalogue grok-config deepseek deepseek-v4-flash --force

# Harness inventory
catalogue scan
catalogue harnesses
catalogue harness-models pi
catalogue harness-models droid
catalogue harness-models opencode
catalogue harness-models codex-cli --kind configured
catalogue harness-models codex-cli --kind available

# Pi writes: register new routes, then enable/select them
catalogue pi-register openrouter 'poolside/laguna-s-2.1:free'
catalogue pi-register openrouter 'poolside/laguna-s-2.1:free' --apply
catalogue pi-select openrouter 'poolside/laguna-s-2.1:free'
catalogue pi-select openrouter 'poolside/laguna-s-2.1:free' --position 5 --apply
catalogue pi-add-latest-free --provider openrouter
catalogue pi-add-latest-free --provider openrouter --apply
catalogue pi-remove openrouter 'poolside/laguna-s-2.1:free' --apply

# Monitoring and maintenance
catalogue monitor
catalogue ingest-subscriptions
catalogue record-warp-tests
catalogue changes --limit 50
catalogue monitor-status
catalogue cron-runs
catalogue validate
catalogue export
```

## Response requirements

- For model lists, show numbered positions, exact `provider/model-id`, mark configured versus available, identify the default, and cite the live local source path. Pi positions are essential — Pi's `enabledModels` is an ordered list where position determines fallback/priority order. Always include positions when showing Pi's model list.
- For a specific model/provider question, use the single `catalogue where '<model>'` result. Read `provider_routes` for every provider route, `offers` for access/pricing semantics, `last_test` for the most recent test timestamp **and outcome/result** (status, reply or error, HTTP status, harness and latency), `harness_matches` for cached configured/available harness records, and `freshness` for timestamps. A “last tested” timestamp without what happened is incomplete. Do not perform exploratory follow-up commands unless a field is genuinely missing.
- When a model supports thinking/reasoning (`reasoning: 1`), include the available `reasoning_efforts`, `thinking_api` endpoints (OpenAI and Anthropic backends), and how to enable thinking in each harness via `harness_matches[n].reasoning_config`. For Grok CLI, use `catalogue grok-config` to generate the exact TOML block.
- For company/model-maker questions, use the catalogue's complete route result and match against canonical developer/company, canonical name, display name, aliases, and identifiers. Report every matching route, regardless of provider, and explicitly distinguish the company that made the model from the provider hosting it.
- `catalogue harnesses` and `catalogue harness-models <harness>` perform a live local rescan before answering. Treat local configuration/availability files as authoritative for the harness question, not stale catalogue rows. Use `--kind configured` or `--kind available` when the user asks for only one category.
- For Codex CLI specifically, configured models come from `~/.codex/config.toml` and available models come from `~/.codex/models_cache.json`; do not substitute the broader provider catalogue.
- Other current local sources include Pi (`~/.pi/agent/settings.json`, `~/.pi/agent/models.json`), Droid (`~/.factory/settings.json`), OpenCode (`~/.config/opencode/opencode.json`), Cline (`~/.cline/data/settings/providers.json`), Aside account 0 (`~/.aside/u/0/models.json`), Antigravity (`~/.gemini/antigravity-cli/settings.json`), and Mistral Vibe (`~/.vibe/config.toml`). If no model source is present, report “no local model list detected” instead of inferring models from provider metadata.
- For latest/free answers, include exact model ID, provider, free-offer type, verification time, provider-created or first-seen time, context/output limits when known, whether it is already configured, and the latest test outcome whenever a test exists. Never report only a `last_tested_at` timestamp without its status/result.
- When an official endpoint supplies them, also expose the route description, max input limit, normalized reasoning/tool/function-calling/structured-output/streaming flags, modalities, tokenizer/quantization, aliases, provider canonical slug, Hugging Face ID, supported reasoning efforts, and the complete sanitised endpoint metadata. Keep missing values unknown rather than treating them as unsupported.
- For OpenCode Go or Zen answers, always show the exact provider ID and endpoint, label subscription-included, pay-as-you-go, and genuinely free models separately, and never substitute the other OpenCode product's model list.
- For subscription answers, show the product/tier, personal entitlement status, covered exact routes, harness-only versus public API access, usage/credit limits, evidence date, and unresolved conflicts. Never infer provider API access from a consumer subscription.
- For Warp answers, show whether each entry is Warp-hosted, BYOK, or a custom endpoint; include the exact local source (`~/.warp/settings.toml` or `oz model list`) and preserve unknown UUID labels as unknown. Do not run an exhaustive custom-model batch unless Aubrey explicitly asks; bounded smoke tests must record incomplete batches rather than infer results.
- For writes, report previous position, new position, backup path, smoke-test result, and post-write validation.
- For newly discovered facts, report them as candidates until Aubrey approves database ingestion. When conflicting, show current versus proposed values side by side.
- Clearly distinguish facts proved by official evidence from local observations or rankings.
- Never claim that the database “knows everything”; state evidence gaps plainly.

## Harness model flags & testing

After adding, switching, or configuring a model in any harness, **always test it** using that harness’s non-interactive prompt with the model flag and **Hyperfine**.

### Non-interactive model flags per harness

| Harness | Binary | Model flag | Non-interactive test command |
|---------|--------|-----------|------------------------------|
| **Pi CLI** | `pi` | `--model <provider/model-id>` | `pi --model '<provider/model-id>' -p 'reply OK'` |
| **Grok CLI** | `grok` | `-m <model-id>` | `grok -p 'reply OK' -m <model-id>'` |
| **Grok CLI / Grok Build** | `grok` | `-m <model-id>` | `grok -p 'reply OK' -m <model-id>` |
| **Droid (FactoryAI)** | `droid` | `-m "custom:<id>"` | `droid exec -m 'custom:<id>' "reply OK"` |
| **OpenCode** | `opencode` | `-m <provider/model>` | `opencode run -m <provider/model> 'reply OK'` |
| **Codex CLI** | `codex` | `-m <MODEL>` | `codex exec -m <MODEL> 'reply OK'` |
| **Antigravity CLI** | `agy` | `--model <model>` | `agy --model <model> --dangerously-skip-permissions --print 'reply OK'` |

### Testing protocol

1. After every model-configuration change in a harness, run the non-interactive test for that harness.
2. Use **Hyperfine** with `--runs 1 --warmup 0 --show-output` for a single pass/fail check.
3. When comparing multiple models (e.g. testing which versions work), use Hyperfine with appropriate flags to test them all in parallel.
4. Report which models responded, which errored, and what the output was.

Example:
```bash
hyperfine --runs 1 --warmup 0 --show-output \
  -n "droid-openrouter-laguna-s21" "droid exec -m 'custom:openrouter:poolside-laguna-s21-free' 'reply OK'" \
  -n "droid-opencode-zen-laguna-s21" "droid exec -m 'custom:opencode-zen:laguna-s-2.1-free' 'reply OK'"
```

## Detailed references

- [Operational workflows](references/workflows.md)
- [Command and SQL cookbook](references/operations.md)
- [Schema and evidence semantics](references/schema.md)
