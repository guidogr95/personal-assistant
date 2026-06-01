from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from assistant.scheduler.application import delete_checkin, list_checkins, register_checkin
from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.shared.exceptions import CheckInNotFoundError
from assistant.telegram.formatting import answer_markdown, bold, code

logger = structlog.get_logger()

router = Router()

_USAGE = (
    "Usage:\n"
    "`/checkin add <name> | <cron 5-field> | <instructions>`\n"
    "`/checkin list`\n"
    "`/checkin delete <name>`\n\n"
    "Cron example: `0 9 * * *` = every day at 09:00 UTC"
)


@router.message(Command("checkin"))
async def cmd_checkin(
    message: Message,
    checkin_repo: ScheduledCheckInRepository,
    scheduler: AsyncIOScheduler,
) -> None:
    """Manage proactive check-ins.

    Subcommands: add, list, delete.
    """
    if not message.text or not message.from_user:
        return

    args = message.text.removeprefix("/checkin").strip()

    if args == "list" or args.startswith("list "):
        await _handle_list(message, checkin_repo)
        return

    if args.startswith("delete "):
        name = args.removeprefix("delete ").strip()
        await _handle_delete(message, name, checkin_repo, scheduler)
        return

    if args.startswith("add "):
        raw = args.removeprefix("add ").strip()
        await _handle_add(message, raw, checkin_repo, scheduler)
        return

    await answer_markdown(message, _USAGE)


async def _handle_list(
    message: Message,
    checkin_repo: ScheduledCheckInRepository,
) -> None:
    checkins = await list_checkins.list_all_checkins(checkin_repo)
    if not checkins:
        await message.answer("No check-ins registered.")
        return
    lines = [
        f"- {bold(c.name)} {code(c.cron_expr)} ({'on' if c.enabled else 'off'})" for c in checkins
    ]
    await answer_markdown(message, "\n".join(lines))


async def _handle_delete(
    message: Message,
    name: str,
    checkin_repo: ScheduledCheckInRepository,
    scheduler: AsyncIOScheduler,
) -> None:
    if not name:
        await answer_markdown(
            message,
            "Provide a check-in name: `/checkin delete <name>`",
        )
        return
    try:
        await delete_checkin.delete_checkin_by_name(name, checkin_repo, scheduler)
        await message.answer(f"Check-in '{name}' deleted.")
    except CheckInNotFoundError:
        await message.answer(f"No check-in named '{name}' found.")


async def _handle_add(
    message: Message,
    raw: str,
    checkin_repo: ScheduledCheckInRepository,
    scheduler: AsyncIOScheduler,
) -> None:
    try:
        name, cron_expr, instructions = [p.strip() for p in raw.split("|", 2)]
    except ValueError:
        await answer_markdown(
            message,
            "Format: `/checkin add <name> | <cron 5-field> | <instructions>`",
        )
        return

    try:
        checkin = await register_checkin.register_checkin(
            name=name,
            cron_expr=cron_expr,
            instructions=instructions,
            repo=checkin_repo,
            scheduler=scheduler,
        )
        await answer_markdown(
            message,
            f"Check-in {bold(checkin.name)} registered with schedule {code(checkin.cron_expr)}.",
        )
    except ValueError as exc:
        await message.answer(f"Invalid input: {exc}")
