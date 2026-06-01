"""Tests for natural-language reminder time parser."""

from __future__ import annotations

from datetime import UTC, datetime

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
