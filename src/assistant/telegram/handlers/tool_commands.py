"""Command-to-tool bridge for direct slash-command access to agent tools."""

from __future__ import annotations

import html
import json
from typing import TypedDict

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

_SUMMARISE_INSTRUCTIONS = (
    "You are summarising the tools available to an AI assistant. "
    "Group them by functional domain and provide a clear one-sentence explanation for each tool. "
    "Format the output as Telegram HTML: use <b>Group Name</b> for group headings and "
    "<code>tool_name</code> for tool names. "
    "Do not invoke any tools — only produce the formatted summary text."
)


class _McpTool(TypedDict):
    name: str
    description: str


async def _fetch_mcp_tools() -> list[_McpTool] | None:
    """Query the MCP memory service for its registered tools and descriptions.

    The MCP streamable-http transport returns SSE-wrapped JSON-RPC responses,
    i.e. one or more lines of the form ``data: <json>\\n\\n``.  We must strip
    the SSE envelope before parsing.

    Returns:
        List of tool dicts (name + description) on success; ``None`` if the
        service is unreachable or returns an unexpected response.
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
            return [
                _McpTool(name=t["name"], description=t.get("description") or "")
                for t in tools
                if isinstance(t, dict) and isinstance(t.get("name"), str)
            ]
    except Exception as exc:
        logger.warning("mcp_tools_fetch_failed", error=str(exc))
        return None


def _build_summary_prompt(
    python_tools: dict[str, str], mcp_tools: list[_McpTool] | None
) -> str:
    """Build the prompt sent to the LLM to produce a grouped tool summary.

    Args:
        python_tools: Mapping of tool name to description for Python-registered tools.
        mcp_tools: List of MCP tool dicts, or ``None`` if the server is unreachable.

    Returns:
        Plain-text prompt string ready for ``agent.run()``.
    """
    lines: list[str] = ["Available tools with their descriptions:", ""]
    for name, desc in sorted(python_tools.items()):
        lines.append(f"- {name}: {desc or '(no description)'}")
    if mcp_tools is not None:
        for tool in mcp_tools:
            desc = tool["description"] or "(no description)"
            lines.append(f"- {tool['name']} (memory/MCP): {desc}")
    else:
        lines.append("(Memory/MCP tools are currently unavailable)")
    lines += [
        "",
        "Group these tools by functional domain and provide a clear one-sentence explanation "
        "for each. Use Telegram HTML formatting as instructed.",
    ]
    return "\n".join(lines)


def _build_fallback_html(
    python_tools: dict[str, str], mcp_tools: list[_McpTool] | None
) -> str:
    """Plain HTML listing used when AI summarisation fails.

    Args:
        python_tools: Mapping of tool name to description.
        mcp_tools: List of MCP tool dicts, or ``None`` if unreachable.

    Returns:
        HTML-formatted string listing tools grouped by source.
    """
    lines: list[str] = ["<b>Available tools</b>\n", "<b>Built-in</b>"]
    for name in sorted(python_tools):
        lines.append(f"  <code>{html.escape(name)}</code>")
    lines.append("")
    if mcp_tools is not None:
        lines.append("<b>Memory (MCP)</b>")
        for tool in mcp_tools:
            lines.append(f"  <code>{html.escape(tool['name'])}</code>")
    else:
        lines.append("<i>Memory tools: MCP server did not respond</i>")
    return "\n".join(lines)


@router.message(Command("tools"))
async def cmd_tools(message: Message) -> None:
    """List all agent tools with AI-generated grouped explanations.

    Collects Python-registered tools and their docstring descriptions directly
    from the agent registry, fetches MCP tool metadata live from the memory
    service, then asks the LLM to group and explain all tools.  Falls back to
    a plain name listing if the LLM call fails.
    """
    try:
        python_tools: dict[str, str] = {
            name: (tool.description or "")
            for name, tool in agent._function_toolset.tools.items()
        }
    except AttributeError:
        logger.warning("agent_function_tools_unavailable")
        python_tools = {}

    mcp_tools = await _fetch_mcp_tools()
    prompt = _build_summary_prompt(python_tools, mcp_tools)

    try:
        run_result = await agent.run(prompt, instructions=_SUMMARISE_INSTRUCTIONS)
        text = run_result.output
    except Exception as exc:
        logger.warning("tools_summary_llm_failed", error=str(exc))
        text = _build_fallback_html(python_tools, mcp_tools)

    await answer_markdown(message, text)


@router.message(Command("time"))
async def cmd_time(message: Message) -> None:
    """Return the current server time with timezone."""
    result = get_current_time()
    await message.answer(result)
