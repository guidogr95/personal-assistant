"""Command-to-tool bridge for direct slash-command access to agent tools."""

from __future__ import annotations

import json
from typing import TypedDict

import httpx
import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from assistant.shared.config import settings
from assistant.shared.time import get_current_time
from assistant.telegram.formatting import send_message
from assistant.telegram.keyboards import (
    _TOOL_CATEGORIES,
    build_tool_categories_keyboard,
)

logger = structlog.get_logger()

router = Router()

# Maximum length for a single Telegram text message (safety margin below 4096).
_MAX_TELEGRAM_MESSAGE_LENGTH: int = 3_800


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


def _categorize_tools(
    python_tools: dict[str, str],
    mcp_tools: list[_McpTool] | None,
) -> dict[str, list[tuple[str, str]]]:
    """Group Python and MCP tools by category.

    Returns a dict mapping category display name to a list of (tool_name, description).
    Tools not matching any known category go into "📦 Other".
    """
    categorized: dict[str, list[tuple[str, str]]] = {cat: [] for cat in _TOOL_CATEGORIES}
    categorized["📦 Other"] = []
    categorized["🧠 Memory"] = []

    # Invert the mapping for O(1) lookup
    name_to_category: dict[str, str] = {}
    for cat, names in _TOOL_CATEGORIES.items():
        for name in names:
            name_to_category[name] = cat

    for name, desc in sorted(python_tools.items()):
        cat = name_to_category.get(name, "📦 Other")
        categorized[cat].append((name, desc))

    if mcp_tools is not None:
        for tool in mcp_tools:
            categorized["🧠 Memory"].append((tool["name"], tool["description"]))
    else:
        categorized["🧠 Memory"] = [("(unavailable)", "MCP server did not respond")]

    # Remove empty categories
    return {k: v for k, v in categorized.items() if v}


def _build_category_detail_markdown(
    category_name: str,
    tools: list[tuple[str, str]],
) -> str:
    """Build Markdown for a single category's tool listing.

    Each tool is shown as `` `name` — one-line description ``.
    """
    lines: list[str] = [f"**{category_name}**", ""]
    for name, desc in tools:
        short_desc = (desc or "(no description)").split("\n")[0].strip()
        if len(short_desc) > 120:
            short_desc = short_desc[:117] + "…"
        lines.append(f"`{name}` — {short_desc}")
    return "\n".join(lines)


def _build_all_tools_markdown(
    categorized: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """Build a compact Markdown listing of all tools, split into message-sized chunks.

    Returns a list of Markdown strings, each under the Telegram message length limit.
    """
    chunks: list[str] = []
    current_lines: list[str] = ["**🛠️ All Assistant Tools**", ""]
    current_length: int = len(current_lines[0]) + len(current_lines[1])

    for category_name, tools in categorized.items():
        category_header = f"**{category_name}**"
        category_lines: list[str] = [category_header]
        for name, desc in tools:
            short_desc = (desc or "(no description)").split("\n")[0].strip()
            if len(short_desc) > 120:
                short_desc = short_desc[:117] + "…"
            category_lines.append(f"  `{name}` — {short_desc}")
        category_lines.append("")

        category_text = "\n".join(category_lines)
        if current_length + len(category_text) > _MAX_TELEGRAM_MESSAGE_LENGTH and current_lines:
            chunks.append("\n".join(current_lines).rstrip())
            current_lines = [category_header]
            current_length = len(category_header)
        else:
            current_lines.extend(category_lines)
            current_length += len(category_text)

    if current_lines:
        chunks.append("\n".join(current_lines).rstrip())

    return chunks


@router.message(Command("tools"))
async def cmd_tools(message: Message) -> None:
    """Show a category browser for all agent tools.

    Presents an inline keyboard where each button selects a functional domain.
    Tapping a category shows the tools in that domain with compact descriptions.
    A "📋 Show All" button sends a compact text listing of every tool.
    """
    await send_message(
        message,
        "**🛠️ Assistant Tools**\n\nTap a category to see the tools inside it:",
        reply_markup=build_tool_categories_keyboard(),
    )


@router.message(Command("time"))
async def cmd_time(message: Message) -> None:
    """Return the current server time with timezone."""
    result = get_current_time()
    await message.answer(result)
