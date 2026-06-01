from __future__ import annotations

import structlog
from pydantic_ai import Agent, RunContext

from assistant.research.application.fetch_page import fetch_page
from assistant.research.application.search_web import search_web

logger = structlog.get_logger()

MAX_FETCH_CHARS: int = 8_000


def register_research_tools(agent: Agent[None, str]) -> None:
    """Register web research tools on the given agent.

    Adds two tools:
    - ``search``: queries SearXNG and returns titles, URLs, and snippets.
    - ``fetch_url``: fetches a URL via Jina Reader with Playwright fallback.
    """

    @agent.tool
    async def search(ctx: RunContext[None], query: str) -> str:
        """Search the web for a query using SearXNG.

        Returns a formatted list of title + URL + snippet for the top results.
        Use fetch_url to read the full content of a specific result.

        Args:
            query: Search query in plain language.
        """
        logger.info("search_tool_called", query=query)
        results = await search_web(query)
        if not results:
            return "No search results found."
        return "\n\n".join(f"**{r.title}**\n{r.url}\n{r.snippet}" for r in results)

    @agent.tool
    async def fetch_url(ctx: RunContext[None], url: str) -> str:
        """Fetch and read the content of a specific URL.

        Tries Jina Reader first (fast, handles JS), falls back to stealth
        Chromium if the page is blocked or returns too little content.
        The first fallback invocation takes 3–5 s longer due to Chromium cold start.

        Args:
            url: Full URL including scheme (https://...).
        """
        logger.info("fetch_url_tool_called", url=url)
        content = await fetch_page(url)
        if content is None:
            return (
                f"Unable to fetch content from {url}. "
                "The page may require login or be blocking automated access."
            )
        if len(content) > MAX_FETCH_CHARS:
            truncation_note = f"\n\n[Content truncated at {MAX_FETCH_CHARS} chars]"
            content = content[:MAX_FETCH_CHARS] + truncation_note
        return content
