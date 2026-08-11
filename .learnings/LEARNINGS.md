# Learnings

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
