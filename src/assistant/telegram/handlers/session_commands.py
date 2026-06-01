from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from assistant.agent.domain.agent import agent
from assistant.conversation.application import close_session, list_sessions, open_session
from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.shared.exceptions import NoActiveSessionError
from assistant.telegram.formatting import answer_markdown, bold
from assistant.telegram.keyboards import build_sessions_keyboard

logger = structlog.get_logger()

router = Router()

_HELP_TEXT = """<b>Available commands</b>

<b>Session management</b>
<code>/new</code> — start a fresh session (closes the active one)
<code>/close</code> — close the active session and generate a title
<code>/sessions</code> — show your 10 most recent sessions as a tappable list

<b>Check-ins</b> <i>(proactive scheduled messages)</i>
<code>/checkin list</code> — list all scheduled check-ins
<code>/checkin add &lt;name&gt; | &lt;cron&gt; | &lt;instructions&gt;</code> — schedule a check-in
<code>/checkin delete &lt;name&gt;</code> — remove a check-in
Cron example: <code>0 9 * * *</code> = every day at 09:00 UTC

<code>/help</code> — show this message

<i>Tip: you don't need slash commands for check-ins. Just say
"set up a daily check-in at 9am to summarise my tasks" and I'll handle it.</i>"""


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """List all available commands."""
    await answer_markdown(message, _HELP_TEXT)


@router.message(Command("new"))
async def cmd_new(
    message: Message,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
) -> None:
    """Start a fresh session, closing the current one if it exists."""
    if not message.from_user:
        return
    await open_session.open_session_for_user(
        user_id=message.from_user.id,
        session_repo=session_repo,
    )
    await message.answer("New session started.")


@router.message(Command("close"))
async def cmd_close(
    message: Message,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
) -> None:
    """Close the active session and display the generated title."""
    if not message.from_user:
        return
    try:
        title = await close_session.close_active_session(
            user_id=message.from_user.id,
            session_repo=session_repo,
            turn_repo=turn_repo,
            agent=agent,
        )
        await answer_markdown(message, f"Session closed: {bold(title)}")
    except NoActiveSessionError:
        await message.answer("No active session to close.")


@router.message(Command("sessions"))
async def cmd_sessions(
    message: Message,
    session_repo: SessionRepository,
) -> None:
    """Show the 10 most recent sessions as a tappable inline keyboard."""
    if not message.from_user:
        return
    sessions = await list_sessions.list_recent_sessions(
        user_id=message.from_user.id,
        session_repo=session_repo,
    )
    if not sessions:
        await message.answer("No sessions found.")
        return
    kb = build_sessions_keyboard(sessions)
    await message.answer("Recent sessions:", reply_markup=kb)
