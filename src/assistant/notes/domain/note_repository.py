"""NoteRepository — structural interface for note persistence."""

from __future__ import annotations

from typing import Protocol

from assistant.notes.domain.note import Note


class NoteRepository(Protocol):
    """Persistence contract for Markdown notes.

    Implementations are expected to be async and return domain ``Note``
    objects.  The application layer is responsible for content-length caps
    and result-count limits; the repository returns full, untruncated data.
    """

    async def save(self, filename: str, content: str) -> Note:
        """Persist ``content`` under ``filename`` and return the saved Note."""
        ...

    async def read(self, filename: str) -> Note | None:
        """Return the Note for ``filename``, or ``None`` if it does not exist."""
        ...

    async def search(self, query: str) -> list[Note]:
        """Return all notes whose content contains ``query`` (case-insensitive)."""
        ...

    async def find_by_title(self, title: str) -> Note | None:
        """Return the most recent note whose title matches ``title``.

        Matching is case-insensitive and strips surrounding whitespace.
        If multiple notes share the same title, the newest is returned.
        """
        ...

    async def list_all(self) -> list[str]:
        """Return all note filenames, newest first."""
        ...

    async def update(self, filename: str, content: str) -> Note | None:
        """Overwrite ``filename`` with ``content`` and return the updated Note.

        Returns:
            The updated Note, or ``None`` if the file does not exist.
        """
        ...

    async def delete(self, filename: str) -> bool:
        """Remove ``filename`` from the vault.

        Returns:
            True if the file was deleted, False if it did not exist.
        """
        ...
