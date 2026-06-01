"""Create a new task in Vikunja."""

from __future__ import annotations

from assistant.tasks.infrastructure.vikunja_client import VikunjaClient, VikunjaTask


async def create_task(
    title: str,
    due_date: str | None,
    client: VikunjaClient,
) -> VikunjaTask:
    """Create a new Vikunja task and return the created task object.

    Args:
        title: Short, actionable task description.
        due_date: Optional ISO-8601 datetime string (e.g. ``'2025-01-17T00:00:00Z'``).
                  ``None`` if no due date was requested.
        client: Vikunja HTTP client to use.

    Returns:
        The created task with its assigned ID.

    Raises:
        InfrastructureError: If Vikunja is unreachable or rejects the request.
    """
    return await client.create_task(title, due_date)
