from __future__ import annotations

from assistant.conversation.domain.repositories import SessionRepository
from assistant.conversation.domain.session import Session


async def list_recent_sessions(
    user_id: int,
    session_repo: SessionRepository,
    limit: int = 10,
) -> list[Session]:
    """Return the most recently active sessions for the user."""
    return await session_repo.list_recent(user_id=user_id, limit=limit)
