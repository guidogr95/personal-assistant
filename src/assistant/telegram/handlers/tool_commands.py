"""Command-to-tool bridge for direct slash-command access to agent tools."""

from __future__ import annotations

import html
import json

import httpx
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from assistant.agent.domain.agent import agent
from assistant.shared.config import settings
from assistant.shared.time import get_current_time
from assistant.telegram.formatting import answer_markdown

logger = structlog.get_logger()

router = Router()


async def _fetch_mcp_tool_names() -> list[str] | None:
    """Query the MCP memory service for its registered tool names.

    The MCP streamable-http transport returns SSE-wrapped JSON-RPC responses,
    i.e. one or more lines of the form ``data: <json>\\n\\n``.  We must strip
    the SSE envelope before parsing.

    Returns:
        Sorted list of tool names on success; ``None`` if the service is
        unreachable or returns an unexpected response.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.memory_service_url}/mcp",
                json={"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            response.raise_for_status()
            raw = response.text.strip()

            # SSE envelope: lines are prefixed with "data: "; find the JSON-RPC response line.
            json_text: str | None = None
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped.startswith("data:"):
                    json_text = stripped[len("data:") :].strip()
                    break
            if json_text is None:
                # Plain JSON response (no SSE envelope).
                json_text = raw

            data: dict[str, object] = json.loads(json_text)
            result = data.get("result", {})
            if not isinstance(result, dict):
                result_type = type(result).__name__
                logger.warning("mcp_tools_unexpected_result_type", result_type=result_type)
                return None
            tools: list[object] = result.get("tools", [])
            return sorted(
                t["name"] for t in tools if isinstance(t, dict) and isinstance(t.get("name"), str)
            )
    except Exception as exc:
        logger.warning("mcp_tools_fetch_failed", error=str(exc))
        return None


def _build_tools_html(python_tool_names: set[str], mcp_tool_names: list[str] | None) -> str:
    """Format all registered tools as an HTML string for Telegram.

    Args:
        python_tool_names: Names of Python-registered agent tools.
        mcp_tool_names: Names from the MCP server, or ``None`` if unreachable.

    Returns:
        HTML-formatted string listing tools grouped by source.
    """
    lines: list[str] = ["<b>Available tools</b>\n"]

    lines.append("<b>Built-in</b>")
    for name in sorted(python_tool_names):
        lines.append(f"  <code>{html.escape(name)}</code>")
    lines.append("")

    if mcp_tool_names is not None:
        lines.append("<b>Memory (MCP)</b>")
        for name in mcp_tool_names:
            lines.append(f"  <code>{html.escape(name)}</code>")
    else:
        lines.append("<i>Memory tools: MCP server did not respond</i>")

    return "\n".join(lines)


@router.message(Command("tools"))
async def cmd_tools(message: Message) -> None:
    """List all tools available to the agent, queried programmatically at runtime.

    Python-registered tools are read directly from the agent's tool registry.
    MCP tools are fetched live from the memory service so the list is always
    accurate regardless of what the service exposes.
    """
    try:
        python_tool_names: set[str] = set(agent._function_tools.keys())  # type: ignore[attr-defined]
    except AttributeError:
        logger.warning("agent_function_tools_unavailable")
        python_tool_names = set()

    mcp_tool_names = await _fetch_mcp_tool_names()
    text = _build_tools_html(python_tool_names, mcp_tool_names)
    await answer_markdown(message, text)


@router.message(Command("time"))
async def cmd_time(message: Message) -> None:
    """Return the current server time with timezone."""
    result = get_current_time()
    await message.answer(result)
