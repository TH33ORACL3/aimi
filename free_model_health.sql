PRAGMA foreign_keys=ON;
BEGIN;

-- Exactly one current row per route. This table does not grow per test run.
CREATE TABLE IF NOT EXISTS free_model_probe_status (
  provider_model_id INTEGER PRIMARY KEY REFERENCES provider_models_v2(provider_model_id) ON DELETE CASCADE,
  provider_id TEXT NOT NULL,
  model_identifier TEXT NOT NULL,
  currently_free INTEGER NOT NULL DEFAULT 1,
  last_tested_at TEXT NOT NULL,
  last_status TEXT NOT NULL CHECK(last_status IN ('ok','http_error','unauthorized','rate_limited','timeout','network_error','unexpected_response','configuration_error')),
  last_ok_at TEXT,
  last_failure_at TEXT,
  latency_ms INTEGER,
  http_status INTEGER,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  last_error_category TEXT,
  last_error_message TEXT,
  offer_type TEXT NOT NULL,
  offer_verified_at TEXT,
  runner_version TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(provider_id,model_identifier)
);

-- One compact aggregate per route per UTC day, retained for 30 days.
CREATE TABLE IF NOT EXISTS free_model_probe_daily (
  provider_model_id INTEGER NOT NULL REFERENCES provider_models_v2(provider_model_id) ON DELETE CASCADE,
  test_date TEXT NOT NULL,
  first_tested_at TEXT NOT NULL,
  last_tested_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  ok_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0,
  last_status TEXT NOT NULL,
  min_latency_ms INTEGER,
  max_latency_ms INTEGER,
  total_latency_ms INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(provider_model_id,test_date)
);

CREATE INDEX IF NOT EXISTS idx_free_probe_status_state ON free_model_probe_status(currently_free,last_status,last_tested_at);
CREATE INDEX IF NOT EXISTS idx_free_probe_daily_date ON free_model_probe_daily(test_date);

DROP VIEW IF EXISTS current_free_model_health;
CREATE VIEW current_free_model_health AS
SELECT f.provider_model_id,f.provider_id,f.model_identifier,f.display_name,f.offer_type,f.offer_verified_at,
       s.last_tested_at,s.last_status,
       CASE
         WHEN s.last_status='ok' THEN 'green'
         WHEN s.last_status='rate_limited' THEN 'orange'
         WHEN s.last_status IS NULL THEN 'untested'
         ELSE 'red'
       END AS status_colour,
       CASE
         WHEN s.last_status='ok' THEN 'ok'
         WHEN s.last_status='rate_limited' THEN 'rate_limited'
         WHEN s.last_status IS NULL THEN 'untested'
         ELSE 'failed'
       END AS health_state,
       s.last_ok_at,s.last_failure_at,s.latency_ms,
       s.http_status,s.consecutive_failures,s.last_error_category,s.last_error_message,
       CASE
         WHEN s.last_status='ok' THEN 'Returned exact OK'
         WHEN s.last_status='rate_limited' THEN 'Rate limited; availability inconclusive' || CASE WHEN s.http_status IS NOT NULL THEN ' (HTTP ' || s.http_status || ')' ELSE '' END
         WHEN s.last_error_message IS NOT NULL THEN s.last_error_message || CASE WHEN s.http_status IS NOT NULL THEN ' (HTTP ' || s.http_status || ')' ELSE '' END
         WHEN s.last_status IS NULL THEN 'Not yet tested'
         ELSE replace(s.last_status,'_',' ')
       END AS result_description
FROM currently_free_provider_models f
LEFT JOIN free_model_probe_status s USING(provider_model_id)
ORDER BY f.provider_id,f.model_identifier;

COMMIT;
