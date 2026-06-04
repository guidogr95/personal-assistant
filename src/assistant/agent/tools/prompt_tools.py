"""Agent tools for viewing and editing the system prompt."""

from __future__ import annotations

import structlog
from pydantic_ai import RunContext

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import tool
from assistant.prompts.application.get_system_prompt import (
    get_system_prompt,
)
from assistant.prompts.application.update_system_prompt import (
    update_system_prompt as _update_system_prompt,
)

logger = structlog.get_logger()


@tool(category="⚙️ System")
async def show_system_prompt(ctx: RunContext[AgentDeps]) -> str:
    """Return the current system prompt text.

    Use this when the user asks "What is your system prompt?" or
    "Show me your instructions."
    """
    return await get_system_prompt(ctx.deps.prompt_repo)


@tool(category="⚙️ System")
async def update_system_prompt(ctx: RunContext[AgentDeps], new_prompt: str) -> str:
    """Replace the system prompt with new text.

    MANDATORY WORKFLOW — follow these steps in order:
    1. Call ``show_system_prompt`` to fetch the current prompt text.
    2. Apply ONLY the change the user explicitly requested to that text.
    3. Pass the COMPLETE updated prompt to this tool.  Do not discard,
       summarise, or remove any existing rule the user did not mention.

    The ``new_prompt`` parameter must contain the ENTIRE prompt after your
    edit, not just the changed fragment.  This tool performs a full
    replacement — any rule you omit will be permanently lost.

    Examples of what the user asks and what you should do:
    - "Be more concise" → add a conciseness rule to the existing prompt
    - "Stop apologising" → add a rule prohibiting apology phrases
    - "Always use bullet points" → add a formatting rule
    - In all cases: keep every other existing rule untouched.

    Args:
        new_prompt: The complete new system prompt text, including all
            existing rules with only the requested change applied.
    """
    await _update_system_prompt(new_prompt, ctx.deps.prompt_repo)
    logger.info("system_prompt_updated_via_tool")
    return "System prompt updated."
