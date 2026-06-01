from __future__ import annotations

import structlog

from assistant.conversation.domain.repositories import SessionRepository
from assistant.conversation.domain.session import Session
from assistant.shared.exceptions import SessionNotFoundError

logger = structlog.get_logger()


async def resume_session(
    user_id: int,
    session_id: str,
    session_repo: SessionRepository,
) -> Session:
    """Make the target session the single active session for the user.

    Closes any currently active session (with its existing title or "Untitled"),
    then reopens the target session. Message history is preserved on the target.

    Raises SessionNotFoundError if the target session does not exist.
    """
    current_active = await session_repo.get_active_for_user(user_id)
    if current_active is not None and current_active.id != session_id:
        current_active.close(title=current_active.title or "Untitled")
        await session_repo.save(current_active)
        logger.info(
            "resume_session_closed_previous",
            closed_id=current_active.id,
            user_id=user_id,
        )

    target = await session_repo.get_by_id(session_id)
    if target is None:
        raise SessionNotFoundError(f"Session {session_id} not found")

    if not target.is_active:
        target.reopen()
        await session_repo.save(target)

    logger.info("resume_session_resumed", session_id=target.id, user_id=user_id)
    return target
