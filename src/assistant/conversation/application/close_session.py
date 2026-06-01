from __future__ import annotations

import structlog
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter

from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.shared.exceptions import NoActiveSessionError

logger = structlog.get_logger()

_TITLE_PROMPT = (
    "Based on the conversation so far, generate a very short title of at most 5 words. "
    "Reply with ONLY the title — no quotes, no punctuation, no explanation."
)


async def close_active_session(
    user_id: int,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
    agent: Agent[None, str],
) -> str:
    """Close the active session for the user and return the generated title.

    Uses the LLM to generate a title from the conversation history.
    Falls back to "Untitled" if title generation fails.

    Raises NoActiveSessionError if no active session exists.
    """
    session = await session_repo.get_active_for_user(user_id)
    if session is None:
        raise NoActiveSessionError(f"No active session to close for user {user_id}")

    title = await _generate_title(session.message_history_json, agent)

    session.close(title=title)
    await session_repo.save(session)
    logger.info("close_session_closed", session_id=session.id, title=title, user_id=user_id)
    return title


async def _generate_title(
    history_json: bytes | None,
    agent: Agent[None, str],
) -> str:
    """Ask the LLM to produce a short title for the conversation.

    Returns "Untitled" on any failure so the close operation always succeeds.
    """
    if not history_json:
        return "Untitled"

    try:
        message_history = ModelMessagesTypeAdapter.validate_json(history_json)
        result = await agent.run(_TITLE_PROMPT, message_history=message_history)
        title = result.output.strip()[:100]
        return title if title else "Untitled"
    except Exception as exc:
        logger.warning("close_session_title_generation_failed", error=str(exc))
        return "Untitled"
