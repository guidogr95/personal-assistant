"""Read a single note from the vault, capped for agent context-window safety."""

from __future__ import annotations

from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository

MAX_NOTE_READ_CHARS: int = 4_000


async def read_note(filename: str, repo: NoteRepository) -> Note | None:
    """Return the note identified by ``filename``, with content capped at 4000 chars.

    The cap prevents a single large note from consuming the LLM context window.
    Returns ``None`` if the note does not exist.

    Args:
        filename: Note filename (e.g. ``2025-01-15-my-note.md``).
        repo: Repository to read from.
    """
    note = await repo.read(filename)
    if note is None:
        return None
    if len(note.content) <= MAX_NOTE_READ_CHARS:
        return note
    return Note(
        filename=note.filename,
        title=note.title,
        content=note.content[:MAX_NOTE_READ_CHARS],
        created_at=note.created_at,
        modified_at=note.modified_at,
    )
