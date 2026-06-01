"""Read the active system prompt."""

from __future__ import annotations

from assistant.prompts.domain.prompt_repository import PromptRepository


async def get_system_prompt(repo: PromptRepository) -> str:
    """Return the current system prompt text."""
    return await repo.get_active()
