"""Agent tools for viewing and editing the system prompt."""

from __future__ import annotations

import structlog
from pydantic_ai import Agent, RunContext

from assistant.prompts.application.get_system_prompt import (
    get_system_prompt,
)
from assistant.prompts.application.update_system_prompt import (
    update_system_prompt as _update_system_prompt,
)
from assistant.prompts.domain.prompt_repository import PromptRepository

logger = structlog.get_logger()

# Injected at startup
_prompt_repo: PromptRepository | None = None


def configure_prompt_tools(*, prompt_repo: PromptRepository) -> None:
    """Inject runtime dependencies before the agent handles any messages."""
    global _prompt_repo
    _prompt_repo = prompt_repo


def register_prompt_tools(agent: Agent[None, str]) -> None:
    """Register system prompt management tools on the agent.

    Adds ``show_system_prompt`` and ``update_system_prompt`` so the user
    can view or edit the prompt via natural language.
    """

    @agent.tool
    async def show_system_prompt(ctx: RunContext[None]) -> str:
        """Return the current system prompt text.

        Use this when the user asks "What is your system prompt?" or
        "Show me your instructions."
        """
        repo = _prompt_repo
        if repo is None:
            return "Prompt tools are not configured."
        return await get_system_prompt(repo)

    @agent.tool
    async def update_system_prompt(ctx: RunContext[None], new_prompt: str) -> str:
        """Replace the system prompt with new text.

        Use this when the user asks you to change your behavior, e.g.
        "Be more concise", "Always use bullet points", or "Stop saying
        'I'm sorry to hear that'".

        Args:
            new_prompt: The complete new system prompt text.
        """
        repo = _prompt_repo
        if repo is None:
            return "Prompt tools are not configured."
        await _update_system_prompt(new_prompt, repo)
        logger.info("system_prompt_updated_via_tool")
        return "System prompt updated."
