"""Agent tools for Vikunja task management."""

from __future__ import annotations

import structlog
from pydantic_ai import Agent, RunContext

from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
from assistant.tasks.application.complete_task import complete_task
from assistant.tasks.application.create_task import create_task
from assistant.tasks.application.list_tasks import list_open_tasks
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient

logger = structlog.get_logger()

# Module-level instance: settings are read once at import time.
_client = VikunjaClient()

_NOT_CONFIGURED_MSG = (
    "Task management is not configured. Set VIKUNJA_API_TOKEN in .env and restart the bot."
)


def register_task_tools(agent: Agent[None, str]) -> None:
    """Register Vikunja task-management tools on the agent.

    Adds three tools: ``add_task``, ``get_open_tasks``, and ``mark_task_done``.
    All tools return a user-facing string — they never raise.
    """

    @agent.tool
    async def add_task(ctx: RunContext[None], title: str, due_date: str | None = None) -> str:
        """Create a task in Vikunja.

        Args:
            title: Short, actionable task description.
            due_date: Optional due date in ISO-8601 format (e.g. '2025-01-17T00:00:00Z').
                      Convert natural language dates (\"by Friday\", \"tomorrow\") to
                      ISO-8601 before calling this tool.
        """
        if not settings.vikunja_api_token:
            return _NOT_CONFIGURED_MSG

        try:
            task = await create_task(title, due_date, _client)
        except InfrastructureError as e:
            logger.error("add_task_tool_failed", title=title, error=str(e))
            return f"Sorry, I couldn't create the task: {e}"

        logger.info("add_task_tool", task_id=task.id, title=task.title)
        due_str = f" (due: {due_date})" if due_date else ""
        return f"Task created: '{task.title}'{due_str} (ID: {task.id})"

    @agent.tool
    async def get_open_tasks(ctx: RunContext[None]) -> str:
        """List all open (incomplete) tasks from Vikunja."""
        if not settings.vikunja_api_token:
            return _NOT_CONFIGURED_MSG

        try:
            tasks = await list_open_tasks(_client)
        except InfrastructureError as e:
            logger.error("get_open_tasks_tool_failed", error=str(e))
            return f"Sorry, I couldn't fetch tasks: {e}"

        if not tasks:
            return "No open tasks."

        lines = [f"- [{t.id}] {t.title}" for t in tasks]
        return "\n".join(lines)

    @agent.tool
    async def mark_task_done(ctx: RunContext[None], task_id: int) -> str:
        """Mark a task as complete by its ID.

        Use ``get_open_tasks`` first to find the task ID if you don't have it.

        Args:
            task_id: The integer task ID from Vikunja.
        """
        if not settings.vikunja_api_token:
            return _NOT_CONFIGURED_MSG

        try:
            await complete_task(task_id, _client)
        except InfrastructureError as e:
            logger.error("mark_task_done_tool_failed", task_id=task_id, error=str(e))
            return f"Sorry, I couldn't complete task {task_id}: {e}"

        logger.info("mark_task_done_tool", task_id=task_id)
        return f"Task {task_id} marked as done."
