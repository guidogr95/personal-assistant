"""Vikunja task management REST API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict, cast

import httpx
import structlog

from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError

logger = structlog.get_logger()

VIKUNJA_TIMEOUT_SECONDS: int = 15
DEFAULT_PROJECT_ID: int = 1  # first project created in Vikunja
DEFAULT_VIEW_ID: int = 1  # "List" view — pre-filtered to done=false in Vikunja v2

# Vikunja returns this sentinel when no due date is set (Go zero time)
_VIKUNJA_ZERO_DATE: str = "0001-01-01T00:00:00Z"


class _TaskResponse(TypedDict):
    """Expected shape of a task object from the Vikunja REST API."""

    id: int
    title: str
    done: bool
    due_date: str


@dataclass(frozen=True)
class VikunjaTask:
    """Immutable DTO for a Vikunja task returned from the API."""

    id: int
    title: str
    done: bool
    due_date: str | None  # None when no due date is set


def _parse_task(raw: _TaskResponse) -> VikunjaTask:
    """Convert a raw API response dict to a typed VikunjaTask.

    Normalises Vikunja's Go zero-time sentinel (``0001-01-01T00:00:00Z``)
    to ``None`` so callers never need to know about the sentinel value.
    """
    raw_due = raw.get("due_date")
    due_date: str | None = raw_due if raw_due and raw_due != _VIKUNJA_ZERO_DATE else None
    return VikunjaTask(
        id=raw["id"],
        title=raw["title"],
        done=raw["done"],
        due_date=due_date,
    )


class VikunjaClient:
    """HTTP client for the Vikunja REST API.

    All HTTP calls are confined to this class. Callers receive typed
    ``VikunjaTask`` objects and never interact with httpx directly.

    Raises ``InfrastructureError`` on any HTTP or network failure so the
    application layer does not need to know about httpx internals.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_token: str | None = None,
    ) -> None:
        self._base_url: str = base_url or settings.vikunja_url
        token: str = api_token or settings.vikunja_api_token
        self._headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def create_task(self, title: str, due_date: str | None = None) -> VikunjaTask:
        """Create a new task in the default Vikunja project.

        Args:
            title: Task title.
            due_date: Optional ISO-8601 datetime string (e.g. ``'2025-01-17T00:00:00Z'``).

        Returns:
            The created task with its assigned ID.

        Raises:
            InfrastructureError: On any HTTP or network failure.
        """
        payload: dict[str, str] = {"title": title}
        if due_date:
            payload["due_date"] = due_date

        try:
            async with httpx.AsyncClient(timeout=VIKUNJA_TIMEOUT_SECONDS) as client:
                response = await client.put(
                    f"{self._base_url}/api/v1/projects/{DEFAULT_PROJECT_ID}/tasks",
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
                data = cast(_TaskResponse, response.json())
        except httpx.HTTPStatusError as e:
            logger.error(
                "vikunja_create_task_failed",
                title=title,
                status=e.response.status_code,
            )
            raise InfrastructureError(
                f"Vikunja rejected create task (HTTP {e.response.status_code})"
            ) from e
        except httpx.RequestError as e:
            logger.error("vikunja_create_task_unreachable", title=title, error=str(e))
            raise InfrastructureError("Vikunja is unreachable") from e

        task = _parse_task(data)
        logger.info("vikunja_task_created", task_id=task.id, title=task.title)
        return task

    async def list_open_tasks(self) -> list[VikunjaTask]:
        """Fetch all open (not done) tasks across all projects.

        Returns:
            List of open tasks, up to 50 results.

        Raises:
            InfrastructureError: On any HTTP or network failure.
        """
        try:
            async with httpx.AsyncClient(timeout=VIKUNJA_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/projects/{DEFAULT_PROJECT_ID}/views/{DEFAULT_VIEW_ID}/tasks",
                    headers=self._headers,
                )
                response.raise_for_status()
                raw_tasks = cast(list[Any], response.json())
        except httpx.HTTPStatusError as e:
            logger.error(
                "vikunja_list_tasks_failed",
                status=e.response.status_code,
            )
            raise InfrastructureError(
                f"Vikunja rejected list tasks (HTTP {e.response.status_code})"
            ) from e
        except httpx.RequestError as e:
            logger.error("vikunja_list_tasks_unreachable", error=str(e))
            raise InfrastructureError("Vikunja is unreachable") from e

        return [_parse_task(cast(_TaskResponse, t)) for t in raw_tasks]

    async def complete_task(self, task_id: int) -> None:
        """Mark a task as done by its ID.

        Args:
            task_id: The Vikunja task ID (from ``list_open_tasks``).

        Raises:
            InfrastructureError: On any HTTP or network failure.
        """
        try:
            async with httpx.AsyncClient(timeout=VIKUNJA_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/tasks/{task_id}",
                    json={"done": True},
                    headers=self._headers,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "vikunja_complete_task_failed",
                task_id=task_id,
                status=e.response.status_code,
            )
            raise InfrastructureError(
                f"Vikunja rejected complete task {task_id} (HTTP {e.response.status_code})"
            ) from e
        except httpx.RequestError as e:
            logger.error("vikunja_complete_task_unreachable", task_id=task_id, error=str(e))
            raise InfrastructureError("Vikunja is unreachable") from e

        logger.info("vikunja_task_completed", task_id=task_id)
