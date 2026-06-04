"""Tests for check-in agent tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.checkin_tools import (
    list_scheduled_checkins,
    remove_checkin,
    schedule_checkin,
)
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn

_VALID_CHECKIN = ScheduledCheckIn(
    name="Morning Tasks",
    cron_expr="0 9 * * *",
    instructions="Summarise my open tasks.",
)


def _make_repo(
    *,
    find_by_name: ScheduledCheckIn | None = None,
    list_all: list[ScheduledCheckIn] | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.save.return_value = None
    repo.delete.return_value = None
    repo.find_by_name.return_value = find_by_name
    repo.list_all.return_value = list_all or []
    return repo


def _make_scheduler() -> MagicMock:
    s = MagicMock()
    s.add_job.return_value = None
    s.get_job.return_value = None
    s.remove_job.return_value = None
    return s


def _make_ctx(*, repo: AsyncMock | None = None, scheduler: MagicMock | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.deps = AgentDeps(
        scheduler=scheduler or _make_scheduler(),
        checkin_repo=repo or _make_repo(),
        prompt_repo=MagicMock(),
        note_repo=MagicMock(),
        bot=MagicMock(),
        vikunja_client=MagicMock(),
        searxng_client=MagicMock(),
        jina_client=MagicMock(),
        rebrowser_client=MagicMock(),
    )
    return ctx


# ---------------------------------------------------------------------------
# schedule_checkin tool
# ---------------------------------------------------------------------------


async def test_should_schedule_checkin_via_tool() -> None:
    repo = _make_repo()
    scheduler = _make_scheduler()
    ctx = _make_ctx(repo=repo, scheduler=scheduler)

    result = await schedule_checkin(
        ctx,
        "Morning Tasks",
        instructions="Summarise tasks.",
        cron_expr="0 9 * * *",
    )

    repo.save.assert_awaited_once()
    scheduler.add_job.assert_called_once()
    assert "Morning Tasks" in result
    assert "0 9 * * *" in result


async def test_should_return_error_message_when_cron_invalid() -> None:
    repo = _make_repo()
    scheduler = _make_scheduler()
    ctx = _make_ctx(repo=repo, scheduler=scheduler)

    result = await schedule_checkin(
        ctx,
        "Bad",
        instructions="Do something.",
        cron_expr="0 9 * *",
    )

    repo.save.assert_not_awaited()
    assert "Couldn't schedule" in result


# ---------------------------------------------------------------------------
# list_scheduled_checkins tool
# ---------------------------------------------------------------------------


async def test_should_list_checkins_via_tool() -> None:
    repo = _make_repo(list_all=[_VALID_CHECKIN])
    ctx = _make_ctx(repo=repo)

    result = await list_scheduled_checkins(ctx)

    assert "Morning Tasks" in result
    assert "0 9 * * *" in result


async def test_should_return_empty_message_when_no_checkins() -> None:
    repo = _make_repo(list_all=[])
    ctx = _make_ctx(repo=repo)

    result = await list_scheduled_checkins(ctx)

    assert "No check-ins" in result


# ---------------------------------------------------------------------------
# remove_checkin tool
# ---------------------------------------------------------------------------


async def test_should_remove_checkin_via_tool() -> None:
    repo = _make_repo(find_by_name=_VALID_CHECKIN)
    scheduler = _make_scheduler()
    ctx = _make_ctx(repo=repo, scheduler=scheduler)

    result = await remove_checkin(ctx, "Morning Tasks")

    repo.delete.assert_awaited_once_with(_VALID_CHECKIN.id)
    assert "removed" in result
