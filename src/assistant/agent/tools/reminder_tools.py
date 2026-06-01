"""Agent tools for setting reminders."""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic_ai import Agent, RunContext

from assistant.scheduler.application.parse_reminder_time import parse_reminder_time
from assistant.scheduler.application.register_checkin import register_checkin
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository

logger = structlog.get_logger()

# Injected at startup
_checkin_repo: ScheduledCheckInRepository | None = None
_scheduler: AsyncIOScheduler | None = None


def configure_reminder_tools(
    *,
    scheduler: AsyncIOScheduler,
    checkin_repo: ScheduledCheckInRepository,
) -> None:
    """Inject runtime dependencies before the agent handles any messages."""
    global _checkin_repo, _scheduler
    _checkin_repo = checkin_repo
    _scheduler = scheduler


def register_reminder_tools(agent: Agent[None, str]) -> None:
    """Register reminder tools on the agent.

    Adds ``set_reminder`` — creates a one-off or recurring reminder from
    natural-language time expressions.
    """

    @agent.tool
    async def set_reminder(ctx: RunContext[None], time_expr: str, message: str) -> str:
        """Set a reminder that sends a message at the specified time.

        Always call ``get_current_time`` first.  The time expression is parsed
        relative to the current server time, so you must know the current time
        and timezone before interpreting expressions like "in 30 minutes" or
        "tomorrow at 9am".  Do not guess the current time.

        The bot will send the reminder message to Telegram automatically without
        any user prompt.  The time expression can be one-off or recurring.

        Examples of time_expr (use the timezone from get_current_time):
        - "in 30 minutes"        → one-off reminder 30 minutes from now
        - "in 2 hours"           → one-off reminder 2 hours from now
        - "tomorrow at 9am"      → one-off reminder at 09:00 tomorrow (local)
        - "next Monday at 8am"   → one-off reminder next Monday 08:00 (local)
        - "at 15:30 today"       → one-off reminder at 15:30 today (local)
        - "every day at 9am"     → recurring daily reminder at 09:00 (local)
        - "every weekday at 8am" → recurring Monday–Friday at 08:00 (local)

        Args:
            time_expr: Natural language time expression (see examples above).
                Include the timezone context from get_current_time if relevant.
            message: The reminder text to send when the time arrives.
        """
        repo = _checkin_repo
        sched = _scheduler
        if repo is None or sched is None:
            return "Reminder tools are not configured."

        try:
            fire_at, cron_expr = parse_reminder_time(time_expr)
        except ValueError as exc:
            return f"Couldn't parse time expression: {exc}"

        try:
            await register_checkin(
                name=f"Reminder: {message[:30]}",
                message=message,
                cron_expr=cron_expr or "",
                fire_at=fire_at,
                max_runs=1 if fire_at else None,
                repo=repo,
                scheduler=sched,
            )
        except (ValueError, RuntimeError) as exc:
            logger.warning("set_reminder_failed", time_expr=time_expr, error=str(exc))
            return f"Couldn't set reminder: {exc}"

        if fire_at:
            return f"Reminder set for {fire_at.strftime('%Y-%m-%d %H:%M')} UTC: '{message}'"
        return f"Recurring reminder scheduled (`{cron_expr}` UTC): '{message}'"
