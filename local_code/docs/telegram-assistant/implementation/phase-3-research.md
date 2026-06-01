# Phase 3: Web Research — Search + Page Fetching

**Goal:** Add three-tier web research capability: SearXNG for search, Jina Reader for page fetching, rebrowser-Playwright as fallback for blocked pages.  
**Prerequisites:** Phase 2 complete (bot with memory running).  
**Output:** Agent can answer "search for X", "what does this URL say?", and "read this article" using live web data.

---

## Critique Review

**What could go wrong?**
- SearXNG returning empty results due to misconfigured engines: test with `curl` before wiring into agent
- Jina Reader rate-limiting or returning 429: add response status check; fall back to Playwright automatically
- Playwright cold start adding 3–5 seconds to response time: acceptable for fallback; the user is told explicitly that the first fetch takes longer
- Playwright using too much RAM: `rebrowser-chromium` with `--no-sandbox` in Docker; set `--disable-extensions` and `--disable-gpu`; terminate browser after each request (no persistent browser instance in Phase 3)
- Pages with CAPTCHA failing all three tiers: agent must state this clearly; never hallucinate page content

**Simplification applied:** No persistent browser session in Phase 3. Each Playwright call launches, fetches, and closes Chromium. A persistent session optimization can be added later if latency is unacceptable.

---

## Files to Create / Modify

```
src/assistant/
├── research/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── search_result.py      (SearchResult value object)
│   ├── application/
│   │   ├── __init__.py
│   │   ├── search_web.py         (use case: query → list of SearchResult)
│   │   └── fetch_page.py         (use case: url → Markdown content, Jina → Playwright)
│   └── infrastructure/
│       ├── __init__.py
│       ├── searxng_client.py
│       ├── jina_client.py
│       └── rebrowser_client.py
├── agent/
│   └── tools/
│       └── research_tools.py     (search_web, fetch_page tools)
├── agent/
│   └── domain/
│       └── agent.py              (modified: register research tools)
├── Dockerfile                    (modified: install Playwright Chromium)
```

---

## Step-by-Step Implementation

### Step 1 — Add research dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "rebrowser-playwright>=0.1",
    "beautifulsoup4>=4.12",   # for HTML stripping if needed
]
```

```bash
uv lock && uv sync
```

### Step 2 — Domain: SearchResult value object

```python
# research/domain/search_result.py
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
```

### Step 3 — SearXNG Client

```python
# research/infrastructure/searxng_client.py
from typing import List
import httpx
from assistant.research.domain.search_result import SearchResult
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

SEARXNG_TIMEOUT_SECONDS = 15


class SearXNGClient:
    def __init__(self, base_url: str = settings.searxng_url) -> None:
        self._base_url = base_url

    async def search(self, query: str, num_results: int = 5) -> List[SearchResult]:
        """Query SearXNG and return top results as SearchResult objects."""
        params = {
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

        data = response.json()
        results = data.get("results", [])[:num_results]

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
            )
            for r in results
        ]
```

### Step 4 — Jina Reader Client

```python
# research/infrastructure/jina_client.py
import httpx
from typing import Optional
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

JINA_BASE_URL = "https://r.jina.ai"
JINA_TIMEOUT_SECONDS = 30
MIN_USEFUL_CONTENT_LENGTH = 200  # below this, treat as blocked/empty


class JinaClient:
    async def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL via Jina Reader and return clean Markdown content.

        Returns None if the page is empty, blocked, or returns an error.
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
                        status=response.status_code,
                    )
                    return None

                content = response.text.strip()
                if len(content) < MIN_USEFUL_CONTENT_LENGTH:
                    logger.warning("jina_content_too_short", url=url, length=len(content))
                    return None

                return content

        except httpx.HTTPError as e:
            logger.warning("jina_request_failed", url=url, error=str(e))
            return None
```

### Step 5 — rebrowser-Playwright Client

```python
# research/infrastructure/rebrowser_client.py
from typing import Optional
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

PLAYWRIGHT_TIMEOUT_MS = 30_000
MIN_USEFUL_CONTENT_LENGTH = 200


class RebrowserClient:
    async def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL using stealth Chromium via rebrowser-Playwright.

        Used as fallback when Jina Reader fails. Launches and closes
        Chromium per call (no persistent browser in Phase 3).

        Returns cleaned page text as Markdown-ish string, or None on failure.
        """
        try:
            from rebrowser_playwright.async_api import async_playwright

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
                content = await page.evaluate("() => document.body.innerText")
                await browser.close()

            if not content or len(content) < MIN_USEFUL_CONTENT_LENGTH:
                logger.warning("playwright_content_too_short", url=url)
                return None

            return content

        except Exception as e:
            logger.error("playwright_fetch_failed", url=url, error=str(e))
            return None
```

### Step 6 — Use Cases

```python
# research/application/fetch_page.py
from typing import Optional
from assistant.research.infrastructure.jina_client import JinaClient
from assistant.research.infrastructure.rebrowser_client import RebrowserClient
import structlog

logger = structlog.get_logger()

_jina = JinaClient()
_rebrowser = RebrowserClient()


async def fetch_page(url: str) -> Optional[str]:
    """Fetch a URL: try Jina Reader first, fall back to Playwright stealth browser."""
    logger.info("fetch_page_start", url=url)

    content = await _jina.fetch(url)
    if content:
        logger.info("fetch_page_jina_success", url=url, chars=len(content))
        return content

    logger.info("fetch_page_falling_back_to_playwright", url=url)
    content = await _rebrowser.fetch(url)
    if content:
        logger.info("fetch_page_playwright_success", url=url, chars=len(content))
        return content

    logger.warning("fetch_page_all_tiers_failed", url=url)
    return None
```

### Step 7 — Research Tools

```python
# agent/tools/research_tools.py
from pydantic_ai import Agent, RunContext
from assistant.research.application.search_web import search_web
from assistant.research.application.fetch_page import fetch_page
import structlog

logger = structlog.get_logger()


def register_research_tools(agent: Agent) -> None:

    @agent.tool
    async def search(ctx: RunContext, query: str) -> str:
        """Search the web for a query using SearXNG.

        Returns a list of title + URL + snippet for the top results.
        Use fetch_url to read the full content of a specific result.

        Args:
            query: Search query in plain language.
        """
        logger.info("search_tool_called", query=query)
        results = await search_web(query)
        if not results:
            return "No search results found."
        return "\n\n".join(
            f"**{r.title}**\n{r.url}\n{r.snippet}" for r in results
        )

    @agent.tool
    async def fetch_url(ctx: RunContext, url: str) -> str:
        """Fetch and read the content of a specific URL.

        Tries Jina Reader first (fast, handles JS), falls back to
        stealth Chromium if the page is blocked or empty.

        Args:
            url: Full URL including scheme (https://...).
        """
        logger.info("fetch_url_tool_called", url=url)
        content = await fetch_page(url)
        if content is None:
            return f"Unable to fetch content from {url}. The page may require login or be blocking automated access."
        # Truncate to avoid overwhelming context window
        max_chars = 8_000
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n[Content truncated at {max_chars} chars]"
        return content
```

### Step 8 — Update Dockerfile for Playwright

```dockerfile
# Add after uv sync line in Dockerfile
RUN uv run playwright install chromium --with-deps
```

### Step 9 — Register tools in agent

```python
# agent/domain/agent.py (modified)
from assistant.agent.tools.research_tools import register_research_tools

agent = Agent(model=_model, system_prompt=SYSTEM_PROMPT, mcp_servers=[memory_server])
register_research_tools(agent)
```

---

## Verification

- [ ] `curl "http://localhost:8080/search?q=python&format=json"` (from inside bot container) returns results
- [ ] Asking the bot "search for Python asyncio tutorial" returns 3+ results with titles and URLs
- [ ] Asking "what does https://python.org say?" fetches and summarises the Python homepage
- [ ] Testing a URL that Jina blocks confirms Playwright fallback is triggered (check logs: `fetch_page_falling_back_to_playwright`)
- [ ] When both tiers fail, the bot says the page is inaccessible — not a fabricated summary
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create / Modify**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] `SearchResult` is a `@dataclass(frozen=True)` value object — not a raw dict
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] No `except Exception: pass` — HTTP errors and Playwright errors caught specifically and logged
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No `print()` in production paths — structlog used throughout
- [ ] No secrets in source code or logs
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `research/` is a **Supporting bounded context** — `SearchResult` is a value object, no entities or repository interfaces needed
- [ ] `research/domain/search_result.py` — pure Python dataclass; no httpx, no aiogram, no sqlalchemy
- [ ] `research/application/fetch_page.py` — orchestrates Jina → Playwright fallback via injected clients; no direct HTTP in the use case
- [ ] `research/infrastructure/` — HTTP clients only; no business logic; each client is independently replaceable
- [ ] Playwright browser lifecycle (launch/close) is scoped to a single `fetch_page` call — no browser state leaked between requests
- [ ] Fallback to Playwright is logged (`fetch_page_falling_back_to_playwright`) so it is observable

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 4** adds Markdown notes: vault read/write via filesystem and Syncthing bidirectional sync.
