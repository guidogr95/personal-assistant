"""Tests for the /tools command helper functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assistant.telegram.handlers.tool_commands import (
    _McpTool,
    _build_fallback_html,
    _build_summary_prompt,
    _fetch_mcp_tools,
)

# ---------------------------------------------------------------------------
# _build_summary_prompt
# ---------------------------------------------------------------------------


def test_should_include_all_python_tools_in_prompt() -> None:
    tools = {"get_current_time": "Get the current time.", "create_note": "Create a note."}
    prompt = _build_summary_prompt(tools, mcp_tools=None)
    assert "get_current_time" in prompt
    assert "create_note" in prompt
    assert "Get the current time." in prompt


def test_should_sort_python_tools_alphabetically_in_prompt() -> None:
    tools = {"zzz_tool": "Last.", "aaa_tool": "First."}
    prompt = _build_summary_prompt(tools, mcp_tools=None)
    assert prompt.index("aaa_tool") < prompt.index("zzz_tool")


def test_should_include_mcp_tools_when_available() -> None:
    mcp: list[_McpTool] = [
        _McpTool(name="store_memory", description="Store a memory."),
        _McpTool(name="recall_memory", description="Recall memories."),
    ]
    prompt = _build_summary_prompt({}, mcp_tools=mcp)
    assert "store_memory" in prompt
    assert "recall_memory" in prompt
    assert "memory/MCP" in prompt


def test_should_note_mcp_unavailable_when_none() -> None:
    prompt = _build_summary_prompt({"a_tool": "Does a thing."}, mcp_tools=None)
    assert "unavailable" in prompt.lower()


def test_should_use_placeholder_for_tool_with_no_description() -> None:
    prompt = _build_summary_prompt({"silent_tool": ""}, mcp_tools=None)
    assert "(no description)" in prompt


# ---------------------------------------------------------------------------
# _build_fallback_html
# ---------------------------------------------------------------------------


def test_should_list_all_python_tool_names_in_fallback_html() -> None:
    tools = {"create_note": "Create a note.", "delete_note": "Delete a note."}
    html = _build_fallback_html(tools, mcp_tools=None)
    assert "<code>create_note</code>" in html
    assert "<code>delete_note</code>" in html


def test_should_show_mcp_unavailable_message_when_none() -> None:
    html = _build_fallback_html({}, mcp_tools=None)
    assert "MCP server did not respond" in html


def test_should_list_mcp_tools_when_available() -> None:
    mcp: list[_McpTool] = [_McpTool(name="store_memory", description="")]
    html = _build_fallback_html({}, mcp_tools=mcp)
    assert "<code>store_memory</code>" in html
    assert "MCP server did not respond" not in html


def test_should_escape_html_special_chars_in_tool_name() -> None:
    # Synthetic name with HTML-unsafe characters — ensures html.escape is called.
    mcp: list[_McpTool] = [_McpTool(name="tool<a>&b", description="")]
    html_output = _build_fallback_html({}, mcp_tools=mcp)
    assert "<a>" not in html_output
    assert "tool&lt;a&gt;&amp;b" in html_output


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

    with patch("assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_mcp_tools()

    assert result is not None
    names = [t["name"] for t in result]
    assert "store_memory" in names
    assert "recall_memory" in names


async def test_should_parse_plain_json_response() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(
        return_value=_make_response(json.dumps(_TOOLS_PAYLOAD))
    )

    with patch("assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_mcp_tools()

    assert result is not None
    assert len(result) == 2
    assert result[0]["description"] == "Store a memory."


async def test_should_return_none_when_http_raises() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

    with patch("assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_mcp_tools()

    assert result is None


async def test_should_return_none_when_result_is_not_dict() -> None:
    payload = {"jsonrpc": "2.0", "id": 1, "result": ["unexpected", "list"]}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=_make_response(json.dumps(payload)))

    with patch("assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client):
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

    with patch("assistant.telegram.handlers.tool_commands.httpx.AsyncClient", return_value=mock_client):
        result = await _fetch_mcp_tools()

    assert result is not None
    assert len(result) == 1
    assert result[0]["name"] == "valid_tool"
