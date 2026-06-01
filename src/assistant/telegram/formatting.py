"""Telegram message formatting helpers.

Provides thin wrappers around aiogram send methods with the project's
default ``parse_mode="HTML"``.  Callers that build formatted text
programmatically should use the ``bold``, ``italic``, ``code``, etc.
helpers so variable content is safely escaped via ``html.escape()``.
AI-generated replies are passed through as-is — the LLM is instructed
to produce Telegram HTML tags directly.
"""

from __future__ import annotations

import html

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message

from assistant.telegram.constants import DEFAULT_PARSE_MODE


def bold(text: str) -> str:
    """Wrap escaped text in an HTML bold tag."""
    return f"<b>{html.escape(text)}</b>"


def italic(text: str) -> str:
    """Wrap escaped text in an HTML italic tag."""
    return f"<i>{html.escape(text)}</i>"


def code(text: str) -> str:
    """Wrap escaped text in an HTML inline-code tag."""
    return f"<code>{html.escape(text)}</code>"


def pre(text: str) -> str:
    """Wrap escaped text in an HTML pre-formatted block."""
    return f"<pre>{html.escape(text)}</pre>"


def link(text: str, url: str) -> str:
    """Build an HTML hyperlink. URL is not escaped — callers must supply safe URLs."""
    return f'<a href="{url}">{html.escape(text)}</a>'


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
