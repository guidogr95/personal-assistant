# Phase 1: Bot Skeleton — Sessions, Agent Loop, First Response

**Goal:** A working Telegram bot that maintains conversation sessions in SQLite and responds to messages using the Pydantic AI agent with OpenCode Go.  
**Prerequisites:** Phase 0 complete (stack running, config, logging, exceptions in place).  
**Output:** A bot that you can message on Telegram and get intelligent responses. Sessions persist across restarts. `/new`, `/close`, `/sessions` commands work.

---

## Critique Review

**What could go wrong?**
- Context window growing unboundedly: managed by `ContextWindow` domain service with a hard `MAX_TURNS` cap
- Agent retrying infinitely on LLM errors: Pydantic AI has built-in retry with backoff; set `max_retries=3`
- Blocking the aiogram event loop with sync code: all DB access is `async` via `aiosqlite`; agent `run()` is `await`-ed
- User ID not checked: `TELEGRAM_ALLOWED_USER_ID` enforced as a middleware before any handler runs
- Session state corruption on concurrent messages: aiogram processes one update at a time per chat; no concurrent access issue

**Simplification applied:** No MCP servers in this phase (memory and calendar come later). Agent has no tools yet — it is a pure conversational agent. Tools are added per phase starting from Phase 2.

---

## Files to Create / Modify

```
src/assistant/
├── main.py                           (replace stub with real bot startup)
├── telegram/
│   ├── __init__.py
│   ├── bot.py                        (Dispatcher setup, middleware)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── message.py                (route user messages → run_turn use case)
│   │   ├── session_commands.py       (/new, /close, /sessions)
│   │   └── callbacks.py              (inline keyboard: tap session → resume it)
│   └── keyboards.py                  (build inline keyboard for /sessions)
├── conversation/
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── session.py                (Session entity)
│   │   ├── turn.py                   (Turn value object)
│   │   ├── context_window.py         (ContextWindow domain service)
│   │   └── repositories.py           (SessionRepository, TurnRepository interfaces)
│   ├── application/
│   │   ├── __init__.py
│   │   ├── open_session.py
│   │   ├── close_session.py
│   │   ├── resume_session.py
│   │   ├── list_sessions.py
│   │   └── build_context.py
│   └── infrastructure/
│       ├── __init__.py
│       └── sqlite_repositories.py
├── agent/
│   ├── domain/
│   │   ├── __init__.py
│   │   └── agent.py                  (Pydantic AI agent, no tools yet)
│   └── application/
│       ├── __init__.py
│       └── run_turn.py               (core use case)
```

---

## Step-by-Step Implementation

### Step 1 — DB Schema Initialization

Add to `conversation/infrastructure/sqlite_repositories.py`:

```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    title       TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL,
    last_active TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    ts          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, last_active DESC);
"""
```

Call `await db.executescript(SCHEMA_SQL)` during bot startup before accepting messages.

### Step 2 — Domain Entities

**`conversation/domain/session.py`:**
```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class Session:
    user_id: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = None
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def close(self, title: str) -> None:
        """Transition session to closed state with a generated title."""
        if self.status == "closed":
            raise ValueError(f"Session {self.id} is already closed")
        self.status = "closed"
        self.title = title

    @property
    def is_active(self) -> bool:
        return self.status == "active"
```

**`conversation/domain/turn.py`:**
```python
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class Turn:
    session_id: str
    role: str      # 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'summary'
    content: str
    id: str = ""
    ts: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", self.id or str(uuid.uuid4()))
        object.__setattr__(self, "ts", self.ts or datetime.now(timezone.utc))
```

**`conversation/domain/context_window.py`:**
```python
from typing import List
from assistant.conversation.domain.turn import Turn

MAX_VERBATIM_TURNS = 20    # most recent turns injected as-is


def build_context_window(turns: List[Turn]) -> List[Turn]:
    """Return the last MAX_VERBATIM_TURNS turns for LLM injection.

    Older turns are summarised by a separate use case (build_context.py).
    This function returns only the verbatim slice.
    """
    return turns[-MAX_VERBATIM_TURNS:]
```

### Step 3 — Repository Interfaces

```python
# conversation/domain/repositories.py
from abc import ABC, abstractmethod
from typing import List, Optional
from assistant.conversation.domain.session import Session
from assistant.conversation.domain.turn import Turn


class SessionRepository(ABC):
    @abstractmethod
    async def save(self, session: Session) -> None: ...

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[Session]: ...

    @abstractmethod
    async def get_active_for_user(self, user_id: int) -> Optional[Session]: ...

    @abstractmethod
    async def list_recent(self, user_id: int, limit: int = 10) -> List[Session]: ...


class TurnRepository(ABC):
    @abstractmethod
    async def save(self, turn: Turn) -> None: ...

    @abstractmethod
    async def list_for_session(self, session_id: str) -> List[Turn]: ...
```

### Step 4 — Agent Definition (no tools yet)

```python
# agent/domain/agent.py
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from assistant.shared.config import settings

SYSTEM_PROMPT = """You are a personal AI assistant accessed via Telegram.
You help with tasks, research, notes, calendar, and general questions.
Be concise but thorough. Use Markdown formatting for lists and code blocks.
"""

_model = OpenAIModel(
    model_name=settings.opencode_model,
    base_url=settings.opencode_base_url,
    api_key=settings.opencode_api_key,
)

agent = Agent(model=_model, system_prompt=SYSTEM_PROMPT)
```

### Step 5 — `run_turn` Use Case

```python
# agent/application/run_turn.py
from typing import List
from assistant.conversation.domain.turn import Turn
from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.agent.domain.agent import agent
from assistant.shared.exceptions import NoActiveSessionError
import structlog

logger = structlog.get_logger()


async def run_turn(
    user_id: int,
    user_message: str,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
) -> str:
    session = await session_repo.get_active_for_user(user_id)
    if session is None:
        raise NoActiveSessionError(f"No active session for user {user_id}")

    existing_turns = await turn_repo.list_for_session(session.id)

    # Build message history for LLM
    history = [
        {"role": t.role, "content": t.content}
        for t in existing_turns[-20:]  # MAX_VERBATIM_TURNS
        if t.role in ("user", "assistant")
    ]

    logger.info("run_turn_start", session_id=session.id, turn_count=len(existing_turns))

    result = await agent.run(
        user_message,
        message_history=history,
    )

    reply = result.output

    # Persist both turns
    await turn_repo.save(Turn(session_id=session.id, role="user", content=user_message))
    await turn_repo.save(Turn(session_id=session.id, role="assistant", content=reply))

    logger.info("run_turn_complete", session_id=session.id)
    return reply
```

### Step 6 — Telegram Handlers

**`telegram/handlers/message.py`:**
```python
from aiogram import Router
from aiogram.types import Message
from assistant.agent.application.run_turn import run_turn
from assistant.conversation.application.open_session import open_session_for_user
from assistant.shared.exceptions import NoActiveSessionError

router = Router()


@router.message()
async def on_message(message: Message, session_repo, turn_repo) -> None:
    if not message.text:
        return

    try:
        reply = await run_turn(
            user_id=message.from_user.id,
            user_message=message.text,
            session_repo=session_repo,
            turn_repo=turn_repo,
        )
    except NoActiveSessionError:
        # Auto-create a session and retry once
        await open_session_for_user(user_id=message.from_user.id, session_repo=session_repo)
        reply = await run_turn(
            user_id=message.from_user.id,
            user_message=message.text,
            session_repo=session_repo,
            turn_repo=turn_repo,
        )

    await message.answer(reply, parse_mode="Markdown")
```

**`telegram/handlers/session_commands.py`:**
```python
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from assistant.conversation.application import open_session, close_session, list_sessions
from assistant.telegram.keyboards import build_sessions_keyboard

router = Router()


@router.message(Command("new"))
async def cmd_new(message: Message, session_repo, turn_repo) -> None:
    await open_session.open_session_for_user(
        user_id=message.from_user.id,
        session_repo=session_repo,
        turn_repo=turn_repo,
    )
    await message.answer("New session started.")


@router.message(Command("close"))
async def cmd_close(message: Message, session_repo, turn_repo, agent_instance) -> None:
    title = await close_session.close_active_session(
        user_id=message.from_user.id,
        session_repo=session_repo,
        turn_repo=turn_repo,
        agent=agent_instance,
    )
    await message.answer(f"Session closed: *{title}*", parse_mode="Markdown")


@router.message(Command("sessions"))
async def cmd_sessions(message: Message, session_repo) -> None:
    sessions = await list_sessions.list_recent_sessions(
        user_id=message.from_user.id,
        session_repo=session_repo,
    )
    kb = build_sessions_keyboard(sessions)
    await message.answer("Recent sessions:", reply_markup=kb)
```

### Step 7 — Allowed User Middleware

```python
# telegram/bot.py
from aiogram import Dispatcher, Bot
from aiogram.types import TelegramObject, Update
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from typing import Any, Callable, Awaitable
from assistant.shared.config import settings


class AllowedUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user and user.id != settings.telegram_allowed_user_id:
            return  # silently ignore unauthorized users
        return await handler(event, data)
```

### Step 8 — Wire up `main.py`

```python
import asyncio
from aiogram import Bot, Dispatcher
from assistant.shared.config import settings
from assistant.shared.logging import configure_logging
from assistant.telegram.bot import AllowedUserMiddleware
from assistant.telegram.handlers import message, session_commands, callbacks
from assistant.conversation.infrastructure.sqlite_repositories import (
    SQLiteSessionRepository,
    SQLiteTurnRepository,
    init_db,
)
import structlog

configure_logging()
logger = structlog.get_logger()


async def main() -> None:
    logger.info("assistant_starting", model=settings.opencode_model)

    await init_db(settings.sqlite_path)

    session_repo = SQLiteSessionRepository(settings.sqlite_path)
    turn_repo = SQLiteTurnRepository(settings.sqlite_path)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.update.middleware(AllowedUserMiddleware())
    dp.include_router(session_commands.router)
    dp.include_router(message.router)
    dp.include_router(callbacks.router)

    # Inject repos into handlers via data dict
    await dp.start_polling(bot, session_repo=session_repo, turn_repo=turn_repo)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Verification

- [ ] Bot responds to a Telegram message with a coherent reply
- [ ] Session is created automatically if none active
- [ ] `/new` starts a fresh session; reply confirms
- [ ] `/sessions` shows an inline keyboard with recent sessions
- [ ] Tapping a session in the list resumes it
- [ ] `/close` closes the active session with a generated title
- [ ] Restarting the container and sending a message resumes the last session
- [ ] A message from an unauthorized Telegram user ID receives no response
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create / Modify**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] `StrEnum` or `Enum` used for fixed value sets (e.g. session status, turn role)
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

- [ ] `conversation/domain/` — no imports from sqlalchemy, httpx, aiogram, or pydantic_ai
- [ ] `conversation/application/` — no SQL drivers or HTTP clients; dependencies injected via repository interfaces
- [ ] `agent/domain/agent.py` — only pydantic_ai and shared config; no aiogram or aiosqlite
- [ ] `agent/application/run_turn.py` — orchestrates domain + repositories only; no raw SQL or HTTP
- [ ] `telegram/handlers/` — no business logic, no SQL; all work delegated to application use cases via injected dependencies
- [ ] `AllowedUserMiddleware` is the single enforcement point for user authorization — not duplicated in handlers
- [ ] Each use case file handles exactly one operation and is named `verb_noun.py`
- [ ] Session status (`active`/`closed`) is represented as an `Enum` or `StrEnum`, not a bare string

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 2** adds the mcp-memory-service connection and the `remember_fact` + `recall_fact` tools to the agent.
