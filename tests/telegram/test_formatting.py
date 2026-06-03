"""Tests for the unified Telegram sender and Markdown helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import InlineKeyboardMarkup, Message

from assistant.telegram.formatting import (
    _generate_file_request_hash,
    _truncate_to_safe_boundary,
    bold,
    code,
    italic,
    link,
    pre,
    send_message,
)


class TestMarkdownHelpers:
    """Test cases for Markdown-producing helpers."""

    def test_bold_should_wrap_in_double_asterisks(self) -> None:
        assert bold("text") == "**text**"

    def test_bold_should_escape_existing_asterisks(self) -> None:
        assert bold("a*b") == "**a\\*b**"

    def test_italic_should_wrap_in_single_asterisks(self) -> None:
        assert italic("text") == "*text*"

    def test_italic_should_escape_existing_underscores(self) -> None:
        assert italic("a_b") == "*a\\_b*"

    def test_code_should_wrap_in_backticks(self) -> None:
        assert code("text") == "`text`"

    def test_code_should_escape_existing_backticks(self) -> None:
        assert code("a`b") == "`a\\`b`"

    def test_pre_should_wrap_in_fences(self) -> None:
        assert pre("text") == "```\ntext\n```"

    def test_link_should_build_markdown_hyperlink(self) -> None:
        assert link("text", "https://example.com") == "[text](https://example.com)"

    def test_link_should_escape_closing_bracket(self) -> None:
        assert link("te]xt", "https://example.com") == "[te\\]xt](https://example.com)"


class TestTruncateToSafeBoundary:
    """Test cases for _truncate_to_safe_boundary."""

    def test_should_return_short_text_unchanged(self) -> None:
        text = "short text"
        assert _truncate_to_safe_boundary(text, 100) == text

    def test_should_truncate_at_end_of_line(self) -> None:
        text = "line one\nline two\nline three"
        result = _truncate_to_safe_boundary(text, 20)
        assert "line one" in result
        assert "line three" not in result
        assert "… (truncated)" in result

    def test_should_truncate_at_end_of_tag(self) -> None:
        text = "<b>bold text</b> more content here"
        result = _truncate_to_safe_boundary(text, 20)
        assert "<b>bold text</b>" in result
        assert "… (truncated)" in result

    def test_should_truncate_at_word_boundary(self) -> None:
        text = "one two three four five"
        result = _truncate_to_safe_boundary(text, 12)
        assert "one two" in result
        assert "… (truncated)" in result

    def test_should_hard_truncate_when_no_safe_boundary(self) -> None:
        text = "a" * 100
        result = _truncate_to_safe_boundary(text, 50)
        assert len(result) <= 70  # 50 + "… (truncated)" with margin
        assert "… (truncated)" in result


class TestGenerateFileRequestHash:
    """Test cases for _generate_file_request_hash."""

    def test_should_return_different_hashes_for_different_inputs(self) -> None:
        h1 = _generate_file_request_hash("text1", "file1")
        h2 = _generate_file_request_hash("text2", "file2")
        assert h1 != h2

    def test_should_return_different_hashes_for_same_input_at_different_times(self) -> None:
        h1 = _generate_file_request_hash("text", "file")
        import time

        time.sleep(0.01)
        h2 = _generate_file_request_hash("text", "file")
        assert h1 != h2

    def test_should_return_16_character_hash(self) -> None:
        h = _generate_file_request_hash("text", "file")
        assert len(h) == 16


class TestSendMessage:
    """Test cases for send_message unified sender."""

    @pytest.mark.asyncio
    async def test_should_send_short_text_as_single_message(self) -> None:
        mock_message = AsyncMock(spec=Message)
        mock_message.answer = AsyncMock(return_value=MagicMock(spec=Message))

        result = await send_message(mock_message, "Hello **world**")

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert call_args.kwargs["parse_mode"] == "HTML"
        assert "<strong>world</strong>" in call_args.args[0]
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_should_send_via_bot_with_chat_id(self) -> None:
        from aiogram import Bot

        mock_bot = AsyncMock(spec=Bot)
        mock_bot.send_message = AsyncMock(return_value=MagicMock(spec=Message))

        result = await send_message(mock_bot, "Hello", chat_id=12345)

        mock_bot.send_message.assert_called_once()
        call_args = mock_bot.send_message.call_args
        assert call_args.kwargs["chat_id"] == 12345
        assert call_args.kwargs["parse_mode"] == "HTML"
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_should_raise_when_bot_without_chat_id(self) -> None:
        from aiogram import Bot

        mock_bot = AsyncMock(spec=Bot)
        with pytest.raises(ValueError, match="chat_id is required"):
            await send_message(mock_bot, "Hello")

    @pytest.mark.asyncio
    async def test_should_truncate_long_text(self) -> None:
        mock_message = AsyncMock(spec=Message)
        mock_message.answer = AsyncMock(return_value=MagicMock(spec=Message))

        long_text = "A" * 5000
        result = await send_message(mock_message, long_text)

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        sent_text = call_args.args[0]
        assert len(sent_text) <= 3800 + 50  # margin for truncation suffix
        assert "… (truncated)" in sent_text

    @pytest.mark.asyncio
    async def test_should_add_file_button_for_long_text_with_source_filename(self) -> None:
        mock_message = AsyncMock(spec=Message)
        mock_message.answer = AsyncMock(return_value=MagicMock(spec=Message))

        long_text = "A" * 5000
        with patch("assistant.telegram.formatting.store_file_request") as mock_store:
            result = await send_message(
                mock_message, long_text, source_filename="note.md"
            )

        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        reply_markup = call_args.kwargs.get("reply_markup")
        assert reply_markup is not None
        mock_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_fallback_to_plain_text_on_telegram_bad_request(self) -> None:
        from aiogram.exceptions import TelegramBadRequest

        mock_message = AsyncMock(spec=Message)
        # First call raises, second call succeeds
        mock_message.answer = AsyncMock(
            side_effect=[
                TelegramBadRequest(method="sendMessage", message="Bad Request"),
                MagicMock(spec=Message),
            ]
        )

        result = await send_message(mock_message, "Hello **world**")

        assert mock_message.answer.call_count == 2
        second_call = mock_message.answer.call_args_list[1]
        assert second_call.kwargs.get("parse_mode") is None
        assert "Hello world" in second_call.args[0]
