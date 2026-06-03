"""Telegram message formatting helpers and unified sender.

Provides Markdown-producing helpers (bold, italic, code, pre, link) and a
unified ``send_message()`` gateway that converts Markdown to Telegram-safe
HTML, handles length limits, and supports file-request fallbacks for long
content.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from assistant.telegram.markdown_to_html import convert_markdown_to_telegram_html
from assistant.telegram.pending_state import store_file_request

# Telegram text message hard limit is 4096 characters; we use a safety margin.
_MAX_MESSAGE_LENGTH: int = 3_800


def bold(text: str) -> str:
    """Wrap text in Markdown bold, escaping existing asterisks."""
    escaped = text.replace("*", "\\*").replace("_", "\\_")
    return f"**{escaped}**"


def italic(text: str) -> str:
    """Wrap text in Markdown italic, escaping existing underscores."""
    escaped = text.replace("*", "\\*").replace("_", "\\_")
    return f"*{escaped}*"


def code(text: str) -> str:
    """Wrap text in Markdown inline code, escaping backticks."""
    escaped = text.replace("`", "\\`")
    return f"`{escaped}`"


def pre(text: str) -> str:
    """Wrap text in a Markdown pre-formatted code block."""
    return f"```\n{text}\n```"


def link(text: str, url: str) -> str:
    """Build a Markdown hyperlink."""
    escaped_text = text.replace("]", "\\]")
    return f"[{escaped_text}]({url})"


def _generate_file_request_hash(text: str, filename: str) -> str:
    """Generate a short deterministic hash for a file request."""
    content = f"{text}:{filename}:{datetime.now(UTC).isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _truncate_to_safe_boundary(text: str, max_length: int) -> str:
    """Truncate text to max_length at the last safe boundary.

    Prefers end-of-line, then end-of-tag, then word boundary.
    """
    if len(text) <= max_length:
        return text

    search_start = max(max_length - 100, 0)

    # Priority 1: end of line
    for i in range(max_length - 1, search_start, -1):
        if text[i] == "\n":
            return text[:i].rstrip() + "\n\n… (truncated)"

    # Priority 2: end of HTML tag
    for i in range(max_length - 1, search_start, -1):
        if text[i] == ">":
            return text[: i + 1] + "\n\n… (truncated)"

    # Priority 3: word boundary (space)
    for i in range(max_length - 1, search_start, -1):
        if text[i] == " ":
            return text[:i] + " … (truncated)"

    # Fallback: hard truncate
    return text[:max_length] + "… (truncated)"


async def send_message(
    message_or_bot: Message | Bot,
    text: str,
    chat_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    source_filename: str | None = None,
) -> list[Message]:
    """Unified sender: converts Markdown to HTML, handles length, sends.

    Accepts either a ``Message`` (for replies) or a ``Bot`` + ``chat_id``
    (for background jobs). Converts Markdown to Telegram-safe HTML,
    checks length, and either sends as a single message or truncates
    with a "Get full file" button when ``source_filename`` is provided.

    Args:
        message_or_bot: Either a ``Message`` to reply to, or a ``Bot`` instance.
        text: Markdown text to send.
        chat_id: Required when ``message_or_bot`` is a ``Bot``.
        reply_markup: Optional inline keyboard markup.
        source_filename: Optional note filename for long-text file requests.

    Returns:
        List of sent messages (usually one).

    Raises:
        ValueError: If ``Bot`` is passed without ``chat_id``.
    """
    html_text = convert_markdown_to_telegram_html(text)

    if len(html_text) <= _MAX_MESSAGE_LENGTH:
        return await _send_single_message(message_or_bot, html_text, chat_id, reply_markup)

    truncated_html = _truncate_to_safe_boundary(html_text, _MAX_MESSAGE_LENGTH)

    if source_filename and reply_markup is None:
        file_hash = _generate_file_request_hash(text, source_filename)
        store_file_request(file_hash, source_filename)

        builder = InlineKeyboardBuilder()
        builder.button(
            text="📄 Get full content as file",
            callback_data=f"file:note:{file_hash}",
        )
        file_markup = builder.as_markup()
        return await _send_single_message(message_or_bot, truncated_html, chat_id, file_markup)

    return await _send_single_message(message_or_bot, truncated_html, chat_id, reply_markup)


async def _send_single_message(
    message_or_bot: Message | Bot,
    html_text: str,
    chat_id: int | None,
    reply_markup: InlineKeyboardMarkup | None,
) -> list[Message]:
    """Send a single HTML message, falling back to plain text on parse error."""
    try:
        if isinstance(message_or_bot, Message):
            sent = await message_or_bot.answer(
                html_text, parse_mode="HTML", reply_markup=reply_markup
            )
            return [sent]
        if isinstance(message_or_bot, Bot):
            if chat_id is None:
                raise ValueError("chat_id is required when sending via Bot")
            sent = await message_or_bot.send_message(
                chat_id=chat_id,
                text=html_text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return [sent]
        raise TypeError(
            f"Expected Message or Bot, got {type(message_or_bot).__name__}"
        )
    except TelegramBadRequest:
        plain_text = re.sub(r"<[^>]+>", "", html_text)
        if isinstance(message_or_bot, Message):
            sent = await message_or_bot.answer(plain_text, reply_markup=reply_markup)
            return [sent]
        if isinstance(message_or_bot, Bot):
            if chat_id is None:
                raise ValueError("chat_id is required when sending via Bot") from None
            sent = await message_or_bot.send_message(
                chat_id=chat_id,
                text=plain_text,
                reply_markup=reply_markup,
            )
            return [sent]
        raise TypeError(
            f"Expected Message or Bot, got {type(message_or_bot).__name__}"
        ) from None
