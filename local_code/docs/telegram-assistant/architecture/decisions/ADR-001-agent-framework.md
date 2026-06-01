# ADR-001: Pydantic AI as Agent Framework

**Date:** 2025  
**Status:** Accepted

## Context

The bot needs an agent loop that can call tools, handle multi-step reasoning, and connect to MCP servers (for mcp-memory-service and the Google Calendar MCP). The framework choice determines how tools are defined, how the LLM provider is configured, and how MCP servers are connected. The bot's workflow is a linear tool-calling loop: receive message → build context → run agent with tools → save result. It is not a graph-shaped workflow.

## Decision

Use **Pydantic AI ≥0.2.0** as the agent framework.

Configuration pattern:
```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

model = OpenAIModel(
    model_name=settings.OPENCODE_MODEL,
    base_url=settings.OPENCODE_BASE_URL,
    api_key=settings.OPENCODE_API_KEY,
)

agent = Agent(
    model=model,
    system_prompt="...",
    tools=[...],
    mcp_servers=[memory_mcp_client, calendar_mcp_client],
)
```

Tools are defined as typed Python async functions and registered directly — no decorator magic beyond `@agent.tool`.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **LangGraph** | Designed for graph-shaped workflows (branching, looping, subgraphs, `interrupt()`). Our workflow is strictly linear: none of those features apply. LangGraph requires 3x more boilerplate for a linear tool loop. No built-in MCP client; would require manual integration. |
| **LangChain** | Over-engineered for this scope. Multiple abstraction layers (chains, agents, callbacks, runnables) add complexity without benefit. Pydantic AI achieves the same in significantly less code. |
| **Direct OpenAI SDK** | Would require implementing the tool-call loop, MCP client management, and retry logic from scratch. Unnecessary given Pydantic AI covers all of this. |
| **OpenAI Agents SDK** | Locked to OpenAI. Does not support custom `base_url` providers (like OpenCode Go) at the model config level without workarounds. |

## Consequences

- The agent is defined once in `src/assistant/agent/domain/agent.py` and shared across all use cases
- Adding a new tool = adding a typed async function + registering it; no framework ceremony
- MCP servers are connected via `pydantic_ai.mcp.MCPClient` — see ADR-002 for provider config
- Pydantic AI is a relatively young framework; breaking API changes are possible; pin to minor version in `pyproject.toml`
- Testing agent tools in isolation: tool functions are plain Python callables; inject mocked clients via constructor
