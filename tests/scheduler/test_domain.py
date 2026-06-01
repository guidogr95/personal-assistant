"""Tests for the ScheduledCheckIn domain entity."""

from __future__ import annotations

import pytest

from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn


def test_should_create_valid_checkin() -> None:
    checkin = ScheduledCheckIn(
        name="Morning Tasks",
        cron_expr="0 9 * * *",
        instructions="Summarise my open tasks.",
    )
    assert checkin.name == "Morning Tasks"
    assert checkin.cron_expr == "0 9 * * *"
    assert checkin.enabled is True
    assert checkin.id  # auto-generated UUID


def test_should_raise_on_invalid_cron_too_few_fields() -> None:
    with pytest.raises(ValueError, match="expected 5 fields"):
        ScheduledCheckIn(name="Bad", cron_expr="0 9 * *", instructions="Do something.")


def test_should_raise_on_invalid_cron_too_many_fields() -> None:
    with pytest.raises(ValueError, match="expected 5 fields"):
        ScheduledCheckIn(name="Bad", cron_expr="0 9 * * * 2026", instructions="Do something.")


def test_should_raise_on_blank_name() -> None:
    with pytest.raises(ValueError, match="name cannot be blank"):
        ScheduledCheckIn(name="   ", cron_expr="0 9 * * *", instructions="Do something.")


def test_should_raise_on_blank_instructions() -> None:
    with pytest.raises(ValueError, match="instructions cannot be blank"):
        ScheduledCheckIn(name="Morning", cron_expr="0 9 * * *", instructions="   ")


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
