"""Tests for the Markdown to Telegram-safe HTML converter."""

from __future__ import annotations

from assistant.telegram.markdown_to_html import convert_markdown_to_telegram_html


class TestConvertMarkdownToTelegramHtml:
    """Test cases for convert_markdown_to_telegram_html."""

    def test_should_convert_bold_text(self) -> None:
        md = "**bold text**"
        result = convert_markdown_to_telegram_html(md)
        assert "<b>bold text</b>" in result or "<strong>bold text</strong>" in result

    def test_should_convert_italic_text(self) -> None:
        md = "*italic text*"
        result = convert_markdown_to_telegram_html(md)
        assert "<i>italic text</i>" in result or "<em>italic text</em>" in result

    def test_should_convert_inline_code(self) -> None:
        md = "`inline code`"
        result = convert_markdown_to_telegram_html(md)
        assert "<code>inline code</code>" in result

    def test_should_convert_code_block(self) -> None:
        md = "```python\nprint(1)\n```"
        result = convert_markdown_to_telegram_html(md)
        assert "<pre>" in result
        assert "print(1)" in result

    def test_should_convert_headings_to_bold(self) -> None:
        md = "# Heading 1\n\n## Heading 2"
        result = convert_markdown_to_telegram_html(md)
        assert "<h1>" not in result
        assert "<h2>" not in result
        assert "<b>Heading 1</b>" in result
        assert "<b>Heading 2</b>" in result

    def test_should_convert_unordered_list(self) -> None:
        md = "- item 1\n- item 2"
        result = convert_markdown_to_telegram_html(md)
        assert "<ul>" not in result
        assert "<li>" not in result
        assert "- item 1" in result
        assert "- item 2" in result

    def test_should_convert_ordered_list(self) -> None:
        md = "1. first\n2. second"
        result = convert_markdown_to_telegram_html(md)
        assert "<ol>" not in result
        assert "<li>" not in result
        assert "1. first" in result
        assert "2. second" in result

    def test_should_convert_blockquote_to_italic(self) -> None:
        md = "> a quote"
        result = convert_markdown_to_telegram_html(md)
        assert "<blockquote>" not in result
        assert "<i>a quote" in result
        assert "</i>" in result

    def test_should_convert_link(self) -> None:
        md = "[text](https://example.com)"
        result = convert_markdown_to_telegram_html(md)
        assert '<a href="https://example.com">text</a>' in result

    def test_should_handle_mixed_content(self) -> None:
        md = (
            "# Title\n\n"
            "Some **bold** and *italic* text.\n\n"
            "- item 1\n"
            "- item 2\n\n"
            "```\ncode block\n```"
        )
        result = convert_markdown_to_telegram_html(md)
        assert "<b>Title</b>" in result
        assert "<b>bold</b>" in result or "<strong>bold</strong>" in result
        assert "- item 1" in result
        assert "<pre>" in result
        assert "<h1>" not in result
        assert "<ul>" not in result

    def test_should_strip_unsupported_tags_defensively(self) -> None:
        # This tests the defensive stripping — mistune shouldn't produce these,
        # but we verify the stripper works.
        md = "<div>content</div>"
        result = convert_markdown_to_telegram_html(md)
        assert "<div>" not in result
        assert "content" in result

    def test_should_preserve_plain_text(self) -> None:
        md = "Just plain text."
        result = convert_markdown_to_telegram_html(md)
        assert "Just plain text." in result

    def test_should_strip_details_and_summary_tags(self) -> None:
        md = "<details><summary>Click me</summary>Hidden content</details>"
        result = convert_markdown_to_telegram_html(md)
        assert "<details>" not in result
        assert "<summary>" not in result
        assert "Click me" in result
        assert "Hidden content" in result
