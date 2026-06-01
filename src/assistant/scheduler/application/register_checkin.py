from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from assistant.scheduler.application.run_checkin import run_checkin
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.scheduler.infrastructure.apscheduler_registry import register_checkin_job

logger = structlog.get_logger()


async def register_checkin(
    name: str,
    cron_expr: str,
    instructions: str,
    repo: ScheduledCheckInRepository,
    scheduler: AsyncIOScheduler,
) -> ScheduledCheckIn:
    """Create a new ScheduledCheckIn, persist it, and register it with the scheduler.

    Raises ValueError if name, instructions, or cron_expr are invalid
    (propagated from ScheduledCheckIn.__post_init__). The repo is not written
    to if entity construction fails.
    """
    checkin = ScheduledCheckIn(name=name, cron_expr=cron_expr, instructions=instructions)
    await repo.save(checkin)
    register_checkin_job(scheduler, checkin.id, checkin.cron_expr, run_checkin)
    logger.info("checkin_registered", checkin_id=checkin.id, name=name, cron_expr=cron_expr)
    return checkin
