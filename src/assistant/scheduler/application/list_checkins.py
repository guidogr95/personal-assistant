from __future__ import annotations

from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn


async def list_all_checkins(repo: ScheduledCheckInRepository) -> list[ScheduledCheckIn]:
    """Return all registered check-ins ordered by creation time."""
    return await repo.list_all()
