"""Server time retrieval with configured timezone awareness."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from assistant.shared.config import settings


def get_current_time(timezone: str | None = None) -> str:
    """Return the current server time as a human-readable string with timezone.

    Args:
        timezone: IANA timezone name (e.g. ``America/Guayaquil``).
            Defaults to the configured ``settings.timezone``.

    Returns:
        A string like ``"Current time: 2026-06-01 14:30:00 (America/Guayaquil)"``.

    Raises:
        ValueError: If the timezone name is unknown to the IANA database.
    """
    tz_name = timezone or settings.timezone
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise ValueError(f"Unknown timezone: {tz_name}") from exc

    now = datetime.now(tz)
    return f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')} ({tz_name})"
