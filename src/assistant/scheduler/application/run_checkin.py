from __future__ import annotations

import structlog
from aiogram import Bot

from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.shared.config import settings
from assistant.telegram.formatting import bold, send_markdown

logger = structlog.get_logger()

# Module-level state configured once at startup by configure_checkin_runner.
# Acceptable for a single-process, single-scheduler personal assistant bot.
_bot: Bot | None = None
_checkin_repo: ScheduledCheckInRepository | None = None


def configure_checkin_runner(
    *,
    bot: Bot,
    checkin_repo: ScheduledCheckInRepository,
) -> None:
    """Inject runtime dependencies before the scheduler starts.

    Must be called exactly once during application startup, before
    scheduler.start() is called.
    """
    global _bot, _checkin_repo
    _bot = bot
    _checkin_repo = checkin_repo


async def run_checkin(checkin_id: str) -> None:
    """APScheduler job: fire a check-in and send output to Telegram.

    Handles both agent-run check-ins (instructions) and direct-message
    reminders (message).  Increments run_count and auto-disables if
    max_runs is reached.  Silently skips disabled or missing check-ins.
    Catches all exceptions so a failing check-in never crashes the scheduler.
    """
    bot = _bot
    checkin_repo = _checkin_repo
    if bot is None or checkin_repo is None:
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

    try:
        if checkin.message:
            # Direct-message reminder (no LLM cost)
            text = f"🔔 {bold(checkin.name)}\n\n{checkin.message}"
        elif checkin.instructions:
            # Agent-run check-in
            from assistant.agent.domain.agent import agent  # noqa: PLC0415

            result = await agent.run(checkin.instructions)
            text = f"📋 {bold(checkin.name)}\n\n{result.output}"
        else:
            text = f"📋 {bold(checkin.name)}\n\n(no message or instructions)"

        try:
            await send_markdown(bot, chat_id, text)
        except Exception:
            # Fallback to plain text if MarkdownV2 parse fails
            logger.warning("checkin_markdown_failed_falling_back", checkin_id=checkin_id)
            await bot.send_message(chat_id=chat_id, text=text)

        # Increment run count and check for auto-disable
        checkin.increment_run()
        await checkin_repo.update(checkin)

        if checkin.has_reached_max_runs():
            checkin.disable()
            await checkin_repo.update(checkin)
            done_text = (
                f"✅ Check-in {bold(checkin.name)} completed after {checkin.max_runs} run(s)."
            )
            try:
                await send_markdown(bot, chat_id, done_text)
            except Exception:
                await bot.send_message(chat_id=chat_id, text=done_text)
            logger.info("checkin_auto_disabled", checkin_id=checkin_id, name=checkin.name)
        else:
            logger.info("checkin_sent", checkin_id=checkin_id, name=checkin.name)

    except Exception as exc:
        logger.error("checkin_failed", checkin_id=checkin_id, name=checkin.name, error=str(exc))
        try:
            fail_text = f"⚠️ Check-in {bold(checkin.name)} failed. See logs for details."
            await send_markdown(bot, chat_id, fail_text)
        except Exception as notify_exc:
            logger.error("checkin_notify_failed", checkin_id=checkin_id, error=str(notify_exc))
