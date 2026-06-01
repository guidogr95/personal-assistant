"""Mark a Vikunja task as complete."""

from __future__ import annotations

from assistant.tasks.infrastructure.vikunja_client import VikunjaClient


async def complete_task(task_id: int, client: VikunjaClient) -> None:
    """Mark a task as done in Vikunja.

    Args:
        task_id: The integer task ID (from ``list_open_tasks``).
        client: Vikunja HTTP client to use.

    Raises:
        InfrastructureError: If Vikunja is unreachable or rejects the request.
    """
    await client.complete_task(task_id)
