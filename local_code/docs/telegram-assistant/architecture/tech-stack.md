# Technology Stack

## Runtime

| Concern | Technology | Version | Justification |
|---|---|---|---|
| Language | Python | 3.12+ | Pydantic AI, aiogram, all chosen libraries are Python-native; async ecosystem mature |
| Package manager | uv | latest | Faster than pip/poetry; deterministic lockfile (`uv.lock`); reproducible builds |
| Async runtime | asyncio (stdlib) | — | Pydantic AI and aiogram both require async; no event loop bridging needed |

## Agent & LLM

| Concern | Technology | Version | Justification |
|---|---|---|---|
| Agent framework | Pydantic AI | ≥0.2.0 | Provider-agnostic via `OpenAIModel(base_url=..., api_key=...)`; built-in `MCPClient`; typed tools via Python type hints; no LangChain dependency; 3x less boilerplate than LangGraph for a linear tool-calling loop |
| LLM provider | OpenCode Go | — | `base_url=https://opencode.ai/zen/go/v1`; OpenAI-compatible API; model list at `/models`; user's existing API keys |
| Telegram library | aiogram | 3.x | Fully async-native design; best inline keyboard / callback query handling; FSM support |

## Storage

| Concern | Technology | Version | Justification |
|---|---|---|---|
| Conversation history + scheduler jobs | SQLite via `aiosqlite` | — | Zero-ops; single file; sufficient for single-user; portable across environments |
| SQL access | SQLAlchemy Core (not ORM) | 2.x | Parameterized queries without ORM overhead; async-compatible via `aiosqlite` dialect |
| Scheduled job persistence | APScheduler `SQLAlchemyJobStore` | 3.x | Jobs survive bot restarts; SQLite-backed; in-process (no extra service) |
| Long-term memory | mcp-memory-service | Docker (`doobidoo/mcp-memory-service`) | Tagging, semantic search, consolidation; already used by the operator |
| Notes | Markdown files (`.md`) | — | Format-independent; no lock-in; native to Obsidian and Logseq; Syncthing-compatible |

## Infrastructure Services

| Concern | Technology | Justification |
|---|---|---|
| Web search | SearXNG (self-hosted Docker) | No API key; aggregates 70+ engines simultaneously; zero marginal cost; no rate limit |
| Page fetching (JS-rendered) | Jina Reader (`https://r.jina.ai`) | Handles JS-rendered pages via hosted headless Chrome; free for personal use; returns clean Markdown |
| Browser automation fallback | rebrowser-Playwright | Stealth Chromium: patches `navigator.webdriver`, CDP fingerprints, canvas entropy; for pages that block Jina |
| Task management | Vikunja | Fully OSS (AGPLv3); single Docker container; REST API + CalDAV; Android/iOS apps |
| Notes sync | Syncthing | P2P, no cloud, free; fully bidirectional; Android app + desktop clients |
| Scheduler | APScheduler (in-process) | No extra service; SQLite job store; check-in schedules configurable from within the bot at runtime |

## External APIs

| Concern | Technology | Cost | Notes |
|---|---|---|---|
| Calendar | Google Calendar API | Free (personal quota) | OAuth2; custom thin MCP wrapper using `google-api-python-client` |
| Alarm bridge | AutoRemote push → Tasker | Free + $3.49 one-time (Tasker) | AutoRemote delivers push via GCM; Tasker fires `AlarmClock.ACTION_SET_ALARM` intent; alarm fires offline |

## Development & Quality

| Concern | Technology | Justification |
|---|---|---|
| Linting + formatting | ruff | Single tool replacing black + isort + flake8; fast |
| Type checking | mypy (strict mode) | All new code fully typed; catches interface mismatches at dev time |
| Structured logging | structlog | Key-value log events throughout; never interpolated strings; no PII |
| Typed config | pydantic-settings | Validates all env vars at startup; raises `ValidationError` on missing/malformed config; fails fast |
| Testing | pytest + pytest-asyncio | Async test support; mocking at I/O boundaries only |
| Containerization | Docker + Docker Compose v2 | Identical behavior WSL2 dev → Linux VPS production |

---

## Environment Variables (all required at startup)

Defined in `.env.example` — copy to `.env`, never commit actual `.env`.

| Variable | Used By | Example |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | bot | `123456:ABC-DEF...` |
| `TELEGRAM_ALLOWED_USER_ID` | bot | `123456789` |
| `OPENCODE_API_KEY` | bot | `oc-go-...` |
| `OPENCODE_MODEL` | bot | (from `/models` endpoint) |
| `AUTOREMOTE_KEY` | bot (alarm tool) | `your-autoremote-key` |
| `VIKUNJA_URL` | bot | `http://vikunja:3456` |
| `VIKUNJA_API_TOKEN` | bot | `vikunja-api-token` |
| `MEMORY_SERVICE_URL` | bot | `http://memory:8001` |
| `SEARXNG_URL` | bot | `http://searxng:8080` |
| `NOTES_VAULT_PATH` | bot | `/srv/notes` |
| `SQLITE_PATH` | bot | `/data/assistant.db` |
| `GOOGLE_CLIENT_ID` | calendar MCP | from GCP console |
| `GOOGLE_CLIENT_SECRET` | calendar MCP | from GCP console |
| `GOOGLE_TOKEN_JSON_PATH` | calendar MCP | `/data/google_token.json` |
