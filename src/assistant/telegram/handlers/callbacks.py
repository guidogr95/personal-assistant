from __future__ import annotations

from typing import cast

import structlog
from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from pydantic_ai import Agent

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import ToolCategory
from assistant.conversation.application.resume_session import resume_session
from assistant.conversation.domain.repositories import SessionRepository
from assistant.notes.application.delete_note import delete_note
from assistant.notes.domain.note_repository import NoteRepository
from assistant.shared.exceptions import InfrastructureError, SessionNotFoundError
from assistant.telegram.handlers.tool_commands import (
    _build_all_tools_markdown,
    _build_category_detail_markdown,
    _categorize_tools,
    _fetch_mcp_tools,
)
from assistant.telegram.keyboards import (
    build_tool_categories_keyboard,
    build_tools_in_category_keyboard,
    parse_session_callback,
    parse_tool_category_callback,
)
from assistant.telegram.markdown_to_html import convert_markdown_to_telegram_html
from assistant.telegram.pending_state import get_file_request, pending_deletions

logger = structlog.get_logger()

router = Router()


@router.callback_query(F.data == "delete:confirm")
async def on_delete_confirm(
    callback: CallbackQuery,
    note_repo: NoteRepository,
) -> None:
    """Execute the pending note deletion after the user confirms."""
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    filename = pending_deletions.pop(callback.from_user.id, None)
    if filename is None:
        await callback.answer(
            "No pending deletion found — the bot may have restarted.",
            show_alert=True,
        )
        return

    try:
        deleted = await delete_note(filename, note_repo)
    except InfrastructureError as exc:
        logger.error("delete_note_failed", filename=filename, error=str(exc))
        await callback.answer("Failed to delete the note. Check the logs.", show_alert=True)
        return

    if deleted:
        await callback.answer("Deleted.")
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                convert_markdown_to_telegram_html(f"🗑 **{filename}** has been deleted."),
                parse_mode="HTML",
            )
    else:
        await callback.answer("Note not found — it may have already been deleted.", show_alert=True)


@router.callback_query(F.data == "delete:cancel")
async def on_delete_cancel(callback: CallbackQuery) -> None:
    """Cancel the pending note deletion."""
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    pending_deletions.pop(callback.from_user.id, None)
    await callback.answer("Cancelled.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Deletion cancelled — note kept.", parse_mode="HTML")


@router.callback_query()
async def on_tool_category_tap(
    callback: CallbackQuery,
    agent: Agent[AgentDeps, str],
) -> None:
    """Handle taps on the /tools category inline keyboard.

    Shows tools in the selected category, returns to the category menu,
    or sends a compact "Show All" listing.
    """
    if not callback.data or not callback.message:
        await callback.answer()
        return

    parsed = parse_tool_category_callback(callback.data)
    if parsed is None:
        # Not a tool-category callback — let the next handler (session tap) try.
        return

    if parsed == ":back":
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                convert_markdown_to_telegram_html(
                    "**🛠️ Assistant Tools**\n\nTap a category to see the tools inside it:"
                ),
                parse_mode="HTML",
                reply_markup=build_tool_categories_keyboard(),
            )
        return

    if parsed == ":all":
        await callback.answer("Loading all tools…")
        try:
            python_tools = {
                name: (tool.description or "")
                for name, tool in agent._function_toolset.tools.items()
            }
        except AttributeError:
            logger.warning("agent_function_tools_unavailable")
            python_tools = {}
        mcp_tools = await _fetch_mcp_tools()
        categorized = _categorize_tools(python_tools, mcp_tools)
        chunks = _build_all_tools_markdown(categorized)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                convert_markdown_to_telegram_html(chunks[0]), parse_mode="HTML"
            )
            for extra_chunk in chunks[1:]:
                await callback.message.answer(
                    convert_markdown_to_telegram_html(extra_chunk), parse_mode="HTML"
                )
        return

    # Specific category selected
    category_name = parsed
    try:
        python_tools = {
            name: (tool.description or "") for name, tool in agent._function_toolset.tools.items()
        }
    except AttributeError:
        logger.warning("agent_function_tools_unavailable")
        python_tools = {}
    mcp_tools = await _fetch_mcp_tools()
    categorized = _categorize_tools(python_tools, mcp_tools)
    tools = categorized.get(cast(ToolCategory, category_name), [])

    if not tools:
        await callback.answer("No tools in this category.")
        return

    await callback.answer()
    markdown_text = _build_category_detail_markdown(category_name, tools)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            convert_markdown_to_telegram_html(markdown_text),
            parse_mode="HTML",
            reply_markup=build_tools_in_category_keyboard(category_name),
        )


@router.callback_query(F.data.startswith("file:note:"))
async def on_file_request(
    callback: CallbackQuery,
    note_repo: NoteRepository,
) -> None:
    """Send a note as a document when the user taps the file-request button."""
    if not callback.data or not callback.from_user or not callback.message:
        await callback.answer()
        return

    file_hash = callback.data.removeprefix("file:note:")
    filename = get_file_request(file_hash)
    if filename is None:
        await callback.answer(
            "File request expired or invalid. Please request the note again.",
            show_alert=True,
        )
        return

    note = await note_repo.read(filename)
    if note is None:
        await callback.answer("Note not found.", show_alert=True)
        return

    document = BufferedInputFile(
        file=note.content.encode("utf-8"),
        filename=note.filename,
    )
    await callback.message.answer_document(document)
    await callback.answer("File sent.")


@router.callback_query()
async def on_session_tap(
    callback: CallbackQuery,
    session_repo: SessionRepository,
) -> None:
    """Resume a session when the user taps it in the /sessions inline keyboard."""
    if not callback.data or not callback.from_user:
        await callback.answer()
        return

    session_id = parse_session_callback(callback.data)
    if session_id is None:
        await callback.answer()
        return

    try:
        await resume_session(
            user_id=callback.from_user.id,
            session_id=session_id,
            session_repo=session_repo,
        )
        await callback.answer("Session resumed.")
        if callback.message:
            await callback.message.answer("Session resumed. Send a message to continue.")
    except SessionNotFoundError:
        await callback.answer("Session not found.", show_alert=True)
