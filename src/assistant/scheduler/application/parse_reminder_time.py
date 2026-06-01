"""Lightweight natural-language time parser for reminder expressions.

Supported formats (explicitly bounded — anything else raises ValueError):
- ``"in 30 minutes"`` → now + 30 min
- ``"in 2 hours"`` → now + 2 h
- ``"tomorrow at 9am"`` → tomorrow 09:00
- ``"next Monday at 8am"`` → next Monday 08:00
- ``"at 15:30 today"`` → today 15:30
- ``"every day at 9am"`` → cron ``"0 9 * * *"``
- ``"every weekday at 8am"`` → cron ``"0 8 * * 1-5"``
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

# Pre-compiled regex patterns for supported expressions
_IN_MINUTES_RE = re.compile(r"^in\s+(\d+)\s+minutes?$", re.IGNORECASE)
_IN_HOURS_RE = re.compile(r"^in\s+(\d+)\s+hours?$", re.IGNORECASE)
_TOMORROW_AT_RE = re.compile(r"^tomorrow\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$", re.IGNORECASE)
_NEXT_DAY_AT_RE = re.compile(
    r"^next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$",
    re.IGNORECASE,
)
_AT_TODAY_RE = re.compile(r"^at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?\s+today$", re.IGNORECASE)
_EVERY_DAY_AT_RE = re.compile(r"^every\s+day\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$", re.IGNORECASE)
_EVERY_WEEKDAY_AT_RE = re.compile(
    r"^every\s+weekday\s+at\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$", re.IGNORECASE
)

_WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _parse_hour_minute(hour_str: str, minute_str: str | None, ampm: str | None) -> tuple[int, int]:
    """Parse hour/minute strings, handling optional AM/PM."""
    hour = int(hour_str)
    minute = int(minute_str) if minute_str else 0

    if ampm:
        ampm_lower = ampm.lower()
        if ampm_lower == "pm" and hour != 12:
            hour += 12
        elif ampm_lower == "am" and hour == 12:
            hour = 0

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time: {hour}:{minute:02d}")

    return hour, minute


def parse_reminder_time(
    time_expr: str,
    now: datetime | None = None,
) -> tuple[datetime | None, str | None]:
    """Parse a natural-language time expression into a fire datetime or cron string.

    Args:
        time_expr: Natural language time expression.
        now: Reference datetime (defaults to UTC now).  Used for testing.

    Returns:
        ``(fire_at, cron_expr)`` — exactly one is non-None.

    Raises:
        ValueError: If the expression is not in the supported set.
    """
    reference = now or datetime.now(UTC)
    expr = time_expr.strip().lower()

    # "in N minutes"
    if m := _IN_MINUTES_RE.match(expr):
        minutes = int(m.group(1))
        return reference + timedelta(minutes=minutes), None

    # "in N hours"
    if m := _IN_HOURS_RE.match(expr):
        hours = int(m.group(1))
        return reference + timedelta(hours=hours), None

    # "tomorrow at HH:MM[am|pm]"
    if m := _TOMORROW_AT_RE.match(expr):
        hour, minute = _parse_hour_minute(m.group(1), m.group(2), m.group(3))
        tomorrow = reference.date() + timedelta(days=1)
        return datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute, tzinfo=UTC), None

    # "next <weekday> at HH:MM[am|pm]"
    if m := _NEXT_DAY_AT_RE.match(expr):
        target_day = _WEEKDAY_MAP[m.group(1)]
        hour, minute = _parse_hour_minute(m.group(2), m.group(3), m.group(4))
        days_ahead = (target_day - reference.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target_date = reference.date() + timedelta(days=days_ahead)
        return (
            datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                tzinfo=UTC,
            ),
            None,
        )

    # "at HH:MM[am|pm] today"
    if m := _AT_TODAY_RE.match(expr):
        hour, minute = _parse_hour_minute(m.group(1), m.group(2), m.group(3))
        target = datetime(reference.year, reference.month, reference.day, hour, minute, tzinfo=UTC)
        if target <= reference:
            raise ValueError("Specified time is in the past")
        return target, None

    # "every day at HH:MM[am|pm]"
    if m := _EVERY_DAY_AT_RE.match(expr):
        hour, minute = _parse_hour_minute(m.group(1), m.group(2), m.group(3))
        return None, f"{minute} {hour} * * *"

    # "every weekday at HH:MM[am|pm]"
    if m := _EVERY_WEEKDAY_AT_RE.match(expr):
        hour, minute = _parse_hour_minute(m.group(1), m.group(2), m.group(3))
        return None, f"{minute} {hour} * * 1-5"

    raise ValueError(f"Unsupported time expression: '{time_expr}'")
