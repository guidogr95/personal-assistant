"""Filesystem-backed Markdown note repository.

All content is stored as plain ``.md`` files under the configured vault path.
This class performs no content truncation — the application layer controls caps.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import aiofiles
import aiofiles.os
import structlog

from assistant.notes.domain.note import Note
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError

logger = structlog.get_logger()


class MarkdownNoteRepository:
    """Reads and writes Markdown notes to a local directory vault.

    The vault directory is created on first instantiation if it does not exist.
    File modification time is used for both ``created_at`` and ``modified_at``
    because the filesystem does not separately track creation time on Linux.
    """

    def __init__(self, vault_path: str = settings.notes_vault_path) -> None:
        self._vault = Path(vault_path)
        self._vault.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content: str) -> Note:
        """Write ``content`` to ``filename`` and return the persisted Note.

        Raises:
            InfrastructureError: if the file cannot be written (permissions,
                disk full, etc.).
        """
        path = self._vault / filename
        try:
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
        except OSError as e:
            logger.error("note_save_failed", filename=filename, error=str(e))
            raise InfrastructureError(f"Failed to save note {filename}") from e

        stat = await aiofiles.os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        title = self._extract_title(filename, content)
        logger.info("note_saved", filename=filename)
        return Note(
            filename=filename,
            title=title,
            content=content,
            created_at=ts,
            modified_at=ts,
        )

    async def read(self, filename: str) -> Note | None:
        """Return full note content, or ``None`` if the file does not exist."""
        path = self._vault / filename
        if not path.exists():
            return None
        async with aiofiles.open(path, encoding="utf-8") as f:
            content = await f.read()
        stat = await aiofiles.os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        return Note(
            filename=filename,
            title=self._extract_title(filename, content),
            content=content,
            created_at=ts,
            modified_at=ts,
        )

    async def search(self, query: str) -> list[Note]:
        """Return notes whose content contains ``query`` (case-insensitive).

        Results are ordered newest-first by modification time.
        The full note content is returned — callers must apply any length caps.
        """
        query_lower = query.lower()
        results: list[Note] = []
        candidates = sorted(
            self._vault.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            async with aiofiles.open(path, encoding="utf-8") as f:
                content = await f.read()
            if query_lower not in content.lower():
                continue
            stat = path.stat()
            ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            results.append(
                Note(
                    filename=path.name,
                    title=self._extract_title(path.name, content),
                    content=content,
                    created_at=ts,
                    modified_at=ts,
                )
            )
        return results

    async def list_all(self) -> list[str]:
        """Return all note filenames, newest first."""
        return sorted(
            [p.name for p in self._vault.glob("*.md")],
            reverse=True,
        )

    async def update(self, filename: str, content: str) -> Note | None:
        """Overwrite ``filename`` with ``content`` and return the updated Note.

        Returns:
            The updated Note, or ``None`` if the file does not exist.

        Raises:
            InfrastructureError: if the file exists but cannot be written.
        """
        path = self._vault / filename
        if not path.exists():
            return None
        try:
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
        except OSError as e:
            logger.error("note_update_failed", filename=filename, error=str(e))
            raise InfrastructureError(f"Failed to update note {filename}") from e
        stat = await aiofiles.os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        title = self._extract_title(filename, content)
        logger.info("note_updated", filename=filename)
        return Note(
            filename=filename,
            title=title,
            content=content,
            created_at=ts,
            modified_at=ts,
        )

    async def delete(self, filename: str) -> bool:
        """Remove the note file from the vault.

        Returns:
            True if deleted, False if the file did not exist.

        Raises:
            InfrastructureError: if the file exists but cannot be removed
                (permissions, locked file, etc.).
        """
        path = self._vault / filename
        if not path.exists():
            return False
        try:
            await aiofiles.os.remove(path)
        except OSError as e:
            logger.error("note_delete_failed", filename=filename, error=str(e))
            raise InfrastructureError(f"Failed to delete note {filename}") from e
        logger.info("note_deleted", filename=filename)
        return True

    @staticmethod
    def _extract_title(filename: str, content: str) -> str:
        """Return H1 heading from content, or a humanised version of the filename."""
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return filename.removesuffix(".md").replace("-", " ")
