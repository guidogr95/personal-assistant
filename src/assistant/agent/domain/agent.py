from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from assistant.agent.tools.checkin_tools import register_checkin_tools
from assistant.agent.tools.notes_tools import register_notes_tools
from assistant.agent.tools.reminder_tools import register_reminder_tools
from assistant.agent.tools.research_tools import register_research_tools
from assistant.agent.tools.task_tools import register_task_tools
from assistant.agent.tools.time_tools import register_time_tools
from assistant.memory.infrastructure.memory_mcp_client import create_memory_mcp_server
from assistant.shared.config import settings

_SYSTEM_PROMPT = """You are a personal AI assistant accessed via Telegram.
You help with tasks, research, notes, calendar, and general questions.
Be concise but thorough.
Today's date is available from context when needed.

Formatting rules (Telegram HTML mode is active):
- Use <b>text</b> for bold, <i>text</i> for italic, <code>text</code> for inline code.
- Use <pre>text</pre> for multi-line code blocks.
- For bullet lists, use plain hyphens: "- item" (no HTML needed).
- Never use Markdown syntax (*bold*, **bold**, `code`, # headings).
- Never write a bare < or > character in plain prose; use &lt; and &gt; if you must.

You have long-term memory that persists across sessions. When the user asks you
to remember something, use the memory tools to store it. When context from past
sessions would be helpful, search your memory proactively."""

_provider = OpenAIProvider(
    base_url=settings.opencode_base_url,
    api_key=settings.opencode_api_key,
)

_model = OpenAIModel(model_name=settings.opencode_model, provider=_provider)

# Memory server is registered as a toolset so the LLM can call mcp-memory-service
# tools (memory_store, memory_retrieve, etc.) directly without Python wrappers.
_memory_server = create_memory_mcp_server()

# Typed as Agent[None, str]: no deps, plain-text output.
agent: Agent[None, str] = Agent(
    model=_model,
    system_prompt=_SYSTEM_PROMPT,
    toolsets=[_memory_server],
)

register_time_tools(agent)
register_research_tools(agent)
register_notes_tools(agent)
register_task_tools(agent)
register_checkin_tools(agent)
register_reminder_tools(agent)
