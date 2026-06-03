"""Slash commands for viewing and editing the system prompt."""

from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from assistant.prompts.application.get_system_prompt import get_system_prompt
from assistant.prompts.application.update_system_prompt import update_system_prompt
from assistant.prompts.domain.prompt_repository import PromptRepository
from assistant.telegram.formatting import bold, pre, send_message

logger = structlog.get_logger()

router = Router()

_MAX_TELEGRAM_MESSAGE_LENGTH = 4000


@router.message(Command("system"))
async def cmd_system(
    message: Message,
    prompt_repo: PromptRepository,
) -> None:
    """Show or update the system prompt.

    Usage:
        /system show
        /system set <new prompt text>
    """
    if not message.text:
        return

    args = message.text.removeprefix("/system").strip()

    if args == "show" or args.startswith("show "):
        await _handle_show(message, prompt_repo)
        return

    if args.startswith("set "):
        new_prompt = args.removeprefix("set ").strip()
        await _handle_set(message, new_prompt, prompt_repo)
        return

    await send_message(
        message,
        "Usage:\n"
        "`/system show` — display current system prompt\n"
        "`/system set <prompt>` — update system prompt",
    )


async def _handle_show(message: Message, prompt_repo: PromptRepository) -> None:
    prompt = await get_system_prompt(prompt_repo)
    if len(prompt) > _MAX_TELEGRAM_MESSAGE_LENGTH:
        prompt = prompt[:_MAX_TELEGRAM_MESSAGE_LENGTH] + "\n\n... (truncated)"
    await send_message(message, f"{bold('Current system prompt:')}\n\n{pre(prompt)}")


async def _handle_set(
    message: Message,
    new_prompt: str,
    prompt_repo: PromptRepository,
) -> None:
    if not new_prompt:
        await send_message(message, "Provide a prompt: `/system set <prompt>`")
        return
    await update_system_prompt(new_prompt, prompt_repo)
    user_id = message.from_user.id if message.from_user else None
    logger.info("system_prompt_updated_via_command", user_id=user_id)
    await message.answer("System prompt updated. Future responses will use the new prompt.")
