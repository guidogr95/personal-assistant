"""Telegram message formatting helpers.

Provides thin wrappers around aiogram send methods with the project's
default ``parse_mode="MarkdownV2"``.  Callers that build formatted text
programmatically should use the ``bold``, ``italic``, ``code``, etc.
helpers so variable content is safely escaped.  AI-generated replies are
passed through as-is (the model writes valid MarkdownV2).
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.utils.markdown import markdown_decoration  # type: ignore[attr-defined]

from assistant.telegram.constants import DEFAULT_PARSE_MODE


def bold(text: str) -> str:
    """Wrap text in MarkdownV2 bold markers."""
    return markdown_decoration.bold(text)


def italic(text: str) -> str:
    """Wrap text in MarkdownV2 italic markers."""
    return markdown_decoration.italic(text)


def code(text: str) -> str:
    """Wrap text in MarkdownV2 inline-code backticks."""
    return markdown_decoration.code(text)


def pre(text: str) -> str:
    """Wrap text in a MarkdownV2 pre-formatted code block."""
    return markdown_decoration.pre(text)


def link(text: str, url: str) -> str:
    """Build a MarkdownV2 hyperlink."""
    return markdown_decoration.link(text, url)


async def answer_markdown(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> Message:
    """Reply to a message using the default parse mode."""
    return await message.answer(text, parse_mode=DEFAULT_PARSE_MODE, reply_markup=reply_markup)


async def send_markdown(
    bot: Bot,
    chat_id: int,
    text: str,
) -> Message:
    """Send a message to a chat using the default parse mode.

    Use this from background jobs (e.g. check-ins) where there is no
    incoming ``Message`` to reply to.
    """
    return await bot.send_message(chat_id=chat_id, text=text, parse_mode=DEFAULT_PARSE_MODE)
