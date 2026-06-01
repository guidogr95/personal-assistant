from __future__ import annotations

from abc import ABC, abstractmethod

from assistant.conversation.domain.session import Session
from assistant.conversation.domain.turn import Turn


class SessionRepository(ABC):
    """Persistence interface for Session aggregates.

    Implementations live in infrastructure/. The domain layer depends only on
    this interface — never on aiosqlite, SQLAlchemy, or any storage driver.
    """

    @abstractmethod
    async def save(self, session: Session) -> None:
        """Insert or update the session record."""
        ...

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Session | None:
        """Return the session with the given ID, or None if not found."""
        ...

    @abstractmethod
    async def get_active_for_user(self, user_id: int) -> Session | None:
        """Return the single active session for the user, or None."""
        ...

    @abstractmethod
    async def list_recent(self, user_id: int, limit: int = 10) -> list[Session]:
        """Return the most recently active sessions for the user, newest first."""
        ...


class TurnRepository(ABC):
    """Persistence interface for Turn value objects."""

    @abstractmethod
    async def save(self, turn: Turn) -> None:
        """Append a new turn record."""
        ...

    @abstractmethod
    async def list_for_session(self, session_id: str) -> list[Turn]:
        """Return all turns for the session in chronological order."""
        ...
