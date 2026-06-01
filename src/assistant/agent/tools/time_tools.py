"""Agent tools for time awareness."""

from __future__ import annotations

import structlog
from pydantic_ai import Agent, RunContext

from assistant.shared.time import get_current_time as _get_current_time

logger = structlog.get_logger()


def register_time_tools(agent: Agent[None, str]) -> None:
    """Register time-related tools on the agent.

    Adds ``get_current_time`` — the agent should call this before any
    time-based action (scheduling, reminders, due dates).
    """

    @agent.tool
    async def get_current_time(ctx: RunContext[None]) -> str:
        """Get the current server time with timezone.

        Always call this tool before scheduling anything or answering questions
        about time, dates, or deadlines. Do not guess the time.

        Examples of when to use this tool:
        - The user asks "What time is it?"
        - The user says "Remind me in 30 minutes"
        - The user says "Schedule a check-in for tomorrow at 9am"
        - The user asks "What day is it today?"

        Returns:
            A string like ``"Current time: 2026-06-01 14:30:00 (America/Guayaquil)"``.
        """
        result = _get_current_time()
        logger.info("get_current_time_tool", result=result)
        return result
