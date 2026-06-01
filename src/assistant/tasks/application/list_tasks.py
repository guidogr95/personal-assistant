"""List open tasks from Vikunja."""

from __future__ import annotations

from assistant.tasks.infrastructure.vikunja_client import VikunjaClient, VikunjaTask


async def list_open_tasks(client: VikunjaClient) -> list[VikunjaTask]:
    """Return all open (not done) tasks from Vikunja.

    Args:
        client: Vikunja HTTP client to use.

    Returns:
        List of open tasks, newest first (up to 50).

    Raises:
        InfrastructureError: If Vikunja is unreachable or rejects the request.
    """
    return await client.list_open_tasks()
