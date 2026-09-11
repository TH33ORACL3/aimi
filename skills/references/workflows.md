# Operational Workflows

Use `catalogue` below as shorthand for:

```bash
catalogue="$HOME/.agents/skills/ai-model-index/scripts/catalogue"
```

## Exact live Pi order

1. Query the live file, not the database:
   ```bash
   "$catalogue" pi-order
   ```
2. Present every entry as a numbered list in returned order.
3. Mark the default model where `is_default` is true.
4. If asked whether the durable profile matches, run:
   ```bash
   "$catalogue" scan
   "$catalogue" order-diff pi
   ```

## Fast provider lookup for a specific model

For questions such as “what providers is model X available from?” run exactly one read command:

```bash
"$catalogue" where '<model-fragment>'
```

The result contains:

- `provider_routes`: every non-removed provider route, exact model ID, endpoint, capabilities, offers and pricing/access semantics, plus the latest handshake under `last_test`;
- `harness_matches`: cached configured/available harness records, including source and last scan time;
- `freshness`: route-observation and monitor timestamps.

When presenting a route, always show `last_test.tested_at` together with `last_test.status` and `last_test.outcome` (or the recorded error). A timestamp alone is incomplete. Do not follow this with `monitor-status`, `route`, raw SQLite, or a harness scan. The command already includes the required freshness metadata. Add `--refresh-harnesses` only when the user specifically asks for the current local harness configuration; it is intentionally slower. Use `--no-harnesses` when only provider routes are needed.

If a live external check discovers a route absent from the result, treat it as a candidate and get Aubrey's approval before ingestion or authoritative database changes.

## Latest-free provider model to Pi

Example request: “Check the latest free model available from OpenRouter and add it to Pi.”

1. Confirm current date/time:
   ```bash
   date '+%Y-%m-%d %H:%M:%S %Z'
   ```
2. Check scheduled-monitor freshness without initiating an ingestion write:
   ```bash
   "$catalogue" monitor-status
   ```
   If the provider is stale or unhealthy, disclose that. A live external check may be used to discover a candidate, but ask Aubrey before ingesting it or replacing any database value.
3. Query currently verified database candidates:
   ```bash
   "$catalogue" latest-free --provider openrouter --limit 5
   ```
4. Interpret `provider_created_at` as the provider's model-list creation time, **not automatically the developer's release date**. If that field is absent, use and label `endpoint_first_seen_at`.
5. Confirm the selected route has an active verified free offer:
   ```bash
   "$catalogue" route openrouter '<exact-model-id>'
   ```
6. Check whether it is already enabled:
   ```bash
   "$catalogue" pi-order
   "$catalogue" where '<distinctive-model-fragment>'
   ```
7. Smoke-test the exact route with a tiny request. Keep the API key in an environment variable and capture only HTTP status, model ID, latency and sanitized output/error. Never echo headers or environment values.
8. Record the handshake:
   ```sql
   INSERT INTO handshake_tests(
     provider_model_id,harness_id,tested_at,test_type,status,latency_ms,
     observed_features_json,sanitized_error,runner_version
   ) VALUES(?, 'pi', datetime('now'), 'minimal_chat_completion', ?, ?, ?, ?, 'ai-model-index-skill/1.0');
   ```
9. If the user explicitly said “add,” register the newly discovered route and append it:
   ```bash
   "$catalogue" pi-register openrouter '<exact-model-id>' --apply
   "$catalogue" pi-select openrouter '<exact-model-id>' --apply
   ```
   Alternatively, after confirming the top candidate, the composite command performs both registration and selection:
   ```bash
   "$catalogue" pi-add-latest-free --provider openrouter --apply
   ```
10. Verify:
    ```bash
    "$catalogue" scan
    "$catalogue" pi-order
    "$catalogue" order-diff pi
    "$catalogue" validate
    ```
11. Report the exact model, position, backup, handshake result and whether adding it intentionally creates a difference from the previous durable order.

## Add a known model to Pi

1. Check `monitor-status`. If a live check finds a route absent from or different to the database, present the candidate evidence and get Aubrey's approval before ingestion.
2. Verify the exact provider/model route with `route` once it exists as an approved/verified route.
3. Generate and preview custom-provider registration when Pi does not yet know the route:
   ```bash
   "$catalogue" pi-fragment <provider> '<model-id>'
   "$catalogue" pi-register <provider> '<model-id>'
   ```
4. Apply registration when authorized. `pi-register` merges the model into the provider and preserves existing entries:
   ```bash
   "$catalogue" pi-register <provider> '<model-id>' --apply
   ```
5. Smoke-test.
6. Preview:
   ```bash
   "$catalogue" pi-select <provider> '<model-id>' --position <n>
   ```
7. Apply only when authorized, then scan and validate.

## Move or make a Pi model default

```bash
"$catalogue" pi-select <provider> '<model-id>' --position <n> --default
"$catalogue" pi-select <provider> '<model-id>' --position <n> --default --apply
```

`pi-select` removes an existing occurrence before inserting it, so it cannot create duplicates. It creates a timestamped backup and writes atomically.

## Remove a Pi model

1. Run `pi-order` and identify the exact entry.
2. If it is the current default, select a different default first.
3. Preview and apply:
   ```bash
   "$catalogue" pi-remove <provider> '<model-id>'
   "$catalogue" pi-remove <provider> '<model-id>' --apply
   ```
4. Scan and validate.

## Subscription and entitlement lookup

Use `catalogue subscriptions --mine` for Aubrey's current product/entitlement view and `catalogue subscription <slug>` for exact covered routes. Keep these distinctions visible:

1. Subscription access is not free API access.
2. A consumer subscription does not imply provider API credentials.
3. An organisation seat is not the same as a direct subscription.
4. Conflicting user-reported and official entitlement paths remain conflicting until resolved.
5. Harness-only coverage can use `harness_id` plus `harness_model_identifier` without inventing a provider route.

When a new chat changes a subscription, entitlement, route list, price, or model claim, present the current value and proposed value with source/date/confidence before ingestion. `ingest-subscriptions` is the approved versioned ingestion path after confirmation.

## Warp custom models and inference endpoints

Use this workflow whenever Aubrey asks what Warp can use or how to change a custom model:

1. Read the live Warp registry with `catalogue warp-models` or `oz model list --output-format json`.
2. Treat `https://docs.warp.dev/agent-platform/inference/model-choice/` as the official hosted-model registry.
3. Treat Warp Settings, searched by “inference endpoint”, as the authority for adding/changing BYOK or custom OpenAI-compatible endpoints. Do not infer a settings database table or invent a public endpoint.
4. Preserve UUID custom IDs exactly. Until Warp exposes labels/configuration, report display name and maker as unknown.
5. Label Warp-hosted, BYOK and custom endpoint access separately. A custom endpoint is not evidence of a Warp-hosted model or a subscription-included provider route.
6. Use the bounded smoke-test process only when requested. Run a single Hyperfine batch, preserve raw NDJSON and the JSON summary, and record only completed results. If interrupted, record the incomplete set rather than marking remaining routes failed or passed.

## OpenCode Go and Zen subscription lookup

Use this workflow whenever Aubrey asks for OpenCode Go or OpenCode Zen models.

1. Identify the requested product before querying anything:
   - Go: provider `opencode-go`, endpoint `https://opencode.ai/zen/go/v1`.
   - Zen: provider `opencode-zen`, endpoint `https://opencode.ai/zen/v1`.
2. Refresh/check endpoint telemetry with `catalogue monitor-status`, then inspect only the matching provider's live endpoint snapshot and route rows. Do not use `catalogue harness-models opencode` as a substitute for either subscription endpoint.
3. Report exact `provider/model-id` routes and mark each as:
   - `subscription_included` when access is through the relevant subscription;
   - `free` only when an independent verified free offer exists;
   - `unknown` when entitlement or pricing evidence is incomplete.
4. Keep Go and Zen model lists, access offers, endpoint timestamps, and health results separate. A model available through Go is not automatically available through Zen, and vice versa.
5. Never include subscription-only routes in `currently_free_provider_models` or the free-only health batch.

## Compare providers or routes

1. Use `route` for each exact provider/model pair.
2. Compare:
   - active offer type and evidence time;
   - input/output price;
   - context and output limits;
   - reasoning, tools, function calling, structured output and streaming;
   - modalities;
   - endpoint status and last-seen time;
   - local harness availability.
3. Unknown fields remain unknown. Do not score missing data as false.

## Release-date verification

1. Query `latest` and route details.
2. Inspect `model_events`, `evidence_claims`, `evidence_sources`, and `evidence_captures` using the read-only SQL in `operations.md`.
3. Prefer primary official evidence.
4. State the event type and time precision.
5. If the newly found information differs from the database, do not write it yet. Show:
   - current database value;
   - proposed value;
   - source URL/type and evidence date;
   - confidence and why the source may be stronger;
   - records that would be added, changed or superseded.
6. Ask Aubrey to choose:
   1. Add/update the verified database information.
   2. Keep the database unchanged.
   3. Store only an unverified candidate claim without changing the authoritative value.
7. If sources conflict, retain both claims and confidence levels only after the chosen approval. Do not silently choose one.
8. Do not use endpoint first-seen as a release date unless explicitly labelled as such.

## Free-window verification

A currently free route must satisfy:

- endpoint status is `available`;
- offer type is `genuine_zero_price`, `temporary_free_window`, or an officially evidenced `free_tier_quota`;
- start is null/past;
- end is null/future;
- evidence source exists;
- last verification is current enough for the question.

Unknown end dates must be reported as “duration unpublished,” not “free forever.”

## Harness inventory and configuration

1. Refresh local observations:
   ```bash
   "$catalogue" scan
   ```
2. Query installations and models. These commands perform a live local rescan first:
   ```bash
   "$catalogue" harnesses
   "$catalogue" harness-models <harness>
   "$catalogue" harness-models <harness> --kind configured
   "$catalogue" harness-models <harness> --kind available
   ```
   Results label each row `record_type=configured` or `record_type=available` and include the exact local `source_path`.
3. Use `harness_provider_support` and `harness_templates` to understand configuration format.
4. Keep provider facts separate from configured local limits. Local config is an observation and must not overwrite official endpoint metadata.
5. For Droid, its custom model configuration is `~/.factory/settings.json` under `customModels`.
6. For Aside, provider definitions are `~/.aside/u/0/models.json` and credentials are separate in `credentials.json`.
7. For OpenCode, inspect its current config through the scanner and documented adapter/template before writing.
8. For Codex CLI, read configured selection from `~/.codex/config.toml` and harness-listed availability from `~/.codex/models_cache.json`; do not replace this with the general OpenAI/provider catalogue.
9. For Mistral Vibe, read `~/.vibe/config.toml`; for Pi, read both `~/.pi/agent/settings.json` and `~/.pi/agent/models.json`; for other installed harnesses use the source path returned by `harnesses`.
10. If a harness has no local model list/config, report that explicitly rather than inferring availability from a provider catalogue.
11. Back up every config before writes and validate its JSON/TOML/YAML syntax.

## Monitoring and change review

```bash
"$catalogue" monitor-status
"$catalogue" changes --limit 50
"$catalogue" changes --provider openrouter --limit 50
"$catalogue" cron-runs
```

- The consolidated 15-minute Hermes job is `762bf502788c`, named `model-release-discovery-desk`.
- It polls the same 11 official model endpoints, including Cline's authenticated ClinePass catalogue, runs `monitor_endpoints.py`, promotes endpoint-only candidates with `ingest_endpoint_candidates.py`, and sends Telegram for newly observed `model_added` or `model_removed` routes.
- The shared model-news gate keeps endpoint observations separate from public news: five or more additions from one provider run are labelled bulk catalogue synchronisation and never enter the editorial queue; origin-provider additions need verified official same-day release evidence; non-bulk additions from the explicit aggregator/gateway allowlist remain route-availability candidates.
- It uses a durable multi-part pending outbox and `hermes send --json`; the endpoint watermark advances only after every part receives a successful delivery acknowledgement. Failed sends retain the next part for the next run, with the outer Hermes Telegram delivery retained as a fallback.
- It is silent when there are no new route or failure-transition notifications. Phone alerts use `🆕 ADDED`, `🗑️ REMOVED`, `⏰ FREE ACCESS ENDED`, and `🔄 RESYNC`; provider failures use explicit unavailable/recovered labels and alert only on transition/change, not every repeated poll.
- A first-run watermark suppresses historical changes; future changes are deduplicated in `~/.hermes/cron/model-catalogue-discovery-notifier.json`.
- Raw payload hashes are preserved, but alerts use normalized stable fields.
- Endpoint observations and endpoint-first-seen events may be written automatically. Do not infer official release dates, pricing, capabilities, or free access from an endpoint listing.
- The former endpoint monitor and the two scheduled free-health jobs are removed. `free_model_health.py` remains available for deliberate manual checks only.
- If the monitor fails, report the provider and missing credential name/error without showing credential values.

## Free-only model health

Use this for “test all free models,” “which free models work,” or “when did this free model last return OK?”

1. Targets must come only from the active `currently_free_provider_models` view. Never manually broaden the list.
2. Run the parallel batch through Hyperfine:
   ```bash
   hyperfine --runs 1 --warmup 0 --show-output \
     -n 'all-verified-free-models-parallel' \
     "zsh -lc 'source ~/.zshrc >/dev/null 2>&1; cd \"/Users/TH33_ORACL3/AZ Labs/2 - Testing/AIMI\"; python3 free_model_health.py --workers 4 --timeout 45 --retention-days 30'"
   ```
3. The prompt is always `Reply with exactly OK`. Classify the latest result as:
   - `green`: final visible content is exactly `OK`;
   - `orange`: rate-limited/HTTP 429, which is inconclusive and not a failure;
   - `red`: any other HTTP error, timeout, authorization error, unexpected response, or unusable result.
   Keep the detailed `last_status`, HTTP code, last-tested time and last-OK time alongside the colour.
4. Query current state:
   ```bash
   "$catalogue" free-health-summary
   "$catalogue" free-health
   "$catalogue" free-health --failures-only
   ```
5. Storage is bounded:
   - `free_model_probe_status`: one upserted current row per route;
   - `free_model_probe_daily`: one aggregate per route per UTC day;
   - daily history older than 30 days is deleted;
   - `last_ok_at` survives later failures.
6. No free-model health cron job is currently scheduled. Run the Hyperfine batch manually when a deliberate health check is requested. Do not fold free health probes into the 15-minute discovery job.
7. Do not insert each periodic health check into `handshake_tests`; that table is for deliberate compatibility tests, not recurring availability telemetry.

## Validation and sanitized export

```bash
"$catalogue" validate
"$catalogue" export
```

The public export must omit local installations, credentials, personal rankings, model order, account identifiers and local paths. Do not publish the private DB, endpoint snapshots, raw evidence directory or session transcript.

## Model-release desk → sellable product linkage (2026-08-13)

The release desk now ties each verified AI-model release to the AZ Labs product we sell. It only processes a route that passed the shared news-eligibility gate: verified official same-day release evidence or a non-bulk aggregator/gateway addition. This is the standing standard for a major-lab release (Google, OpenAI, Anthropic, xAI).

Flow: AIMI endpoint poll → `endpoint_changes` → news-eligibility gate → durable queue → `model_release_desk.py process` → Pi editorial worker.

Product linkage is resolved by `sellable_products_for()` in `model_release_desk.py`, which joins `subscription_model_access` → `subscription_products` via `provider_model_id` (provider + model identifier). It returns matching active products (slug, display name, vendor). The `work_input` carries each trigger item's `sellable_products` matches, and the `release_prompt` instructs Pi to lead the news article back to the matching sellable product.

When no catalogue linkage exists yet, `matches` is empty and Pi falls back to the generic editorial path.

What changed:
- `sellable_products_for()` added: provider/model → active sellable products.
- `process_pending` resolves `sellable_products` per trigger item and adds it to `work_input`.
- `release_prompt` documents `always_link_sellable_product` and instructs Pi to point readers at the sellable product.
- `model_discovery_notifier.py` unchanged: it enqueues candidates; the rescue desk resolves product linkage at process time so a provider allowlist is not needed in the polling wrapper.

Verify with:
```bash
cd "/Users/TH33_ORACL3/AZ Labs/2 - Testing/AIMI"
python3 model_release_desk.py process --dry-run   # preview work_input incl. sellable_products
python3 model_release_desk.py list
```
