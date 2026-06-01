# Phase 6: Proactive Check-ins + Session Management UX

**Goal:** Add APScheduler-based proactive check-ins that fire on cron schedules and send Telegram messages. Also complete the session management UX: inline keyboard session list, session title generation on close, context window summarization.  
**Prerequisites:** Phase 5 complete (full agent with all tools except calendar/alarms).  
**Output:** "Schedule a morning check-in every day at 9am to summarise my open tasks" — the bot sends a task summary to Telegram every morning without user prompting.

---

## Critique Review

**What could go wrong?**
- APScheduler firing while bot is shutting down: use `scheduler.shutdown(wait=False)` in cleanup
- Concurrent check-in + user message using the same agent instance: Pydantic AI agent is stateless and safe for concurrent calls; `run()` creates a new run context each time
- SQLite write contention between APScheduler jobs and conversation writes: SQLite WAL mode handles concurrent readers; writes are serialized; acceptable for single-user
- Cron expression typos from user: validate cron expression before saving; return error to user if invalid
- Title generation calling the LLM on every `/close`: yes, intentional; it's a short call and improves session list readability

**Simplification applied:** Context window summarization in Phase 6 is basic (just truncate to last 20 turns). A proper summarization step (LLM-generated summaries of older turns) can be added in a follow-up.

---

## Files to Create / Modify

```
src/assistant/
├── scheduler/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── scheduled_checkin.py     (entity: name, cron_expr, system_prompt, enabled)
│   ├── application/
│   │   ├── __init__.py
│   │   ├── register_checkin.py
│   │   ├── toggle_checkin.py
│   │   ├── delete_checkin.py
│   │   ├── list_checkins.py
│   │   └── run_checkin.py           (APScheduler job payload)
│   └── infrastructure/
│       ├── __init__.py
│       └── apscheduler_registry.py
├── conversation/
│   └── application/
│       └── close_session.py         (modified: LLM title generation)
├── telegram/
│   └── handlers/
│       └── checkin_commands.py      (/checkin add, /checkin list, /checkin delete)
├── main.py                          (modified: start APScheduler)
```

---

## Step-by-Step Implementation

### Step 1 — ScheduledCheckIn Entity

```python
# scheduler/domain/scheduled_checkin.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


@dataclass
class ScheduledCheckIn:
    name: str
    cron_expr: str          # standard 5-field cron: "0 9 * * *" = daily at 09:00 UTC
    system_prompt: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def disable(self) -> None:
        self.enabled = False

    def enable(self) -> None:
        self.enabled = True
```

### Step 2 — SQLite Schema for Check-ins

Add to the schema init in `conversation/infrastructure/sqlite_repositories.py`:

```sql
CREATE TABLE IF NOT EXISTS scheduled_checkins (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    cron_expr    TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);
```

### Step 3 — APScheduler Setup

```python
# scheduler/infrastructure/apscheduler_registry.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from typing import Callable, Awaitable
from assistant.shared.config import settings
import structlog

logger = structlog.get_logger()


def create_scheduler() -> AsyncIOScheduler:
    """Create APScheduler with SQLite job store for persistence across restarts."""
    return AsyncIOScheduler(
        jobstores={
            "default": SQLAlchemyJobStore(url=f"sqlite:///{settings.sqlite_path}")
        },
        timezone="UTC",
        job_defaults={"misfire_grace_time": 60 * 5},  # re-fire up to 5 minutes late
    )


def register_checkin_job(
    scheduler: AsyncIOScheduler,
    checkin_id: str,
    cron_expr: str,
    job_func: Callable[[str], Awaitable[None]],
) -> None:
    """Register or replace a check-in job in APScheduler."""
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: '{cron_expr}' — must have 5 fields")

    minute, hour, day, month, day_of_week = parts
    trigger = CronTrigger(
        minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week
    )

    scheduler.add_job(
        job_func,
        trigger=trigger,
        args=[checkin_id],
        id=checkin_id,
        replace_existing=True,
    )
    logger.info("checkin_job_registered", checkin_id=checkin_id, cron_expr=cron_expr)
```

### Step 4 — run_checkin Use Case

```python
# scheduler/application/run_checkin.py
from assistant.agent.domain.agent import agent
from assistant.shared.config import settings
import structlog

logger = structlog.get_logger()

# These are injected at startup; not module-level globals to avoid circular imports
_bot = None
_checkin_repo = None


def inject_dependencies(bot, checkin_repo) -> None:
    global _bot, _checkin_repo
    _bot = bot
    _checkin_repo = checkin_repo


async def run_checkin(checkin_id: str) -> None:
    """APScheduler job: run agent with check-in's system prompt, send result to Telegram."""
    checkin = await _checkin_repo.get_by_id(checkin_id)
    if checkin is None or not checkin.enabled:
        logger.warning("checkin_skipped", checkin_id=checkin_id)
        return

    logger.info("checkin_firing", checkin_id=checkin_id, name=checkin.name)

    try:
        result = await agent.run(
            "Perform the scheduled check-in task.",
            system_prompt_override=checkin.system_prompt,
        )
        await _bot.send_message(
            chat_id=settings.telegram_allowed_user_id,
            text=f"**Check-in: {checkin.name}**\n\n{result.output}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error("checkin_failed", checkin_id=checkin_id, error=str(e))
        await _bot.send_message(
            chat_id=settings.telegram_allowed_user_id,
            text=f"Check-in '{checkin.name}' failed: {e}",
        )
```

### Step 5 — Session Title Generation on Close

```python
# conversation/application/close_session.py
from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.agent.domain.agent import agent
import structlog

logger = structlog.get_logger()

TITLE_PROMPT = """Generate a title for this conversation in 5 words or fewer.
Return only the title — no punctuation, no quotes, no explanation."""


async def close_active_session(
    user_id: int,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
) -> str:
    session = await session_repo.get_active_for_user(user_id)
    if session is None:
        raise ValueError(f"No active session for user {user_id}")

    turns = await turn_repo.list_for_session(session.id)
    first_turns_summary = "\n".join(
        f"{t.role}: {t.content[:100]}" for t in turns[:6]
    )

    result = await agent.run(
        f"{TITLE_PROMPT}\n\nConversation:\n{first_turns_summary}",
    )
    title = result.output.strip()[:60]

    session.close(title)
    await session_repo.save(session)

    logger.info("session_closed", session_id=session.id, title=title)
    return title
```

### Step 6 — Check-in Telegram Commands

```python
# telegram/handlers/checkin_commands.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from assistant.scheduler.application import register_checkin, list_checkins, delete_checkin

router = Router()


@router.message(Command("checkin"))
async def cmd_checkin(message: Message, scheduler_repo, scheduler) -> None:
    """Usage: /checkin add <name> | <cron> | <system prompt>
              /checkin list
              /checkin delete <name>
    """
    if not message.text:
        return

    parts = message.text.removeprefix("/checkin").strip()

    if parts.startswith("list"):
        checkins = await list_checkins.list_all_checkins(scheduler_repo)
        if not checkins:
            await message.answer("No check-ins registered.")
            return
        lines = [f"- **{c.name}** `{c.cron_expr}` ({'on' if c.enabled else 'off'})" for c in checkins]
        await message.answer("\n".join(lines), parse_mode="Markdown")
        return

    if parts.startswith("delete "):
        name = parts.removeprefix("delete ").strip()
        await delete_checkin.delete_checkin_by_name(name, scheduler_repo, scheduler)
        await message.answer(f"Check-in '{name}' deleted.")
        return

    if parts.startswith("add "):
        raw = parts.removeprefix("add ").strip()
        try:
            name, cron_expr, system_prompt = [p.strip() for p in raw.split("|", 2)]
        except ValueError:
            await message.answer(
                "Format: `/checkin add <name> | <cron 5-field> | <system prompt>`",
                parse_mode="Markdown",
            )
            return
        await register_checkin.register_checkin(
            name=name,
            cron_expr=cron_expr,
            system_prompt=system_prompt,
            repo=scheduler_repo,
            scheduler=scheduler,
        )
        await message.answer(f"Check-in '{name}' registered with schedule `{cron_expr}`.")
        return

    await message.answer("Usage: `/checkin add <name> | <cron> | <prompt>`, `/checkin list`, `/checkin delete <name>`")
```

### Step 7 — Update main.py for Scheduler

```python
# main.py additions
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from assistant.scheduler.infrastructure.apscheduler_registry import create_scheduler
from assistant.scheduler.application.run_checkin import inject_dependencies

async def main() -> None:
    # ... existing setup ...

    scheduler = create_scheduler()
    inject_dependencies(bot=bot, checkin_repo=checkin_repo)

    # Re-register all enabled check-ins from DB on startup
    checkins = await checkin_repo.list_all()
    for checkin in checkins:
        if checkin.enabled:
            register_checkin_job(scheduler, checkin.id, checkin.cron_expr, run_checkin)

    scheduler.start()
    logger.info("scheduler_started")

    try:
        async with agent.run_mcp_servers():
            await dp.start_polling(bot, ...)
    finally:
        scheduler.shutdown(wait=False)
```

---

## Verification

- [ ] `/checkin add Morning Tasks | 0 9 * * * | Summarise my open Vikunja tasks and any notes from today` registers a check-in
- [ ] `/checkin list` shows the registered check-in with its schedule
- [ ] Restarting the bot and running `/checkin list` still shows the check-in (persisted via APScheduler job store)
- [ ] Temporarily setting cron to `* * * * *` (every minute) confirms the bot sends a message on schedule
- [ ] `/close` generates a title from the conversation and shows it
- [ ] `/sessions` shows the closed session with its title in the inline keyboard
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create / Modify**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] `ScheduledCheckin` is a proper entity with its own invariants — not a raw dict or TypedDict
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] No `except Exception: pass` — APScheduler errors and LLM title-generation errors caught specifically and logged
- [ ] Cron expression validated before saving — invalid expressions return a user-facing error, not an unhandled exception
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No `print()` in production paths — structlog used throughout
- [ ] No secrets in source code or logs
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `scheduler/` is a **Supporting bounded context** — `ScheduledCheckin` is an entity with a cron expression and system prompt
- [ ] `scheduler/domain/scheduled_checkin.py` — pure Python; no APScheduler imports; cron validation logic belongs here
- [ ] `scheduler/infrastructure/apscheduler_registry.py` — all APScheduler API calls here; no domain rules
- [ ] APScheduler job store uses the same SQLite database as conversations (single file, single connection pool)
- [ ] `run_checkin.py` job payload calls `run_turn` use case — it does not duplicate agent invocation logic
- [ ] APScheduler lifecycle (`start`/`shutdown`) managed in `main.py` with proper cleanup on shutdown

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 7** adds Google Calendar and Android alarms. Phase 7a is a mandatory manual device test gate before any alarm code is written.
