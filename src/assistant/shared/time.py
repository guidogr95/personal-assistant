"""Server time retrieval with configured timezone awareness."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from assistant.shared.config import settings


def get_current_time(timezone: str | None = None) -> str:
    """Return the current local time with UTC offset and the equivalent UTC time.

    Args:
        timezone: IANA timezone name (e.g. ``America/Guayaquil``).
            Defaults to the configured ``settings.timezone``.

    Returns:
        A string like::

            "Local: 2026-06-01 20:50:00 (America/Guayaquil, UTC-5) | UTC: 2026-06-02 01:50:00"

    Raises:
        ValueError: If the timezone name is unknown to the IANA database.
    """
    tz_name = timezone or settings.timezone
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError(f"Unknown timezone: {tz_name}") from exc

    now = datetime.now(tz)
    now_utc = now.astimezone(UTC)

    offset = now.utcoffset()
    total_seconds = int(offset.total_seconds())  # type: ignore[union-attr]
    sign = "+" if total_seconds >= 0 else "-"
    hours, remainder = divmod(abs(total_seconds), 3600)
    minutes = remainder // 60
    offset_str = f"UTC{sign}{hours}:{minutes:02d}" if minutes else f"UTC{sign}{hours}"

    local_str = now.strftime("%Y-%m-%d %H:%M:%S")
    utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    return f"Local: {local_str} ({tz_name}, {offset_str}) | UTC: {utc_str}"
