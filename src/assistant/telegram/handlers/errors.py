from __future__ import annotations

import structlog
from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

from assistant.shared.exceptions import AssistantError, LLMUnavailableError
from assistant.telegram.formatting import send_message

logger = structlog.get_logger()

router = Router()

_GENERIC_ERROR_MESSAGE = "Something went wrong while processing your request. Please try again."


def _user_message_for(exc: Exception) -> str:
    """Map an exception to a Telegram-safe user-facing message.

    Specific domain errors and external API errors surface meaningful context.
    Unexpected internal exceptions get a generic message so stack traces and
    internal paths are never exposed to the user.
    """
    if isinstance(exc, LLMUnavailableError):
        return f"⚠️ {exc.user_message}"
    if isinstance(exc, TelegramBadRequest):
        # Telegram errors are safe to forward — they come from the external API
        # and contain no internal application details.
        return f"⚠️ Telegram: {exc.message}"
    if isinstance(exc, AssistantError):
        # Domain errors carry user-safe messages constructed by the application.
        return f"⚠️ {exc}"
    # Truly unexpected exception — keep generic but hint at the error type
    # so the operator (the user) knows roughly what failed.
    return f"{_GENERIC_ERROR_MESSAGE} (Error type: {type(exc).__name__})"


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

    if not isinstance(exc, (AssistantError, TelegramBadRequest)):
        # Log full traceback for unexpected exceptions — these are bugs.
        logger.exception("unexpected_exception_traceback")

    if chat_id is not None:
        try:
            await send_message(bot, _user_message_for(exc), chat_id=chat_id)
        except Exception as send_exc:
            logger.error("error_reply_send_failed", send_error=str(send_exc))

    return True
