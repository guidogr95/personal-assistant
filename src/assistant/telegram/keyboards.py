from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from assistant.conversation.domain.session import Session

_SESSION_CALLBACK_PREFIX = "session:"
_DELETE_CALLBACK_CONFIRM = "delete:confirm"
_DELETE_CALLBACK_CANCEL = "delete:cancel"


def build_sessions_keyboard(sessions: list[Session]) -> InlineKeyboardMarkup:
    """Build an inline keyboard where each button resumes a session on tap."""
    builder = InlineKeyboardBuilder()
    for session in sessions:
        label = session.title or f"Session {session.id[:8]}…"
        builder.button(text=label, callback_data=f"{_SESSION_CALLBACK_PREFIX}{session.id}")
    builder.adjust(1)
    return builder.as_markup()


def parse_session_callback(data: str) -> str | None:
    """Extract the session ID from a callback data string.

    Returns None if the data does not match the expected prefix.
    """
    if data.startswith(_SESSION_CALLBACK_PREFIX):
        return data[len(_SESSION_CALLBACK_PREFIX) :]
    return None


def build_delete_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Build a Yes/No inline keyboard for note deletion confirmation."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes, delete it", callback_data=_DELETE_CALLBACK_CONFIRM)
    builder.button(text="❌ No, keep it", callback_data=_DELETE_CALLBACK_CANCEL)
    builder.adjust(2)
    return builder.as_markup()


def is_delete_confirm_callback(data: str) -> bool:
    """Return True if the callback data represents a delete confirmation."""
    return data == _DELETE_CALLBACK_CONFIRM


def is_delete_cancel_callback(data: str) -> bool:
    """Return True if the callback data represents a delete cancellation."""
    return data == _DELETE_CALLBACK_CANCEL
