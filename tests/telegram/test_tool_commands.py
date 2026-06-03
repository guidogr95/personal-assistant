"""Tests for the /tools command helper functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from assistant.telegram.handlers.tool_commands import (
    _build_all_tools_markdown,
    _build_category_detail_markdown,
    _categorize_tools,
    _fetch_mcp_tools,
    _McpTool,
)

# ---------------------------------------------------------------------------
# _categorize_tools
# ---------------------------------------------------------------------------


def test_should_group_known_tools_into_categories() -> None:
    tools = {
        "get_current_time": "Get time.",
        "create_note": "Create a note.",
        "search": "Search web.",
    }
    categorized = _categorize_tools(tools, mcp_tools=None)
    assert "🕐 Time" in categorized
    assert "📝 Notes" in categorized
    assert "🔍 Research" in categorized
    assert any(name == "get_current_time" for name, _ in categorized["🕐 Time"])


def test_should_place_unknown_tools_in_other() -> None:
    tools = {"mystery_tool": "Unknown."}
    categorized = _categorize_tools(tools, mcp_tools=None)
    assert "📦 Other" in categorized
    assert any(name == "mystery_tool" for name, _ in categorized["📦 Other"])


def test_should_include_mcp_tools_in_memory_category() -> None:
    mcp: list[_McpTool] = [
        _McpTool(name="store_memory", description="Store a memory."),
    ]
    categorized = _categorize_tools({}, mcp_tools=mcp)
    assert "🧠 Memory" in categorized
    assert any(name == "store_memory" for name, _ in categorized["🧠 Memory"])


def test_should_show_mcp_unavailable_when_none() -> None:
    categorized = _categorize_tools({}, mcp_tools=None)
    assert "🧠 Memory" in categorized
    assert any(name == "(unavailable)" for name, _ in categorized["🧠 Memory"])


# ---------------------------------------------------------------------------
# _build_category_detail_markdown
# ---------------------------------------------------------------------------


def test_should_render_tools_in_category_with_descriptions() -> None:
    tools = [
        ("get_current_time", "Get the current server time."),
        ("search", "Search the web."),
    ]
    markdown = _build_category_detail_markdown("🕐 Time", tools)
    assert "**🕐 Time**" in markdown
    assert "`get_current_time`" in markdown
    assert "Get the current server time." in markdown


def test_should_truncate_long_descriptions() -> None:
    long_desc = "x" * 200
    tools = [("slow_tool", long_desc)]
    markdown = _build_category_detail_markdown("📦 Other", tools)
    assert "…" in markdown
    assert len(markdown) < len(long_desc) + 100


def test_should_preserve_html_in_tool_names_in_markdown() -> None:
    tools = [("tool<a>", "Does a thing.")]
    markdown = _build_category_detail_markdown("📦 Other", tools)
    assert "`tool<a>`" in markdown


# ---------------------------------------------------------------------------
# _build_all_tools_markdown
# ---------------------------------------------------------------------------


def test_should_split_into_chunks_when_text_exceeds_limit() -> None:
    # Create many tools with very long descriptions to force chunking
    tools = {f"tool_{i}": "Description line one. Line two. Line three." * 100 for i in range(30)}
    categorized = _categorize_tools(tools, mcp_tools=None)
    chunks = _build_all_tools_markdown(categorized)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 3_800


def test_should_include_all_categories_in_chunks() -> None:
    tools = {"get_current_time": "Get time.", "create_note": "Create."}
    categorized = _categorize_tools(tools, mcp_tools=None)
    chunks = _build_all_tools_markdown(categorized)
    full_text = "\n".join(chunks)
    assert "🕐 Time" in full_text
    assert "📝 Notes" in full_text
    assert "`get_current_time`" in full_text


# ---------------------------------------------------------------------------
# _fetch_mcp_tools — SSE and plain JSON parsing
# ---------------------------------------------------------------------------


def _make_response(text: str, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _sse_wrap(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


_TOOLS_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {"name": "store_memory", "description": "Store a memory."},
            {"name": "recall_memory", "description": "Recall past memories."},
        ]
    },
}


async def test_should_parse_sse_wrapped_response() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=_make_response(_sse_wrap(_TOOLS_PAYLOAD)))

    with patch(
        "assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client
    ):
        result = await _fetch_mcp_tools()

    assert result is not None
    names = [t["name"] for t in result]
    assert "store_memory" in names
    assert "recall_memory" in names


async def test_should_parse_plain_json_response() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=_make_response(json.dumps(_TOOLS_PAYLOAD)))

    with patch(
        "assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client
    ):
        result = await _fetch_mcp_tools()

    assert result is not None
    assert len(result) == 2
    assert result[0]["description"] == "Store a memory."


async def test_should_return_none_when_http_raises() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

    with patch(
        "assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client
    ):
        result = await _fetch_mcp_tools()

    assert result is None


async def test_should_return_none_when_result_is_not_dict() -> None:
    payload = {"jsonrpc": "2.0", "id": 1, "result": ["unexpected", "list"]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=_make_response(json.dumps(payload)))

    with patch(
        "assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client
    ):
        result = await _fetch_mcp_tools()

    assert result is None


async def test_should_skip_tools_without_string_name() -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "tools": [
                {"name": "valid_tool", "description": "Fine."},
                {"name": 123, "description": "Bad name type."},
                {"description": "Missing name entirely."},
            ]
        },
    }
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=_make_response(json.dumps(payload)))

    with patch(
        "assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client
    ):
        result = await _fetch_mcp_tools()

    assert result is not None
    assert len(result) == 1
    assert result[0]["name"] == "valid_tool"
