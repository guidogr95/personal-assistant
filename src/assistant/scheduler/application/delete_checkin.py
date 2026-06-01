from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.infrastructure.apscheduler_registry import remove_checkin_job
from assistant.shared.exceptions import CheckInNotFoundError

logger = structlog.get_logger()


async def delete_checkin_by_name(
    name: str,
    repo: ScheduledCheckInRepository,
    scheduler: AsyncIOScheduler,
) -> None:
    """Delete a check-in by name and remove its scheduled job.

    Raises CheckInNotFoundError if no check-in with that name exists.
    """
    checkin = await repo.find_by_name(name)
    if checkin is None:
        raise CheckInNotFoundError(f"Check-in '{name}' not found")

    await repo.delete(checkin.id)
    remove_checkin_job(scheduler, checkin.id)
    logger.info("checkin_deleted", checkin_id=checkin.id, name=name)
