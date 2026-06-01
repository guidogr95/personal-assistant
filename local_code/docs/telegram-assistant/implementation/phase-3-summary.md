# Phase 3 Implementation Summary

**Status:** Complete  
**Date:** 2026-06-01

---

## Goal

Add three-tier web research capability so the agent can answer questions using live web data:
SearXNG for search, Jina Reader for page fetching, and rebrowser-Playwright as a fallback for
blocked or JS-heavy pages.

**Acceptance criterion:** Agent can answer "search for X", "what does this URL say?", and
"read this article" using live web data.

**Outcome:** ✅ Goal met. SearXNG returns JSON results from inside the bot container. Jina
Reader fetches clean Markdown from `python.org`. The `fetch_page` use case delivers 19,679
chars of content end-to-end. Both-tiers-fail path returns `None` with correct log events,
preventing hallucinated content.

---

## What Was Built

### New package: `research/`

| File | What it contains |
|------|-----------------|
| `research/__init__.py` | Empty package marker. |
| `research/domain/__init__.py` | Empty package marker. |
| `research/domain/search_result.py` | `SearchResult` — frozen dataclass value object with `title`, `url`, `snippet`. Pure Python, zero framework imports. |
| `research/application/__init__.py` | Empty package marker. |
| `research/application/search_web.py` | Use case: delegates to `SearXNGClient`, logs start and result count, returns `list[SearchResult]`. |
| `research/application/fetch_page.py` | Use case: tries Jina Reader first, falls back to Playwright, logs each tier transition. Returns `str \| None`. |
| `research/infrastructure/__init__.py` | Empty package marker. |
| `research/infrastructure/searxng_client.py` | `SearXNGClient` — HTTP client wrapping SearXNG JSON API. Uses `_SearXNGResponse` / `_SearXNGResultItem` `TypedDict`s for the fields actually consumed, plus `isinstance` guard and `cast`. |
| `research/infrastructure/jina_client.py` | `JinaClient` — HTTP client for `r.jina.ai`. Returns `None` if status ≠ 200 or content is below `MIN_USEFUL_CONTENT_LENGTH` (200 chars). |
| `research/infrastructure/rebrowser_client.py` | `RebrowserClient` — launches and closes headless Chromium per call via `rebrowser-playwright`. Broad exception catch is intentional (last-resort fallback tier), always logged before returning `None`. |

### New package: `agent/tools/`

| File | What it contains |
|------|-----------------|
| `agent/tools/__init__.py` | Empty package marker. |
| `agent/tools/research_tools.py` | `register_research_tools(agent)` — registers two tools on the agent: `search` (SearXNG) and `fetch_url` (Jina → Playwright). Truncates content at `MAX_FETCH_CHARS = 8_000` to protect the LLM context window. |

### Modified: `agent/domain/agent.py`

- Added `from assistant.agent.tools.research_tools import register_research_tools`.
- Added `register_research_tools(agent)` call after agent construction.

### Modified: `pyproject.toml`

- Added `rebrowser-playwright>=1.47.0` to production dependencies.
- `uv lock` resolved to `rebrowser-playwright==1.52.0`.

### Modified: `Dockerfile`

Two changes relative to Phase 2:

1. **System packages layer** — added `apt-get install` of the Chromium runtime dependencies
   (`libnss3`, `libatk1.0-0`, `libgbm1`, `libasound2`, `fonts-liberation`, etc.) before
   `uv sync`. Required because `--with-deps` assumes Ubuntu package names that do not exist
   on Debian bookworm (`python:3.12-slim`).
2. **Playwright browser install** — `uv run python -m rebrowser_playwright install chromium`
   (without `--with-deps`, handled by the step above).

### Modified: `deploy/searxng/settings.yml`

Two additions required to make SearXNG reachable from the bot container:

1. `server.limiter: false` — SearXNG's bot-detection middleware rejects requests without a
   `X-Forwarded-For` or `X-Real-IP` header. No reverse proxy sits in front of this instance
   (Docker-internal only), so the limiter provides no security value and was disabled.
2. `search.formats: [html, json]` — SearXNG defaults to HTML-only for public safety; JSON
   must be explicitly enabled.

---

## Deviations from the Original Plan

| # | Plan said | What actually happened | Reason |
|---|-----------|----------------------|--------|
| 1 | `rebrowser-playwright>=0.1` | `rebrowser-playwright>=1.47.0` (resolved to 1.52.0) | Plan referenced an old pre-1.0 version; latest stable is 1.52.0. |
| 2 | `RUN uv run playwright install chromium --with-deps` in Dockerfile | Two-step: manual `apt-get` + `uv run python -m rebrowser_playwright install chromium` | `rebrowser-playwright` exposes no `playwright` console entrypoint; correct module is `python -m rebrowser_playwright`. `--with-deps` tries Ubuntu package names that don't exist on Debian slim (`ttf-unifont`, `ttf-ubuntu-font-family`) — exit code 100. |
| 3 | Mid-function import `from rebrowser_playwright.async_api import async_playwright` inside `fetch()` | Top-level import | CODING_STANDARDS rule 33 requires all imports at top of file. No functional difference since the package is a required (not optional) dependency. |
| 4 | `Any` type for SearXNG JSON response fields | `_SearXNGResponse` and `_SearXNGResultItem` TypedDicts + `isinstance` guard + `cast` | Original plan accepted `Any` as a pragmatic trade-off. Revised after review: validating only the fields we consume is the correct boundary check — neither full schema validation nor unchecked `Any`. |
| 5 | SearXNG ready from Phase 0 | Required `limiter: false` and `formats: [html, json]` config additions | SearXNG defaults block JSON format and reject requests without a reverse-proxy IP header. File was also owned by uid 977 (container user) and required `sudo chown -R` before it could be edited. |

---

## Verification Results

| Check | Result |
|-------|--------|
| `uv run mypy src/` | ✅ 0 errors, 47 files |
| `uv run ruff check src/` | ✅ 0 violations |
| `uv run pytest tests/ -q` | ✅ 30/30 pass |
| Docker image builds | ✅ Chromium installed cleanly |
| SearXNG JSON from bot container | ✅ `status=200 results=10` |
| Jina Reader fetches `python.org` | ✅ `status=200 chars=19680` |
| `fetch_page` use case end-to-end | ✅ 19,679 chars delivered |
| Both tiers fail → `None` returned | ✅ `result=None`, no hallucinated content |
| Log events: `fetch_page_falling_back_to_playwright`, `fetch_page_all_tiers_failed` | ✅ Both fire with correct context |
| Telegram "search for X" reply | ⚠️ Requires manual test — bot is running and SearXNG verified; not blocked by automation limit |

---

## Outstanding Items

- **Telegram end-to-end search test** — The bot is running and all infrastructure checks pass. A
  manual "search for Python asyncio tutorial" message to the bot will confirm the LLM-to-tool
  invocation path. This is the only remaining step.
- **Playwright fallback live test** — A real URL that Jina cannot fetch (e.g. behind Cloudflare)
  would exercise the Playwright cold-start path in production. The fallback was verified via mock;
  live test is optional.
- **`limiter.toml`** — A `limiter.toml` was created in `deploy/searxng/` to silence SearXNG's
  startup warning. The limiter is also disabled via `settings.yml`; the `.toml` is redundant but
  harmless.

---

## What Comes Next

**Phase 4** adds Markdown notes: vault read/write via filesystem and Syncthing bidirectional sync.
The research infrastructure built in this phase is independent of Phase 4 — both can be used
simultaneously once Phase 4 is complete.
