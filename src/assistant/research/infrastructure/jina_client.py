from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

JINA_BASE_URL: str = "https://r.jina.ai"
JINA_TIMEOUT_SECONDS: int = 30
MIN_USEFUL_CONTENT_LENGTH: int = 200


class JinaClient:
    """HTTP client for the Jina Reader free API.

    Converts URLs into clean Markdown. Returns None if the page is empty,
    blocked, or returns a non-200 response — the caller decides whether to
    fall back to another tier.
    """

    async def fetch(self, url: str) -> str | None:
        """Fetch a URL via Jina Reader and return clean Markdown content.

        Args:
            url: Full URL including scheme (https://...).

        Returns:
            Markdown string if the page is fetchable and has meaningful content.
            None if Jina returns an error, the page is blocked, or content is too short
            to be useful (likely a CAPTCHA or login wall).
        """
        try:
            async with httpx.AsyncClient(timeout=JINA_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{JINA_BASE_URL}/{url}",
                    headers={"Accept": "text/markdown"},
                )
                if response.status_code != 200:
                    logger.warning(
                        "jina_non_200",
                        url=url,
                        status_code=response.status_code,
                    )
                    return None

                content = response.text.strip()
                if len(content) < MIN_USEFUL_CONTENT_LENGTH:
                    # Suspiciously short — likely a CAPTCHA page or login wall.
                    logger.warning("jina_content_too_short", url=url, length=len(content))
                    return None

                return content

        except httpx.HTTPError as e:
            logger.warning("jina_request_failed", url=url, error=str(e))
            return None
