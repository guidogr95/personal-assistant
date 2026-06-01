"""Agent tools for managing proactive check-ins."""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic_ai import Agent, RunContext

from assistant.scheduler.application import delete_checkin, list_checkins, register_checkin
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.shared.exceptions import CheckInNotFoundError

logger = structlog.get_logger()

# Injected once at startup by configure_checkin_tools before the agent is used.
_scheduler: AsyncIOScheduler | None = None
_checkin_repo: ScheduledCheckInRepository | None = None


def configure_checkin_tools(
    *,
    scheduler: AsyncIOScheduler,
    checkin_repo: ScheduledCheckInRepository,
) -> None:
    """Inject runtime dependencies before the agent handles any messages.

    Must be called exactly once during application startup.
    """
    global _scheduler, _checkin_repo
    _scheduler = scheduler
    _checkin_repo = checkin_repo


def register_checkin_tools(agent: Agent[None, str]) -> None:
    """Register check-in management tools on the agent.

    Adds three tools: ``schedule_checkin``, ``list_scheduled_checkins``, and
    ``remove_checkin``. All tools return a user-facing string — they never raise.
    """

    @agent.tool
    async def schedule_checkin(
        ctx: RunContext[None],
        name: str,
        instructions: str = "",
        message: str = "",
        cron_expr: str = "",
        fire_at: str = "",
        max_runs: int | None = None,
    ) -> str:
        """Schedule a proactive check-in or one-off reminder.

        The bot will send output to Telegram automatically on the given schedule.

        Always call ``get_current_time`` first.  All times are stored in UTC.
        Use the offset reported by ``get_current_time`` to convert the user's
        local time to UTC before setting ``cron_expr`` or ``fire_at``.
        Do not guess the current time or timezone offset.

        Args:
            name: Short label for the check-in (e.g. "Morning Tasks").
            instructions: What the assistant should do when the check-in fires.
                Use this for agent-run check-ins. Example:
                "Summarise my open Vikunja tasks and flag any overdue ones."
            message: Direct message text to send (no LLM cost). Use this for
                simple reminders. Example: "Call mom" or "Drink water".
            cron_expr: Standard 5-field cron expression for recurring jobs (UTC).
                - "every day at 9am local"   → convert to UTC, e.g. "0 13 * * *"
                - "every weekday at 8am"     → "0 8 * * 1-5" (after UTC conversion)
                - "every Monday at 10am"     → "0 10 * * 1" (after UTC conversion)
                - "every hour"               → "0 * * * *"
            fire_at: ISO-8601 datetime (UTC) for a one-off job. Use this OR
                cron_expr, not both. Example: "2026-06-01T14:30:00".
            max_runs: Maximum number of times this check-in fires before
                auto-disabling. None = infinite. Set to 1 for one-off reminders.
        """
        scheduler = _scheduler
        checkin_repo = _checkin_repo
        if scheduler is None or checkin_repo is None:
            return (
                "Check-in tools are not configured. This is a startup bug — contact the developer."
            )

        # Parse fire_at string to datetime if provided
        from datetime import datetime as _dt

        fire_at_dt: _dt | None = None
        if fire_at.strip():
            try:
                fire_at_dt = _dt.fromisoformat(fire_at.strip())
            except ValueError:
                return f"Invalid fire_at datetime: '{fire_at}'. Use ISO-8601 format."

        try:
            checkin = await register_checkin.register_checkin(
                name=name,
                instructions=instructions,
                message=message,
                cron_expr=cron_expr,
                fire_at=fire_at_dt,
                max_runs=max_runs,
                repo=checkin_repo,
                scheduler=scheduler,
            )
        except ValueError as exc:
            logger.warning("schedule_checkin_tool_invalid", name=name, error=str(exc))
            return f"Couldn't schedule check-in: {exc}"

        if checkin.fire_at:
            return (
                f"Check-in '{checkin.name}' scheduled for "
                f"{checkin.fire_at.strftime('%Y-%m-%d %H:%M')} UTC."
            )
        return f"Check-in '{checkin.name}' scheduled (`{checkin.cron_expr}` UTC)."

    @agent.tool
    async def list_scheduled_checkins(ctx: RunContext[None]) -> str:
        """List all registered check-ins with their schedules and enabled status."""
        checkin_repo = _checkin_repo
        if checkin_repo is None:
            return "Check-in tools are not configured."

        checkins = await list_checkins.list_all_checkins(checkin_repo)
        if not checkins:
            return "No check-ins are currently scheduled."

        def _format_checkin(c: ScheduledCheckIn) -> str:
            if c.cron_expr:
                schedule = f"`{c.cron_expr}` UTC"
            elif c.fire_at:
                schedule = f"one-off at `{c.fire_at.strftime('%Y-%m-%d %H:%M')}` UTC"
            else:
                schedule = "unknown schedule"
            return f"- **{c.name}** {schedule} ({'enabled' if c.enabled else 'disabled'})"

        lines = [_format_checkin(c) for c in checkins]
        return "\n".join(lines)

    @agent.tool
    async def remove_checkin(ctx: RunContext[None], name: str) -> str:
        """Remove a scheduled check-in by name.

        Use ``list_scheduled_checkins`` first if you need to confirm the exact name.

        Args:
            name: The exact name of the check-in to remove.
        """
        scheduler = _scheduler
        checkin_repo = _checkin_repo
        if scheduler is None or checkin_repo is None:
            return "Check-in tools are not configured."

        try:
            await delete_checkin.delete_checkin_by_name(name, checkin_repo, scheduler)
        except CheckInNotFoundError:
            return f"No check-in named '{name}' found."

        logger.info("remove_checkin_tool", name=name)
        return f"Check-in '{name}' removed."
