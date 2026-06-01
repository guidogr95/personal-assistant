from __future__ import annotations

import structlog
from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from assistant.conversation.application.resume_session import resume_session
from assistant.conversation.domain.repositories import SessionRepository
from assistant.notes.application.delete_note import delete_note
from assistant.notes.infrastructure.markdown_repository import MarkdownNoteRepository
from assistant.shared.exceptions import InfrastructureError, SessionNotFoundError
from assistant.telegram.keyboards import parse_session_callback
from assistant.telegram.pending_state import pending_deletions

logger = structlog.get_logger()

router = Router()

_note_repo = MarkdownNoteRepository()


@router.callback_query(F.data == "delete:confirm")
async def on_delete_confirm(callback: CallbackQuery) -> None:
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
        deleted = await delete_note(filename, _note_repo)
    except InfrastructureError as exc:
        logger.error("delete_note_failed", filename=filename, error=str(exc))
        await callback.answer("Failed to delete the note. Check the logs.", show_alert=True)
        return

    if deleted:
        await callback.answer("Deleted.")
        if isinstance(callback.message, Message):
            await callback.message.edit_text(f"🗑 *{filename}* has been deleted.")
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
        await callback.message.edit_text("Deletion cancelled — note kept.")


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
