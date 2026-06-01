from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = structlog.get_logger()


def create_scheduler() -> AsyncIOScheduler:
    """Create an in-memory AsyncIOScheduler.

    A persistent job store is not needed: all enabled check-ins are
    re-registered from the database on every startup, so in-memory scheduling
    is sufficient. Missed firings during downtime are silently skipped.
    """
    return AsyncIOScheduler(
        timezone="UTC",
        job_defaults={"misfire_grace_time": 60 * 5},  # re-fire up to 5 min late
    )


def register_checkin_job(
    scheduler: AsyncIOScheduler,
    checkin_id: str,
    cron_expr: str,
    job_func: Callable[[str], Awaitable[None]],
    timezone: ZoneInfo | None = None,
) -> None:
    """Add or replace a check-in job in the scheduler.

    Assumes cron_expr has already been validated by ScheduledCheckIn.__post_init__.
    Uses replace_existing=True so re-registration at startup is idempotent.

    Args:
        timezone: Timezone in which cron fields are interpreted.  Defaults to
            UTC (the scheduler's base timezone).  Pass the user's local
            ZoneInfo so that e.g. ``"0 9 * * *"`` fires at 9am local time.
    """
    minute, hour, day, month, day_of_week = cron_expr.strip().split()
    trigger = CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=timezone,
    )
    scheduler.add_job(
        job_func,
        trigger=trigger,
        args=[checkin_id],
        id=checkin_id,
        replace_existing=True,
    )
    logger.info("checkin_job_registered", checkin_id=checkin_id, cron_expr=cron_expr)


def register_one_off_job(
    scheduler: AsyncIOScheduler,
    checkin_id: str,
    fire_at: datetime,
    job_func: Callable[[str], Awaitable[None]],
) -> None:
    """Add or replace a one-off check-in job using a DateTrigger.

    Uses replace_existing=True so re-registration at startup is idempotent.
    """
    trigger = DateTrigger(run_date=fire_at)
    scheduler.add_job(
        job_func,
        trigger=trigger,
        args=[checkin_id],
        id=checkin_id,
        replace_existing=True,
    )
    logger.info("checkin_one_off_registered", checkin_id=checkin_id, fire_at=fire_at.isoformat())


def remove_checkin_job(scheduler: AsyncIOScheduler, checkin_id: str) -> None:
    """Remove a check-in job from the scheduler if it exists."""
    if scheduler.get_job(checkin_id):
        scheduler.remove_job(checkin_id)
        logger.info("checkin_job_removed", checkin_id=checkin_id)
