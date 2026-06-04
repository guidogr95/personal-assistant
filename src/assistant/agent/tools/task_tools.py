"""Agent tools for Vikunja task management."""

from __future__ import annotations

import structlog
from pydantic_ai import RunContext

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import tool
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
from assistant.tasks.application.complete_task import complete_task
from assistant.tasks.application.create_task import create_task
from assistant.tasks.application.list_tasks import list_open_tasks

logger = structlog.get_logger()

_NOT_CONFIGURED_MSG = (
    "Task management is not configured. Set VIKUNJA_API_TOKEN in .env and restart the bot."
)


@tool(category="✅ Tasks")
async def add_task(ctx: RunContext[AgentDeps], title: str, due_date: str | None = None) -> str:
    """Create a task in Vikunja.

    When the user specifies a relative due date ("by Friday", "tomorrow",
    "in 3 days"), call ``get_current_time`` first to get today's date, then
    compute the absolute date.  Do not guess the current date.

    Args:
        title: Short, actionable task description.
        due_date: Optional due date in ISO-8601 format (e.g. '2025-01-17T00:00:00Z').
                  Always compute from the result of ``get_current_time``.
    """
    if not settings.vikunja_api_token:
        return _NOT_CONFIGURED_MSG

    try:
        task = await create_task(title, due_date, ctx.deps.vikunja_client)
    except InfrastructureError as e:
        logger.error("add_task_tool_failed", title=title, error=str(e))
        return f"Sorry, I couldn't create the task: {e}"

    logger.info("add_task_tool", task_id=task.id, title=task.title)
    due_str = f" (due: {due_date})" if due_date else ""
    return f"Task created: '{task.title}'{due_str} (ID: {task.id})"


@tool(category="✅ Tasks")
async def get_open_tasks(ctx: RunContext[AgentDeps]) -> str:
    """List all open (incomplete) tasks from Vikunja."""
    if not settings.vikunja_api_token:
        return _NOT_CONFIGURED_MSG

    try:
        tasks = await list_open_tasks(ctx.deps.vikunja_client)
    except InfrastructureError as e:
        logger.error("get_open_tasks_tool_failed", error=str(e))
        return f"Sorry, I couldn't fetch tasks: {e}"

    if not tasks:
        return "No open tasks."

    lines = [f"- [{t.id}] {t.title}" for t in tasks]
    return "\n".join(lines)


@tool(category="✅ Tasks")
async def mark_task_done(ctx: RunContext[AgentDeps], task_id: int) -> str:
    """Mark a task as complete by its ID.

    Use ``get_open_tasks`` first to find the task ID if you don't have it.

    Args:
        task_id: The integer task ID from Vikunja.
    """
    if not settings.vikunja_api_token:
        return _NOT_CONFIGURED_MSG

    try:
        await complete_task(task_id, ctx.deps.vikunja_client)
    except InfrastructureError as e:
        logger.error("mark_task_done_tool_failed", task_id=task_id, error=str(e))
        return f"Sorry, I couldn't complete task {task_id}: {e}"

    logger.info("mark_task_done_tool", task_id=task_id)
    return f"Task {task_id} marked as done."
