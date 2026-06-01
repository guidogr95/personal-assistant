"""Tests for Phase 5 — Vikunja task management (use cases + client)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from assistant.shared.exceptions import InfrastructureError
from assistant.tasks.application.complete_task import complete_task
from assistant.tasks.application.create_task import create_task
from assistant.tasks.application.list_tasks import list_open_tasks
from assistant.tasks.infrastructure.vikunja_client import (
    _VIKUNJA_ZERO_DATE,
    VikunjaClient,
    VikunjaTask,
    _parse_task,
)

# ---------------------------------------------------------------------------
# _parse_task — unit tests for the response normalisation helper
# ---------------------------------------------------------------------------


def test_should_normalise_zero_date_to_none() -> None:
    raw = {"id": 1, "title": "Task", "done": False, "due_date": _VIKUNJA_ZERO_DATE}
    task = _parse_task(raw)  # type: ignore[arg-type]
    assert task.due_date is None


def test_should_preserve_valid_due_date() -> None:
    raw = {"id": 1, "title": "Task", "done": False, "due_date": "2025-06-01T00:00:00Z"}
    task = _parse_task(raw)  # type: ignore[arg-type]
    assert task.due_date == "2025-06-01T00:00:00Z"


def test_should_handle_empty_due_date_string() -> None:
    # Defensive: API may return empty string for due_date
    raw = {"id": 2, "title": "No due", "done": True, "due_date": ""}
    task = _parse_task(raw)  # type: ignore[arg-type]
    assert task.due_date is None


def test_should_build_vikunja_task_fields() -> None:
    raw = {"id": 99, "title": "Buy milk", "done": True, "due_date": _VIKUNJA_ZERO_DATE}
    task = _parse_task(raw)  # type: ignore[arg-type]
    assert task.id == 99
    assert task.title == "Buy milk"
    assert task.done is True


def test_vikunja_task_is_immutable() -> None:
    task = VikunjaTask(id=1, title="Task", done=False, due_date=None)
    with pytest.raises(FrozenInstanceError):
        task.id = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_http(
    json_return: object,
    raise_on_raise_for_status: Exception | None = None,
) -> tuple[AsyncMock, MagicMock]:
    """Build a mock httpx session that returns ``json_return`` from ``response.json()``."""
    mock_response = MagicMock()
    mock_response.json.return_value = json_return
    if raise_on_raise_for_status:
        mock_response.raise_for_status.side_effect = raise_on_raise_for_status
    else:
        mock_response.raise_for_status.return_value = None

    mock_http = AsyncMock()
    mock_http.put.return_value = mock_response
    mock_http.get.return_value = mock_response
    mock_http.post.return_value = mock_response
    return mock_http, mock_response


def _patch_httpx(mock_http: AsyncMock) -> patch:  # type: ignore[type-arg]
    """Return a context manager that patches ``httpx.AsyncClient`` with ``mock_http``."""
    mock_cls = MagicMock()
    mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)
    return patch("httpx.AsyncClient", mock_cls)


# ---------------------------------------------------------------------------
# VikunjaClient — tests using httpx mocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_should_return_vikunja_task_on_successful_create() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_http, _ = _make_mock_http(
        {"id": 42, "title": "Buy groceries", "done": False, "due_date": _VIKUNJA_ZERO_DATE}
    )

    with _patch_httpx(mock_http):
        task = await client.create_task("Buy groceries")

    assert task.id == 42
    assert task.title == "Buy groceries"
    assert task.done is False
    assert task.due_date is None


@pytest.mark.asyncio
async def test_should_pass_due_date_in_create_payload() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_http, _ = _make_mock_http(
        {"id": 5, "title": "Doctor", "done": False, "due_date": "2025-07-01T00:00:00Z"}
    )

    with _patch_httpx(mock_http):
        task = await client.create_task("Doctor", due_date="2025-07-01T00:00:00Z")

    assert task.due_date == "2025-07-01T00:00:00Z"
    called_payload = mock_http.put.call_args.kwargs["json"]
    assert called_payload["due_date"] == "2025-07-01T00:00:00Z"


@pytest.mark.asyncio
async def test_should_raise_infrastructure_error_on_http_status_error() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_request = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_http, _ = _make_mock_http(
        {},
        raise_on_raise_for_status=httpx.HTTPStatusError(
            "401", request=mock_request, response=mock_resp
        ),
    )

    with _patch_httpx(mock_http), pytest.raises(InfrastructureError, match="401"):
        await client.create_task("Test")


@pytest.mark.asyncio
async def test_should_raise_infrastructure_error_on_request_error() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_http = AsyncMock()
    mock_http.put.side_effect = httpx.ConnectError("Connection refused")

    with _patch_httpx(mock_http), pytest.raises(InfrastructureError, match="unreachable"):
        await client.create_task("Test")


@pytest.mark.asyncio
async def test_should_return_open_tasks_list() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_http, _ = _make_mock_http(
        [
            {"id": 1, "title": "Task A", "done": False, "due_date": _VIKUNJA_ZERO_DATE},
            {"id": 2, "title": "Task B", "done": False, "due_date": "2025-08-01T00:00:00Z"},
        ]
    )

    with _patch_httpx(mock_http):
        tasks = await client.list_open_tasks()

    assert len(tasks) == 2
    assert tasks[0].id == 1
    assert tasks[0].due_date is None
    assert tasks[1].due_date == "2025-08-01T00:00:00Z"


@pytest.mark.asyncio
async def test_should_return_empty_list_when_no_open_tasks() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_http, _ = _make_mock_http([])

    with _patch_httpx(mock_http):
        tasks = await client.list_open_tasks()

    assert tasks == []


@pytest.mark.asyncio
async def test_should_complete_task_without_returning_value() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_http, _ = _make_mock_http({})

    with _patch_httpx(mock_http):
        result = await client.complete_task(7)

    assert result is None
    mock_http.post.assert_called_once()
    call_kwargs = mock_http.post.call_args.kwargs
    assert call_kwargs["json"] == {"done": True}


@pytest.mark.asyncio
async def test_should_raise_infrastructure_error_on_complete_task_failure() -> None:
    client = VikunjaClient(base_url="http://test", api_token="tok")
    mock_request = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_http, _ = _make_mock_http(
        {},
        raise_on_raise_for_status=httpx.HTTPStatusError(
            "404", request=mock_request, response=mock_resp
        ),
    )

    with _patch_httpx(mock_http), pytest.raises(InfrastructureError, match="404"):
        await client.complete_task(99)


# ---------------------------------------------------------------------------
# Use cases — tests with mocked VikunjaClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task_use_case_delegates_to_client() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    expected = VikunjaTask(id=10, title="Meeting prep", done=False, due_date=None)
    mock_client.create_task.return_value = expected

    result = await create_task("Meeting prep", None, mock_client)  # type: ignore[arg-type]

    mock_client.create_task.assert_called_once_with("Meeting prep", None)
    assert result == expected


@pytest.mark.asyncio
async def test_create_task_use_case_passes_due_date_through() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    expected = VikunjaTask(id=11, title="Call dentist", done=False, due_date="2025-07-01T00:00:00Z")
    mock_client.create_task.return_value = expected

    result = await create_task(  # type: ignore[arg-type]
        "Call dentist", "2025-07-01T00:00:00Z", mock_client
    )

    mock_client.create_task.assert_called_once_with("Call dentist", "2025-07-01T00:00:00Z")
    assert result.due_date == "2025-07-01T00:00:00Z"


@pytest.mark.asyncio
async def test_create_task_use_case_propagates_infrastructure_error() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    mock_client.create_task.side_effect = InfrastructureError("Vikunja is unreachable")

    with pytest.raises(InfrastructureError):
        await create_task("Test", None, mock_client)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_list_open_tasks_use_case_delegates_to_client() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    expected = [
        VikunjaTask(id=1, title="Alpha", done=False, due_date=None),
        VikunjaTask(id=2, title="Beta", done=False, due_date=None),
    ]
    mock_client.list_open_tasks.return_value = expected

    result = await list_open_tasks(mock_client)  # type: ignore[arg-type]

    mock_client.list_open_tasks.assert_called_once()
    assert result == expected


@pytest.mark.asyncio
async def test_list_open_tasks_use_case_returns_empty_list_when_none() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    mock_client.list_open_tasks.return_value = []

    result = await list_open_tasks(mock_client)  # type: ignore[arg-type]

    assert result == []


@pytest.mark.asyncio
async def test_complete_task_use_case_delegates_to_client() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    mock_client.complete_task.return_value = None

    await complete_task(5, mock_client)  # type: ignore[arg-type]

    mock_client.complete_task.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_complete_task_use_case_propagates_infrastructure_error() -> None:
    mock_client = AsyncMock(spec=VikunjaClient)
    mock_client.complete_task.side_effect = InfrastructureError("Vikunja is unreachable")

    with pytest.raises(InfrastructureError):
        await complete_task(5, mock_client)  # type: ignore[arg-type]
