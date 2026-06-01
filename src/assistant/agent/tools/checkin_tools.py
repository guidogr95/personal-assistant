"""Agent tools for managing proactive check-ins."""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic_ai import Agent, RunContext

from assistant.scheduler.application import delete_checkin, list_checkins, register_checkin
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
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
        cron_expr: str,
        instructions: str,
    ) -> str:
        """Schedule a recurring proactive check-in.

        The bot will run the check-in on the given cron schedule and send the
        result to Telegram automatically, without any user prompt.

        Args:
            name: Short label for the check-in (e.g. "Morning Tasks").
            cron_expr: Standard 5-field cron expression (minute hour day month weekday).
                Translate natural language schedules to cron before calling:
                - "every day at 9am"      → "0 9 * * *"
                - "every weekday at 8am"  → "0 8 * * 1-5"
                - "every Monday at 10am"  → "0 10 * * 1"
                - "every hour"            → "0 * * * *"
                All times are UTC.
            instructions: What the assistant should do when the check-in fires.
                Write this as a direct instruction, e.g.
                "Summarise my open Vikunja tasks and flag any overdue ones."
        """
        scheduler = _scheduler
        checkin_repo = _checkin_repo
        if scheduler is None or checkin_repo is None:
            return (
                "Check-in tools are not configured. This is a startup bug — contact the developer."
            )

        try:
            checkin = await register_checkin.register_checkin(
                name=name,
                cron_expr=cron_expr,
                instructions=instructions,
                repo=checkin_repo,
                scheduler=scheduler,
            )
        except ValueError as exc:
            logger.warning("schedule_checkin_tool_invalid", name=name, error=str(exc))
            return f"Couldn't schedule check-in: {exc}"

        logger.info("schedule_checkin_tool", checkin_id=checkin.id, name=name)
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

        lines = [
            f"- **{c.name}** `{c.cron_expr}` UTC ({'enabled' if c.enabled else 'disabled'})"
            for c in checkins
        ]
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
