from __future__ import annotations

import structlog
from aiogram import Bot, Router
from aiogram.types import ErrorEvent

from assistant.shared.exceptions import AssistantError, LLMUnavailableError

logger = structlog.get_logger()

router = Router()

_GENERIC_ERROR_MESSAGE = "Something went wrong while processing your request. Please try again."


def _user_message_for(exc: Exception) -> str:
    """Map an exception to a Telegram-safe user-facing message.

    Specific domain errors surface meaningful context. Everything else gets a
    generic message so internal details are never exposed to the user.
    """
    if isinstance(exc, LLMUnavailableError):
        return f"\u26a0\ufe0f {exc.user_message}"
    if isinstance(exc, AssistantError):
        return _GENERIC_ERROR_MESSAGE
    return _GENERIC_ERROR_MESSAGE


@router.errors()
async def on_unhandled_error(event: ErrorEvent, bot: Bot) -> bool:
    """Global last-resort handler for any exception that escapes a handler.

    Sends a user-facing error message back via Telegram so the user is never
    left with no response. Returns True to mark the error as handled so
    aiogram stops propagation.
    """
    exc = event.exception
    update = event.update

    # Extract chat_id from whichever update type triggered the error
    chat_id: int | None = None
    if update.message and update.message.chat:
        chat_id = update.message.chat.id
    elif update.callback_query and update.callback_query.message:
        chat_id = update.callback_query.message.chat.id

    logger.error(
        "unhandled_update_error",
        exception_type=type(exc).__name__,
        exception=str(exc),
        chat_id=chat_id,
        update_id=update.update_id,
    )

    if chat_id is not None:
        try:
            await bot.send_message(chat_id, _user_message_for(exc))
        except Exception as send_exc:
            logger.error("error_reply_send_failed", send_error=str(send_exc))

    return True
