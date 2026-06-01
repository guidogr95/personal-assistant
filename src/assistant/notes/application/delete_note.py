"""Delete a note from the vault by filename."""

from __future__ import annotations

from assistant.notes.domain.note_repository import NoteRepository


async def delete_note(filename: str, repo: NoteRepository) -> bool:
    """Remove the note identified by ``filename`` from the vault.

    Args:
        filename: Note filename (e.g. ``2025-01-15-my-note.md``).
        repo: Repository to delete from.

    Returns:
        True if the note was deleted, False if it did not exist.
    """
    return await repo.delete(filename)
