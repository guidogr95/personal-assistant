"""List all note filenames from the vault."""

from __future__ import annotations

from assistant.notes.domain.note_repository import NoteRepository


async def list_notes(repo: NoteRepository) -> list[str]:
    """Return all note filenames, newest first.

    Args:
        repo: Repository to list from.

    Returns:
        List of filenames (e.g. ``['2025-01-15-my-note.md', ...]``).
    """
    return await repo.list_all()
