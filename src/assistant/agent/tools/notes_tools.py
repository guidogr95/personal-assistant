"""Agent tools for the Markdown notes vault."""

from __future__ import annotations

import structlog
from pydantic_ai import RunContext

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import tool
from assistant.notes.application.find_note_by_title import find_note_by_title
from assistant.notes.application.find_notes import find_notes
from assistant.notes.application.list_notes import list_notes
from assistant.notes.application.read_note import read_note
from assistant.notes.application.save_note import save_note
from assistant.notes.application.update_note import update_note as _update_note

logger = structlog.get_logger()

# Sentinel prefix returned by delete_note to trigger a Telegram confirmation
# keyboard.  The message handler detects this prefix and does NOT echo the
# raw string to the user.
DELETE_CONFIRM_SENTINEL = "__CONFIRM_DELETE__"


@tool(category="📝 Notes")
async def create_note(ctx: RunContext[AgentDeps], title: str, content: str) -> str:
    """Create a new Markdown note in the vault, or update an existing one.

    This tool FIRST checks whether a note with the exact same title already
    exists.  If it does, the existing note is updated in place (its content
    is overwritten) rather than creating a duplicate.  The filename is never
    changed on update.

    Only when no matching note exists does it create a brand-new file with
    a timestamped filename.

    Args:
        title: Short descriptive title (becomes the H1 heading and filename
            for new notes).  Used as the lookup key for existing notes.
        content: Note body in Markdown format.  Include only what the user
            explicitly asked to write — do not add extra context, summaries,
            or sections the user did not request.
    """
    existing = await find_note_by_title(title, ctx.deps.note_repo)
    if existing is not None:
        note = await _update_note(existing.filename, content, ctx.deps.note_repo)
        if note is None:
            return f"Note not found: {existing.filename}"
        logger.info("create_note_updated_existing", filename=note.filename, title=title)
        return f"Note updated (was: {existing.filename}): {note.filename}"

    note = await save_note(title, content, ctx.deps.note_repo)
    logger.info("create_note_tool", filename=note.filename)
    return f"Note saved: {note.filename}"


@tool(category="📝 Notes")
async def search_notes(ctx: RunContext[AgentDeps], query: str) -> str:
    """Search notes by content (case-insensitive full-text search).

    Returns up to 10 matching notes showing the title, filename, and a
    200-character excerpt.

    Args:
        query: Word or phrase to search for across all notes.
    """
    results = await find_notes(query, ctx.deps.note_repo)
    if not results:
        return f"No notes found matching '{query}'."
    return "\n\n".join(f"**{n.title}** (`{n.filename}`)\n{n.content[:200]}..." for n in results)


@tool(category="📝 Notes")
async def read_note_by_name(ctx: RunContext[AgentDeps], filename: str) -> str:
    """Read the full content of a specific note by filename.

    Args:
        filename: Note filename (e.g. ``2025-01-15-my-note.md``).
    """
    note = await read_note(filename, ctx.deps.note_repo)
    if note is None:
        return f"Note not found: {filename}"
    return note.content


@tool(category="📝 Notes")
async def update_note(ctx: RunContext[AgentDeps], filename: str, content: str) -> str:
    """Edit an existing note in place without changing its filename.

    MANDATORY WORKFLOW — follow these steps in order:
    1. Call ``read_note_by_name(filename)`` to fetch the current content.
    2. Apply ONLY the change the user explicitly requested to that content.
    3. Pass the COMPLETE modified content (all original sections intact) to
       this tool.  Do not drop, summarise, or rewrite any section the user
       did not mention.

    The ``content`` parameter must be the ENTIRE note after your edit, not
    just the changed fragment.  This tool performs a full overwrite — any
    text you omit will be lost.

    Do NOT call this tool:
    - Without reading the note first.
    - With content that omits sections the user did not ask to change.
    - If the filename was not confirmed via ``list_notes_in_vault`` or
      ``search_notes`` (filenames are generated; never guess them).

    Args:
        filename: Exact note filename (e.g. ``2025-01-15-my-note.md``).
        content: The COMPLETE new content of the note, including all
            unmodified sections from the original.

    Returns:
        Confirmation message, or ``"Note not found: <filename>"`` if the
        file does not exist.
    """
    note = await _update_note(filename, content, ctx.deps.note_repo)
    if note is None:
        return f"Note not found: {filename}"
    logger.info("update_note_tool", filename=note.filename)
    return f"Note updated: {note.filename}"


@tool(category="📝 Notes")
async def list_notes_in_vault(ctx: RunContext[AgentDeps]) -> str:
    """List all notes in the vault, newest first (up to 20 shown)."""
    filenames = await list_notes(ctx.deps.note_repo)
    if not filenames:
        return "No notes saved yet."
    return "\n".join(f"- {f}" for f in filenames[:20])


@tool(category="📝 Notes")
async def delete_note(ctx: RunContext[AgentDeps], filename: str) -> str:
    """Request deletion of a note — the user must confirm before it is removed.

    Returns a sentinel string that triggers a Yes/No confirmation keyboard
    in Telegram.  Do NOT assume the note has been deleted until the user
    confirms.  Always use ``list_notes_in_vault`` or ``search_notes`` first
    to obtain the exact filename before calling this tool.

    Args:
        filename: Exact note filename (e.g. ``2025-01-15-my-note.md``).
    """
    logger.info("delete_note_requested", filename=filename)
    return f"{DELETE_CONFIRM_SENTINEL}:{filename}"
