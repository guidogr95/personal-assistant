"""Agent factory — creates a pydantic-ai Agent with configurable dependencies.

No module-level Agent instance is created here. The application layer (main.py)
calls ``create_agent()`` after all runtime dependencies are ready, then
registers tools via the ``@tool`` decorator and ``ALL_TOOLS`` registry.
"""

from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from assistant.agent.domain.deps import AgentDeps
from assistant.agent.domain.system_prompt import _SYSTEM_PROMPT
from assistant.memory.infrastructure.memory_mcp_client import create_memory_mcp_server
from assistant.shared.config import settings


def create_agent(
    *,
    system_prompt: str | None = None,
) -> Agent[AgentDeps, str]:
    """Create a new Agent instance with the given configuration.

    Args:
        system_prompt: System prompt text. Defaults to the built-in
            ``_SYSTEM_PROMPT``.

    Returns:
        Configured Agent ready for tool registration. The caller must
        register tools (e.g. by iterating over ``ALL_TOOLS``) before
        the agent handles any messages.
    """
    provider = OpenAIProvider(
        base_url=settings.opencode_base_url,
        api_key=settings.opencode_api_key,
    )
    model = OpenAIModel(model_name=settings.opencode_model, provider=provider)
    memory_server = create_memory_mcp_server()

    return Agent(
        model=model,
        system_prompt=system_prompt or _SYSTEM_PROMPT,
        toolsets=[memory_server],
    )
