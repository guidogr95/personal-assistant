"""Update the active system prompt."""

from __future__ import annotations

from assistant.prompts.domain.prompt_repository import PromptRepository


async def update_system_prompt(text: str, repo: PromptRepository) -> None:
    """Replace the active system prompt with ``text``."""
    await repo.update(text)
