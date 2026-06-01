from __future__ import annotations

from abc import ABC, abstractmethod

from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn


class ScheduledCheckInRepository(ABC):
    """Persistence interface for ScheduledCheckIn entities.

    Implementations live in infrastructure/. The domain layer depends only on
    this interface — never on aiosqlite or any storage driver.
    """

    @abstractmethod
    async def save(self, checkin: ScheduledCheckIn) -> None:
        """Insert or update a check-in record."""
        ...

    @abstractmethod
    async def get_by_id(self, checkin_id: str) -> ScheduledCheckIn | None:
        """Return the check-in with the given ID, or None if not found."""
        ...

    @abstractmethod
    async def find_by_name(self, name: str) -> ScheduledCheckIn | None:
        """Return the check-in with the given name, or None if not found."""
        ...

    @abstractmethod
    async def list_all(self) -> list[ScheduledCheckIn]:
        """Return all check-ins ordered by created_at ascending."""
        ...

    @abstractmethod
    async def update(self, checkin: ScheduledCheckIn) -> None:
        """Update an existing check-in record (full replace)."""
        ...

    @abstractmethod
    async def delete(self, checkin_id: str) -> None:
        """Permanently remove a check-in record."""
        ...
