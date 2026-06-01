"""SQLite-backed prompt repository."""

from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite

from assistant.prompts.domain.prompt_repository import PromptRepository
from assistant.shared.exceptions import InfrastructureError


class SQLitePromptRepository(PromptRepository):
    """Reads and writes the system prompt from a SQLite table.

    The table is expected to have exactly one row (id=1).  ``init_db``
    seeds the default prompt on first run.
    """

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path

    async def get_active(self) -> str:
        """Return the current system prompt text.

        Raises:
            InfrastructureError: if the query fails.
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                async with db.execute(
                    "SELECT prompt_text FROM system_prompts WHERE id = 1"
                ) as cursor:
                    row = await cursor.fetchone()
                    if row is None:
                        raise InfrastructureError("System prompt row missing")
                    return str(row[0])
        except Exception as exc:
            raise InfrastructureError("Failed to read system prompt") from exc

    async def update(self, text: str) -> None:
        """Replace the active system prompt.

        Raises:
            InfrastructureError: if the update fails.
        """
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(
                    "UPDATE system_prompts SET prompt_text = ?, updated_at = ? WHERE id = 1",
                    (text, datetime.now(UTC).isoformat()),
                )
                await db.commit()
        except Exception as exc:
            raise InfrastructureError("Failed to update system prompt") from exc
