# ADR-005: SearXNG + Jina Reader + rebrowser-Playwright for Web Research

**Date:** 2025  
**Status:** Accepted

## Context

The agent needs two capabilities: (1) discovering relevant pages given a query, and (2) fetching and reading the content of a specific page. Many pages are JavaScript-rendered (SPAs, news sites, documentation). Some pages use anti-bot measures. The solution must require no paid API keys and must work reliably for personal use.

## Decision

Three-tier web research stack:

**Tier 1 — Search:** SearXNG (self-hosted Docker), queried via HTTP.
- No API key. Aggregates 70+ engines (Google, Bing, DuckDuckGo, Wikipedia, etc.) simultaneously.
- Returns title + URL + snippet; agent selects which URLs to fetch.
- Config at `deploy/searxng/settings.yml`.

**Tier 2 — Page fetch (primary):** Jina Reader (`https://r.jina.ai/{url}`)
- `GET https://r.jina.ai/https://example.com` returns clean Markdown.
- Hosted headless Chrome handles JS-rendered pages.
- Free for personal use; no key required.

**Tier 3 — Page fetch (fallback):** rebrowser-Playwright
- Used when Jina Reader returns empty content, a 403, or a blocked-page indicator.
- Stealth Chromium: patches `navigator.webdriver`, randomizes canvas fingerprint, CDP patches.
- Slower than Jina (cold start ~3s); reserved for pages that block standard fetchers.

Decision logic in `research/application/fetch_page.py`:
```python
result = await jina_client.fetch(url)
if not result or len(result.content) < MIN_USEFUL_CONTENT_LENGTH:
    result = await rebrowser_client.fetch(url)
```

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **DuckDuckGo Python library** | Unofficial library; no SLA; has had multi-week outages; scrapes DDGO UI (fragile) |
| **Brave Search API** | Free tier: 2,000 queries/month — hits limit quickly; paid beyond that |
| **Google Custom Search API** | 100 free queries/day; paid beyond; requires GCP setup and billing |
| **Bing Search API** | Paid (Azure). Not free-tier viable for research-heavy personal use |
| **Standard Playwright (non-stealth)** | Many sites detect headless Chromium via `navigator.webdriver`; rebrowser patches this at the CDP level |
| **Scrapy** | Full crawling framework; too heavy for single-page fetching; no built-in JS rendering |

## Consequences

- SearXNG container must be running for web search; if it is down, the search tool returns a descriptive error
- Jina Reader requires outbound HTTPS from the bot container; no config needed beyond the URL constant
- rebrowser-Playwright needs Chromium installed in the bot container; add to `Dockerfile` as optional install
- For pages that require login or CAPTCHA, all three tiers will fail; the agent should state this clearly rather than hallucinating content
- Future improvement: add a Playwright cache layer to avoid re-fetching the same URL within a session
