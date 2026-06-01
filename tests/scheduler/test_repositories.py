"""Integration tests for SQLiteScheduledCheckInRepository.

Uses an in-memory SQLite database (":memory:" is not supported by aiosqlite
across separate connections, so we use a temporary file via tmp_path).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from assistant.conversation.infrastructure.sqlite_repositories import init_db
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.scheduler.infrastructure.sqlite_checkin_repository import (
    SQLiteScheduledCheckInRepository,
)


async def test_should_persist_and_reload_cron_timezone(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """cron_timezone survives a save → list_all round-trip.

    This is the regression test for the startup re-registration bug: a cron
    job set with a local timezone must reload that timezone from the DB so it
    fires at the correct local hour after a bot restart.
    """
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    repo = SQLiteScheduledCheckInRepository(db_path)
    checkin = ScheduledCheckIn(
        name="Morning Tasks",
        cron_expr="0 9 * * *",
        instructions="Summarise tasks.",
        cron_timezone="America/Guayaquil",
    )
    await repo.save(checkin)

    loaded = await repo.list_all()
    assert len(loaded) == 1
    assert loaded[0].cron_timezone == "America/Guayaquil"


async def test_should_persist_none_cron_timezone(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """cron_timezone=None (UTC jobs) is also persisted and reloaded correctly."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    repo = SQLiteScheduledCheckInRepository(db_path)
    checkin = ScheduledCheckIn(
        name="UTC Job",
        cron_expr="0 14 * * *",
        instructions="Run at 14:00 UTC.",
    )
    await repo.save(checkin)

    loaded = await repo.list_all()
    assert len(loaded) == 1
    assert loaded[0].cron_timezone is None


async def test_should_round_trip_one_off_without_timezone(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """One-off fire_at jobs have no cron_timezone — field stays None."""
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)

    repo = SQLiteScheduledCheckInRepository(db_path)
    future = datetime.now(UTC) + timedelta(hours=2)
    checkin = ScheduledCheckIn(
        name="One Off",
        fire_at=future,
        message="Ping!",
        max_runs=1,
    )
    await repo.save(checkin)

    loaded = await repo.list_all()
    assert len(loaded) == 1
    assert loaded[0].fire_at is not None
    assert loaded[0].cron_timezone is None
