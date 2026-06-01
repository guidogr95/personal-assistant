# Phase 6.5: Agent Refinement — Time Awareness, Edit Notes, Dynamic Prompt, Reminders, Command Bridge

**Goal:** Make the agent time-aware, self-critiquing, and editable — closing UX gaps in note editing, scheduling, and response quality. Unify one-off reminders with check-ins via `max_runs` self-destruction.

**Prerequisites:** Phase 6 complete (check-ins, sessions, all tools running on VPS).

**Output:**
- "What time is it?" → accurate server time with timezone stated explicitly.
- "Remind me to call mom in 30 minutes" → one-off Telegram message at the right time.
- "Update my note 'weekend-ideas' with …" → file edited in place, no delete/recreate.
- "Be more concise" → system prompt updated from chat, affects all future turns.
- `/remind in 30 minutes | call mom` → slash command creates reminder directly.

---

## Critique Review

**What could go wrong?**

- **pydantic-ai `instructions` parameter name:** The parameter that overrides the system prompt at run time is `instructions`, not `system_prompt`. Verified from live `Agent.run()` signature. Using the wrong name would silently fall back to the default prompt.
- **APScheduler in-memory jobs lost on container restart:** Every `docker compose up -d` or host reboot kills the Python process. APScheduler's in-memory store evaporates. The existing check-in system already solves this by storing definitions in SQLite and re-registering jobs at startup. Reminders must use the exact same pattern — APScheduler alone is **not** sufficient for persistence.
- **Time-based action enforcement:** We cannot force the LLM to call a tool. The best we can do is make the system prompt strongly instruct it, embed examples in tool docstrings, and accept occasional misses. True enforcement would require a pre-processing classifier layer — over-engineering for a single-user bot.
- **Self-critique token cost:** Adding a structured review paragraph to the system prompt adds ~80–100 tokens per turn. At current usage this is negligible. If latency becomes an issue it can be shortened later.
- **Check-in `max_runs` schema migration:** Adding columns to `scheduled_checkins` requires a migration step in `init_db`, same pattern as the existing `system_prompt → instructions` rename.
- **One-off vs recurring reminder parsing:** Natural language like "in 30 minutes" maps to a `DateTrigger` (one datetime), while "every day at 9am" maps to a `CronTrigger`. The `ScheduledCheckIn` entity must support both.
- **Timezone configuration:** The `bot` service in `docker-compose.yml` does not currently pass `TZ`. `python:3.12-slim` has `tzdata`; `zoneinfo` reads `TZ` automatically. We must add the env var.

**Simplification applied:**
- No separate `reminders` table. One-off reminders are check-ins with `max_runs=1` and a `message` field (sent directly) instead of `instructions` (agent-run).
- No pre-processing classifier for time-based actions. We instruct via system prompt and tool docstrings.
- Command-tool bridge is a simple Python mapping dict, not a database table or decorator registry. Easy to extend; no indirection overhead.

---

## Files to Create / Modify

```
src/assistant/
├── shared/
│   └── config.py                    (+ timezone field)
├── time/
│   ├── __init__.py
│   └── domain/
│       └── current_time.py          (get_current_time value object / function)
├── agent/
│   ├── domain/
│   │   └── agent.py                 (make _SYSTEM_PROMPT the fallback default)
│   ├── application/
│   │   └── run_turn.py              (inject instructions= from DB)
│   └── tools/
│       ├── time_tools.py            (register get_current_time)
│       ├── notes_tools.py           (+ update_note tool)
│       ├── checkin_tools.py         (+ max_runs param, message vs instructions)
│       └── prompt_tools.py          (agent tool: update_system_prompt)
├── notes/
│   ├── domain/
│   │   └── note_repository.py       (+ update method)
│   ├── application/
│   │   └── update_note.py
│   └── infrastructure/
│       └── markdown_repository.py   (+ update implementation)
├── scheduler/
│   ├── domain/
│   │   └── scheduled_checkin.py     (+ message, max_runs, run_count, fire_at)
│   ├── domain/
│   │   └── repositories.py          (+ get_by_id, update)
│   ├── infrastructure/
│   │   ├── apscheduler_registry.py  (+ register_one_off_job)
│   │   └── sqlite_checkin_repository.py (+ new columns, get_by_id, update)
│   └── application/
│       ├── register_checkin.py      (+ max_runs, message, fire_at)
│       └── run_checkin.py           (+ send message directly, increment run_count, auto-disable)
├── prompts/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   └── prompt_repository.py     (Protocol: get_active, update)
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   └── sqlite_prompt_repository.py
│   └── application/
│       ├── __init__.py
│       ├── get_system_prompt.py
│       └── update_system_prompt.py
├── telegram/
│   └── handlers/
│       ├── tool_commands.py         (/remind, /time — command→tool bridge)
│       └── prompt_commands.py       (/system show, /system set)
├── conversation/
│   └── infrastructure/
│       └── sqlite_repositories.py   (+ system_prompts table, migration)
├── main.py                          (re-register unsent one-offs, wire new routers)
└── tests/                           (new test files for each package)

deploy/docker-compose.yml            (+ TZ env var for bot service)
```

---

## Step-by-Step Implementation

### Step 0 — TZ Env Var + Settings

**Why first:** Every later step depends on timezone being available.

1. Add `TZ=${TZ:-UTC}` to the `bot` service environment in `deploy/docker-compose.yml`.
2. Add `timezone: str = Field(default="UTC", alias="TZ")` to `Settings` in `shared/config.py`.
3. Verify: `uv run python -c "from assistant.shared.config import settings; print(settings.timezone)"` with `TZ=America/New_York` set.

---

### Step 1 — Time Tool

**Create:**
- `src/assistant/time/__init__.py`
- `src/assistant/time/domain/current_time.py` — `get_current_time(timezone: str) -> str` returning `"Current time: 2026-06-01 14:30:00 (America/New_York)"`
- `src/assistant/agent/tools/time_tools.py` — `register_time_tools(agent)` with `get_current_time` tool

**Modify:**
- `src/assistant/agent/domain/agent.py` — add `register_time_tools(agent)` call

**Tool docstring must include:**
- "Always call this tool before scheduling anything or answering questions about time."
- 3 examples of output format.

**Tests:** time formatting, timezone awareness, default fallback, explicit timezone in output.

---

### Step 2 — Update Note

**Modify:**
- `src/assistant/notes/domain/note_repository.py` — add `async def update(self, filename: str, content: str) -> Note`
- `src/assistant/notes/infrastructure/markdown_repository.py` — implement `update` (overwrite file, preserve filename, update modified_at)

**Create:**
- `src/assistant/notes/application/update_note.py` — `update_note(filename, content, repo) -> Note | None` (returns `None` if file missing)

**Modify:**
- `src/assistant/agent/tools/notes_tools.py` — add `update_note` tool. Docstring: "Edit an existing note in place. Returns 'Note not found' if the file does not exist."

**Tests:** update existing, update missing returns error, filename unchanged, content changed, modified_at updated.

---

### Step 3 — System Prompt Persistence

**Modify:**
- `src/assistant/conversation/infrastructure/sqlite_repositories.py`:
  - Add `system_prompts` table to `_SCHEMA_SQL`
  - Add `_seed_system_prompt(db)` that inserts the current `_SYSTEM_PROMPT` text if the table is empty

**Create:**
- `src/assistant/prompts/__init__.py`
- `src/assistant/prompts/domain/__init__.py`
- `src/assistant/prompts/domain/prompt_repository.py` — `PromptRepository` Protocol with `get_active() -> str`, `update(text: str) -> None`
- `src/assistant/prompts/infrastructure/__init__.py`
- `src/assistant/prompts/infrastructure/sqlite_prompt_repository.py`
- `src/assistant/prompts/application/__init__.py`
- `src/assistant/prompts/application/get_system_prompt.py`
- `src/assistant/prompts/application/update_system_prompt.py`

**Tests:** get default, update, get updated, seed on empty DB.

---

### Step 4 — Dynamic System Prompt Injection

**Modify:**
- `src/assistant/agent/application/run_turn.py`:
  - Inject `prompt_repo: PromptRepository` parameter
  - Read active prompt via `get_system_prompt`
  - Pass `instructions=active_prompt` to `agent.run(...)`
- `src/assistant/main.py`:
  - Create `SQLitePromptRepository`
  - Pass it through dispatcher polling data to `run_turn`

**System prompt content (stored in DB, seeded by init_db):**

```
You are a personal AI assistant accessed via Telegram.
You help with tasks, research, notes, calendar, and general questions.
Use Markdown formatting for lists and code blocks.

=== TIME AWARENESS ===
When the user asks for any time-based action — scheduling a check-in, setting a reminder, setting a task due date, or any request involving a specific time — you MUST call get_current_time first to know the current time and timezone. Do not guess the time. Do not assume UTC unless the user explicitly says so.

=== RESPONSE REVIEW (run before every response) ===
1. ASSUMPTIONS — What am I assuming? Did I validate it? (e.g., did I call get_current_time before scheduling?)
2. TOOL USAGE — Did I use the required tools for this request? Did I skip any that the instructions mandate?
3. CONCISENESS — Can I remove 30% of the words without losing meaning? Remove filler, sympathy phrases ('I'm sorry to hear that', 'I understand'), and redundant explanations.
4. ACCURACY — Is every fact grounded in tool output or user input? No hallucination.
5. ACTIONABILITY — Did I provide a clear next step or concrete answer? Avoid vague suggestions.
```

**Tests:** `run_turn` passes correct instructions, fallback works when DB empty, prompt text includes all 5 review points.

---

### Step 5 — Extend Check-ins with max_runs, message, fire_at

**Modify:**
- `src/assistant/scheduler/domain/scheduled_checkin.py`:
  - Add `message: str | None = None`, `max_runs: int | None = None`, `run_count: int = 0`, `fire_at: datetime | None = None`
  - Update `__post_init__` validation:
    - At least one of `instructions` or `message` must be set
    - Exactly one of `cron_expr` or `fire_at` must be set
    - If `fire_at` is set, it must be in the future
    - If `max_runs` is set, it must be >= 1

**Modify:**
- `src/assistant/scheduler/domain/repositories.py` — add `get_by_id(id) -> ScheduledCheckIn | None`, `update(checkin) -> None`
- `src/assistant/scheduler/infrastructure/sqlite_checkin_repository.py` — implement new methods, handle new columns

**Modify:**
- `src/assistant/conversation/infrastructure/sqlite_repositories.py`:
  - Add migration in `init_db` to add `message`, `max_runs`, `run_count`, `fire_at` columns to `scheduled_checkins` if missing
  - Same pattern as `_migrate_checkin_instructions_column`

**Tests:** entity validation (valid, missing message+instructions, both cron and fire_at, future fire_at, invalid max_runs), repository get_by_id and update.

---

### Step 6 — One-Off Job Registration + Run Check-in Enhancement

**Modify:**
- `src/assistant/scheduler/infrastructure/apscheduler_registry.py`:
  - Add `register_one_off_job(scheduler, checkin_id, fire_at, job_func)` using `DateTrigger`

**Modify:**
- `src/assistant/scheduler/application/register_checkin.py`:
  - Accept optional `max_runs: int | None = None`, `message: str | None = None`, `fire_at: datetime | None = None`
  - Choose `DateTrigger` or `CronTrigger` based on `fire_at` vs `cron_expr`

**Modify:**
- `src/assistant/scheduler/application/run_checkin.py`:
  - If `checkin.message` is set, send it directly to Telegram (no agent run)
  - If `checkin.instructions` is set, run the agent (existing behavior)
  - Increment `run_count`
  - If `max_runs` is set and `run_count >= max_runs`:
    - Disable the check-in
    - Remove the job from APScheduler
    - Send a "Check-in '{name}' completed after {max_runs} run(s)" message

**Tests:** one-off registration, message-only check-in fires correctly, agent-run check-in still works, auto-disable after max_runs reached.

---

### Step 7 — Reminder Tool (Natural Language)

**Create:**
- `src/assistant/scheduler/application/parse_reminder_time.py` — lightweight parser for natural language time expressions:
  - "in 30 minutes" → `fire_at = now + 30min`
  - "in 2 hours" → `fire_at = now + 2h`
  - "tomorrow at 9am" → `fire_at = tomorrow 09:00`
  - "next Monday at 8am" → `fire_at = next Monday 08:00`
  - "at 15:30 today" → `fire_at = today 15:30`
  - "every day at 9am" → `cron_expr = "0 9 * * *"`
  - "every weekday at 8am" → `cron_expr = "0 8 * * 1-5"`
  - Returns `(fire_at: datetime | None, cron_expr: str | None)`

**Create:**
- `src/assistant/agent/tools/reminder_tools.py` — `register_reminder_tools(agent)`:
  - `set_reminder(time_expr: str, message: str)` tool
  - Calls `parse_reminder_time`, then `register_checkin` with `max_runs=1`, `message=message`
  - Returns confirmation string

**Tool docstring must contain 5+ concrete examples** (for the LLM to learn from):
```
Examples of time_expr:
- "in 30 minutes" → one-off reminder 30 minutes from now
- "tomorrow at 9am" → one-off reminder at 09:00 tomorrow
- "in 2 hours" → one-off reminder 2 hours from now
- "next Monday at 8am" → one-off reminder next Monday 08:00
- "at 15:30 today" → one-off reminder at 15:30 today
- "every day at 9am" → recurring daily reminder at 09:00
- "every weekday at 8am" → recurring Monday–Friday at 08:00
```

**Modify:**
- `src/assistant/agent/domain/agent.py` — add `register_reminder_tools(agent)` call

**Tests:** parse all 7 examples, set_reminder tool success, set_reminder tool error on unparseable time.

---

### Step 8 — Command-Tool Bridge

**Create:**
- `src/assistant/telegram/handlers/tool_commands.py`:
  - `/remind <time_expr> | <message>` — parses, calls `set_reminder` tool function directly, replies with result
  - `/time` — calls `get_current_time` directly, replies with result
  - `_COMMAND_TOOL_MAP: dict[str, Callable]` — extensible mapping; adding a new command-tool pair is one line

**Modify:**
- `src/assistant/main.py`:
  - Include `tool_commands.router` in dispatcher
  - Add `/remind` and `/time` to `bot.set_my_commands()`

**Tests:** `/remind` success, `/remind` bad format, `/time` returns time with timezone.

---

### Step 9 — System Prompt Chat Commands

**Create:**
- `src/assistant/telegram/handlers/prompt_commands.py`:
  - `/system show` — displays current system prompt (truncated to 3000 chars if too long for Telegram)
  - `/system set <prompt>` — updates the system prompt in DB

**Modify:**
- `src/assistant/main.py`:
  - Include `prompt_commands.router` in dispatcher
  - Add `/system` to `bot.set_my_commands()`

**Tests:** show current, update, show updated, truncation on long prompt.

---

### Step 10 — Agent Tool for System Prompt Editing

**Create:**
- `src/assistant/agent/tools/prompt_tools.py` — `register_prompt_tools(agent)`:
  - `update_system_prompt(new_prompt: str)` tool — updates the DB directly
  - `show_system_prompt()` tool — returns current prompt text

**Modify:**
- `src/assistant/agent/domain/agent.py` — add `register_prompt_tools(agent)` call

**Tests:** tool updates prompt, tool shows prompt, natural language "be more concise" triggers tool use.

---

### Step 11 — Startup Re-registration of One-Off Jobs

**Modify:**
- `src/assistant/main.py`:
  - After re-registering enabled check-ins (recurring), also query for unsent one-off check-ins (`fire_at IS NOT NULL AND sent = 0` or `enabled = 1 AND fire_at > now()`)
  - Register each with `register_one_off_job`

**Note on persistence:** APScheduler's in-memory job store loses all jobs when the container restarts. The SQLite table is the source of truth. On every startup we re-register all enabled recurring check-ins (existing behavior) and all unsent one-off reminders (new behavior). This is why we cannot rely on APScheduler alone — it has no persistence across process restarts.

**Tests:** startup re-registers future one-off, skips past one-off, skips disabled one-off.

---

### Step 12 — Integration + Verification

- `uv run mypy src/` — 0 errors
- `uv run ruff check src/ tests/` — 0 violations
- `uv run pytest tests/ -q` — all pass
- Live tests:
  - `/time` → shows time with timezone
  - "What time is it?" → agent calls tool, shows time with timezone
  - "Remind me to call mom in 5 minutes" → message arrives on time
  - "Update note '2026-06-01-weekend-ideas.md' with new content" → file edited
  - `/system show` → displays current prompt
  - `/system set You are a pirate` → next turn uses pirate prompt
  - "Be more concise" → agent uses prompt tool to update system prompt

---

## Verification Results

(To be filled after implementation.)

| Check | Result |
|-------|--------|
| `uv run mypy src/` | ⬜ |
| `uv run ruff check src/ tests/` | ⬜ |
| `uv run pytest tests/ -q` | ⬜ |
| `/time` returns time with timezone | ⬜ |
| Agent calls get_current_time for time-based requests | ⬜ |
| `update_note` edits existing file | ⬜ |
| `update_note` returns error for missing file | ⬜ |
| `/system show` displays prompt | ⬜ |
| `/system set` updates prompt | ⬜ |
| Agent uses prompt tool for natural language edits | ⬜ |
| `/remind` creates one-off reminder | ⬜ |
| Natural language "remind me in X" creates reminder | ⬜ |
| One-off reminder fires and self-destructs | ⬜ |
| Recurring check-in with max_runs auto-disables | ⬜ |
| Startup re-registers unsent one-offs | ⬜ |
