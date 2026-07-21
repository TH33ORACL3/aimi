PRAGMA foreign_keys=ON;
BEGIN;

CREATE TABLE IF NOT EXISTS canonical_models (
  canonical_model_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_slug TEXT NOT NULL UNIQUE,
  developer TEXT NOT NULL,
  family TEXT,
  canonical_name TEXT NOT NULL,
  base_model_slug TEXT,
  architecture TEXT,
  total_parameters INTEGER,
  active_parameters INTEGER,
  training_tokens INTEGER,
  weights_status TEXT NOT NULL DEFAULT 'unknown' CHECK(weights_status IN ('open','open_with_restrictions','closed','announced','unknown')),
  license_spdx TEXT,
  model_card_url TEXT,
  official_repository_url TEXT,
  lifecycle_status TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle_status IN ('announced','preview','active','deprecated','retired','withdrawn','unknown')),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS provider_models_v2 (
  provider_model_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT NOT NULL REFERENCES providers(provider_id),
  canonical_model_id INTEGER REFERENCES canonical_models(canonical_model_id),
  model_identifier TEXT NOT NULL,
  display_name TEXT,
  provider_alias_of INTEGER REFERENCES provider_models_v2(provider_model_id),
  endpoint_status TEXT NOT NULL DEFAULT 'available' CHECK(endpoint_status IN ('available','unavailable','deprecated','removed','unknown')),
  endpoint_first_seen_at TEXT NOT NULL,
  endpoint_last_seen_at TEXT NOT NULL,
  endpoint_removed_at TEXT,
  context_window_tokens INTEGER,
  max_input_tokens INTEGER,
  max_output_tokens INTEGER,
  reasoning INTEGER,
  tools INTEGER,
  function_calling INTEGER,
  structured_outputs INTEGER,
  streaming INTEGER,
  input_modalities_json TEXT,
  output_modalities_json TEXT,
  tokenizer TEXT,
  quantization TEXT,
  provider_metadata_json TEXT,
  source_snapshot_id INTEGER REFERENCES model_sources(source_id),
  UNIQUE(provider_id, model_identifier)
);

CREATE TABLE IF NOT EXISTS evidence_sources (
  evidence_source_id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL UNIQUE,
  source_type TEXT NOT NULL CHECK(source_type IN ('api_endpoint','official_docs','official_blog','official_changelog','official_x','official_github','official_model_card','technical_report','paper','pricing_page','terms','third_party','local_config','local_observation','other')),
  publisher TEXT,
  title TEXT,
  author TEXT,
  official INTEGER NOT NULL DEFAULT 0,
  primary_source INTEGER NOT NULL DEFAULT 0,
  publication_time TEXT,
  retrieved_at TEXT NOT NULL,
  content_sha256 TEXT,
  archived_path TEXT,
  http_status INTEGER,
  trust_priority INTEGER NOT NULL DEFAULT 50,
  verification_status TEXT NOT NULL DEFAULT 'captured' CHECK(verification_status IN ('captured','verified','failed','superseded','unavailable')),
  notes TEXT
);

CREATE TABLE IF NOT EXISTS evidence_captures (
  evidence_capture_id INTEGER PRIMARY KEY AUTOINCREMENT,
  evidence_source_id INTEGER NOT NULL REFERENCES evidence_sources(evidence_source_id),
  retrieved_at TEXT NOT NULL,
  publication_time_observed TEXT,
  content_sha256 TEXT NOT NULL,
  archived_path TEXT,
  http_status INTEGER,
  extraction_method TEXT NOT NULL,
  extractor_version TEXT,
  immutable INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  UNIQUE(evidence_source_id,content_sha256)
);

CREATE TABLE IF NOT EXISTS evidence_claims (
  claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_type TEXT NOT NULL CHECK(subject_type IN ('canonical_model','provider_model','provider','harness','access_offer','monitoring_target','other')),
  subject_key TEXT NOT NULL,
  field_name TEXT NOT NULL,
  value_json TEXT NOT NULL,
  value_type TEXT NOT NULL DEFAULT 'json',
  evidence_source_id INTEGER NOT NULL REFERENCES evidence_sources(evidence_source_id),
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  supporting_quote TEXT,
  observed_at TEXT NOT NULL,
  valid_from TEXT,
  valid_until TEXT,
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','corroborated','single_source','inferred','unverified','conflicting')),
  verification_method TEXT NOT NULL,
  source_priority INTEGER NOT NULL DEFAULT 50,
  supersedes_claim_id INTEGER REFERENCES evidence_claims(claim_id),
  notes TEXT,
  UNIQUE(subject_type,subject_key,field_name,evidence_source_id,value_json)
);

CREATE TABLE IF NOT EXISTS model_events (
  model_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_model_id INTEGER REFERENCES canonical_models(canonical_model_id),
  provider_model_id INTEGER REFERENCES provider_models_v2(provider_model_id),
  event_type TEXT NOT NULL CHECK(event_type IN ('announcement','preview_release','general_release','api_availability','model_card_publication','weights_release','endpoint_first_seen','endpoint_removed','pricing_change','free_window_start','free_window_end','deprecation_announced','deprecated','retired','renamed','capability_change','context_change','other')),
  event_time TEXT NOT NULL,
  time_precision TEXT NOT NULL DEFAULT 'day' CHECK(time_precision IN ('second','minute','hour','day','month','year','unknown')),
  evidence_source_id INTEGER NOT NULL REFERENCES evidence_sources(evidence_source_id),
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  supporting_quote TEXT,
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','corroborated','single_source','inferred','unverified','conflicting')),
  details_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK(canonical_model_id IS NOT NULL OR provider_model_id IS NOT NULL),
  UNIQUE(canonical_model_id,provider_model_id,event_type,event_time,evidence_source_id)
);

CREATE TABLE IF NOT EXISTS access_offers (
  access_offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_model_id INTEGER NOT NULL REFERENCES provider_models_v2(provider_model_id),
  offer_type TEXT NOT NULL CHECK(offer_type IN ('genuine_zero_price','free_tier_quota','temporary_free_window','promotional_credit','subscription_included','paid','unknown')),
  starts_at TEXT,
  ends_at TEXT,
  announced_at TEXT,
  input_price_per_million_usd TEXT,
  output_price_per_million_usd TEXT,
  cache_read_price_per_million_usd TEXT,
  cache_write_price_per_million_usd TEXT,
  request_price_usd TEXT,
  first_observed_at TEXT,
  last_observed_at TEXT,
  discount_percent TEXT,
  quota_json TEXT,
  rate_limits_json TEXT,
  requires_payment_method INTEGER,
  requires_subscription INTEGER,
  region_restrictions_json TEXT,
  terms_summary TEXT,
  evidence_source_id INTEGER NOT NULL REFERENCES evidence_sources(evidence_source_id),
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','corroborated','single_source','inferred','unverified','conflicting')),
  last_verified_at TEXT NOT NULL,
  UNIQUE(provider_model_id,offer_type,starts_at,evidence_source_id)
);

CREATE TABLE IF NOT EXISTS harnesses (
  harness_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  vendor TEXT,
  category TEXT NOT NULL,
  homepage_url TEXT,
  config_format TEXT,
  custom_provider_support INTEGER,
  model_order_semantics TEXT,
  source_note_path TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS harness_installations (
  installation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  harness_id TEXT NOT NULL REFERENCES harnesses(harness_id),
  machine_id TEXT NOT NULL,
  installed INTEGER NOT NULL,
  version TEXT,
  executable_path TEXT,
  config_path TEXT,
  installation_method TEXT,
  status TEXT,
  first_used_at TEXT,
  last_scanned_at TEXT NOT NULL,
  local_metadata_json TEXT,
  UNIQUE(harness_id,machine_id)
);

CREATE TABLE IF NOT EXISTS harness_provider_support (
  harness_id TEXT NOT NULL REFERENCES harnesses(harness_id),
  provider_id TEXT NOT NULL REFERENCES providers(provider_id),
  support_type TEXT NOT NULL CHECK(support_type IN ('built_in','custom_openai_compatible','native_custom','proxy_only','extension','unsupported','unknown')),
  api_style TEXT,
  config_location TEXT,
  config_schema_json TEXT,
  required_fields_json TEXT,
  compatibility_notes TEXT,
  evidence_source_id INTEGER REFERENCES evidence_sources(evidence_source_id),
  last_verified_at TEXT,
  PRIMARY KEY(harness_id,provider_id)
);

CREATE TABLE IF NOT EXISTS harness_model_entries (
  harness_model_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  installation_id INTEGER NOT NULL REFERENCES harness_installations(installation_id),
  provider_id TEXT,
  provider_model_id INTEGER REFERENCES provider_models_v2(provider_model_id),
  configured_provider_name TEXT,
  configured_model_identifier TEXT NOT NULL,
  display_name TEXT,
  position INTEGER,
  enabled INTEGER NOT NULL DEFAULT 1,
  is_default INTEGER NOT NULL DEFAULT 0,
  reasoning_level TEXT,
  config_source_path TEXT,
  first_observed_at TEXT NOT NULL,
  last_observed_at TEXT NOT NULL,
  config_metadata_json TEXT,
  UNIQUE(installation_id,configured_provider_name,configured_model_identifier)
);

CREATE TABLE IF NOT EXISTS harness_available_model_entries (
  harness_available_model_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  installation_id INTEGER NOT NULL REFERENCES harness_installations(installation_id) ON DELETE CASCADE,
  provider_name TEXT,
  model_identifier TEXT NOT NULL,
  display_name TEXT,
  position INTEGER,
  source_path TEXT NOT NULL,
  first_observed_at TEXT NOT NULL,
  last_observed_at TEXT NOT NULL,
  metadata_json TEXT,
  UNIQUE(installation_id,provider_name,model_identifier,source_path)
);

CREATE TABLE IF NOT EXISTS user_rankings (
  ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_type TEXT NOT NULL CHECK(subject_type IN ('harness','canonical_model','provider_model','provider')),
  subject_key TEXT NOT NULL,
  ranking_system TEXT NOT NULL,
  rank_value REAL,
  stars REAL,
  tier TEXT,
  use_case TEXT,
  source TEXT NOT NULL,
  valid_from TEXT,
  valid_until TEXT,
  recorded_at TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS model_order_profiles (
  profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
  harness_id TEXT NOT NULL REFERENCES harnesses(harness_id),
  profile_name TEXT NOT NULL,
  description TEXT,
  optimization_goal TEXT NOT NULL,
  max_cycle_distance INTEGER,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(harness_id,profile_name)
);

CREATE TABLE IF NOT EXISTS model_order_profile_entries (
  profile_id INTEGER NOT NULL REFERENCES model_order_profiles(profile_id) ON DELETE CASCADE,
  provider_model_id INTEGER REFERENCES provider_models_v2(provider_model_id),
  provider_id TEXT,
  model_identifier TEXT NOT NULL,
  position INTEGER NOT NULL,
  role TEXT,
  task_tags_json TEXT,
  fallback_group TEXT,
  pinned INTEGER NOT NULL DEFAULT 0,
  rationale TEXT,
  PRIMARY KEY(profile_id,position),
  UNIQUE(profile_id,provider_id,model_identifier)
);

CREATE TABLE IF NOT EXISTS credential_inventory (
  provider_id TEXT NOT NULL REFERENCES providers(provider_id),
  machine_id TEXT NOT NULL,
  env_var_name TEXT NOT NULL,
  present INTEGER NOT NULL,
  source_type TEXT NOT NULL CHECK(source_type IN ('environment','keychain','config_reference','oauth','unknown')),
  last_checked_at TEXT NOT NULL,
  notes TEXT,
  PRIMARY KEY(provider_id,machine_id,env_var_name)
);

CREATE TABLE IF NOT EXISTS monitoring_targets (
  monitoring_target_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_id TEXT REFERENCES providers(provider_id),
  target_type TEXT NOT NULL CHECK(target_type IN ('models_endpoint','pricing_endpoint','docs','changelog','rss','official_x','github_releases','huggingface_org','status_page','other')),
  url TEXT NOT NULL,
  schedule_class TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  expected_format TEXT,
  parser_name TEXT,
  etag TEXT,
  last_modified TEXT,
  last_checked_at TEXT,
  last_changed_at TEXT,
  last_success_at TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  UNIQUE(target_type,url)
);

CREATE TABLE IF NOT EXISTS monitoring_runs (
  monitoring_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitoring_target_id INTEGER NOT NULL REFERENCES monitoring_targets(monitoring_target_id),
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running','success','unchanged','changed','failed','rate_limited')),
  http_status INTEGER,
  response_sha256 TEXT,
  snapshot_path TEXT,
  added_count INTEGER DEFAULT 0,
  removed_count INTEGER DEFAULT 0,
  changed_count INTEGER DEFAULT 0,
  error_summary TEXT
);

CREATE TABLE IF NOT EXISTS endpoint_changes (
  endpoint_change_id INTEGER PRIMARY KEY AUTOINCREMENT,
  monitoring_run_id INTEGER NOT NULL REFERENCES monitoring_runs(monitoring_run_id),
  provider_id TEXT REFERENCES providers(provider_id),
  change_type TEXT NOT NULL CHECK(change_type IN ('model_added','model_removed','model_changed','pricing_changed','capability_changed','alias_changed','other')),
  model_identifier TEXT,
  before_json TEXT,
  after_json TEXT,
  detected_at TEXT NOT NULL,
  reviewed INTEGER NOT NULL DEFAULT 0,
  review_notes TEXT
);

CREATE TABLE IF NOT EXISTS handshake_tests (
  handshake_test_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_model_id INTEGER NOT NULL REFERENCES provider_models_v2(provider_model_id),
  harness_id TEXT REFERENCES harnesses(harness_id),
  tested_at TEXT NOT NULL,
  test_type TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('passed','failed','skipped','rate_limited','unauthorized','timeout')),
  latency_ms INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  observed_features_json TEXT,
  sanitized_error TEXT,
  runner_version TEXT
);

CREATE TABLE IF NOT EXISTS subscription_products (
  subscription_product_id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_slug TEXT NOT NULL UNIQUE,
  vendor TEXT NOT NULL,
  display_name TEXT NOT NULL,
  tier_name TEXT,
  product_type TEXT NOT NULL CHECK(product_type IN ('consumer','individual','team','business','enterprise','gateway','cloud','developer','other')),
  billing_model TEXT NOT NULL CHECK(billing_model IN ('subscription','subscription_with_credits','pay_as_you_go','free','credit_quota','custom_contract','unknown')),
  monthly_price TEXT,
  annual_price TEXT,
  currency TEXT,
  official_product_url TEXT,
  official_pricing_url TEXT,
  official_models_url TEXT,
  region_restrictions_json TEXT,
  product_status TEXT NOT NULL DEFAULT 'active' CHECK(product_status IN ('active','preview','paused','coming_soon','deprecated','retired','unknown')),
  evidence_source_id INTEGER REFERENCES evidence_sources(evidence_source_id),
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','corroborated','single_source','inferred','unverified','conflicting','user_confirmed')),
  last_verified_at TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS personal_subscription_entitlements (
  personal_entitlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subscription_product_id INTEGER NOT NULL REFERENCES subscription_products(subscription_product_id),
  owner_label TEXT NOT NULL DEFAULT 'Aubrey Zemba',
  entitlement_status TEXT NOT NULL CHECK(entitlement_status IN ('active','inactive','expired','trial','reported','conflicting','unknown')),
  account_label TEXT,
  organization_label TEXT,
  relationship_type TEXT CHECK(relationship_type IN ('direct_subscription','organization_seat','bundled','trial','reported_access','unknown')),
  started_at TEXT,
  ends_at TEXT,
  confirmed_at TEXT NOT NULL,
  confirmation_source TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','corroborated','single_source','inferred','unverified','conflicting','user_confirmed')),
  notes TEXT,
  UNIQUE(subscription_product_id,owner_label,account_label,organization_label)
);

CREATE TABLE IF NOT EXISTS subscription_model_access (
  subscription_model_access_id INTEGER PRIMARY KEY AUTOINCREMENT,
  subscription_product_id INTEGER NOT NULL REFERENCES subscription_products(subscription_product_id),
  provider_model_id INTEGER REFERENCES provider_models_v2(provider_model_id),
  harness_id TEXT REFERENCES harnesses(harness_id),
  harness_model_identifier TEXT,
  access_type TEXT NOT NULL CHECK(access_type IN ('subscription_included','subscription_credits','pay_as_you_go','free_quota','byok','custom_endpoint','unknown')),
  client_restrictions_json TEXT,
  quota_json TEXT,
  starts_at TEXT,
  ends_at TEXT,
  evidence_source_id INTEGER REFERENCES evidence_sources(evidence_source_id),
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','corroborated','single_source','inferred','unverified','conflicting','user_confirmed')),
  last_verified_at TEXT,
  notes TEXT,
  CHECK(provider_model_id IS NOT NULL OR (harness_id IS NOT NULL AND harness_model_identifier IS NOT NULL)),
  UNIQUE(subscription_product_id,provider_model_id,harness_id,harness_model_identifier,access_type)
);

CREATE TABLE IF NOT EXISTS harness_model_tests (
  harness_model_test_id INTEGER PRIMARY KEY AUTOINCREMENT,
  harness_id TEXT NOT NULL REFERENCES harnesses(harness_id),
  model_identifier TEXT NOT NULL,
  tested_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('passed','failed','skipped','rate_limited','unauthorized','timeout')),
  latency_ms INTEGER,
  exact_output TEXT,
  sanitized_error TEXT,
  runner_version TEXT,
  test_command_template TEXT
);

CREATE VIEW IF NOT EXISTS current_personal_subscriptions AS
SELECT sp.*,pe.personal_entitlement_id,pe.owner_label,pe.entitlement_status,pe.account_label,
       pe.organization_label,pe.relationship_type,pe.confirmed_at,pe.confirmation_source,
       pe.confidence AS entitlement_confidence,pe.notes AS entitlement_notes
FROM personal_subscription_entitlements pe JOIN subscription_products sp USING(subscription_product_id)
WHERE pe.entitlement_status IN ('active','trial','reported','conflicting');

CREATE VIEW IF NOT EXISTS latest_harness_model_tests AS
SELECT t.* FROM harness_model_tests t
WHERE t.harness_model_test_id=(SELECT t2.harness_model_test_id FROM harness_model_tests t2
 WHERE t2.harness_id=t.harness_id AND t2.model_identifier=t.model_identifier
 ORDER BY datetime(t2.tested_at) DESC,t2.harness_model_test_id DESC LIMIT 1);

-- Migrate the legacy provider-specific rows without pretending they are canonical identities.
INSERT OR IGNORE INTO provider_models_v2(
  provider_id,model_identifier,display_name,endpoint_status,endpoint_first_seen_at,endpoint_last_seen_at,
  context_window_tokens,max_output_tokens,reasoning,tools,structured_outputs,streaming,
  input_modalities_json,output_modalities_json,provider_metadata_json
)
SELECT provider,model_id,display_name,'available',discovered_at,last_verified_at,context_window,max_output_tokens,
       supports_reasoning,supports_tools,supports_structured_output,supports_streaming,
       CASE WHEN input_modalities IS NULL THEN NULL ELSE json_quote(input_modalities) END,
       CASE WHEN output_modalities IS NULL THEN NULL ELSE json_quote(output_modalities) END,
       json_object('legacy_model_row_id',id,'legacy_pricing_status',pricing_status)
FROM models
WHERE provider IN (SELECT provider_id FROM providers);

CREATE INDEX IF NOT EXISTS idx_evidence_captures_source ON evidence_captures(evidence_source_id,retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_provider_models_v2_provider ON provider_models_v2(provider_id);
CREATE INDEX IF NOT EXISTS idx_provider_models_v2_canonical ON provider_models_v2(canonical_model_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON model_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON model_events(event_type);
CREATE INDEX IF NOT EXISTS idx_claim_subject ON evidence_claims(subject_type,subject_key,field_name);
CREATE INDEX IF NOT EXISTS idx_claim_source ON evidence_claims(evidence_source_id);
CREATE INDEX IF NOT EXISTS idx_offers_active ON access_offers(offer_type,starts_at,ends_at);
CREATE INDEX IF NOT EXISTS idx_harness_entries_order ON harness_model_entries(installation_id,position);
CREATE INDEX IF NOT EXISTS idx_harness_available_order ON harness_available_model_entries(installation_id,position);
CREATE INDEX IF NOT EXISTS idx_monitoring_runs_target ON monitoring_runs(monitoring_target_id,started_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_provider_access
  ON subscription_model_access(subscription_product_id,provider_model_id,access_type)
  WHERE provider_model_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_harness_access
  ON subscription_model_access(subscription_product_id,harness_id,harness_model_identifier,access_type)
  WHERE provider_model_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_subscription_products_vendor ON subscription_products(vendor,display_name);
CREATE INDEX IF NOT EXISTS idx_personal_entitlements_status ON personal_subscription_entitlements(entitlement_status);
CREATE INDEX IF NOT EXISTS idx_subscription_model_access_product ON subscription_model_access(subscription_product_id);
CREATE INDEX IF NOT EXISTS idx_harness_model_tests_latest ON harness_model_tests(harness_id,model_identifier,tested_at DESC);

CREATE VIEW IF NOT EXISTS currently_free_provider_models AS
SELECT pm.*,ao.offer_type,ao.starts_at,ao.ends_at,ao.quota_json,ao.rate_limits_json,ao.last_verified_at AS offer_verified_at
FROM provider_models_v2 pm
JOIN access_offers ao ON ao.provider_model_id=pm.provider_model_id
WHERE ao.offer_type IN ('genuine_zero_price','temporary_free_window','free_tier_quota')
  AND (ao.starts_at IS NULL OR datetime(ao.starts_at) <= datetime('now'))
  AND (ao.ends_at IS NULL OR datetime(ao.ends_at) > datetime('now'))
  AND pm.endpoint_status='available';

CREATE VIEW IF NOT EXISTS latest_verified_model_events AS
SELECT me.*,cm.canonical_slug,cm.canonical_name,pm.provider_id,pm.model_identifier,es.url AS evidence_url,es.title AS evidence_title
FROM model_events me
LEFT JOIN canonical_models cm ON cm.canonical_model_id=me.canonical_model_id
LEFT JOIN provider_models_v2 pm ON pm.provider_model_id=me.provider_model_id
JOIN evidence_sources es ON es.evidence_source_id=me.evidence_source_id
WHERE me.confidence IN ('verified','corroborated')
ORDER BY datetime(me.event_time) DESC;

COMMIT;
