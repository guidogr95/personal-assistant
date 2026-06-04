from __future__ import annotations

import structlog

from assistant.research.domain.search_result import SearchResult
from assistant.research.infrastructure.searxng_client import SearXNGClient

logger = structlog.get_logger()


async def search_web(query: str, client: SearXNGClient) -> list[SearchResult]:
    """Execute a web search via SearXNG and return structured results.

    Args:
        query: Plain-language search query.

    Returns:
        List of SearchResult value objects. Empty list if no results found.

    Raises:
        InfrastructureError: If SearXNG is unreachable.
    """
    logger.info("search_web_start", query=query)
    results = await client.search(query)
    logger.info("search_web_complete", query=query, result_count=len(results))
    return results
