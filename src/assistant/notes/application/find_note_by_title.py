"""Find a single note by its exact title."""

from __future__ import annotations

from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository


async def find_note_by_title(title: str, repo: NoteRepository) -> Note | None:
    """Return the most recent note whose title matches ``title``.

    Matching is case-insensitive.  If multiple notes share the same title,
    the newest (by modification time) is returned.

    Args:
        title: Note title to search for.
        repo: Repository to search.

    Returns:
        The matching Note, or ``None`` if no note has this title.
    """
    return await repo.find_by_title(title)
