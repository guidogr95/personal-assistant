"""Agent tools for time awareness."""

from __future__ import annotations

import structlog
from pydantic_ai import RunContext

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import tool
from assistant.shared.time import get_current_time as _get_current_time

logger = structlog.get_logger()


@tool(category="🕐 Time")
async def get_current_time(ctx: RunContext[AgentDeps]) -> str:
    """Get the current server time with timezone.

    Always call this tool before scheduling anything or answering questions
    about time, dates, or deadlines. Do not guess the time.

    Examples of when to use this tool:
    - The user asks "What time is it?"
    - The user says "Remind me in 30 minutes"
    - The user says "Schedule a check-in for tomorrow at 9am"
    - The user asks "What day is it today?"

    Returns:
        A string like::

            "Local: 2026-06-01 20:50:00 (America/Guayaquil, UTC-5) | UTC: 2026-06-02 01:50:00"

        The ``UTC:`` portion is always present and ready to use directly
        as a base for computing ``fire_at`` values.
    """
    result = _get_current_time()
    logger.info("get_current_time_tool", result=result)
    return result
