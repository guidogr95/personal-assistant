"""Markdown to Telegram-safe HTML converter.

Uses mistune for parsing, then maps unsupported HTML tags to Telegram's
supported subset (<b>, <i>, <code>, <pre>, <a>). Telegram does not support
<h1>–<h6>, <ul>, <ol>, <li>, <blockquote>, <p>, or <br>.
"""

from __future__ import annotations

import re

import mistune


def convert_markdown_to_telegram_html(markdown_text: str) -> str:
    """Convert Markdown to Telegram-safe HTML.

    Uses mistune for parsing, then maps unsupported tags to
    Telegram's supported subset.

    Args:
        markdown_text: Raw Markdown text.

    Returns:
        HTML string safe for Telegram's parse_mode="HTML".
    """
    raw_html = mistune.html(markdown_text)
    if not isinstance(raw_html, str):
        raise TypeError(
            f"Expected str from mistune.html, got {type(raw_html).__name__}"
        )
    return _map_unsupported_tags(raw_html)


def _map_unsupported_tags(html_text: str) -> str:
    """Map HTML tags unsupported by Telegram to supported equivalents.

    Telegram supports: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>,
    <strike>, <del>, <code>, <pre>, <a href="...">.

    Maps:
        <h1>–<h6> → <b>text</b>
        <ul> / <ol> → plain text with list prefixes on <li> items
        <li> → item text with "- " or "1. " prefix
        <blockquote> → <i>text</i>
        <br> → \n
        <p> → \n\n

    Any remaining unsupported tags are stripped defensively.
    """
    # Process block-level elements first (headings, lists, blockquotes, paragraphs)
    result = _process_headings(html_text)
    result = _process_lists(result)
    result = _process_blockquotes(result)
    result = _process_paragraphs(result)
    result = _process_line_breaks(result)

    # Defensive: strip any remaining unsupported tags while preserving content
    result = _strip_remaining_unsupported_tags(result)

    # Clean up excessive blank lines from tag removal
    result = _collapse_excessive_blank_lines(result)

    return result.strip()


def _process_headings(html_text: str) -> str:
    """Replace <h1>–<h6> with <b>text</b>."""
    for level in range(1, 7):
        open_tag = f"<h{level}>"
        close_tag = f"</h{level}>"
        html_text = html_text.replace(open_tag, "<b>")
        html_text = html_text.replace(close_tag, "</b>")
    return html_text


def _process_lists(html_text: str) -> str:
    """Replace <ul>/<ol> with plain text; prefix <li> items.

    Handles nested lists by tracking depth.
    """
    # Simple approach: process li tags with their parent context
    # First, handle ordered lists (ol)
    result = _process_ordered_lists(html_text)
    # Then unordered lists (ul)
    result = _process_unordered_lists(result)
    return result


def _process_ordered_lists(html_text: str) -> str:
    """Replace <ol>...<li>...</li>...</ol> with numbered items."""
    pattern = re.compile(r"<ol[^>]*>(.*?)</ol>", re.DOTALL)

    def replace_ol(match: re.Match[str]) -> str:
        content = match.group(1)
        items = _extract_list_items(content)
        lines = [f"{i + 1}. {_strip_li_tags(item)}" for i, item in enumerate(items)]
        return "\n".join(lines)

    return pattern.sub(replace_ol, html_text)


def _process_unordered_lists(html_text: str) -> str:
    """Replace <ul>...<li>...</li>...</ul> with bullet items."""
    pattern = re.compile(r"<ul[^>]*>(.*?)</ul>", re.DOTALL)

    def replace_ul(match: re.Match[str]) -> str:
        content = match.group(1)
        items = _extract_list_items(content)
        lines = [f"- {_strip_li_tags(item)}" for item in items]
        return "\n".join(lines)

    return pattern.sub(replace_ul, html_text)


def _extract_list_items(content: str) -> list[str]:
    """Extract top-level <li> items from list content.

    Handles nested lists by only matching direct <li> children.
    """
    items: list[str] = []
    depth = 0
    current = ""
    i = 0
    while i < len(content):
        if content[i : i + 4].lower() == "<li>":
            if depth == 0:
                current = ""
            depth += 1
            i += 4
            continue
        if content[i : i + 5].lower() == "</li>":
            depth -= 1
            i += 5
            if depth == 0:
                items.append(current)
                current = ""
            continue
        if depth > 0:
            current += content[i]
        i += 1
    return items


def _strip_li_tags(item_text: str) -> str:
    """Remove any remaining <li> / </li> tags from item text."""
    return (
        item_text
        .replace("<li>", "")
        .replace("</li>", "")
        .replace("<LI>", "")
        .replace("</LI>", "")
        .strip()
    )


def _process_blockquotes(html_text: str) -> str:
    """Replace <blockquote> with <i>text</i>."""
    pattern = re.compile(r"<blockquote[^>]*>(.*?)</blockquote>", re.DOTALL)

    def replace_blockquote(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        return f"<i>{content}</i>"

    return pattern.sub(replace_blockquote, html_text)


def _process_paragraphs(html_text: str) -> str:
    """Replace <p> with double newlines."""
    # Handle <p>...</p> pairs
    pattern = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)

    def replace_p(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        return f"{content}\n\n"

    return pattern.sub(replace_p, html_text)


def _process_line_breaks(html_text: str) -> str:
    """Replace <br> and <br/> with single newlines."""
    html_text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
    return html_text


def _strip_remaining_unsupported_tags(html_text: str) -> str:
    """Defensively strip any remaining unsupported HTML tags.

    Preserves the text content inside the tags.
    """
    # List of tags that Telegram does NOT support (that might remain)
    unsupported_tags = [
        "div", "span", "table", "thead", "tbody", "tr", "td", "th",
        "hr", "dl", "dt", "dd", "figure", "figcaption", "main",
        "article", "section", "header", "footer", "nav", "aside",
    ]

    for tag in unsupported_tags:
        # Remove opening tags with attributes
        html_text = re.sub(rf"<{tag}[^>]*>", "", html_text, flags=re.IGNORECASE)
        # Remove closing tags
        html_text = re.sub(rf"</{tag}>", "", html_text, flags=re.IGNORECASE)

    return html_text


def _collapse_excessive_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive newlines to 2 newlines."""
    return re.sub(r"\n{3,}", "\n\n", text)
