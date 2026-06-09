"""Agent tools for managing proactive check-ins."""

from __future__ import annotations

import structlog
from pydantic_ai import RunContext

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import tool
from assistant.scheduler.application import delete_checkin, list_checkins, register_checkin
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.shared.exceptions import CheckInNotFoundError

logger = structlog.get_logger()


@tool(category="⏰ Check-ins")
async def schedule_checkin(
    ctx: RunContext[AgentDeps],
    name: str,
    instructions: str = "",
    message: str = "",
    cron_expr: str = "",
    fire_at: str = "",
    max_runs: int | None = None,
) -> str:
    """Schedule a proactive check-in or one-off reminder.

    The bot will send output to Telegram automatically on the given schedule.

    MANDATORY: call ``get_current_time`` before this tool, every time, no
    exceptions.  The response includes both the user's local time and the
    UTC equivalent::

        "Local: 2026-06-01 20:50:00 (America/Guayaquil, UTC-5) | UTC: 2026-06-02 01:50:00"

    All time expressions are in the user's local timezone (America/Guayaquil,
    UTC-5).  The tool handles all timezone conversion internally.  Do NOT
    convert to UTC.  Pass the expression exactly as the user stated it.
    Never guess the current time.

    Args:
        name: Short label for the check-in (e.g. "Morning Tasks").
        instructions: What the assistant should do when the check-in fires.
            Use this for agent-run check-ins. Example:
            "Summarise my open Vikunja tasks and flag any overdue ones."
        message: Direct message text to send (no LLM cost). Use this for
            simple reminders. Example: "Call mom" or "Drink water".
        cron_expr: Standard 5-field cron expression for recurring jobs.
            The tool converts local time to UTC internally.  Pass the
            expression exactly as the user stated it.
            - "every day at 9am"     → daily at 09:00 local
            - "every weekday at 8am" → Monday–Friday at 08:00 local
            - "every Monday at 10am" → Monday at 10:00 local
            - "every hour"           → every hour on the hour
        fire_at: ISO-8601 datetime for a one-off job. Use this OR
            cron_expr, not both.  Pass local time; the tool converts to UTC.
            Example: "2026-06-01T14:30:00".
        max_runs: Maximum number of times this check-in fires before
            auto-disabling. None = infinite. Set to 1 for one-off reminders.
    """
    scheduler = ctx.deps.scheduler
    checkin_repo = ctx.deps.checkin_repo

    # Parse fire_at string to datetime if provided
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    fire_at_dt: _dt | None = None
    if fire_at.strip():
        try:
            fire_at_dt = _dt.fromisoformat(fire_at.strip())
            # fromisoformat returns a naive datetime when no timezone suffix
            # is present (e.g. "2026-06-01T20:43:59" from the LLM).
            # Treat naive datetimes as UTC so downstream comparisons work.
            if fire_at_dt.tzinfo is None:
                fire_at_dt = fire_at_dt.replace(tzinfo=_UTC)
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
            f"{checkin.fire_at.strftime('%Y-%m-%d %H:%M')} local time."
        )
    return f"Check-in '{checkin.name}' scheduled (`{checkin.cron_expr}` local time)."


@tool(category="⏰ Check-ins")
async def list_scheduled_checkins(ctx: RunContext[AgentDeps]) -> str:
    """List all registered check-ins with their schedules and enabled status."""
    checkins = await list_checkins.list_all_checkins(ctx.deps.checkin_repo)
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


@tool(category="⏰ Check-ins")
async def remove_checkin(ctx: RunContext[AgentDeps], name: str) -> str:
    """Remove a scheduled check-in by name.

    Use ``list_scheduled_checkins`` first if you need to confirm the exact name.

    Args:
        name: The exact name of the check-in to remove.
    """
    try:
        await delete_checkin.delete_checkin_by_name(name, ctx.deps.checkin_repo, ctx.deps.scheduler)
    except CheckInNotFoundError:
        return f"No check-in named '{name}' found."

    logger.info("remove_checkin_tool", name=name)
    return f"Check-in '{name}' removed."


@tool(category="⏰ Check-ins")
async def get_checkin_history(
    ctx: RunContext[AgentDeps],
    name: str,
    limit: int = 10,
) -> str:
    """Show recent execution history for a check-in.

    Use this when the user asks "did my check-in fire?" or
    "show me the history of my morning check-in."

    Args:
        name: The exact name of the check-in.
        limit: Maximum number of history entries to return (default 10).
    """
    checkin = await ctx.deps.checkin_repo.find_by_name(name)
    if checkin is None:
        return f"No check-in named '{name}' found."

    history = await ctx.deps.checkin_repo.get_execution_history(checkin.id, limit=limit)
    if not history:
        return f"No execution history for '{name}' yet."

    lines = [f"<b>History for '{name}'</b>"]
    for record in history:
        status = record["status"]
        fired_at = record["fired_at"][:16].replace("T", " ")
        if status == "success":
            lines.append(f"✅ {fired_at} — succeeded")
        else:
            error = record.get("error_message") or "unknown error"
            lines.append(f"❌ {fired_at} — failed: {error}")

    return "\n".join(lines)
