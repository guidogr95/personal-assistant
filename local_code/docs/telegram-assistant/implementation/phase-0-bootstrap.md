# Phase 0: Project Bootstrap

**Goal:** Create a deployable project scaffold from a blank repository.  
**Prerequisites:** None — this is the starting point.  
**Output:** A Docker Compose stack that starts without errors, a typed config system, structured logging, and a project structure that all future phases build into.

---

## Critique Review

**What could go wrong with this phase?**
- Config missing at startup: caught immediately by pydantic-settings `ValidationError` if we validate all vars in `__post_init__`
- Docker volume paths don't match between `docker-compose.yml` and `Dockerfile` `WORKDIR`: prevented by explicit mapping in this doc
- WSL2 filesystem rule ignored: documented prominently; no technical enforcement possible — it's a developer discipline rule
- `uv` lockfile not committed: prevented by running `uv lock` and committing `uv.lock`

**Simplification applied:** No application code in this phase — only skeleton. No domain entities. No tests (nothing to test yet). The single acceptance criterion for this phase is "all containers start and stay running."

---

## Files to Create

```
assistant/
├── .gitignore
├── .env.example
├── pyproject.toml
├── Dockerfile
├── README.md                   (see local_code/docs/telegram-assistant/README.md)
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.override.yml
│   └── searxng/
│       └── settings.yml
├── src/
│   └── assistant/
│       ├── __init__.py
│       ├── main.py             (stub: prints "bot starting" and exits)
│       └── shared/
│           ├── __init__.py
│           ├── config.py       (pydantic-settings — all env vars declared + validated)
│           ├── logging.py      (structlog setup)
│           └── exceptions.py   (base exception hierarchy)
└── .github/
    └── instructions/
        └── ARCHITECTURE.instructions.md
```

---

## Step-by-Step Implementation

### Step 1 — Initialize the project with uv

```bash
# Inside WSL2 terminal — ~/assistant/ is inside WSL2 filesystem (required)
mkdir ~/assistant && cd ~/assistant
git init
uv init --name assistant --python 3.12
```

This creates `pyproject.toml` with Python 3.12 constraint. Edit it:

```toml
[project]
name = "assistant"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "aiosqlite>=0.20",
    "sqlalchemy[asyncio]>=2.0",
    "aiogram>=3.0",
    "pydantic-ai>=0.2.0",
    "apscheduler>=3.10",
    "httpx>=0.27",
    "aiofiles>=23.0",
]

[project.optional-dependencies]
dev = [
    "mypy>=1.0",
    "ruff>=0.4",
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "watchfiles>=0.21",    # for dev live reload
]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "ANN", "S", "B", "A"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

```bash
uv lock
uv sync
```

### Step 2 — `.env.example`

```dotenv
# LLM
OPENCODE_API_KEY=your-opencode-api-key
OPENCODE_BASE_URL=https://opencode.ai/zen/go/v1
OPENCODE_MODEL=claude-3-5-sonnet   # verify from /models endpoint

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF-your-token
TELEGRAM_ALLOWED_USER_ID=123456789

# Storage
SQLITE_PATH=/data/assistant.db
NOTES_VAULT_PATH=/srv/notes

# Services (internal Docker DNS names)
MEMORY_SERVICE_URL=http://memory:8001
SEARXNG_URL=http://searxng:8080
VIKUNJA_URL=http://vikunja:3456
VIKUNJA_API_TOKEN=your-vikunja-token

# Alarms
AUTOREMOTE_KEY=your-autoremote-key

# Google Calendar
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_TOKEN_JSON_PATH=/data/google_token.json

# Optional
LOG_LEVEL=INFO
TZ=UTC
```

### Step 3 — `shared/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    opencode_api_key: str
    opencode_base_url: str = "https://opencode.ai/zen/go/v1"
    opencode_model: str

    # Telegram
    telegram_bot_token: str
    telegram_allowed_user_id: int

    # Storage
    sqlite_path: str = "/data/assistant.db"
    notes_vault_path: str = "/srv/notes"

    # Services
    memory_service_url: str
    searxng_url: str
    vikunja_url: str
    vikunja_api_token: str

    # Alarms
    autoremote_key: str

    # Google Calendar
    google_client_id: str = ""
    google_client_secret: str = ""
    google_token_json_path: str = "/data/google_token.json"

    # Misc
    log_level: str = "INFO"


settings = Settings()  # raises ValidationError at import if required vars missing
```

### Step 4 — `shared/logging.py`

```python
import logging
import structlog
from assistant.shared.config import settings


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if settings.log_level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

### Step 5 — `shared/exceptions.py`

```python
class AssistantError(Exception):
    """Base exception for all domain errors."""


class SessionNotFoundError(AssistantError):
    pass


class NoActiveSessionError(AssistantError):
    pass


class SessionAlreadyActiveError(AssistantError):
    pass


class InfrastructureError(AssistantError):
    """Wraps external service failures."""
```

### Step 6 — `main.py` stub

```python
import asyncio
from assistant.shared.logging import configure_logging
from assistant.shared.config import settings
import structlog

configure_logging()
logger = structlog.get_logger()


async def main() -> None:
    logger.info("assistant_starting", model=settings.opencode_model)
    # Phase 1 will replace this with bot startup


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 7 — `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/

ENV PYTHONPATH=/app/src
CMD ["uv", "run", "python", "-m", "assistant.main"]
```

### Step 8 — `deploy/docker-compose.yml`

```yaml
services:
  bot:
    build: .
    restart: unless-stopped
    env_file: ../.env
    volumes:
      - sqlite_data:/data
      - notes_data:/srv/notes
    depends_on:
      - memory
      - searxng
      - vikunja
    networks:
      - assistant_net

  memory:
    image: doobidoo/mcp-memory-service:latest
    restart: unless-stopped
    volumes:
      - memory_data:/app/data
    networks:
      - assistant_net

  searxng:
    image: searxng/searxng:latest
    restart: unless-stopped
    volumes:
      - ./searxng:/etc/searxng
    networks:
      - assistant_net

  vikunja:
    image: vikunja/vikunja:latest
    restart: unless-stopped
    environment:
      VIKUNJA_DATABASE_TYPE: mysql
      VIKUNJA_DATABASE_HOST: vikunja_db
      VIKUNJA_DATABASE_NAME: vikunja
      VIKUNJA_DATABASE_USER: vikunja
      VIKUNJA_DATABASE_PASSWORD: ${VIKUNJA_DB_PASSWORD}
    volumes:
      - vikunja_data:/app/data
    depends_on:
      - vikunja_db
    networks:
      - assistant_net

  vikunja_db:
    image: mariadb:10
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: vikunja
      MYSQL_USER: vikunja
      MYSQL_PASSWORD: ${VIKUNJA_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${VIKUNJA_DB_ROOT_PASSWORD}
    volumes:
      - vikunja_db_data:/var/lib/mysql
    networks:
      - assistant_net

  syncthing:
    image: syncthing/syncthing:latest
    restart: unless-stopped
    volumes:
      - notes_data:/var/syncthing
    ports:
      - "22000:22000"   # sync protocol (must be reachable from phone/PC)
      - "8384:8384"     # web UI (bind to 127.0.0.1 in production behind nginx)
    networks:
      - assistant_net

networks:
  assistant_net:

volumes:
  sqlite_data:
  memory_data:
  notes_data:
  vikunja_data:
  vikunja_db_data:
```

### Step 9 — `deploy/docker-compose.override.yml` (dev only)

```yaml
services:
  bot:
    build:
      context: ..
      dockerfile: Dockerfile
    volumes:
      - ../src:/app/src    # live code reload — works only from WSL2 filesystem
    command: ["uv", "run", "watchfiles", "python -m assistant.main src/"]
    ports:
      - "5678:5678"        # debugpy
```

### Step 10 — `deploy/searxng/settings.yml`

```yaml
use_default_settings: true
server:
  secret_key: "change-me-in-production"
  limiter: false
search:
  safe_search: 0
  autocomplete: ""
engines:
  - name: google
    engine: google
    categories: general
  - name: bing
    engine: bing
    categories: general
  - name: duckduckgo
    engine: duckduckgo
    categories: general
  - name: wikipedia
    engine: wikipedia
    categories: general
```

### Step 11 — `.github/instructions/ARCHITECTURE.instructions.md`

Create a Copilot instructions file to enforce conventions in this repo:

```markdown
---
applyTo: "src/**"
---
# Architecture Conventions

## Layer Rules
- `*/domain/` files MUST NOT import: sqlalchemy, httpx, aiogram, pydantic_ai, or any third-party library
- `telegram/` handlers MUST NOT contain SQL queries or business logic
- All config is read from `shared/config.settings`; never use `os.getenv()` directly in application code

## Naming
- Use case files: verb_noun.py (open_session.py, not session_manager.py)
- Domain entities: named after the domain concept (Session, Turn, not SessionModel)
- Infrastructure clients: <Service>Client (VikunjaClient, JinaClient)

## Type Safety
- All functions must have complete type hints
- No `Any` types without a comment explaining why
- `Optional[T]` for nullable returns
```

---

## Verification

- [ ] `docker compose -f deploy/docker-compose.yml up -d` starts all 6 services without errors
- [ ] `docker compose ps` shows all services as `running` after 30 seconds
- [ ] `python -c "from assistant.shared.config import settings; print(settings.opencode_model)"` prints the model name
- [ ] Removing a required env var from `.env` causes startup to fail with a clear `ValidationError`
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] Enums used for fixed value sets (if applicable)
- [ ] `TypedDict` used for structured dicts (if applicable)
- [ ] No `except Exception: pass` — all catch blocks narrow the exception type and log with context
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No docstrings that restate the function name
- [ ] No `print()` in production paths — structlog used throughout
- [ ] No secrets in source code
- [ ] No sensitive data in logs
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] Domain layer (`*/domain/`) imports nothing outside stdlib and `shared/` — no sqlalchemy, httpx, aiogram, or pydantic_ai
- [ ] Application layer (`*/application/`) contains no SQL drivers, HTTP clients, or framework calls — only domain objects and injected interfaces
- [ ] Interface layer (`telegram/`) contains no business logic and no direct SQL — all work delegated to application use cases
- [ ] Infrastructure layer (`*/infrastructure/`) contains no domain rules — only persistence and HTTP mechanics
- [ ] No cross-bounded-context domain imports (e.g. `conversation` domain never imports from `agent` domain)
- [ ] Each use case file is named as `verb_noun.py` and handles exactly one operation

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 1** builds on this scaffold to add the actual Telegram bot, conversation sessions, and the first agent turn.
