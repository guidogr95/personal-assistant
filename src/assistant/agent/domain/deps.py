"""Dependency container for agent tools.

All runtime dependencies required by agent tools are injected via
RunContext[AgentDeps] instead of module-level globals.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from assistant.notes.domain.note_repository import NoteRepository
from assistant.prompts.domain.prompt_repository import PromptRepository
from assistant.research.infrastructure.jina_client import JinaClient
from assistant.research.infrastructure.rebrowser_client import RebrowserClient
from assistant.research.infrastructure.searxng_client import SearXNGClient
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient


@dataclass
class AgentDeps:
    """Runtime dependencies for agent tools.

    Passed to Agent via RunContext so tools can access infrastructure
    without module-level globals.
    """

    scheduler: AsyncIOScheduler
    checkin_repo: ScheduledCheckInRepository
    prompt_repo: PromptRepository
    note_repo: NoteRepository
    bot: Bot
    vikunja_client: VikunjaClient
    searxng_client: SearXNGClient
    jina_client: JinaClient
    rebrowser_client: RebrowserClient
