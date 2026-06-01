from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from assistant.scheduler.application.run_checkin import run_checkin
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.scheduler.infrastructure.apscheduler_registry import (
    register_checkin_job,
    register_one_off_job,
)

logger = structlog.get_logger()


async def register_checkin(
    name: str,
    instructions: str = "",
    message: str = "",
    cron_expr: str = "",
    fire_at: datetime | None = None,
    max_runs: int | None = None,
    timezone: ZoneInfo | None = None,
    repo: ScheduledCheckInRepository | None = None,
    scheduler: AsyncIOScheduler | None = None,
) -> ScheduledCheckIn:
    """Create a new ScheduledCheckIn, persist it, and register it with the scheduler.

    Args:
        name: Short label for the check-in.
        instructions: Agent instructions (for recurring agent-run check-ins).
        message: Direct message text (for one-off reminders).
        cron_expr: Standard 5-field cron expression (for recurring jobs).
        fire_at: Exact datetime to fire (for one-off jobs).
        max_runs: Maximum number of firings before auto-disable. None = infinite.
        timezone: Timezone used to interpret cron fields.  Defaults to UTC.
            Pass the user's local ZoneInfo so cron times fire at the expected
            local hour.
        repo: Check-in repository.
        scheduler: APScheduler instance.

    Raises:
        ValueError: If entity validation fails (propagated from __post_init__).
        RuntimeError: If repo or scheduler is None.
    """
    if repo is None or scheduler is None:
        raise RuntimeError("repo and scheduler are required")

    if fire_at is not None and fire_at <= datetime.now(UTC):
        raise ValueError("fire_at must be in the future")

    checkin = ScheduledCheckIn(
        name=name,
        instructions=instructions,
        message=message,
        cron_expr=cron_expr,
        fire_at=fire_at,
        max_runs=max_runs,
        cron_timezone=str(timezone) if timezone else None,
    )
    await repo.save(checkin)

    if checkin.cron_expr:
        register_checkin_job(
            scheduler, checkin.id, checkin.cron_expr, run_checkin, timezone=timezone
        )
    elif checkin.fire_at:
        register_one_off_job(scheduler, checkin.id, checkin.fire_at, run_checkin)

    logger.info(
        "checkin_registered",
        checkin_id=checkin.id,
        name=name,
        cron_expr=cron_expr,
        fire_at=fire_at.isoformat() if fire_at else None,
        timezone=str(timezone) if timezone else "UTC",
    )
    return checkin
