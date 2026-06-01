"""Save a new Markdown note to the vault."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository


async def save_note(title: str, content: str, repo: NoteRepository) -> Note:
    """Generate a timestamped filename and persist the note.

    The filename format is ``YYYY-MM-DD-<slug>.md`` where the slug is derived
    from the title.  A timestamp prefix prevents filename collisions when
    multiple notes share similar titles on the same day.

    Args:
        title: Short descriptive title — becomes the H1 heading and filename slug.
        content: Note body in Markdown format.
        repo: Repository to persist the note.

    Returns:
        The persisted ``Note`` value object.
    """
    date_prefix = datetime.now(UTC).strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")[:50]
    filename = f"{date_prefix}-{slug}.md"
    full_content = f"# {title}\n\n{content}\n"
    return await repo.save(filename, full_content)
