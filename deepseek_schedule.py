"""DeepSeek API peak and off-peak schedule helpers."""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SOURCE_URL = "https://api-docs.deepseek.com/quick_start/pricing"
UTC = timezone.utc
PEAK_WINDOWS_UTC = (
    (time(1, 0), time(4, 0)),
    (time(6, 0), time(10, 0)),
)


def resolve_timezone(name: str | None = None) -> tzinfo:
    """Resolve an IANA timezone, AIMI_TIMEZONE, or the machine timezone."""
    requested = name or os.environ.get("AIMI_TIMEZONE")
    if requested:
        try:
            return ZoneInfo(requested)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown IANA timezone: {requested}") from exc

    local = datetime.now().astimezone().tzinfo
    key = getattr(local, "key", None)
    return ZoneInfo(key) if key else local or UTC


def _format_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _timezone_label(value: tzinfo, local: datetime) -> str:
    return getattr(value, "key", None) or local.tzname() or str(value)


def _timezone_abbreviation(local: datetime) -> str:
    return local.tzname() or str(local.tzinfo)


def _parse_instant(value: str | datetime | None, local_timezone: tzinfo) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "Invalid --at value; use an ISO-8601 datetime, for example "
                "2026-08-16T23:19:00Z"
            ) from exc
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(UTC)


def _period_at(instant_utc: datetime) -> str:
    current = instant_utc.timetz().replace(tzinfo=None)
    for start, end in PEAK_WINDOWS_UTC:
        if start <= current < end:
            return "peak"
    return "off_peak"


def _window_record(period: str, start: datetime, end: datetime) -> dict[str, str]:
    return {
        "period": period,
        "start": _format_time(start),
        "end": _format_time(end),
    }


def _local_windows(local_date: date, local_timezone: tzinfo) -> list[dict[str, str]]:
    """Return the DeepSeek periods that fall on one local calendar date."""
    local_start = datetime.combine(local_date, time.min, tzinfo=local_timezone)
    local_end = datetime.combine(
        local_date + timedelta(days=1),
        time.min,
        tzinfo=local_timezone,
    )
    utc_start = local_start.astimezone(UTC)
    utc_end = local_end.astimezone(UTC)
    windows: list[dict[str, str]] = []

    for day_offset in range(-2, 3):
        utc_date = local_date + timedelta(days=day_offset)
        segments = (
            ("off_peak", time.min, time(1, 0), utc_date),
            ("peak", time(1, 0), time(4, 0), utc_date),
            ("off_peak", time(4, 0), time(6, 0), utc_date),
            ("peak", time(6, 0), time(10, 0), utc_date),
            ("off_peak", time(10, 0), time.min, utc_date + timedelta(days=1)),
        )
        for period, start_time, end_time, end_date in segments:
            start = datetime.combine(utc_date, start_time, tzinfo=UTC)
            end = datetime.combine(end_date, end_time, tzinfo=UTC)
            if end <= utc_start or start >= utc_end:
                continue
            local_period_start = max(start, utc_start).astimezone(local_timezone)
            local_period_end = min(end, utc_end).astimezone(local_timezone)
            windows.append(_window_record(period, local_period_start, local_period_end))

    ordered = sorted(
        windows,
        key=lambda window: datetime.strptime(window["start"], "%I:%M %p").time(),
    )
    merged: list[dict[str, str]] = []
    for window in ordered:
        if (
            merged
            and merged[-1]["period"] == window["period"]
            and merged[-1]["end"] == window["start"]
        ):
            merged[-1]["end"] = window["end"]
        else:
            merged.append(window)
    return merged


def _next_transition(instant_utc: datetime, local_timezone: tzinfo) -> dict[str, str]:
    candidates: list[datetime] = []
    for day_offset in range(-1, 3):
        utc_date = instant_utc.date() + timedelta(days=day_offset)
        for start, end in PEAK_WINDOWS_UTC:
            candidates.extend(
                (
                    datetime.combine(utc_date, start, tzinfo=UTC),
                    datetime.combine(utc_date, end, tzinfo=UTC),
                )
            )
    next_boundary = min(candidate for candidate in candidates if candidate > instant_utc)
    return {
        "period_after_transition": _period_at(next_boundary + timedelta(microseconds=1)),
        "local_time": (
            f"{next_boundary.astimezone(local_timezone).strftime('%d %b %Y, ')}"
            f"{_format_time(next_boundary.astimezone(local_timezone))}"
        ),
    }


def status_at(
    value: str | datetime | None = None,
    timezone_name: str | None = None,
) -> dict[str, object]:
    """Return the current or supplied DeepSeek API pricing period."""
    local_timezone = resolve_timezone(timezone_name)
    instant_utc = _parse_instant(value, local_timezone)
    local = instant_utc.astimezone(local_timezone)
    period = _period_at(instant_utc)
    windows = _local_windows(local.date(), local_timezone)
    return {
        "service": "DeepSeek API",
        "model_scope": "DeepSeek API peak/off-peak pricing",
        "period": period,
        "period_label": "Peak" if period == "peak" else "Off-peak",
        "is_off_peak": period == "off_peak",
        "answer": (
            "Yes, you are currently in an off-peak period."
            if period == "off_peak"
            else "No, you are currently in a peak period."
        ),
        "timezone": _timezone_label(local_timezone, local),
        "local_time": (
            f"{local.strftime('%d %b %Y, ')}{_format_time(local)} "
            f"{_timezone_abbreviation(local)}"
        ),
        "utc_time": f"{instant_utc.strftime('%d %b %Y, ')}{_format_time(instant_utc)} UTC",
        "peak_windows_today": [
            window for window in windows if window["period"] == "peak"
        ],
        "off_peak_windows_today": [
            window for window in windows if window["period"] == "off_peak"
        ],
        "next_transition": _next_transition(instant_utc, local_timezone),
        "source_url": SOURCE_URL,
    }
