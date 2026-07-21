PRAGMA foreign_keys=OFF;
BEGIN;

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

ALTER TABLE evidence_claims ADD COLUMN evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id);
ALTER TABLE model_events ADD COLUMN evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id);

DROP VIEW IF EXISTS currently_free_provider_models;
ALTER TABLE access_offers RENAME TO access_offers_old;
CREATE TABLE access_offers (
  access_offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
  provider_model_id INTEGER NOT NULL REFERENCES provider_models_v2(provider_model_id),
  offer_type TEXT NOT NULL CHECK(offer_type IN ('genuine_zero_price','free_tier_quota','temporary_free_window','temporary_discount','promotional_credit','subscription_included','paid','unknown')),
  starts_at TEXT,
  ends_at TEXT,
  announced_at TEXT,
  first_observed_at TEXT,
  last_observed_at TEXT,
  input_price_per_million_usd TEXT,
  output_price_per_million_usd TEXT,
  cache_read_price_per_million_usd TEXT,
  cache_write_price_per_million_usd TEXT,
  request_price_usd TEXT,
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
INSERT INTO access_offers(access_offer_id,provider_model_id,offer_type,starts_at,ends_at,announced_at,input_price_per_million_usd,output_price_per_million_usd,cache_read_price_per_million_usd,cache_write_price_per_million_usd,request_price_usd,quota_json,rate_limits_json,requires_payment_method,requires_subscription,region_restrictions_json,terms_summary,evidence_source_id,confidence,last_verified_at)
SELECT access_offer_id,provider_model_id,offer_type,starts_at,ends_at,announced_at,input_price_per_million_usd,output_price_per_million_usd,cache_read_price_per_million_usd,cache_write_price_per_million_usd,request_price_usd,quota_json,rate_limits_json,requires_payment_method,requires_subscription,region_restrictions_json,terms_summary,evidence_source_id,confidence,last_verified_at FROM access_offers_old;
DROP TABLE access_offers_old;

CREATE VIEW currently_free_provider_models AS
SELECT pm.*,ao.offer_type,ao.starts_at,ao.ends_at,ao.first_observed_at,ao.last_observed_at,ao.quota_json,ao.rate_limits_json,ao.last_verified_at AS offer_verified_at
FROM provider_models_v2 pm
JOIN access_offers ao ON ao.provider_model_id=pm.provider_model_id
WHERE ao.offer_type IN ('genuine_zero_price','free_tier_quota','temporary_free_window')
  AND (ao.starts_at IS NULL OR datetime(ao.starts_at) <= datetime('now'))
  AND (ao.ends_at IS NULL OR datetime(ao.ends_at) > datetime('now'))
  AND pm.endpoint_status='available';

CREATE INDEX IF NOT EXISTS idx_evidence_captures_source ON evidence_captures(evidence_source_id,retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_offers_window ON access_offers(offer_type,starts_at,ends_at);
COMMIT;
PRAGMA foreign_keys=ON;
