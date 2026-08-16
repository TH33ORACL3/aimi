-- Relax benchmark_scores to store arbitrary metrics, units and values.
-- SQLite cannot ALTER a CHECK constraint, so rebuild the table in place.
-- Preserves all existing rows (value_unit defaults to 'ratio').
PRAGMA foreign_keys=OFF;
BEGIN;

ALTER TABLE benchmark_scores RENAME TO benchmark_scores_old;

CREATE TABLE benchmark_scores (
  benchmark_score_id INTEGER PRIMARY KEY AUTOINCREMENT,
  canonical_model_id INTEGER NOT NULL REFERENCES canonical_models(canonical_model_id),
  provider_model_id INTEGER REFERENCES provider_models_v2(provider_model_id),
  benchmark TEXT NOT NULL DEFAULT 'deepswe',
  benchmark_version TEXT NOT NULL DEFAULT '1.1',
  metric TEXT NOT NULL,
  value REAL NOT NULL CHECK(value >= 0),
  value_unit TEXT NOT NULL DEFAULT 'ratio' CHECK(value_unit IN ('ratio','percent','elo','points','count')),
  config_text TEXT,
  reasoning_effort TEXT,
  agent_harness TEXT,
  is_best_config INTEGER NOT NULL DEFAULT 0 CHECK(is_best_config IN (0,1)),
  source_type TEXT NOT NULL CHECK(source_type IN ('leaderboard','vendor','third_party','official_maker','official_benchmark','provider_linked')),
  score_date TEXT,
  n_tasks INTEGER,
  n_attempted INTEGER,
  n_tasks_passed_any INTEGER,
  n_runs INTEGER,
  ci_lo REAL,
  ci_hi REAL,
  confidence TEXT NOT NULL DEFAULT 'single_source' CHECK(confidence IN ('verified','corroborated','single_source','unverified')),
  source_url TEXT,
  evidence_source_id INTEGER REFERENCES evidence_sources(evidence_source_id),
  evidence_capture_id INTEGER REFERENCES evidence_captures(evidence_capture_id),
  recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
  notes TEXT,
  UNIQUE(canonical_model_id, benchmark, benchmark_version, metric, value_unit, config_text, score_date, source_type)
);

INSERT INTO benchmark_scores (
  benchmark_score_id, canonical_model_id, provider_model_id, benchmark, benchmark_version,
  metric, value, value_unit, config_text, reasoning_effort, agent_harness, is_best_config,
  source_type, score_date, n_tasks, n_attempted, n_tasks_passed_any, n_runs, ci_lo, ci_hi,
  confidence, source_url, evidence_source_id, evidence_capture_id, recorded_at, notes
)
SELECT
  benchmark_score_id, canonical_model_id, provider_model_id, benchmark, benchmark_version,
  metric, value, 'ratio', config_text, reasoning_effort, agent_harness, is_best_config,
  source_type, score_date, n_tasks, n_attempted, n_tasks_passed_any, n_runs, ci_lo, ci_hi,
  confidence, source_url, evidence_source_id, evidence_capture_id, recorded_at, notes
FROM benchmark_scores_old;

DROP TABLE benchmark_scores_old;

CREATE INDEX IF NOT EXISTS idx_benchmark_scores_model
  ON benchmark_scores(canonical_model_id, benchmark, benchmark_version);
CREATE INDEX IF NOT EXISTS idx_benchmark_scores_best
  ON benchmark_scores(canonical_model_id, benchmark, benchmark_version, is_best_config);

COMMIT;
PRAGMA foreign_keys=ON;
