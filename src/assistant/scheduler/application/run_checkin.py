from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

import structlog
from aiogram import Bot

from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.shared.config import settings
from assistant.telegram.formatting import bold, send_message

logger = structlog.get_logger()

# Module-level state configured once at startup by configure_checkin_runner.
# Acceptable for a single-process, single-scheduler personal assistant bot.
_bot: Bot | None = None
_checkin_repo: ScheduledCheckInRepository | None = None
_run_agent: Callable[[str], Awaitable[str]] | None = None


def configure_checkin_runner(
    *,
    bot: Bot,
    checkin_repo: ScheduledCheckInRepository,
    run_agent: Callable[[str], Awaitable[str]],
) -> None:
    """Inject runtime dependencies before the scheduler starts.

    Must be called exactly once during application startup, before
    scheduler.start() is called.

    Args:
        bot: Telegram Bot instance for sending messages.
        checkin_repo: Repository for check-in persistence.
        run_agent: Callback that runs the agent with given instructions.
            Signature: ``async def run_agent(instructions: str) -> str``.
            This callback breaks the circular dependency between the
            scheduler and the agent domain.
    """
    global _bot, _checkin_repo, _run_agent
    _bot = bot
    _checkin_repo = checkin_repo
    _run_agent = run_agent


async def run_checkin(checkin_id: str) -> None:
    """APScheduler job: fire a check-in and send output to Telegram.

    Handles both agent-run check-ins (instructions) and direct-message
    reminders (message).  Increments run_count and auto-disables if
    max_runs is reached.  Silently skips disabled or missing check-ins.
    Catches all exceptions so a failing check-in never crashes the scheduler.
    """
    bot = _bot
    checkin_repo = _checkin_repo
    run_agent = _run_agent
    if bot is None or checkin_repo is None or run_agent is None:
        raise RuntimeError("configure_checkin_runner must be called before the scheduler starts")

    checkin = await checkin_repo.get_by_id(checkin_id)
    if checkin is None:
        logger.warning("checkin_not_found_skipped", checkin_id=checkin_id)
        return

    if not checkin.enabled:
        logger.info("checkin_disabled_skipped", checkin_id=checkin_id, name=checkin.name)
        return

    logger.info("checkin_firing", checkin_id=checkin_id, name=checkin.name)
    chat_id = settings.telegram_allowed_user_id
    execution_id = str(uuid4())
    fired_at = datetime.now(UTC)

    try:
        if checkin.message:
            # Direct-message reminder (no LLM cost)
            text = f"🔔 {bold(checkin.name)}\n\n{checkin.message}"
        elif checkin.instructions:
            # Agent-run check-in — uses the injected callback to avoid
            # circular dependency (scheduler → agent → scheduler tools).
            result = await run_agent(checkin.instructions)
            text = f"📋 {bold(checkin.name)}\n\n{result}"
        else:
            text = f"📋 {bold(checkin.name)}\n\n(no message or instructions)"

        try:
            await send_message(bot, text, chat_id=chat_id)
        except Exception:
            logger.warning("checkin_markdown_failed_falling_back", checkin_id=checkin_id)
            await bot.send_message(chat_id=chat_id, text=text)

        # Increment run count and check for auto-disable
        checkin.increment_run()
        await checkin_repo.update(checkin)

        await checkin_repo.log_execution(
            execution_id=execution_id,
            checkin_id=checkin.id,
            checkin_name=checkin.name,
            fired_at=fired_at,
            status="success",
            error_message=None,
            output_text=text,
        )

        if checkin.has_reached_max_runs():
            checkin.disable()
            await checkin_repo.update(checkin)
            done_text = (
                f"✅ Check-in {bold(checkin.name)} completed after {checkin.max_runs} run(s)."
            )
            try:
                await send_message(bot, done_text, chat_id=chat_id)
            except Exception:
                await bot.send_message(chat_id=chat_id, text=done_text)
            logger.info("checkin_auto_disabled", checkin_id=checkin_id, name=checkin.name)
        else:
            logger.info("checkin_sent", checkin_id=checkin_id, name=checkin.name)

    except Exception as exc:
        logger.error("checkin_failed", checkin_id=checkin_id, name=checkin.name, error=str(exc))
        await checkin_repo.log_execution(
            execution_id=execution_id,
            checkin_id=checkin.id,
            checkin_name=checkin.name,
            fired_at=fired_at,
            status="failed",
            error_message=str(exc),
            output_text=None,
        )
        try:
            fail_text = f"⚠️ Check-in {bold(checkin.name)} failed. See logs for details."
            await send_message(bot, fail_text, chat_id=chat_id)
        except Exception as notify_exc:
            logger.error("checkin_notify_failed", checkin_id=checkin_id, error=str(notify_exc))
