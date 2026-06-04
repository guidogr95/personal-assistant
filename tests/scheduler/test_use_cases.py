"""Tests for Phase 6 — scheduler use cases."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot

from assistant.scheduler.application.delete_checkin import delete_checkin_by_name
from assistant.scheduler.application.list_checkins import list_all_checkins
from assistant.scheduler.application.register_checkin import register_checkin
from assistant.scheduler.application.run_checkin import configure_checkin_runner, run_checkin
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.shared.exceptions import CheckInNotFoundError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CHECKIN = ScheduledCheckIn(
    name="Morning Tasks",
    cron_expr="0 9 * * *",
    instructions="Summarise my open tasks.",
)


def _make_mock_repo(
    *,
    find_by_name: ScheduledCheckIn | None = None,
    get_by_id: ScheduledCheckIn | None = None,
    list_all: list[ScheduledCheckIn] | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.save.return_value = None
    repo.delete.return_value = None
    repo.find_by_name.return_value = find_by_name
    repo.get_by_id.return_value = get_by_id
    repo.list_all.return_value = list_all or []
    return repo


def _make_mock_scheduler() -> MagicMock:
    scheduler = MagicMock()
    scheduler.add_job.return_value = None
    scheduler.get_job.return_value = None
    scheduler.remove_job.return_value = None
    return scheduler


# ---------------------------------------------------------------------------
# register_checkin
# ---------------------------------------------------------------------------


async def test_should_register_checkin_saves_to_repo_and_schedules_job() -> None:
    repo = _make_mock_repo()
    scheduler = _make_mock_scheduler()

    checkin = await register_checkin(
        name="Morning Tasks",
        cron_expr="0 9 * * *",
        instructions="Summarise tasks.",
        repo=repo,
        scheduler=scheduler,
    )

    repo.save.assert_awaited_once()
    scheduler.add_job.assert_called_once()
    assert checkin.name == "Morning Tasks"


async def test_should_not_save_when_cron_invalid() -> None:
    repo = _make_mock_repo()
    scheduler = _make_mock_scheduler()

    with pytest.raises(ValueError, match="expected 5 fields"):
        await register_checkin(
            name="Bad",
            cron_expr="0 9 * *",  # only 4 fields
            instructions="Do something.",
            repo=repo,
            scheduler=scheduler,
        )

    repo.save.assert_not_awaited()
    scheduler.add_job.assert_not_called()


async def test_should_not_save_when_name_blank() -> None:
    repo = _make_mock_repo()
    scheduler = _make_mock_scheduler()

    with pytest.raises(ValueError, match="name cannot be blank"):
        await register_checkin(
            name="",
            cron_expr="0 9 * * *",
            instructions="Do something.",
            repo=repo,
            scheduler=scheduler,
        )

    repo.save.assert_not_awaited()


# ---------------------------------------------------------------------------
# list_all_checkins
# ---------------------------------------------------------------------------


async def test_should_list_all_returns_repo_results() -> None:
    repo = _make_mock_repo(list_all=[_VALID_CHECKIN])
    result = await list_all_checkins(repo)
    assert result == [_VALID_CHECKIN]
    repo.list_all.assert_awaited_once()


async def test_should_list_all_returns_empty_list_when_none_registered() -> None:
    repo = _make_mock_repo(list_all=[])
    result = await list_all_checkins(repo)
    assert result == []


# ---------------------------------------------------------------------------
# delete_checkin_by_name
# ---------------------------------------------------------------------------


async def test_should_delete_checkin_by_name() -> None:
    repo = _make_mock_repo(find_by_name=_VALID_CHECKIN)
    scheduler = _make_mock_scheduler()

    await delete_checkin_by_name("Morning Tasks", repo, scheduler)

    repo.delete.assert_awaited_once_with(_VALID_CHECKIN.id)


async def test_should_raise_when_checkin_not_found_for_delete() -> None:
    repo = _make_mock_repo(find_by_name=None)
    scheduler = _make_mock_scheduler()

    with pytest.raises(CheckInNotFoundError, match="Morning Tasks"):
        await delete_checkin_by_name("Morning Tasks", repo, scheduler)

    repo.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_checkin
# ---------------------------------------------------------------------------


async def test_should_skip_run_when_checkin_not_found() -> None:
    mock_bot = AsyncMock()
    repo = _make_mock_repo(get_by_id=None)
    configure_checkin_runner(bot=mock_bot, checkin_repo=repo, run_agent=AsyncMock())

    await run_checkin("nonexistent-id")

    mock_bot.send_message.assert_not_awaited()


async def test_should_skip_run_when_checkin_disabled() -> None:
    disabled = ScheduledCheckIn(
        name="Disabled",
        cron_expr="0 9 * * *",
        instructions="Do something.",
    )
    disabled.disable()

    mock_bot = AsyncMock()
    repo = _make_mock_repo(get_by_id=disabled)
    configure_checkin_runner(bot=mock_bot, checkin_repo=repo, run_agent=AsyncMock())

    await run_checkin(disabled.id)

    mock_bot.send_message.assert_not_awaited()


async def test_should_run_checkin_and_send_message() -> None:
    mock_bot = AsyncMock()
    repo = _make_mock_repo(get_by_id=_VALID_CHECKIN)
    mock_run_agent = AsyncMock(return_value="You have 3 open tasks.")
    configure_checkin_runner(bot=mock_bot, checkin_repo=repo, run_agent=mock_run_agent)

    with patch("assistant.scheduler.application.run_checkin.settings") as mock_settings:
        mock_settings.telegram_allowed_user_id = 12345

        await run_checkin(_VALID_CHECKIN.id)

    mock_run_agent.assert_awaited_once_with(_VALID_CHECKIN.instructions)
    mock_bot.send_message.assert_awaited_once()
    call_kwargs = mock_bot.send_message.call_args
    assert "Morning Tasks" in call_kwargs.kwargs["text"]
    assert "3 open tasks" in call_kwargs.kwargs["text"]


async def test_should_send_failure_notification_when_agent_raises() -> None:
    mock_bot = AsyncMock(spec=Bot)
    repo = _make_mock_repo(get_by_id=_VALID_CHECKIN)
    mock_run_agent = AsyncMock(side_effect=RuntimeError("LLM down"))
    configure_checkin_runner(bot=mock_bot, checkin_repo=repo, run_agent=mock_run_agent)

    with patch("assistant.scheduler.application.run_checkin.settings") as mock_settings:
        mock_settings.telegram_allowed_user_id = 12345

        await run_checkin(_VALID_CHECKIN.id)

    # A failure notification must be sent — the check-in must not silently vanish
    mock_bot.send_message.assert_awaited_once()
    text = mock_bot.send_message.call_args.kwargs["text"]
    assert "failed" in text.lower() or "⚠️" in text
