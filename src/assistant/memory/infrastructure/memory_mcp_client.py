from __future__ import annotations

from pydantic_ai.mcp import MCPToolset

from assistant.shared.config import settings


def create_memory_mcp_server() -> MCPToolset:
    """Create the Streamable HTTP MCP toolset connection to mcp-memory-service.

    Returns an MCPToolset instance to be registered as a toolset on the Agent.
    The Agent manages connection lifecycle via `async with agent:`.
    No connection is opened at construction time.
    """
    return MCPToolset(f"{settings.memory_service_url}/mcp")
