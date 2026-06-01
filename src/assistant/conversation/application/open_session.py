from __future__ import annotations

import structlog

from assistant.conversation.domain.repositories import SessionRepository
from assistant.conversation.domain.session import Session

logger = structlog.get_logger()


async def open_session_for_user(
    user_id: int,
    session_repo: SessionRepository,
) -> Session:
    """Create a new active session for the user.

    If the user already has an active session, it is closed with the title
    "Untitled" before the new session is created. This makes /new always safe
    to call without requiring the caller to close the previous session first.
    """
    existing = await session_repo.get_active_for_user(user_id)
    if existing is not None:
        existing.close(title=existing.title or "Untitled")
        await session_repo.save(existing)
        logger.info("open_session_closed_previous", session_id=existing.id, user_id=user_id)

    new_session = Session(user_id=user_id)
    await session_repo.save(new_session)
    logger.info("open_session_created", session_id=new_session.id, user_id=user_id)
    return new_session
