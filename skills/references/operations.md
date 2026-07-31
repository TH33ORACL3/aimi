# Command and SQL Cookbook

## Wrapper actions

The wrapper resolves the canonical project and keeps provider credentials out of command output.

| Command | Purpose |
|---|---|
| `catalogue summary` | Live database counts |
| `catalogue doctor` | Fast integrity/gap checks |
| `catalogue providers` | Known provider metadata and credential variable names |
| `catalogue subscriptions [--mine]` | Subscription products and Aubrey's active/reported entitlements |
| `catalogue subscription PRODUCT` | One subscription with entitlement, covered routes and limits |
| `catalogue model-info QUERY` | Canonical identities, every matching provider route, events and latest test |
| `catalogue maker-models MAKER` | Match model maker/family across all providers and harness routes |
| `catalogue warp-models [--custom]` | Live Warp/Oz registry, including exact custom UUIDs and saved tests |
| `catalogue free [--provider ID]` | Active, evidence-backed free routes |
| `catalogue latest-free --provider ID` | Free routes ordered by provider-created time then endpoint first-seen |
| `catalogue free-health-summary` | Count current OK/failure/untested free routes and retained daily rows |
| `catalogue free-health [--failures-only]` | Last-tested, last-OK, status, latency and bounded health details |
| `catalogue latest` | Verified canonical model events |
| `catalogue route PROVIDER MODEL` | Complete route, normalized capabilities, aliases, full sanitised endpoint metadata, offer details, and latest test outcome/result |
| `catalogue grok-config PROVIDER MODEL` | Generate a Grok CLI `config.toml` `[model.*]` block with thinking enabled; uses `harness_provider_support` to apply the correct `api_backend = "messages"` + `reasoning_effort` + `extra_headers` pattern. Requires `reasoning=1` in the provider route, or `--force` to override. |
| `catalogue where MODEL` | Fast all-provider lookup: every available provider route, normalized capabilities, aliases, full sanitised endpoint metadata, access offers, latest test outcome/result, cached harness matches, and freshness metadata |
| `catalogue where MODEL --refresh-harnesses` | Same lookup after refreshing local harness files; use only when current harness config is specifically required |
| `catalogue where MODEL --no-harnesses` | Provider routes/offers/freshness only |
| `catalogue recommend` | Task/free/provider-filtered candidates |
| `catalogue pi-order` | Exact live `enabledModels` order |
| `catalogue pi-register PROVIDER MODEL` | Preview/apply registration of a newly discovered route in Pi's model catalogue |
| `catalogue pi-select PROVIDER MODEL` | Preview/apply enabling, moving or default selection |
| `catalogue pi-add-latest-free` | Composite register-and-enable operation for the newest active free route |
| `catalogue order-diff pi` | Current database profile versus durable preferred profile |
| `catalogue harnesses` | Local installation inventory |
| `catalogue harness-models ID` | Live configured and harness-listed models, with `record_type` and source path |
| `catalogue harness-models ID --kind configured` | Live configured/selected models only |
| `catalogue harness-models ID --kind available` | Live models listed by the harness's own registry/cache only |
| `catalogue monitor` | Poll ten official endpoints, retain full sanitised per-model metadata, update normalized capabilities and aliases, and persist evidence-linked diffs |
| `catalogue monitor-status` | Target health |
| `catalogue changes` | Unreviewed endpoint changes by default |
| `catalogue scan` | Refresh safe local harness observations; never copies secret values |
| `catalogue ingest-subscriptions` | Apply evidence-backed subscription/provider ingestion |
| `catalogue record-warp-tests` | Persist completed Warp smoke results and interrupted-batch evidence |
| `catalogue validate` | Full catalogue audit |
| `catalogue export` | Sanitized public SQLite export |
| `catalogue cron-runs` | Hermes model-discovery and Telegram-notification run history |

Run `catalogue <command> --help` for arguments.

## Read-only database access

```bash
DB="$HOME/AZ Labs/2 - Testing/AIMI/aimi.db"
sqlite3 -readonly -json "$DB" '<SQL>' | jq '.'
```

Use `sqlite3 -readonly`. Do not make ad hoc writes. Add reusable operations to `aimi` or a versioned migration instead.

### Evidence claims for a subject

```sql
SELECT ec.subject_type, ec.subject_key, ec.field_name, ec.value_json,
       ec.confidence, ec.observed_at, ec.supporting_quote,
       es.url, es.source_type, es.publisher, es.official, es.primary_source
FROM evidence_claims ec
JOIN evidence_sources es USING(evidence_source_id)
WHERE ec.subject_key LIKE '%glm-5.2%'
ORDER BY ec.source_priority, datetime(ec.observed_at) DESC;
```

### Release events with primary proof

```sql
SELECT cm.canonical_name, me.event_type, me.event_time, me.time_precision,
       me.confidence, es.url, es.title, me.supporting_quote
FROM model_events me
LEFT JOIN canonical_models cm USING(canonical_model_id)
JOIN evidence_sources es USING(evidence_source_id)
WHERE cm.canonical_slug = 'glm-5.2'
ORDER BY datetime(me.event_time);
```

### All active offers for a route

```sql
SELECT pm.provider_id, pm.model_identifier, ao.offer_type, ao.starts_at,
       ao.ends_at, ao.input_price_per_million_usd,
       ao.output_price_per_million_usd, ao.quota_json, ao.rate_limits_json,
       ao.confidence, ao.last_verified_at, es.url
FROM access_offers ao
JOIN provider_models_v2 pm USING(provider_model_id)
JOIN evidence_sources es USING(evidence_source_id)
WHERE pm.provider_id = 'openrouter'
  AND pm.model_identifier = 'poolside/laguna-s-2.1:free'
ORDER BY datetime(ao.last_verified_at) DESC;
```

### Harness provider support

```sql
SELECT h.display_name, hps.provider_id, hps.support_type, hps.api_style,
       hps.config_location, hps.required_fields_json,
       hps.compatibility_notes, hps.last_verified_at
FROM harness_provider_support hps
JOIN harnesses h USING(harness_id)
WHERE hps.harness_id = 'pi'
ORDER BY hps.provider_id;
```

### Handshake history

```sql
SELECT pm.provider_id, pm.model_identifier, ht.harness_id, ht.tested_at,
       ht.test_type, ht.status, ht.latency_ms, ht.observed_features_json,
       ht.sanitized_error, ht.runner_version
FROM handshake_tests ht
JOIN provider_models_v2 pm USING(provider_model_id)
WHERE pm.model_identifier LIKE '%laguna%'
ORDER BY datetime(ht.tested_at) DESC;
```

### Monitoring changes including before/after

```sql
SELECT ec.endpoint_change_id, ec.provider_id, ec.change_type,
       ec.model_identifier, ec.before_json, ec.after_json,
       ec.detected_at, ec.reviewed, ec.review_notes
FROM endpoint_changes ec
ORDER BY datetime(ec.detected_at) DESC
LIMIT 50;
```

### Credential availability without secret values

```sql
SELECT provider_id, env_var_name, present, source_type, last_checked_at
FROM credential_inventory
ORDER BY provider_id, env_var_name;
```

### Subscription and Warp records

```sql
SELECT product_slug,vendor,display_name,tier_name,billing_model,confidence,last_verified_at
FROM subscription_products ORDER BY vendor,display_name;

SELECT sp.product_slug,pe.entitlement_status,pe.relationship_type,
       pe.organization_label,pe.confirmation_source,pe.confidence
FROM personal_subscription_entitlements pe
JOIN subscription_products sp USING(subscription_product_id)
ORDER BY sp.product_slug;

SELECT a.position,a.provider_name,a.model_identifier,a.display_name,
       a.metadata_json,t.tested_at,t.status,t.exact_output,t.sanitized_error
FROM harness_available_model_entries a
JOIN harness_installations i USING(installation_id)
LEFT JOIN latest_harness_model_tests t
  ON t.harness_id='obsidian-warp' AND t.model_identifier=a.model_identifier
WHERE i.harness_id='obsidian-warp'
ORDER BY a.position;
```

Only report variable names and presence.

## Safe write conventions

- Pi changes: use `pi-select`, `pi-add-latest-free`, or `pi-remove`.
- Database changes: use a transaction and versioned script.
- Evidence additions: store source, immutable capture, field claim and event separately.
- Endpoint-change review: set `reviewed=1` with a clear note only after inspection.
- Never delete conflicting evidence; supersede or annotate it.
- Never manually alter `free` classifications without official evidence.
