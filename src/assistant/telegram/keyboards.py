from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from assistant.conversation.domain.session import Session

_SESSION_CALLBACK_PREFIX = "session:"
_DELETE_CALLBACK_CONFIRM = "delete:confirm"
_DELETE_CALLBACK_CANCEL = "delete:cancel"

_TOOL_CATEGORY_PREFIX = "toolcat:"
_TOOL_BACK_CALLBACK = "toolcat:back"
_TOOL_SHOW_ALL_CALLBACK = "toolcat:all"

# Mapping of display emoji+name to the list of tool names that belong there.
# Tools not in any list are placed in "📦 Other" at runtime.
_TOOL_CATEGORIES: dict[str, list[str]] = {
    "🕐 Time": ["get_current_time"],
    "🔍 Research": ["search", "fetch_url"],
    "📝 Notes": [
        "create_note",
        "search_notes",
        "read_note_by_name",
        "update_note",
        "list_notes_in_vault",
        "delete_note",
    ],
    "✅ Tasks": ["add_task", "get_open_tasks", "mark_task_done"],
    "⏰ Check-ins": ["schedule_checkin", "list_scheduled_checkins", "remove_checkin"],
    "🔔 Reminders": ["set_reminder"],
    "🎬 Video": ["get_video_transcript", "get_transcription_queue_status"],
    "⚙️ System": ["show_system_prompt", "update_system_prompt"],
}


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


def build_tool_categories_keyboard() -> InlineKeyboardMarkup:
    """Build an inline keyboard for browsing tool categories.

    Each button selects a category; tapping it shows the tools in that category.
    A "📋 Show All" button sends a compact text listing of every tool.
    """
    builder = InlineKeyboardBuilder()
    for category_name in _TOOL_CATEGORIES:
        builder.button(
            text=category_name,
            callback_data=f"{_TOOL_CATEGORY_PREFIX}{category_name}",
        )
    builder.button(text="📋 Show All", callback_data=_TOOL_SHOW_ALL_CALLBACK)
    builder.adjust(2)
    return builder.as_markup()


def build_tools_in_category_keyboard(category_name: str) -> InlineKeyboardMarkup:
    """Build a keyboard with a single 🔙 Back button for returning to categories."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Back to categories", callback_data=_TOOL_BACK_CALLBACK)
    builder.adjust(1)
    return builder.as_markup()


def parse_tool_category_callback(data: str) -> str | None:
    """Extract the category name from a tool-category callback data string.

    Returns ``None`` if the data does not match the expected prefix.
    Special values:
    - ``":back"`` → user pressed the Back button
    - ``":all"`` → user pressed Show All
    """
    if data == _TOOL_BACK_CALLBACK:
        return ":back"
    if data == _TOOL_SHOW_ALL_CALLBACK:
        return ":all"
    if data.startswith(_TOOL_CATEGORY_PREFIX):
        return data[len(_TOOL_CATEGORY_PREFIX) :]
    return None
