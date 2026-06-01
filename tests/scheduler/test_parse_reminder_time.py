"""Tests for natural-language reminder time parser."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from assistant.scheduler.application.parse_reminder_time import parse_reminder_time


class TestParseReminderTime:
    def test_in_30_minutes(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("in 30 minutes", now=now)
        assert fire_at == datetime(2026, 6, 1, 12, 30, tzinfo=UTC)
        assert cron is None

    def test_in_2_hours(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("in 2 hours", now=now)
        assert fire_at == datetime(2026, 6, 1, 14, 0, tzinfo=UTC)
        assert cron is None

    def test_tomorrow_at_9am(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("tomorrow at 9am", now=now)
        assert fire_at == datetime(2026, 6, 2, 9, 0, tzinfo=UTC)
        assert cron is None

    def test_tomorrow_at_1530(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("tomorrow at 15:30", now=now)
        assert fire_at == datetime(2026, 6, 2, 15, 30, tzinfo=UTC)
        assert cron is None

    def test_next_monday_at_8am(self) -> None:
        # 2026-06-01 is a Monday
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("next Monday at 8am", now=now)
        assert fire_at == datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
        assert cron is None

    def test_at_1530_today(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("at 15:30 today", now=now)
        assert fire_at == datetime(2026, 6, 1, 15, 30, tzinfo=UTC)
        assert cron is None

    def test_at_past_time_today_raises(self) -> None:
        now = datetime(2026, 6, 1, 15, 0, tzinfo=UTC)
        with pytest.raises(ValueError, match="in the past"):
            parse_reminder_time("at 12:00 today", now=now)

    def test_every_day_at_9am(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("every day at 9am", now=now)
        assert fire_at is None
        assert cron == "0 9 * * *"

    def test_every_weekday_at_8am(self) -> None:
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        fire_at, cron = parse_reminder_time("every weekday at 8am", now=now)
        assert fire_at is None
        assert cron == "0 8 * * 1-5"

    def test_unsupported_expression_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported time expression"):
            parse_reminder_time("sometime next week")


class TestParseReminderTimeLocalTimezone:
    """Verify that absolute time expressions fire in the user's local timezone.

    Guayaquil is UTC-5 (no DST).  All assertions compare against the UTC
    equivalent so the test stays correct regardless of the host's local clock.
    """

    _TZ = ZoneInfo("America/Guayaquil")  # UTC-5

    def test_tomorrow_at_9am_fires_in_local_tz(self) -> None:
        # Local now: 2026-06-01 18:00 (UTC-5) → UTC 2026-06-01 23:00
        now = datetime(2026, 6, 1, 18, 0, tzinfo=self._TZ)
        fire_at, cron = parse_reminder_time("tomorrow at 9am", now=now, tz=self._TZ)
        assert cron is None
        assert fire_at is not None
        # 9am Guayaquil on June 2 = 14:00 UTC
        assert fire_at.year == 2026 and fire_at.month == 6 and fire_at.day == 2
        assert fire_at.hour == 9 and fire_at.minute == 0
        assert fire_at.tzinfo == self._TZ
        # Confirm UTC equivalent
        from datetime import UTC

        assert fire_at.astimezone(UTC) == datetime(2026, 6, 2, 14, 0, tzinfo=UTC)

    def test_next_monday_at_8am_fires_in_local_tz(self) -> None:
        # 2026-06-01 is Monday; "next Monday" = 2026-06-08
        now = datetime(2026, 6, 1, 8, 0, tzinfo=self._TZ)
        fire_at, cron = parse_reminder_time("next Monday at 8am", now=now, tz=self._TZ)
        assert cron is None
        assert fire_at is not None
        assert fire_at.year == 2026 and fire_at.month == 6 and fire_at.day == 8
        assert fire_at.hour == 8
        assert fire_at.tzinfo == self._TZ

    def test_at_time_today_fires_in_local_tz(self) -> None:
        now = datetime(2026, 6, 1, 8, 0, tzinfo=self._TZ)
        fire_at, cron = parse_reminder_time("at 15:30 today", now=now, tz=self._TZ)
        assert cron is None
        assert fire_at is not None
        assert fire_at.hour == 15 and fire_at.minute == 30
        assert fire_at.tzinfo == self._TZ

    def test_relative_expressions_unaffected_by_tz(self) -> None:
        # "in N minutes" adds a timedelta — result is in whatever tz 'now' is
        now = datetime(2026, 6, 1, 18, 0, tzinfo=self._TZ)
        fire_at, cron = parse_reminder_time("in 30 minutes", now=now, tz=self._TZ)
        assert cron is None
        assert fire_at == datetime(2026, 6, 1, 18, 30, tzinfo=self._TZ)

    def test_cron_expr_returned_unchanged_tz_handled_by_apscheduler(self) -> None:
        # parse_reminder_time returns raw cron string; timezone is forwarded to
        # APScheduler's CronTrigger, not embedded in the string itself.
        now = datetime(2026, 6, 1, 8, 0, tzinfo=self._TZ)
        fire_at, cron = parse_reminder_time("every day at 9am", now=now, tz=self._TZ)
        assert fire_at is None
        assert cron == "0 9 * * *"  # raw — APScheduler receives tz separately
