from __future__ import annotations

from typing import NotRequired, TypedDict, cast

import httpx
import structlog

from assistant.research.domain.search_result import SearchResult
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError

logger = structlog.get_logger()

SEARXNG_TIMEOUT_SECONDS: int = 15
DEFAULT_NUM_RESULTS: int = 5


class _SearXNGResultItem(TypedDict, total=False):
    """Partial shape of a SearXNG result item — only the fields we consume."""

    title: str
    url: str
    content: str


class _SearXNGResponse(TypedDict):
    """Partial shape of the SearXNG JSON response — only the field we consume."""

    results: NotRequired[list[_SearXNGResultItem]]


class SearXNGClient:
    """HTTP client for the self-hosted SearXNG meta-search engine.

    Fetches results as JSON and converts them to SearchResult value objects.
    Raises InfrastructureError on any HTTP or network failure.
    """

    def __init__(self, base_url: str = settings.searxng_url) -> None:
        self._base_url = base_url

    async def search(
        self, query: str, num_results: int = DEFAULT_NUM_RESULTS
    ) -> list[SearchResult]:
        """Query SearXNG and return the top results.

        Args:
            query: Plain-language search query.
            num_results: Maximum number of results to return.

        Returns:
            List of SearchResult value objects (may be empty if the engine returns none).

        Raises:
            InfrastructureError: If SearXNG is unreachable, returns a non-2xx response,
                or returns a body that is not a JSON object.
        """
        params: dict[str, str | int] = {
            "q": query,
            "format": "json",
            "language": "en",
            "safesearch": "0",
        }
        try:
            async with httpx.AsyncClient(timeout=SEARXNG_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{self._base_url}/search", params=params)
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("searxng_request_failed", query=query, error=str(e))
            raise InfrastructureError("SearXNG search failed") from e

        body = response.json()
        if not isinstance(body, dict):
            logger.error(
                "searxng_unexpected_response_shape",
                query=query,
                body_type=type(body).__name__,
            )
            raise InfrastructureError("SearXNG returned an unexpected response format")

        data: _SearXNGResponse = cast(_SearXNGResponse, body)
        raw_results: list[_SearXNGResultItem] = data.get("results", [])[:num_results]

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in raw_results
        ]
