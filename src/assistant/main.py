from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, Dispatcher

from assistant.agent.domain.agent import create_agent
from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import ALL_TOOLS
from assistant.conversation.infrastructure.sqlite_repositories import (
    SQLiteSessionRepository,
    SQLiteTurnRepository,
    init_db,
)
from assistant.notes.infrastructure.markdown_repository import MarkdownNoteRepository
from assistant.prompts.infrastructure.sqlite_prompt_repository import SQLitePromptRepository
from assistant.research.infrastructure.jina_client import JinaClient
from assistant.research.infrastructure.rebrowser_client import RebrowserClient
from assistant.research.infrastructure.searxng_client import SearXNGClient
from assistant.scheduler.application.run_checkin import configure_checkin_runner, run_checkin
from assistant.scheduler.infrastructure.apscheduler_registry import (
    create_scheduler,
    register_checkin_job,
    register_one_off_job,
)
from assistant.scheduler.infrastructure.sqlite_checkin_repository import (
    SQLiteScheduledCheckInRepository,
)
from assistant.shared.config import settings
from assistant.shared.logging import configure_logging
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient
from assistant.telegram.bot import AllowedUserMiddleware
from assistant.telegram.handlers import discover_commands, discover_routers
from assistant.video.application.transcription_queue import (
    configure_transcription_queue,
    start_worker,
)

configure_logging()
logger = structlog.get_logger()


async def main() -> None:
    """Start the Telegram bot and begin long-polling for updates."""
    logger.info("assistant_starting", model=settings.opencode_model)

    await init_db(settings.sqlite_path)

    session_repo = SQLiteSessionRepository(settings.sqlite_path)
    turn_repo = SQLiteTurnRepository(settings.sqlite_path)
    checkin_repo = SQLiteScheduledCheckInRepository(settings.sqlite_path)
    prompt_repo = SQLitePromptRepository(settings.sqlite_path)
    note_repo = MarkdownNoteRepository()

    bot = Bot(token=settings.telegram_bot_token)
    await bot.set_my_commands(discover_commands())
    dp = Dispatcher()

    dp.update.middleware(AllowedUserMiddleware())

    # Auto-discover and register all routers. Order matters: errors first,
    # then specific command routers, then the catch-all message handler.
    _ROUTER_PRIORITY: dict[str, int] = {
        "errors": 0,
        "session_commands": 1,
        "checkin_commands": 2,
        "tool_commands": 3,
        "prompt_commands": 4,
        "callbacks": 5,
        "video_commands": 6,
        "message": 99,
    }
    module_routers = discover_routers()
    module_routers.sort(key=lambda item: _ROUTER_PRIORITY.get(item[0], 50))
    for _name, router in module_routers:
        dp.include_router(router)

    scheduler = create_scheduler()

    # Infrastructure clients — created at runtime, not import time.
    vikunja_client = VikunjaClient()
    searxng_client = SearXNGClient()
    jina_client = JinaClient()
    rebrowser_client = RebrowserClient()

    agent_deps = AgentDeps(
        scheduler=scheduler,
        checkin_repo=checkin_repo,
        prompt_repo=prompt_repo,
        note_repo=note_repo,
        bot=bot,
        vikunja_client=vikunja_client,
        searxng_client=searxng_client,
        jina_client=jina_client,
        rebrowser_client=rebrowser_client,
    )

    # Agent must be created AFTER prompt_repo is ready so the system prompt
    # can be loaded from DB on startup.
    agent = create_agent()

    # Auto-discover and register all tools decorated with @tool.
    for tool_fn in ALL_TOOLS:
        agent.tool(tool_fn)

    configure_checkin_runner(
        bot=bot,
        checkin_repo=checkin_repo,
        run_agent=lambda instructions: agent.run(instructions, deps=agent_deps).output,
    )
    configure_transcription_queue(bot=bot, note_repo=note_repo)
    asyncio.create_task(start_worker())
    logger.info("transcription_worker_task_created")

    # Re-register all enabled check-ins from DB so jobs survive bot restarts.
    enabled_checkins = [c for c in await checkin_repo.list_all() if c.enabled]
    recurring_count = 0
    one_off_count = 0
    for checkin in enabled_checkins:
        if checkin.cron_expr:
            tz = ZoneInfo(checkin.cron_timezone) if checkin.cron_timezone else None
            register_checkin_job(scheduler, checkin.id, checkin.cron_expr, run_checkin, timezone=tz)
            recurring_count += 1
        elif checkin.fire_at and checkin.fire_at > datetime.now(UTC):
            register_one_off_job(scheduler, checkin.id, checkin.fire_at, run_checkin)
            one_off_count += 1

    if recurring_count or one_off_count:
        logger.info(
            "scheduler_checkins_loaded",
            recurring=recurring_count,
            one_off=one_off_count,
        )

    scheduler.start()
    logger.info("scheduler_started")

    try:
        # `async with agent:` connects all registered MCP server toolsets (including
        # mcp-memory-service) and enters the model's HTTP client. Both are torn down
        # cleanly on exit regardless of how polling terminates.
        async with agent:
            logger.info("mcp_servers_connected", memory_url=settings.memory_service_url)
            await dp.start_polling(
                bot,
                session_repo=session_repo,
                turn_repo=turn_repo,
                checkin_repo=checkin_repo,
                prompt_repo=prompt_repo,
                scheduler=scheduler,
                agent=agent,
                agent_deps=agent_deps,
                note_repo=note_repo,
            )
    finally:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    asyncio.run(main())
