"""Shared invariants for temporary free-window offers.

The model catalogue endpoint can keep a ``-free`` route listed after the
provider has withdrawn its free promotion.  These helpers keep the offer
history coherent without treating a transient probe failure as a withdrawal.
"""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3


ACTIVE_TEMPORARY_FREE_INDEX = "uq_active_temporary_free_window"
FREE_WINDOW_EVENT_INDEX = "idx_model_events_free_window_end"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_offer_indexes(connection: sqlite3.Connection) -> None:
    """Create indexes used by the free-window reconciliation path."""
    connection.execute(
        f"""CREATE UNIQUE INDEX IF NOT EXISTS {ACTIVE_TEMPORARY_FREE_INDEX}
        ON access_offers(provider_model_id, offer_type)
        WHERE offer_type='temporary_free_window' AND ends_at IS NULL"""
    )
    connection.execute(
        f"""CREATE INDEX IF NOT EXISTS {FREE_WINDOW_EVENT_INDEX}
        ON model_events(provider_model_id, event_type, event_time DESC)
        WHERE event_type='free_window_end'"""
    )


def reconcile_active_temporary_free_windows(
    connection: sqlite3.Connection,
    *,
    detected_at: str | None = None,
) -> int:
    """Collapse duplicate active temporary windows, retaining the oldest row.

    Older AIMI runs could create duplicate rows because SQLite treats NULLs as
    distinct inside the historical UNIQUE constraint.  Preserve those rows as
    closed historical observations, then enforce one active window per route.
    """
    detected_at = detected_at or utc_now()
    rows = connection.execute(
        """SELECT access_offer_id, provider_model_id, last_verified_at,
                  last_observed_at, first_observed_at
           FROM access_offers
           WHERE offer_type='temporary_free_window' AND ends_at IS NULL
           ORDER BY provider_model_id, access_offer_id"""
    ).fetchall()
    retained: set[int] = set()
    closed = 0
    for row in rows:
        provider_model_id = int(row[1])
        if provider_model_id not in retained:
            retained.add(provider_model_id)
            continue
        ends_at = row[2] or row[3] or row[4] or detected_at
        connection.execute(
            """UPDATE access_offers
               SET ends_at=?, last_observed_at=?
               WHERE access_offer_id=? AND ends_at IS NULL""",
            (ends_at, detected_at, row[0]),
        )
        closed += 1
    ensure_offer_indexes(connection)
    return closed


def has_free_window_end(
    connection: sqlite3.Connection,
    provider_model_id: int,
) -> bool:
    """Return whether an authoritative free-window closure exists for a route."""
    return connection.execute(
        """SELECT 1 FROM model_events
           WHERE provider_model_id=? AND event_type='free_window_end'
           LIMIT 1""",
        (provider_model_id,),
    ).fetchone() is not None
