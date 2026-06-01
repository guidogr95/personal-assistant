"""Command-to-tool bridge for direct slash-command access to agent tools."""

from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from assistant.shared.time import get_current_time

logger = structlog.get_logger()

router = Router()


@router.message(Command("time"))
async def cmd_time(message: Message) -> None:
    """Return the current server time with timezone."""
    result = get_current_time()
    await message.answer(result)
