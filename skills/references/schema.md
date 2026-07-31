# Schema and Evidence Semantics

## Identity layers

### `canonical_models`
The conceptual developer release, independent of route. Examples: GPT-5.6 Sol, GLM-5.2, Kimi K2.7 Code.

### `provider_models_v2`
An exact provider/model ID. Unique by `(provider_id, model_identifier)`. Carries current endpoint state, context/output limits, capabilities, modalities and normalized provider metadata.

A canonical model can have multiple routes. A provider route can remain unlinked until identity is proven.

## Evidence system

### `evidence_sources`
Stable source identity: URL, publisher, source type, official/primary flags, priority and retrieval state.

### `evidence_captures`
Immutable retrieval versions identified by content hash, retrieval time and archived path. Claims and offers should point to the exact captured version used.

### `evidence_claims`
Field-level assertions with subject, JSON value, supporting quotation, validity range, confidence, verification method and source priority.

### `model_events`
Time-specific events. Supported concepts include announcement, preview, GA, API availability, model-card publication, weights release, endpoint addition/removal, pricing/free-window/context/capability changes, deprecation and retirement.

Do not replace one event type with another merely because it has a more precise timestamp.

## Access and pricing

### `access_offers`
Route-level access state and evidence.

- `genuine_zero_price`: official source proves zero prompt/completion price.
- `free_tier_quota`: limited quota.
- `temporary_free_window`: currently free but finite or duration unpublished.
- `temporary_discount`: represented by pricing semantics/migration extensions; reduced is not free.
- `promotional_credit`: credit balance against paid usage.
- `subscription_included`: subscription required.
- `paid`: priced use.
- `unknown`: insufficient evidence.

`currently_free_provider_models` is the safe active-free view. It requires an available route, accepted free offer type, started window and unexpired end. `subscription_included` is intentionally excluded: subscription access is a separate entitlement category, not free access.

OpenCode has two distinct subscription providers and endpoint families:

| Provider ID | Product | Endpoint |
|---|---|---|
| `opencode-go` | OpenCode Go | `https://opencode.ai/zen/go/v1` |
| `opencode-zen` | OpenCode Zen | `https://opencode.ai/zen/v1` |

Keep their routes, offers, telemetry, and model availability separate. A model being included in one subscription does not establish inclusion in the other.

### Subscription tables

- `subscription_products`: vendor/product/tier, billing semantics, official URLs and evidence.
- `personal_subscription_entitlements`: Aubrey's account/organisation relationship and confidence, including unresolved conflicts.
- `subscription_model_access`: exact provider routes or harness-only IDs covered by a product, with limits and evidence.
- `harness_model_tests`: bounded runtime tests for harness-only entries, separate from provider API `handshake_tests`.

`current_personal_subscriptions` returns active, trial, reported and conflicting personal entitlements. `subscription_included` never enters the free-only view or free health probes.

## Harness system

- `harnesses`: Pi, Droid, OpenCode, Codex, Copilot, Aside, Cline, Antigravity, Vibe and other tools.
- `harness_installations`: machine-specific installed/version/config observations.
- `harness_provider_support`: built-in/custom/proxy support and config schema.
- `harness_model_entries`: exact locally configured/selected models and positions, including source paths.
- `harness_available_model_entries`: models listed by each installed harness's own local registry/cache/config, including source path and last observation. This is intentionally separate from configured entries because a harness may list models that are not currently selected. Warp/Oz entries come from `oz model list --output-format json`; UUID custom entries retain the UUID and do not receive guessed names.
- `model_order_profiles`: current, preferred and future task-specific order sets.
- `model_order_profile_entries`: ordered route entries, roles, tags and rationale.
- `credential_inventory`: environment-variable/keychain/config-reference presence only; never values.
- `user_rankings`: Aubrey's preferences, kept separate from published benchmarks.

Live config and model-list files are authoritative for “right now” questions about a harness. `aimi harnesses` and `aimi harness-models` invoke the scanner before reading the database. The scanner synchronizes configured observations into `harness_model_entries` and harness-listed availability into `harness_available_model_entries`; the database is the audit/cache layer, not the authority for stale current state.

## Monitoring system

- `monitoring_targets`: official endpoints/docs/changelogs/feeds.
- `monitoring_runs`: health, hashes, counts and snapshots.
- `endpoint_changes`: normalized additions, removals and stable metadata changes.
- `automation_jobs`: Hermes and other scheduler inventory.

Raw payloads remain immutable for audit. User-facing changes are based on normalized fields to avoid volatile timestamp/order false positives.

## Runtime verification

`handshake_tests` records exact route/harness tests with status, latency, observed features and sanitized errors. Runtime observation is strongest for actual compatibility, but it does not prove pricing or public release dates.

## Legacy compatibility

Legacy tables remain because earlier tools depend on them, including the historical `models` table and typo `catagory`. New work should use normalized v2 tables and views. `free_models.db` is a compatibility symlink to `aimi.db`.

## Authority order by field

| Fact | Best evidence |
|---|---|
| Current exact model ID/availability | Official endpoint plus successful handshake |
| Provider-supplied context, limits, capabilities, aliases and metadata | Full captured official endpoint payload, normalized into `provider_models_v2` and `provider_model_aliases` |
| API price/free state | Official pricing/models endpoint and pricing page |
| Release/announcement date | Dated official launch post, changelog or announcement |
| Context/output/capabilities | Official model documentation/endpoint, then runtime test |
| Open weights/license | Official repository/model card/license |
| Current Pi order | Live `~/.pi/agent/settings.json` |
| Durable preferred Pi order | `~/.pi/agent/AGENTS.md` and preferred profile |
| Harness compatibility | Local config observation plus successful handshake |
| Personal quality preference | `user_rankings`, never presented as objective benchmark truth |
