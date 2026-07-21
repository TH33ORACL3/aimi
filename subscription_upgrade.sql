PRAGMA foreign_keys=ON;
BEGIN;

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

DELETE FROM subscription_model_access
WHERE provider_model_id IS NOT NULL
  AND rowid NOT IN (SELECT MIN(rowid) FROM subscription_model_access WHERE provider_model_id IS NOT NULL GROUP BY subscription_product_id,provider_model_id,access_type);
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

DROP VIEW IF EXISTS currently_free_provider_models;
CREATE VIEW currently_free_provider_models AS
SELECT pm.*,ao.offer_type,ao.starts_at,ao.ends_at,ao.first_observed_at,ao.last_observed_at,ao.quota_json,ao.rate_limits_json,ao.last_verified_at AS offer_verified_at
FROM provider_models_v2 pm JOIN access_offers ao ON ao.provider_model_id=pm.provider_model_id
WHERE ao.offer_type IN ('genuine_zero_price','free_tier_quota','temporary_free_window')
  AND (ao.starts_at IS NULL OR datetime(ao.starts_at)<=datetime('now'))
  AND (ao.ends_at IS NULL OR datetime(ao.ends_at)>datetime('now'))
  AND pm.endpoint_status='available';

CREATE VIEW IF NOT EXISTS current_personal_subscriptions AS
SELECT sp.*,pe.personal_entitlement_id,pe.owner_label,pe.entitlement_status,pe.account_label,
       pe.organization_label,pe.relationship_type,pe.confirmed_at,pe.confirmation_source,
       pe.confidence AS entitlement_confidence,pe.notes AS entitlement_notes
FROM personal_subscription_entitlements pe
JOIN subscription_products sp USING(subscription_product_id)
WHERE pe.entitlement_status IN ('active','trial','reported','conflicting');

CREATE VIEW IF NOT EXISTS latest_harness_model_tests AS
SELECT t.* FROM harness_model_tests t
WHERE t.harness_model_test_id=(
  SELECT t2.harness_model_test_id FROM harness_model_tests t2
  WHERE t2.harness_id=t.harness_id AND t2.model_identifier=t.model_identifier
  ORDER BY datetime(t2.tested_at) DESC,t2.harness_model_test_id DESC LIMIT 1
);

COMMIT;
