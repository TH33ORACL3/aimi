# Learnings

## [LRN-20260812-002] correction

**Logged**: 2026-08-12T18:27:00+02:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
OpenCode model `created` timestamps are volatile response-time values, not deployment or release evidence.

### Details
The OpenCode Go `/models` records for `deepseek-v4-flash` and `deepseek-v4-pro` showed identical `created` timestamps. I incorrectly treated that as evidence they were re-listed together. A later poll changed both timestamps from 16:01 to 16:17 UTC, proving OpenCode generates this field per response. It cannot establish model version, deployment time, or shared upstream.

### Suggested Action
Classify OpenCode `created` as volatile and exclude it from release/version inference. Origin verification requires a provider attestation, immutable build ID, upstream metadata, or a controlled China-opt-in test.

### Metadata
- Source: error
- Related Files: `monitor_endpoints.py`, `correct_volatile_changes.py`, `aimi.db`
- Tags: opencode-go, provider-created, volatile-metadata, provenance

---

## [LRN-20260812-001] correction

**Logged**: 2026-08-12T18:11:00+02:00
**Priority**: medium
**Status**: pending
**Area**: tooling

### Summary
For model-release checks in the AIMI project, use AIMI only unless Aubrey explicitly asks for web research.

### Details
Aubrey asked which models were released today. The correct scope was the AIMI catalogue and endpoint monitor, not the research or search skills. AIMI distinguishes provider-created timestamps and endpoint-first-seen events from verified announcement or GA dates.

### Suggested Action
Run `aimi timeline`, `aimi changes`, and `aimi where`; clearly label endpoint detections versus actual releases. Do not invoke Antigravity or Firecrawl unless explicitly requested.

### Metadata
- Source: user_feedback
- Related Files: `aimi`, `.agents/skills/ai-model-index/SKILL.md`
- Tags: aimi, model-releases, scope, research-routing

---

## [LRN-20260807-001] pricing_object_is_not_a_complete_free_model_source

**Logged**: 2026-08-07T01:02:22+02:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
Vercel AI Gateway's `/v1/models` response can use an empty `pricing` object for a promotional free route, so zero-valued pricing fields alone do not enumerate all current free models.

### Details
`inclusionai/ling-3.0-tiny-free` has `pricing: {}` but Vercel Developers explicitly announced on 2026-08-06 that it is free until 2026-08-14 08:00 PT. Free-route discovery must combine the API catalogue with current official promotion evidence and must distinguish empty pricing from unknown pricing.

### Suggested Action
Classify a route as free only with direct zero pricing or official time-bounded promotion evidence; do not classify all empty-pricing models as free.

### Metadata
- Source: user_feedback
- Related Files: `aimi`, `handshake.py`
- Tags: vercel, ai-gateway, pricing, free-models

### Resolution
- **Resolved**: 2026-08-07
- **Decision**: Vercel AI Gateway not added to AIMI. Although all three candidate routes (`inclusionai/ling-3.0-tiny-free`, `poolside/laguna-s-2.1-free`, `zai/glm-4.6v-flash`) authenticate with the user's key, the gateway refuses to service any request until a valid credit card is on file (HTTP 403). Because it requires billing, Aubrey decided it should not enter the catalogue at all. `AI_GATEWAY_API_KEY` remains set in `~/.zshrc` but is unused.

---

## [LRN-20260804-001] correction

**Logged**: 2026-08-04T18:20:00+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
Never test a model route merely to see whether it responds unless AIMI has verified it as genuinely free.

### Details
Aubrey clarified that even tiny paid OpenRouter usage accumulates over time. Paid, subscription-only, unknown-pricing, and unverified routes must not receive response tests or smoke tests. Only genuinely free routes with verified zero-price, temporary-free, or evidenced free-tier-quota semantics may be tested.

### Suggested Action
Before proposing or running any model test, check the route's current AIMI access offer. If it is not verified free, do not test it. Report it as untested instead.

### Metadata
- Source: user_feedback
- Related Files: /Users/TH33_ORACL3/.agents/skills/ai-model-index/SKILL.md
- Tags: free-only, paid-usage, openrouter, model-testing

---

## [LRN-20260806-002] correction

**Logged**: 2026-08-06T22:00:23+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
A Pi provider error affecting several models can be caused by a stale long-running Pi process after a self-update, not by the provider or model.

### Details
Aubrey correctly pointed out that `MIN_ANSWER_TOKENS` failures occurred with DeepSeek, GPT-5.6 Luna, and ClinePass, so ClinePass was not the root cause. Pi 0.84.0 was installed while the current Pi session had been running since before the update. The running process referenced a deleted temporary package directory. Fresh Pi 0.84.0 processes successfully completed all three model tests, while the static ESM error indicates mismatched `pi-ai` module files (`openai-completions.js` importing a symbol absent from its `simple-options.js`).

### Suggested Action
When an identical JavaScript import error appears across unrelated models after a Pi update, check the running process start time and package path first. Restart Pi completely after the update before debugging providers or model configuration.

### Metadata
- Source: user_feedback
- Related Files: /Users/TH33_ORACL3/.npm-global/lib/node_modules/@earendil-works/pi-coding-agent/CHANGELOG.md
- Tags: pi, update, stale-process, esm, pi-ai, provider-independent

---

## [LRN-20260809-001] subscription_route_smoke_test

**Logged**: 2026-08-09T20:45:00+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
Custom harness setup must not automatically send paid or subscription-backed smoke requests.

### Details
While wiring Claude Code to the ClinePass DeepSeek route, end-to-end plain-text and tool-call smoke tests were run to validate the local translation proxy. The route is subscription-backed, not genuinely free. The setup itself was valid, but the test gate should have required explicit approval before sending upstream requests.

### Suggested Action
For paid or subscription routes, complete syntax, health, translation-fixture, and configuration checks locally first. Ask for explicit approval before an upstream smoke test.

### Metadata
- Source: error
- Related Files: `/Users/TH33_ORACL3/bin/claude-cline-proxy.py`, `/Users/TH33_ORACL3/bin/claude-cline`
- Tags: free-only, paid-usage, clinepass, harness-setup
- See Also: LRN-20260804-001

---

## [LRN-20260811-001] knowledge_gap

**Logged**: 2026-08-11T16:00:00+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
Do not trust a package's security documentation without inspecting its shipped entry point.

### Details
`pi-agentsmd@0.1.3` ships `extensions/index.ts`, which calls `reportInstallTelemetry()` at extension load. `src/install-telemetry.ts` reports package version, OS, runtime, and architecture to `https://mocito.dev/api/report-install` by default. Its `SECURITY.md` simultaneously claims the package does not send data to external services. The package was installed only after setting `enableInstallTelemetry: false` in `~/.pi/agent/settings.json`.

### Suggested Action
Inspect installed Pi package manifests and entry points before installation. Treat security/privacy claims as unverified until they match the shipped code. Keep install telemetry disabled unless Aubrey explicitly approves it.

### Metadata
- Source: knowledge_gap
- Related Files: `~/.pi/agent/settings.json`, `/tmp/pi-ext-compare.uxIaoA/extracted/pi-agentsmd-0.1.3/package/src/install-telemetry.ts`
- Tags: pi, extensions, telemetry, package-review

---

## [LRN-20260811-002] provider_free_allocation_vs_model_pricing

**Logged**: 2026-08-11T16:15:45+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
A provider-wide free allocation can make an image route usable at no charge even when the model endpoint reports a paid per-unit price.

### Details
Cloudflare Workers AI's current pricing page gives Workers Free accounts 10,000 Neurons per day at no charge, while the model endpoint reports per-Neuron prices for image models. AIMI's strict `free` route query therefore omits those image routes unless a model-level free offer is recorded.

### Suggested Action
For free-capability questions, inspect both model-level access offers and provider-level quota/free-plan evidence. Report account-wide free allocations separately from genuinely zero-priced model routes.

### Metadata
- Source: knowledge_gap
- Related Files: `aimi.db`, `/Users/TH33_ORACL3/.agents/skills/ai-model-index/SKILL.md`
- Tags: aimi, image-generation, cloudflare, free-tier, pricing

---

## [LRN-20260811-003] cloudflare-free-plan-model-gates

**Logged**: 2026-08-11T16:58:52+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
Cloudflare's account-wide free Neuron allocation does not mean every Workers AI model is available on the Free plan.

### Details
A direct test of `@cf/zai-org/glm-5.2` returned HTTP 403 before inference: the model is not available on the current Workers Free plan and requires an upgrade. The free allocation and model eligibility are separate gates.

### Suggested Action
Before recommending a Cloudflare route as usable for free, check both the provider's free allocation and the account/model plan-eligibility response. Treat catalogue availability as distinct from current-plan usability.

### Metadata
- Source: error
- Related Files: `aimi.db`, Cloudflare Workers AI route test
- Tags: cloudflare, workers-ai, free-plan, model-eligibility

---

## [LRN-20260812-001] correction

**Logged**: 2026-08-12T17:48:00+02:00
**Priority**: critical
**Status**: resolved
**Area**: config

### Summary
Never claim a protected CCR fix is durable until its persistence baseline and scheduled repair pass are validated.

### Details
The Codex bridge fix initially passed direct and Claude Code tests, but `ai.azlabs.claude-3p-persistence` restored the old proxy five minutes later. The same job repeatedly restored runtime-normalized Desktop files and CCR migration timestamps, restarting the gateway and causing `ConnectionRefused`. Aubrey correctly reported that GPT traffic was still falling back.

### Suggested Action
For every protected CCR change: patch the live file and exact baseline, update manifest hashes, run the persistence validator at least twice, prove gateway and proxy PIDs stay unchanged, then run end-to-end model tests and verify `provider=Codex` with `route_attempt_count=1`.

### Metadata
- Source: user_feedback
- Related Files: `~/bin/codex-ccr-proxy.py`, `~/.claude/3p-persistence/`, `~/.claude/settings.json`
- Tags: ccr, codex, persistence, fallback, connection-refused, validation

### Resolution
- **Resolved**: 2026-08-12T17:48:00+02:00
- **Notes**: Stabilized persistence checks, updated the baseline, removed malformed model suffixes, and verified Luna, Terra, and Sol through Codex with one attempt each.

---

## [LRN-20260814-ZCODE] correction

**Logged**: 2026-08-14T19:48:10+02:00
**Priority**: critical
**Status**: promoted
**Area**: config

### Summary
ZCode means Z.ai Code and is a separate harness from Claude Code Router.

### Details
A request for ZCode model display names was incorrectly applied to `~/.claude-code-router/config.sqlite`. The correct ZCode source is `~/.zcode/v2/config.json`, where custom providers use provider-level `modelDisplayNames`. CCR and ZCode must never be treated as interchangeable.

### Suggested Action
Route by the exact harness name before any model-config write. For ZCode, inspect and edit only `~/.zcode/v2/config.json`; for CCR, use `~/.claude-code-router/config.sqlite`. Confirm the target path and schema before mutation.

### Metadata
- Source: user_feedback
- Related Files: `~/.pi/agent/AGENTS.md`, `~/.zcode/v2/config.json`, `~/.claude-code-router/config.sqlite`
- Tags: zcode, zai-code, ccr, claude-code-router, harness-routing

### Resolution
- **Resolved**: 2026-08-14T19:50:00+02:00
- **Promoted**: `~/.pi/agent/AGENTS.md`
- **Notes**: Added permanent routing rules and restored CCR's original display names before editing ZCode.

---

## [LRN-20260819-AIMI-SELF] correction

**Logged**: 2026-08-19T20:40:00+02:00
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
For Aubrey's forensic award review, do not delegate to subagents when the configured client model is unavailable or quota-exhausted; complete the review directly.

### Details
Aubrey explicitly clarified that he wants the analysis performed by the primary agent only. The review had already been completed directly, but failed background subagent attempts created unnecessary quota-error notifications.

### Suggested Action
Respect explicit no-subagent instructions immediately. When the user names a model as unavailable or says quota is exhausted, do not launch agents using that route. Continue with local extraction and direct analysis.

### Metadata
- Source: user_feedback
- Related Files: `tmp/pdfs/award/award-pages-indexed.txt`
- Tags: correction, subagents, quota, forensic-review

---

## [LRN-20260820-AIMI-004] correction

**Logged**: 2026-08-20T07:40:00+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
Pi's effective custom model settings live in `~/.pi/agent/models.json`; changing a secondary model catalogue does not wire the model picker.

### Details
The contributor entry in `models-store.json` had the desired context, output, and thinking metadata, but the actual Pi custom-provider entry in `models.json` still had `128000` context, `16384` max output, and no `thinkingLevelMap`. Pi therefore exposed only the standard levels through `high`. The model picker must receive explicit non-null mappings for `xhigh`; unsupported `max` should be omitted rather than aliased.

### Suggested Action
When configuring a Pi custom route, update and validate `~/.pi/agent/models.json`, set `settings.json` to the supported top level, and test both a fresh default launch and an explicit `:xhigh` model suffix.

### Metadata
- Source: user_feedback
- Related Files: `~/.pi/agent/models.json`, `~/.pi/agent/settings.json`, `~/.pi/agent/agents/*.md`
- Tags: correction, pi, thinking-levels, xhigh, models-json

### Resolution
- **Resolved**: 2026-08-20T07:40:00+02:00
- **Notes**: Updated the live custom-provider config, default selection, all 10 subagent profiles, and verified fresh default plus explicit xhigh smoke tests.

---

## [LRN-20260822-OXA] correction

**Logged**: 2026-08-22T18:42:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
Pal's intended OpenCode Go default is `opencode-go/ox-alpha-free`, not `opencode-go/deepseek-v4-flash`.

### Details
The initial fallback choice was applied from the known-working DeepSeek Flash route. Aubrey corrected the intended OpenCode Go model to `ox-alpha-free`, which is already present in Pal's mirrored 39-model scope at position 24.

### Suggested Action
When mirroring a scoped list, confirm the intended default model separately from the known-working smoke-test fallback before applying the default.

### Metadata
- Source: user_feedback
- Related Files: `/root/.pi/agent/settings.json`
- Tags: correction, pal, opencode-go, ox-alpha-free

### Resolution
- **Resolved**: 2026-08-22T18:42:00+02:00
- **Notes**: Pal now defaults to `opencode-go/ox-alpha-free`; Hyperfine smoke test returned `OK`.

---

## [LRN-20260822-DFL] default-flip-anomaly

**Logged**: 2026-08-22T18:51:00+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
MacBook `~/.pi/agent/settings.json` default flipped from `openai-codex/gpt-5.6-luna` to `opencode-go/deepseek-v4-flash` between 18:08 and 18:49 SAST without an explicit write from this session.

### Details
The first `pi-remove` backup (18:49:31) already showed the flipped default with 39 models, so the change predated today's removals. No local settings write was issued in this session before that point; only read-only inspections, remote (Pal/AJ) writes, and local hyperfine Pi runs occurred. The cause is unidentified.

### Suggested Action
Investigate whether Pi CLI writes its default on model-fallback paths (e.g. failed `--model` runs) or whether another agent/cron touched the file. Restore was applied; verify it stays stable.

### Metadata
- Source: anomaly
- Related Files: `~/.pi/agent/settings.json`
- Tags: pi, settings, default-model, anomaly

---

## [LRN-20260826-BUL] correction

**Logged**: 2026-08-26T14:23:18+02:00
**Priority**: high
**Status**: in_progress
**Area**: backend

### Summary
AIMI endpoint `model_added` events must not be treated as public model-news candidates when they come from a bulk catalogue synchronisation.

### Details
A manual OpenAI models-endpoint pull exposed more than 200 existing IDs; AIMI subsequently recorded 12 OpenAI additions in one monitoring run. These are endpoint first-seen observations, not evidence that the models were released that day. Public website/X posting should be reserved for genuinely news-relevant same-day releases or a model aggregator newly exposing a previously unavailable model.

### Suggested Action
Gate discovery-to-news generation on release-day evidence or a meaningful single-model aggregator addition, and suppress bulk endpoint syncs. Add regression tests for batch discovery, same-day release, and aggregator-addition cases.

### Metadata
- Source: user_feedback
- Related Files: `model_discovery_notifier.py`, `model_release_desk.py`, `monitor_endpoints.py`
- Tags: correction, model-discovery, bulk-sync, website, x, news

---

## [LRN-20260827-PIW] correction

**Logged**: 2026-08-27T00:35:50+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
For Pi context-window questions, Aubrey requires the effective value from Pi's local configuration, not AIMI catalogue evidence or another provider route.

### Details
Pi's built-in GPT-5.6 Codex models default to 272000 in the effective model metadata. The persistent override belongs under `providers.openai-codex.modelOverrides` in `~/.pi/agent/models.json`; overrides under `providers.openai` do not change the `openai-codex/*` routes.

### Suggested Action
Keep all three `gpt-5.6-*` Codex overrides explicitly set to `contextWindow: 1000000`, then verify by reloading Pi's model registry and inspecting the effective local configuration only.

### Metadata
- Source: user_feedback
- Related Files: `~/.pi/agent/models.json`, `~/.pi/agent/settings.json`
- Tags: correction, pi, codex, context-window, persistence

### Resolution
- **Resolved**: 2026-08-27T00:39:00+02:00
- **Notes**: Added the three `openai-codex` model-level overrides. A fresh `pi --list-models` process reports `1M` for Luna, Terra, and Sol, and all three `pi -p 'reply OK'` smoke tests passed.

---

## [LRN-20260827-MERGE-001] best_practice

**Logged**: 2026-08-27T11:08:15+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
Pi custom-provider API keys should use plain `$ENV_VAR` references when the environment is already managed by the shell; interactive `!command` resolvers can inject startup banners into HTTP headers.

### Details
The Merge route was initially made launcher-independent with `!zsh -lic ...`. In a restored interactive shell, zsh emitted a `Restored session: ...` banner before the key. Pi passed the complete multiline command output to `Headers.append`, producing an invalid Bearer header. Filtering a pipeline inside the command did not help because startup output occurred before the pipeline. The provider already followed the same plain environment convention as all working providers, and a fresh normal zsh process inherited the key correctly.

### Suggested Action
Prefer `apiKey: "$ENV_VAR"` in Pi `models.json` for shell-managed credentials. Verify with `pi auth check`, `pi --list-models`, and a fresh inference whose session record confirms the exact provider/model and successful stop reason. Never treat a same-text reply as proof without provider metadata.

### Metadata
- Source: user_feedback
- Related Files: `~/.pi/agent/models.json`, `~/.pi/agent/settings.json`, `~/.zshrc`
- Tags: pi, custom-provider, env-var, command-substitution, session-restore

### Resolution
- **Resolved**: 2026-08-27T11:08:15+02:00
- **Notes**: Restored `$MERGE_API_KEY`, preserved the global 28-model ordered scope with Merge at 28/28, and verified an actual home-directory Pi request returned `OK` with `provider=merge-gateway`, `model=deepseek/deepseek-v4-flash`, `stopReason=stop`, and no error.

---

## [LRN-20260902-001] correction

**Logged**: 2026-09-02T21:12:43+02:00
**Priority**: high
**Status**: resolved
**Area**: tooling

### Summary
Time-window model-change checks must use Pal's canonical AIMI state and Telegram monitor alerts, not the stale MacBook checkout.

### Details
Aubrey asked whether models had been added or removed in the last one or two hours. I queried the project-local `python3 aimi changes` database, which had not been monitored since the previous day, and then queried live endpoints after the transient Muse Spark 1.3 routes had already disappeared. Pal's 15-minute endpoint monitor had correctly recorded both the add and removal and Katara had delivered the Telegram alert, but I did not inspect that Telegram history until Aubrey explicitly directed me to it.

### Suggested Action
For current AIMI answers on macOS, use the Pal-forwarding `aimi` command, check `monitor-status` freshness, filter `changes` by the requested UTC window, inspect both OpenCode Go and Zen with `--include-removed`, and read Katara's Telegram notifications when an alert is referenced. Never use `python3 aimi` or the local `aimi.db` for current operational conclusions.

### Metadata
- Source: user_feedback
- Related Files: `/Users/TH33_ORACL3/.pi/agent/AGENTS.md`, `/Users/TH33_ORACL3/.agents/skills/ai-model-index/SKILL.md`, `/Users/TH33_ORACL3/.agents/skills/ai-model-index/scripts/catalogue`
- Tags: correction, aimi, pal-first, telegram, opencode-go, opencode-zen, model-removal

### Resolution
- **Resolved**: 2026-09-02T21:19:55+02:00
- **Completed**: 2026-09-02T21:19:55+02:00
- **Verified**: `skills/scripts/catalogue changes --since ... --type model_removed` returned the Pal-recorded Muse 1.3 Go removal, and `provider-models opencode-zen --include-removed` returned the Zen removal.
- **Notes**: Updated persistent routing rules and changed the catalogue wrapper so operational AIMI reads on macOS forward to Pal while local harness/configuration commands remain local.

---
