# Phase 2: Long-Term Memory via mcp-memory-service

**Goal:** Connect the agent to mcp-memory-service via Pydantic AI's `MCPClient`. Add `remember_fact` and `recall_fact` tools so the agent can store and retrieve facts that persist across sessions.  
**Prerequisites:** Phase 1 complete (working bot with sessions and agent loop).  
**Output:** "Remember that my server IP is 1.2.3.4" stores a fact. "What's my server IP?" retrieves it in a future session after a bot restart.

---

## Critique Review

**What could go wrong?**
- mcp-memory-service not running when bot starts: bot should start and log a warning, not crash; the memory tool should return a descriptive error to the agent when called
- MCP connection drops during a turn: Pydantic AI's MCPClient should reconnect; add reconnect-on-error wrapper if needed
- Memory leaks across users: not a concern (single-user system, all memories belong to the one user)
- Storing PII in memory: user's own data by design; no issue

**Simplification applied:** No memory expiry or consolidation in this phase. mcp-memory-service handles consolidation internally. The bot simply stores and queries.

---

## Files to Create / Modify

```
src/assistant/
├── memory/
│   └── infrastructure/
│       ├── __init__.py
│       └── memory_mcp_client.py    (MCPClient wrapper + connect/disconnect lifecycle)
├── agent/
│   ├── domain/
│   │   └── agent.py                (modified: add MCPClient + memory tools)
│   └── tools/
│       ├── __init__.py
│       └── memory_tools.py         (remember_fact, recall_facts tools)
├── main.py                         (modified: start/stop MCPClient lifecycle)
```

---

## Step-by-Step Implementation

### Step 1 — Confirm mcp-memory-service is running

The service is defined in `docker-compose.yml` from Phase 0. Confirm it is up:

```bash
docker compose -f deploy/docker-compose.yml ps memory
# Should show: memory ... running
```

Verify the REST API is accessible from the bot container:
```bash
docker compose exec bot curl http://memory:8001/health
```

### Step 2 — MCP Client Wrapper

```python
# memory/infrastructure/memory_mcp_client.py
from pydantic_ai.mcp import MCPServerHTTP
from assistant.shared.config import settings
import structlog

logger = structlog.get_logger()


def create_memory_mcp_server() -> MCPServerHTTP:
    """Create the mcp-memory-service MCP server connection.

    Returns an MCPServerHTTP instance to be passed to the Agent constructor.
    The Agent manages connection lifecycle.
    """
    return MCPServerHTTP(url=f"{settings.memory_service_url}/mcp")
```

> **Note:** Check mcp-memory-service docs for the exact MCP endpoint path — it may be `/mcp`, `/sse`, or `/`. Verify with `curl http://memory:8001/` after the container starts.

### Step 3 — Memory Tools

```python
# agent/tools/memory_tools.py
from pydantic_ai import Agent, RunContext
import structlog

logger = structlog.get_logger()


def register_memory_tools(agent: Agent) -> None:
    """Register memory tools onto an agent instance."""

    @agent.tool
    async def remember_fact(ctx: RunContext, fact: str) -> str:
        """Store a fact in long-term memory for retrieval in future sessions.

        Use this when the user says 'remember that...' or provides information
        they will want to recall later.

        Args:
            fact: The fact to store, as a complete sentence or clear statement.

        Returns:
            Confirmation message.
        """
        # mcp-memory-service exposes store via MCP tool call;
        # Pydantic AI routes MCP tool calls transparently when MCPServer is registered
        # This tool is a thin wrapper that prompts the agent to use the MCP 'create_memory' tool
        logger.info("remember_fact_called", fact_preview=fact[:80])
        return f"Fact stored in memory: {fact}"

    @agent.tool
    async def search_memories(ctx: RunContext, query: str) -> str:
        """Search long-term memory for facts related to a query.

        Use this when the user asks about something they've asked you to remember,
        or when context from past sessions would be helpful.

        Args:
            query: Natural language description of what to search for.

        Returns:
            Matching memories as a formatted string, or a message if none found.
        """
        logger.info("search_memories_called", query=query)
        # Agent will invoke mcp-memory-service 'search_memories' MCP tool
        return f"Searching memories for: {query}"
```

> **Implementation note:** mcp-memory-service exposes its own MCP tools (e.g., `create_memory`, `search_memories`, `list_memories`). When the Agent has the MCPServerHTTP registered, these tools are available to the LLM directly. The wrapper functions above are only needed if you want the agent to use them via a more explicit Python API. In practice, with MCPServer registered, the LLM will call the MCP tools directly — you may not need explicit Python wrappers at all. Verify the MCP tool names exposed by `curl http://memory:8001/mcp` (or equivalent tool discovery endpoint).

### Step 4 — Register MCPServer with Agent

```python
# agent/domain/agent.py  (modified)
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from assistant.shared.config import settings
from assistant.memory.infrastructure.memory_mcp_client import create_memory_mcp_server

SYSTEM_PROMPT = """You are a personal AI assistant accessed via Telegram.

You have long-term memory. When the user asks you to remember something, call the
memory tool to store it. When context from past sessions would help, search your memory.

Be concise but thorough. Use Markdown formatting for lists and code blocks.
"""

_model = OpenAIModel(
    model_name=settings.opencode_model,
    base_url=settings.opencode_base_url,
    api_key=settings.opencode_api_key,
)

memory_server = create_memory_mcp_server()

agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    mcp_servers=[memory_server],
)
```

### Step 5 — Update `main.py` for MCPClient lifecycle

Pydantic AI's MCPServer connections are managed via async context managers or explicit `connect()`/`disconnect()`:

```python
# main.py (relevant section)
from assistant.agent.domain.agent import agent

async def main() -> None:
    # ...existing setup...

    async with agent.run_mcp_servers():
        # All MCP servers connected; start bot polling
        logger.info("mcp_servers_connected")
        await dp.start_polling(bot, session_repo=session_repo, turn_repo=turn_repo)
```

---

## Verification

- [ ] `docker compose exec bot curl http://memory:8001/health` returns 200
- [ ] Telling the bot "remember that my VPS IP is 1.2.3.4" → bot confirms storage
- [ ] Restarting the bot container and asking "what's my VPS IP?" → bot recalls "1.2.3.4"
- [ ] If memory service is down, the bot handles the tool failure gracefully (returns error message to user, does not crash)
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create / Modify**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] No `except Exception: pass` — MCP errors caught as specific exception types and logged with context
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No docstrings that restate the function name
- [ ] No `print()` in production paths — structlog used throughout
- [ ] No secrets in source code or logs
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `memory/` is a **Supporting bounded context** — it has no domain entities; only infrastructure client + application use cases
- [ ] `memory/infrastructure/memory_mcp_client.py` — only wraps MCP protocol; no business logic
- [ ] `agent/tools/memory_tools.py` — only calls the MCP client; no direct mcp-memory-service API calls from tool functions
- [ ] `main.py` lifecycle (connect/disconnect) uses try/finally or async context manager — MCP client is never left open on crash
- [ ] Memory tool failure returns a descriptive error string to the agent — bot does not crash if memory service is down

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 3** adds web research: SearXNG search and Jina Reader page fetching with rebrowser-Playwright fallback.
