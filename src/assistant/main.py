from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from assistant.agent.domain.agent import agent
from assistant.agent.tools.checkin_tools import configure_checkin_tools
from assistant.agent.tools.prompt_tools import configure_prompt_tools
from assistant.agent.tools.reminder_tools import configure_reminder_tools
from assistant.conversation.infrastructure.sqlite_repositories import (
    SQLiteSessionRepository,
    SQLiteTurnRepository,
    init_db,
)
from assistant.prompts.infrastructure.sqlite_prompt_repository import SQLitePromptRepository
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
from assistant.telegram.bot import AllowedUserMiddleware
from assistant.telegram.handlers import (
    callbacks,
    checkin_commands,
    errors,
    message,
    prompt_commands,
    session_commands,
    tool_commands,
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

    bot = Bot(token=settings.telegram_bot_token)
    await bot.set_my_commands(
        [
            BotCommand(command="help", description="List all commands"),
            BotCommand(command="new", description="Start a fresh session"),
            BotCommand(command="close", description="Close session and generate title"),
            BotCommand(command="sessions", description="Browse recent sessions"),
            BotCommand(command="checkin", description="Manage proactive check-ins"),
            BotCommand(command="time", description="Show current server time"),
            BotCommand(command="system", description="Show or update system prompt"),
        ]
    )
    dp = Dispatcher()

    dp.update.middleware(AllowedUserMiddleware())

    # Error handler registered first so it catches exceptions from all other routers
    dp.include_router(errors.router)
    # Session commands registered before the catch-all message handler
    dp.include_router(session_commands.router)
    dp.include_router(checkin_commands.router)
    dp.include_router(tool_commands.router)
    dp.include_router(prompt_commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(message.router)

    scheduler = create_scheduler()
    configure_checkin_runner(bot=bot, checkin_repo=checkin_repo)
    configure_checkin_tools(scheduler=scheduler, checkin_repo=checkin_repo)
    configure_reminder_tools(checkin_repo=checkin_repo)
    configure_prompt_tools(prompt_repo=prompt_repo)

    # Re-register all enabled check-ins from DB so jobs survive bot restarts.
    enabled_checkins = [c for c in await checkin_repo.list_all() if c.enabled]
    recurring_count = 0
    one_off_count = 0
    for checkin in enabled_checkins:
        if checkin.cron_expr:
            register_checkin_job(scheduler, checkin.id, checkin.cron_expr, run_checkin)
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
            )
    finally:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")


if __name__ == "__main__":
    asyncio.run(main())
