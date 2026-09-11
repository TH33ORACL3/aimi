"""Deterministic gate between endpoint observations and public model news.

An endpoint ``model_added`` row proves only that a provider returned a route
that AIMI had not seen before.  It does not prove that the model was released
that day.  This module keeps that distinction in one place for the fast
notifier and the slower editorial desk.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
import sqlite3
from typing import Any
from zoneinfo import ZoneInfo

BULK_DISCOVERY_THRESHOLD = 5

# These providers expose multi-vendor or gateway catalogues.  A single route
# addition from one of them can be useful news even when the model's maker
# released it earlier.  The allowlist is deliberate: provider names are not
# reliable evidence of an aggregator role.
AGGREGATOR_PROVIDERS = frozenset(
    {
        "cloudflare-ai",
        "cline",
        "kilo",
        "nvidia-nim",
        "ollama-cloud",
        "openrouter",
        "opencode-go",
        "opencode-zen",
    }
)

RELEASE_EVENT_TYPES = frozenset(
    {
        "announcement",
        "preview_release",
        "general_release",
        "api_availability",
        "weights_release",
    }
)
VERIFIED_CONFIDENCE = frozenset({"verified", "corroborated"})
RELEASE_TIME_PRECISIONS = frozenset({"second", "minute", "hour", "day"})

DEFAULT_LOCAL_TIMEZONE = ZoneInfo("Africa/Johannesburg")


def route_value(route: Mapping[str, Any] | sqlite3.Row, key: str, default: Any = None) -> Any:
    """Read a value from either a dict-like route or a sqlite row."""
    if isinstance(route, Mapping):
        return route.get(key, default)
    try:
        if key not in route.keys():
            return default
        return route[key]
    except (AttributeError, IndexError, KeyError):
        return default


def _as_dict(route: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    if isinstance(route, Mapping):
        return dict(route)
    try:
        return dict(route)
    except (TypeError, ValueError):
        return {key: route_value(route, key) for key in ("endpoint_change_id",)}


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def local_date_for(value: Any, local_timezone: ZoneInfo = DEFAULT_LOCAL_TIMEZONE) -> date | None:
    parsed = parse_timestamp(value)
    return parsed.astimezone(local_timezone).date() if parsed else None


def discovery_group_key(route: Mapping[str, Any] | sqlite3.Row) -> tuple[str, str, str]:
    """Group rows from one provider poll, with a safe fallback for fixtures."""
    provider = str(route_value(route, "provider_id", "unknown") or "unknown")
    run_id = str(route_value(route, "monitoring_run_id", "") or "")
    detected_date = local_date_for(route_value(route, "detected_at"))
    return provider, run_id, detected_date.isoformat() if detected_date else ""


def _group_size(
    route: Mapping[str, Any] | sqlite3.Row,
    counts: Counter[tuple[str, str, str]],
) -> int:
    # The monitoring run's count is authoritative when available.  Counting
    # the supplied rows is the backwards-compatible fallback for old queue
    # records and small unit-test fixtures.
    run_count = _as_int(route_value(route, "monitoring_run_added_count"))
    if run_count is not None and run_count > 0:
        return run_count
    return counts[discovery_group_key(route)]


def classify_routes(
    routes: Sequence[Mapping[str, Any] | sqlite3.Row],
    *,
    threshold: int = BULK_DISCOVERY_THRESHOLD,
) -> list[dict[str, Any]]:
    """Annotate routes with the public-news decision without database access."""
    items = [_as_dict(route) for route in routes]
    counts: Counter[tuple[str, str, str]] = Counter(
        discovery_group_key(route) for route in routes
    )
    safe_threshold = max(1, int(threshold))
    for item in items:
        group_size = _group_size(item, counts)
        provider = str(item.get("provider_id") or "unknown")
        same_day_release = _truthy(item.get("same_day_official_release"))
        bulk = group_size >= safe_threshold
        if same_day_release:
            eligible = True
            reason = "same_day_official_release"
        elif provider in AGGREGATOR_PROVIDERS and not bulk:
            eligible = True
            reason = "aggregator_route_added"
        elif bulk:
            eligible = False
            reason = "bulk_endpoint_sync"
        else:
            eligible = False
            reason = "endpoint_observation_without_release"
        item.update(
            {
                "news_eligible": eligible,
                "news_eligibility_reason": reason,
                "bulk_discovery": bulk,
                "discovery_group_size": group_size,
            }
        )
    return items


def _missing_table(exc: sqlite3.OperationalError) -> bool:
    text = str(exc).lower()
    return "no such table" in text or "no such column" in text


def _hydrate_endpoint_metadata(
    connection: sqlite3.Connection,
    items: list[dict[str, Any]],
) -> None:
    ids = sorted(
        {
            int(item["endpoint_change_id"])
            for item in items
            if _as_int(item.get("endpoint_change_id")) is not None
        }
    )
    if not ids:
        return
    placeholders = ",".join("?" for _ in ids)
    try:
        rows = connection.execute(
            f"""
            SELECT ec.endpoint_change_id, ec.monitoring_run_id,
                   mr.added_count AS monitoring_run_added_count,
                   pm.provider_model_id, pm.canonical_model_id,
                   pm.endpoint_first_seen_at, pm.provider_created_at
            FROM endpoint_changes ec
            LEFT JOIN monitoring_runs mr ON mr.monitoring_run_id = ec.monitoring_run_id
            LEFT JOIN provider_models_v2 pm
              ON pm.provider_id = ec.provider_id
             AND pm.model_identifier = ec.model_identifier
            WHERE ec.endpoint_change_id IN ({placeholders})
            """,
            ids,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # Keep pure-logic callers and older fixture databases useful.  The
        # production schema always has these tables and columns.
        if _missing_table(exc):
            return
        raise
    metadata = {int(row["endpoint_change_id"]): dict(row) for row in rows}
    for item in items:
        change_id = _as_int(item.get("endpoint_change_id"))
        if change_id not in metadata:
            continue
        for key, value in metadata[change_id].items():
            if value is not None:
                item[key] = value


def _release_event_keys(
    connection: sqlite3.Connection,
    items: list[dict[str, Any]],
) -> set[tuple[int | None, int | None, str, str]]:
    provider_model_ids = sorted(
        {
            int(item["provider_model_id"])
            for item in items
            if _as_int(item.get("provider_model_id")) is not None
        }
    )
    canonical_model_ids = sorted(
        {
            int(item["canonical_model_id"])
            for item in items
            if _as_int(item.get("canonical_model_id")) is not None
        }
    )
    if not provider_model_ids and not canonical_model_ids:
        return set()

    clauses: list[str] = []
    params: list[Any] = []
    if provider_model_ids:
        placeholders = ",".join("?" for _ in provider_model_ids)
        clauses.append(f"me.provider_model_id IN ({placeholders})")
        params.extend(provider_model_ids)
    if canonical_model_ids:
        placeholders = ",".join("?" for _ in canonical_model_ids)
        clauses.append(f"me.canonical_model_id IN ({placeholders})")
        params.extend(canonical_model_ids)
    event_types = sorted(RELEASE_EVENT_TYPES)
    confidence = sorted(VERIFIED_CONFIDENCE)
    event_placeholders = ",".join("?" for _ in event_types)
    confidence_placeholders = ",".join("?" for _ in confidence)
    params.extend(event_types)
    params.extend(confidence)
    try:
        rows = connection.execute(
            f"""
            SELECT me.provider_model_id, me.canonical_model_id,
                   me.event_time, me.time_precision
            FROM model_events me
            JOIN evidence_sources es ON es.evidence_source_id = me.evidence_source_id
            WHERE ({" OR ".join(clauses)})
              AND me.event_type IN ({event_placeholders})
              AND me.confidence IN ({confidence_placeholders})
              AND es.official = 1
              AND es.primary_source = 1
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _missing_table(exc):
            return set()
        raise
    return {
        (
            _as_int(row["provider_model_id"]),
            _as_int(row["canonical_model_id"]),
            str(row["event_time"]),
            str(row["time_precision"] or "unknown"),
        )
        for row in rows
    }


def annotate_routes(
    connection: sqlite3.Connection | None,
    routes: Sequence[Mapping[str, Any] | sqlite3.Row],
) -> list[dict[str, Any]]:
    """Hydrate route metadata and mark verified official same-day releases."""
    items = [_as_dict(route) for route in routes]
    if connection is None or not items:
        return items
    _hydrate_endpoint_metadata(connection, items)
    event_rows = _release_event_keys(connection, items)
    for item in items:
        if _truthy(item.get("same_day_official_release")):
            continue
        detected_date = local_date_for(item.get("detected_at"))
        provider_model_id = _as_int(item.get("provider_model_id"))
        canonical_model_id = _as_int(item.get("canonical_model_id"))
        item["same_day_official_release"] = any(
            (
                (provider_model_id is not None and provider_model_id == event_provider_id)
                or (
                    canonical_model_id is not None
                    and canonical_model_id == event_canonical_id
                )
            )
            and detected_date is not None
            and local_date_for(event_time) == detected_date
            for (
                event_provider_id,
                event_canonical_id,
                event_time,
                time_precision,
            ) in event_rows
            if time_precision in RELEASE_TIME_PRECISIONS
        )
    return items


def filter_news_candidates(
    routes: Sequence[Mapping[str, Any] | sqlite3.Row],
    *,
    connection: sqlite3.Connection | None = None,
    threshold: int = BULK_DISCOVERY_THRESHOLD,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(eligible, suppressed)`` route records for editorial work."""
    annotated = annotate_routes(connection, routes)
    classified = classify_routes(annotated, threshold=threshold)
    return (
        [item for item in classified if item["news_eligible"]],
        [item for item in classified if not item["news_eligible"]],
    )
