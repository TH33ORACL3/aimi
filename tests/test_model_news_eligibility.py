from __future__ import annotations

import sqlite3
import unittest

from model_news_eligibility import filter_news_candidates


class ModelNewsEligibilityTests(unittest.TestCase):
    def test_bulk_group_is_suppressed_even_when_provider_is_an_origin(self) -> None:
        routes = [
            {
                "endpoint_change_id": 100 + position,
                "provider_id": "openai",
                "model_identifier": f"legacy/model-{position}",
                "monitoring_run_id": 7,
                "detected_at": "2026-08-26T12:15:46+00:00",
            }
            for position in range(5)
        ]

        eligible, suppressed = filter_news_candidates(routes)

        self.assertEqual(eligible, [])
        self.assertEqual(len(suppressed), 5)
        self.assertTrue(
            all(item["bulk_discovery"] for item in suppressed)
        )

    def test_bulk_aggregator_discovery_is_also_suppressed(self) -> None:
        routes = [
            {
                "endpoint_change_id": 200 + position,
                "provider_id": "openrouter",
                "model_identifier": f"bulk/model-{position}",
                "monitoring_run_id": 9,
                "detected_at": "2026-08-26T12:15:46+00:00",
            }
            for position in range(5)
        ]

        eligible, suppressed = filter_news_candidates(routes)

        self.assertEqual(eligible, [])
        self.assertEqual(
            {item["news_eligibility_reason"] for item in suppressed},
            {"bulk_endpoint_sync"},
        )

    def test_verified_official_release_on_same_local_day_overrides_bulk(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE endpoint_changes (
              endpoint_change_id INTEGER PRIMARY KEY,
              monitoring_run_id INTEGER,
              provider_id TEXT,
              model_identifier TEXT,
              change_type TEXT,
              detected_at TEXT
            );
            CREATE TABLE monitoring_runs (
              monitoring_run_id INTEGER PRIMARY KEY,
              added_count INTEGER
            );
            CREATE TABLE provider_models_v2 (
              provider_model_id INTEGER PRIMARY KEY,
              canonical_model_id INTEGER,
              provider_id TEXT,
              model_identifier TEXT,
              endpoint_first_seen_at TEXT,
              provider_created_at TEXT
            );
            CREATE TABLE model_events (
              model_event_id INTEGER PRIMARY KEY,
              canonical_model_id INTEGER,
              provider_model_id INTEGER,
              event_type TEXT,
              event_time TEXT,
              time_precision TEXT,
              confidence TEXT,
              evidence_source_id INTEGER
            );
            CREATE TABLE evidence_sources (
              evidence_source_id INTEGER PRIMARY KEY,
              official INTEGER,
              primary_source INTEGER
            );
            INSERT INTO monitoring_runs VALUES (7, 12);
            INSERT INTO endpoint_changes VALUES
              (1, 7, 'openai', 'new/model', 'model_added', '2026-08-26T12:15:46+00:00');
            INSERT INTO provider_models_v2 VALUES
              (11, 22, 'openai', 'new/model', '2026-08-26T12:15:46+00:00', '2026-08-26T12:00:00+00:00');
            INSERT INTO evidence_sources VALUES (31, 1, 1);
            INSERT INTO model_events VALUES
              (41, 22, NULL, 'general_release', '2026-08-26T09:00:00+00:00', 'hour', 'verified', 31);
            """
        )
        route = {
            "endpoint_change_id": 1,
            "provider_id": "openai",
            "model_identifier": "new/model",
            "detected_at": "2026-08-26T12:15:46+00:00",
        }

        eligible, suppressed = filter_news_candidates([route], connection=connection)

        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["discovery_group_size"], 12)
        self.assertEqual(
            eligible[0]["news_eligibility_reason"],
            "same_day_official_release",
        )
        self.assertEqual(suppressed, [])

        connection.execute("UPDATE model_events SET time_precision = 'unknown'")
        connection.commit()
        eligible, suppressed = filter_news_candidates([route], connection=connection)
        self.assertEqual(eligible, [])
        self.assertEqual(suppressed[0]["news_eligibility_reason"], "bulk_endpoint_sync")
        connection.close()

    def test_single_aggregator_addition_is_eligible(self) -> None:
        route = {
            "endpoint_change_id": 2,
            "provider_id": "openrouter",
            "model_identifier": "maker/new-model",
            "monitoring_run_id": 8,
            "detected_at": "2026-08-26T12:15:46+00:00",
        }

        eligible, suppressed = filter_news_candidates([route])

        self.assertEqual(suppressed, [])
        self.assertEqual(eligible[0]["news_eligibility_reason"], "aggregator_route_added")


if __name__ == "__main__":
    unittest.main()
