"""Agent tools package.

Importing this package registers all tool modules, running their @tool
decorators and populating ALL_TOOLS in registry.py.
"""

from assistant.agent.tools import (
    checkin_tools,
    notes_tools,
    prompt_tools,
    reminder_tools,
    research_tools,
    task_tools,
    time_tools,
    video_tools,
)

__all__ = [
    "checkin_tools",
    "notes_tools",
    "prompt_tools",
    "reminder_tools",
    "research_tools",
    "task_tools",
    "time_tools",
    "video_tools",
]
