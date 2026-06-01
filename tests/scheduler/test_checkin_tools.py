"""Tests for Phase 6 check-in agent tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from assistant.agent.tools.checkin_tools import configure_checkin_tools
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


# ---------------------------------------------------------------------------
# schedule_checkin tool
# ---------------------------------------------------------------------------


async def test_should_schedule_checkin_via_tool() -> None:
    repo = _make_repo()
    scheduler = _make_scheduler()
    configure_checkin_tools(scheduler=scheduler, checkin_repo=repo)

    mock_agent = MagicMock()
    registered_tools: dict[str, object] = {}

    def capture_tool(fn: object) -> object:
        import inspect

        if inspect.iscoroutinefunction(fn):
            registered_tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    mock_agent.tool = capture_tool

    from assistant.agent.tools.checkin_tools import register_checkin_tools

    register_checkin_tools(mock_agent)  # type: ignore[arg-type]

    tool_fn = registered_tools["schedule_checkin"]
    result = await tool_fn(
        None,
        "Morning Tasks",
        instructions="Summarise tasks.",
        cron_expr="0 9 * * *",
    )  # type: ignore[operator]

    repo.save.assert_awaited_once()
    scheduler.add_job.assert_called_once()
    assert "Morning Tasks" in result
    assert "0 9 * * *" in result


async def test_should_return_error_message_when_cron_invalid() -> None:
    repo = _make_repo()
    scheduler = _make_scheduler()
    configure_checkin_tools(scheduler=scheduler, checkin_repo=repo)

    mock_agent = MagicMock()
    registered_tools: dict[str, object] = {}

    def capture_tool(fn: object) -> object:
        import inspect

        if inspect.iscoroutinefunction(fn):
            registered_tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    mock_agent.tool = capture_tool

    from assistant.agent.tools.checkin_tools import register_checkin_tools

    register_checkin_tools(mock_agent)  # type: ignore[arg-type]

    tool_fn = registered_tools["schedule_checkin"]
    result = await tool_fn(
        None,
        "Bad",
        instructions="Do something.",
        cron_expr="0 9 * *",
    )  # type: ignore[operator]

    repo.save.assert_not_awaited()
    assert "Couldn't schedule" in result


# ---------------------------------------------------------------------------
# list_scheduled_checkins tool
# ---------------------------------------------------------------------------


async def test_should_list_checkins_via_tool() -> None:
    repo = _make_repo(list_all=[_VALID_CHECKIN])
    scheduler = _make_scheduler()
    configure_checkin_tools(scheduler=scheduler, checkin_repo=repo)

    mock_agent = MagicMock()
    registered_tools: dict[str, object] = {}

    def capture_tool(fn: object) -> object:
        import inspect

        if inspect.iscoroutinefunction(fn):
            registered_tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    mock_agent.tool = capture_tool

    from assistant.agent.tools.checkin_tools import register_checkin_tools

    register_checkin_tools(mock_agent)  # type: ignore[arg-type]

    tool_fn = registered_tools["list_scheduled_checkins"]
    result = await tool_fn(None)  # type: ignore[operator]

    assert "Morning Tasks" in result
    assert "0 9 * * *" in result


async def test_should_return_empty_message_when_no_checkins() -> None:
    repo = _make_repo(list_all=[])
    scheduler = _make_scheduler()
    configure_checkin_tools(scheduler=scheduler, checkin_repo=repo)

    mock_agent = MagicMock()
    registered_tools: dict[str, object] = {}

    def capture_tool(fn: object) -> object:
        import inspect

        if inspect.iscoroutinefunction(fn):
            registered_tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    mock_agent.tool = capture_tool

    from assistant.agent.tools.checkin_tools import register_checkin_tools

    register_checkin_tools(mock_agent)  # type: ignore[arg-type]

    tool_fn = registered_tools["list_scheduled_checkins"]
    result = await tool_fn(None)  # type: ignore[operator]

    assert "No check-ins" in result


# ---------------------------------------------------------------------------
# remove_checkin tool
# ---------------------------------------------------------------------------


async def test_should_remove_checkin_via_tool() -> None:
    repo = _make_repo(find_by_name=_VALID_CHECKIN)
    scheduler = _make_scheduler()
    configure_checkin_tools(scheduler=scheduler, checkin_repo=repo)

    mock_agent = MagicMock()
    registered_tools: dict[str, object] = {}

    def capture_tool(fn: object) -> object:
        import inspect

        if inspect.iscoroutinefunction(fn):
            registered_tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    mock_agent.tool = capture_tool

    from assistant.agent.tools.checkin_tools import register_checkin_tools

    register_checkin_tools(mock_agent)  # type: ignore[arg-type]

    tool_fn = registered_tools["remove_checkin"]
    result = await tool_fn(None, "Morning Tasks")  # type: ignore[operator]

    repo.delete.assert_awaited_once_with(_VALID_CHECKIN.id)
    assert "removed" in result


async def test_should_return_not_found_message_when_checkin_missing() -> None:
    repo = _make_repo(find_by_name=None)
    scheduler = _make_scheduler()
    configure_checkin_tools(scheduler=scheduler, checkin_repo=repo)

    mock_agent = MagicMock()
    registered_tools: dict[str, object] = {}

    def capture_tool(fn: object) -> object:
        import inspect

        if inspect.iscoroutinefunction(fn):
            registered_tools[fn.__name__] = fn  # type: ignore[union-attr]
        return fn

    mock_agent.tool = capture_tool

    from assistant.agent.tools.checkin_tools import register_checkin_tools

    register_checkin_tools(mock_agent)  # type: ignore[arg-type]

    tool_fn = registered_tools["remove_checkin"]
    result = await tool_fn(None, "Ghost")  # type: ignore[operator]

    repo.delete.assert_not_awaited()
    assert "no check-in named" in result.lower()
