"""Tests for the ScheduledCheckIn domain entity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn


def test_should_create_valid_recurring_checkin() -> None:
    checkin = ScheduledCheckIn(
        name="Morning Tasks",
        cron_expr="0 9 * * *",
        instructions="Summarise my open tasks.",
    )
    assert checkin.name == "Morning Tasks"
    assert checkin.cron_expr == "0 9 * * *"
    assert checkin.enabled is True
    assert checkin.id  # auto-generated UUID
    assert checkin.max_runs is None
    assert checkin.run_count == 0


def test_should_create_valid_one_off_reminder() -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    checkin = ScheduledCheckIn(
        name="Call Mom",
        fire_at=future,
        message="Call mom",
        max_runs=1,
    )
    assert checkin.fire_at == future
    assert checkin.message == "Call mom"
    assert checkin.max_runs == 1


def test_should_raise_on_invalid_cron_too_few_fields() -> None:
    with pytest.raises(ValueError, match="expected 5 fields"):
        ScheduledCheckIn(name="Bad", cron_expr="0 9 * *", instructions="Do something.")


def test_should_raise_on_invalid_cron_too_many_fields() -> None:
    with pytest.raises(ValueError, match="expected 5 fields"):
        ScheduledCheckIn(name="Bad", cron_expr="0 9 * * * 2026", instructions="Do something.")


def test_should_raise_on_blank_name() -> None:
    with pytest.raises(ValueError, match="name cannot be blank"):
        ScheduledCheckIn(name="   ", cron_expr="0 9 * * *", instructions="Do something.")


def test_should_raise_on_missing_instructions_and_message() -> None:
    with pytest.raises(ValueError, match="At least one of instructions or message"):
        ScheduledCheckIn(name="Morning", cron_expr="0 9 * * *")


def test_should_raise_on_both_cron_and_fire_at() -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    with pytest.raises(ValueError, match="Exactly one of cron_expr or fire_at"):
        ScheduledCheckIn(
            name="Bad",
            cron_expr="0 9 * * *",
            fire_at=future,
            instructions="Task.",
        )


def test_should_raise_on_neither_cron_nor_fire_at() -> None:
    with pytest.raises(ValueError, match="Exactly one of cron_expr or fire_at"):
        ScheduledCheckIn(name="Bad", instructions="Task.")


def test_should_accept_past_fire_at() -> None:
    # Past fire_at is valid on the entity — it represents a fired or missed job.
    # The "must be in the future" constraint is enforced by the application layer
    # (register_checkin) on user input, not here.
    past = datetime.now(UTC) - timedelta(hours=1)
    checkin = ScheduledCheckIn(name="Expired", fire_at=past, message="Task.")
    assert checkin.fire_at == past


def test_should_raise_on_invalid_max_runs() -> None:
    with pytest.raises(ValueError, match="max_runs must be >= 1"):
        ScheduledCheckIn(name="Bad", cron_expr="0 9 * * *", instructions="Task.", max_runs=0)


def test_should_disable_checkin() -> None:
    checkin = ScheduledCheckIn(name="A", cron_expr="0 9 * * *", instructions="Task.")
    checkin.disable()
    assert checkin.enabled is False


def test_should_enable_disabled_checkin() -> None:
    checkin = ScheduledCheckIn(name="A", cron_expr="0 9 * * *", instructions="Task.")
    checkin.disable()
    checkin.enable()
    assert checkin.enabled is True


def test_should_accept_every_minute_cron() -> None:
    checkin = ScheduledCheckIn(name="Frequent", cron_expr="* * * * *", instructions="Check.")
    assert checkin.cron_expr == "* * * * *"


def test_should_track_run_count() -> None:
    checkin = ScheduledCheckIn(name="A", cron_expr="0 9 * * *", instructions="Task.", max_runs=3)
    assert checkin.has_reached_max_runs() is False
    checkin.increment_run()
    assert checkin.run_count == 1
    assert checkin.has_reached_max_runs() is False
    checkin.increment_run()
    checkin.increment_run()
    assert checkin.has_reached_max_runs() is True


def test_should_reach_max_runs_on_one_off() -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    checkin = ScheduledCheckIn(name="A", fire_at=future, message="Task.", max_runs=1)
    checkin.increment_run()
    assert checkin.has_reached_max_runs() is True


def test_should_store_cron_timezone() -> None:
    checkin = ScheduledCheckIn(
        name="Morning Tasks",
        cron_expr="0 9 * * *",
        instructions="Summarise tasks.",
        cron_timezone="America/Guayaquil",
    )
    assert checkin.cron_timezone == "America/Guayaquil"


def test_cron_timezone_defaults_to_none() -> None:
    checkin = ScheduledCheckIn(
        name="Morning Tasks",
        cron_expr="0 9 * * *",
        instructions="Summarise tasks.",
    )
    assert checkin.cron_timezone is None
