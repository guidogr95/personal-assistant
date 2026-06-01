from __future__ import annotations

import structlog
from rebrowser_playwright.async_api import async_playwright

logger = structlog.get_logger()

PLAYWRIGHT_TIMEOUT_MS: int = 30_000
MIN_USEFUL_CONTENT_LENGTH: int = 200


class RebrowserClient:
    """Stealth browser fallback using rebrowser-Playwright + Chromium.

    Used only when Jina Reader fails (blocked page or non-200 response).
    Each call launches a fresh Chromium process and closes it after the fetch —
    no persistent browser state between requests. This keeps memory bounded
    at the cost of a ~3-5 s cold-start latency per fallback invocation.
    """

    async def fetch(self, url: str) -> str | None:
        """Fetch a URL using a headless Chromium browser and return the page text.

        Args:
            url: Full URL including scheme (https://...).

        Returns:
            Plain-text page content if the page loads and has meaningful content.
            None if the page fails to load, times out, or returns too-short content.
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                        "--disable-extensions",
                    ]
                )
                page = await browser.new_page()
                await page.goto(url, timeout=PLAYWRIGHT_TIMEOUT_MS, wait_until="domcontentloaded")
                content: str = await page.evaluate("() => document.body.innerText")
                await browser.close()

            if not content or len(content) < MIN_USEFUL_CONTENT_LENGTH:
                logger.warning("playwright_content_too_short", url=url, length=len(content))
                return None

            return content

        except Exception as e:
            # Playwright raises many exception types (TimeoutError, TargetClosedError,
            # network errors). Catch broadly here since this is the last fallback tier —
            # we log the failure and surface None to the caller.
            logger.error("playwright_fetch_failed", url=url, error=str(e))
            return None
