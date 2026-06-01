"""Agent tools for the Markdown notes vault."""

from __future__ import annotations

import structlog
from pydantic_ai import Agent, RunContext

from assistant.notes.application.find_notes import find_notes
from assistant.notes.application.list_notes import list_notes
from assistant.notes.application.read_note import read_note
from assistant.notes.application.save_note import save_note
from assistant.notes.application.update_note import update_note as _update_note
from assistant.notes.infrastructure.markdown_repository import MarkdownNoteRepository

logger = structlog.get_logger()

# Sentinel prefix returned by delete_note to trigger a Telegram confirmation
# keyboard.  The message handler detects this prefix and does NOT echo the
# raw string to the user.
DELETE_CONFIRM_SENTINEL = "__CONFIRM_DELETE__"

# Module-level instance: vault path comes from settings at import time.
_repo = MarkdownNoteRepository()


def register_notes_tools(agent: Agent[None, str]) -> None:
    """Register Markdown-vault tools on the agent.

    Adds four tools: ``create_note``, ``search_notes``, ``read_note_by_name``,
    and ``list_notes``.
    """

    @agent.tool
    async def create_note(ctx: RunContext[None], title: str, content: str) -> str:
        """Create a new Markdown note in the vault.

        Args:
            title: Short descriptive title (becomes the H1 heading and filename).
            content: Note body in Markdown format.
        """
        note = await save_note(title, content, _repo)
        logger.info("create_note_tool", filename=note.filename)
        return f"Note saved: {note.filename}"

    @agent.tool
    async def search_notes(ctx: RunContext[None], query: str) -> str:
        """Search notes by content (case-insensitive full-text search).

        Returns up to 10 matching notes showing the title, filename, and a
        200-character excerpt.

        Args:
            query: Word or phrase to search for across all notes.
        """
        results = await find_notes(query, _repo)
        if not results:
            return f"No notes found matching '{query}'."
        return "\n\n".join(f"**{n.title}** (`{n.filename}`)\n{n.content[:200]}..." for n in results)

    @agent.tool
    async def read_note_by_name(ctx: RunContext[None], filename: str) -> str:
        """Read the full content of a specific note by filename.

        Args:
            filename: Note filename (e.g. ``2025-01-15-my-note.md``).
        """
        note = await read_note(filename, _repo)
        if note is None:
            return f"Note not found: {filename}"
        return note.content

    @agent.tool
    async def update_note(ctx: RunContext[None], filename: str, content: str) -> str:
        """Edit an existing note in place without changing its filename.

        Use this when the user wants to change the content of a note they
        already created.  The filename stays the same; only the content is
        overwritten.

        Args:
            filename: Exact note filename (e.g. ``2025-01-15-my-note.md``).
            content: New Markdown content for the note.

        Returns:
            Confirmation message, or ``"Note not found: <filename>"`` if the
            file does not exist.
        """
        note = await _update_note(filename, content, _repo)
        if note is None:
            return f"Note not found: {filename}"
        logger.info("update_note_tool", filename=note.filename)
        return f"Note updated: {note.filename}"

    @agent.tool
    async def list_notes_in_vault(ctx: RunContext[None]) -> str:
        """List all notes in the vault, newest first (up to 20 shown)."""
        filenames = await list_notes(_repo)
        if not filenames:
            return "No notes saved yet."
        return "\n".join(f"- {f}" for f in filenames[:20])

    @agent.tool
    async def delete_note(ctx: RunContext[None], filename: str) -> str:
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
