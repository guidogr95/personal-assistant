from __future__ import annotations

import structlog

from assistant.research.infrastructure.jina_client import JinaClient
from assistant.research.infrastructure.rebrowser_client import RebrowserClient

logger = structlog.get_logger()


async def fetch_page(url: str, jina: JinaClient, rebrowser: RebrowserClient) -> str | None:
    """Fetch a URL and return its content as text.

    Tries Jina Reader first (fast, handles JS-heavy pages). Falls back to
    a headless Chromium browser if Jina returns an empty or blocked response.

    Args:
        url: Full URL including scheme (https://...).

    Returns:
        Page content as a string, or None if both tiers fail (e.g. CAPTCHA,
        login wall, or network error). Callers must handle the None case and
        inform the user rather than hallucinating content.
    """
    logger.info("fetch_page_start", url=url)

    content = await jina.fetch(url)
    if content:
        logger.info("fetch_page_jina_success", url=url, chars=len(content))
        return content

    logger.info("fetch_page_falling_back_to_playwright", url=url)
    content = await rebrowser.fetch(url)
    if content:
        logger.info("fetch_page_playwright_success", url=url, chars=len(content))
        return content

    logger.warning("fetch_page_all_tiers_failed", url=url)
    return None
