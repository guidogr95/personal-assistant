from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.types import Message

from assistant.agent.application.run_turn import run_turn
from assistant.agent.tools.notes_tools import DELETE_CONFIRM_SENTINEL
from assistant.conversation.application.open_session import open_session_for_user
from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.prompts.domain.prompt_repository import PromptRepository
from assistant.shared.exceptions import NoActiveSessionError
from assistant.telegram.keyboards import build_delete_confirmation_keyboard
from assistant.telegram.pending_state import pending_deletions

logger = structlog.get_logger()

router = Router()


@router.message()
async def on_message(
    message: Message,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
    prompt_repo: PromptRepository,
) -> None:
    """Route a plain user message through the agent and reply."""
    if not message.text or not message.from_user:
        return

    user_id = message.from_user.id

    try:
        reply = await run_turn(
            user_id=user_id,
            user_message=message.text,
            session_repo=session_repo,
            turn_repo=turn_repo,
            prompt_repo=prompt_repo,
        )
    except NoActiveSessionError:
        # First message ever or after all sessions were closed: auto-create a session.
        await open_session_for_user(user_id=user_id, session_repo=session_repo)
        reply = await run_turn(
            user_id=user_id,
            user_message=message.text,
            session_repo=session_repo,
            turn_repo=turn_repo,
            prompt_repo=prompt_repo,
        )

    # Try Markdown first; fall back to plain text if the reply contains
    # characters that break Telegram's parser.
    delete_prefix = DELETE_CONFIRM_SENTINEL + ":"
    if reply.startswith(delete_prefix):
        filename = reply[len(delete_prefix) :]
        pending_deletions[message.from_user.id] = filename
        await message.answer(
            f"Delete *{filename}*? This cannot be undone.",
            parse_mode="Markdown",
            reply_markup=build_delete_confirmation_keyboard(),
        )
        return

    try:
        await message.answer(reply, parse_mode="Markdown")
    except Exception:
        logger.warning("markdown_parse_failed_falling_back_to_plain_text")
        await message.answer(reply)
