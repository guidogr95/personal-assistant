"""Full-text search across all notes in the vault."""

from __future__ import annotations

from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository

MAX_SEARCH_RESULTS: int = 10
MAX_NOTE_READ_CHARS: int = 4_000


async def find_notes(query: str, repo: NoteRepository) -> list[Note]:
    """Return notes whose content matches ``query``, capped for agent safety.

    At most ``MAX_SEARCH_RESULTS`` notes are returned to avoid flooding the
    context window.  Each note's content is truncated to ``MAX_NOTE_READ_CHARS``
    for the same reason.

    Args:
        query: Word or phrase to search for (case-insensitive).
        repo: Repository to search.
    """
    all_matches = await repo.search(query)
    limited = all_matches[:MAX_SEARCH_RESULTS]
    return [
        Note(
            filename=n.filename,
            title=n.title,
            content=n.content[:MAX_NOTE_READ_CHARS],
            created_at=n.created_at,
            modified_at=n.modified_at,
        )
        if len(n.content) > MAX_NOTE_READ_CHARS
        else n
        for n in limited
    ]
