"""Update an existing Markdown note in place."""

from __future__ import annotations

from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository


async def update_note(filename: str, content: str, repo: NoteRepository) -> Note | None:
    """Overwrite an existing note's content without changing its filename.

    Args:
        filename: Exact note filename (e.g. ``2025-01-15-my-note.md``).
        content: New Markdown content.
        repo: Note repository implementation.

    Returns:
        The updated Note, or ``None`` if the file does not exist.
    """
    return await repo.update(filename, content)
