# Phase 1 Implementation Summary

**Status:** Complete  
**Date:** 2026-05-31  
**pydantic-ai version at implementation time:** 1.104.0

---

## What Was Built

### Domain layer (`conversation/domain/`)

| File | What it contains |
|------|-----------------|
| `session.py` | `Session` entity + `SessionStatus` StrEnum. Owns `close()`, `reopen()`, `touch()`, `update_message_history()`. Holds `message_history_json: bytes | None`. |
| `turn.py` | `Turn` frozen dataclass + `TurnRole` StrEnum. Immutable; validated by dataclass machinery. |
| `context_window.py` | `build_verbatim_window()` — slices last 20 user/assistant turns. For display only; LLM context comes from the blob. |
| `repositories.py` | `SessionRepository` and `TurnRepository` ABCs. Zero infrastructure imports. |

### Infrastructure layer (`conversation/infrastructure/`)

| File | What it contains |
|------|-----------------|
| `sqlite_repositories.py` | `SQLiteSessionRepository`, `SQLiteTurnRepository`, `init_db()`. Schema includes `message_history_json BLOB` on `sessions`. One `aiosqlite.connect()` per operation — no persistent connection pool. |

### Agent layer (`agent/`)

| File | What it contains |
|------|-----------------|
| `domain/agent.py` | Pydantic-ai `Agent[None, str]` wired to OpenCode Go via `OpenAIProvider`. No tools yet. |
| `application/run_turn.py` | Loads the `ModelMessage` blob from the session, calls `agent.run()`, persists both `Turn` rows and the updated blob, calls `session.touch()`. |

### Application use cases (`conversation/application/`)

| File | Operation |
|------|-----------|
| `open_session.py` | Creates a new session; auto-closes any existing active session with its current title or "Untitled". |
| `close_session.py` | Calls LLM to generate a ≤5-word title from the message history blob; falls back to "Untitled" on any failure. |
| `list_sessions.py` | Thin delegation to `session_repo.list_recent()`. |
| `resume_session.py` | Closes the current active session (if different from the target), then reopens the target session. |

### Telegram layer (`telegram/`)

| File | What it contains |
|------|-----------------|
| `bot.py` | `AllowedUserMiddleware` — single enforcement point for `TELEGRAM_ALLOWED_USER_ID`. Logs and silently drops all other users. |
| `keyboards.py` | `build_sessions_keyboard()` / `parse_session_callback()` — inline keyboard for `/sessions`. |
| `handlers/message.py` | Catch-all message handler. Auto-creates a session if none is active. Falls back from Markdown to plain text if Telegram rejects the parse. |
| `handlers/session_commands.py` | `/new`, `/close`, `/sessions`. |
| `handlers/callbacks.py` | Inline keyboard tap → `resume_session` use case. |

### Entrypoint

`main.py` — replaces Phase 0 stub: calls `init_db`, constructs repos, attaches middleware and routers, starts aiogram long-polling. Repos are injected into handlers via aiogram's `start_polling(**kwargs)` pattern.

### Tests

30 tests across three files, all passing. No external services called.

| File | Coverage |
|------|----------|
| `tests/conversation/test_domain.py` | `Session` invariants, `Turn` immutability, `build_verbatim_window` slicing and filtering |
| `tests/conversation/test_repositories.py` | CRUD round-trips, upsert, `message_history_json` blob persistence, empty-result cases |
| `tests/conversation/test_use_cases.py` | `open_session`, `close_session`, `list_sessions`, `resume_session` — including error paths |

---

## Deviations from the Plan

### 1. `message_history` is a serialised blob, not a list of dicts

**Plan said:** Build `message_history` by iterating `Turn` rows and constructing `{"role": ..., "content": ...}` dicts to pass to `agent.run(message_history=...)`.

**What actually works in pydantic-ai 1.104.0:** `message_history` requires `Sequence[ModelMessage]` — typed pydantic objects, not plain dicts. Passing dicts raises a validation error at runtime.

**Resolution:** The session entity stores the full `ModelMessage` list serialised to JSON bytes via `ModelMessagesTypeAdapter.dump_json(result.all_messages())`. On the next turn it is deserialised with `ModelMessagesTypeAdapter.validate_json(blob)` and passed directly. This is the canonical pydantic-ai approach and preserves all message metadata (tool calls, tool results, timestamps, run IDs).

**Impact:** `Turn` rows still exist for display purposes (e.g. `/sessions` history browsing in a later phase) but are not the source of truth for LLM context. The blob on the session is.

### 2. `Session.message_history_json` added to the domain entity

**Plan said:** No mention of storing message history on the session entity itself.

**Resolution:** Necessary consequence of deviation 1. The field is typed `bytes | None` and carries a comment explaining why it lives in the domain despite referencing an infrastructure serialisation format. The domain layer itself never imports `pydantic_ai`; the field is opaque bytes as far as the domain is concerned.

### 3. `Session.reopen()` added

**Plan said:** No explicit `reopen()` method — the spec showed direct status mutation.

**Resolution:** Consistent with the rule that entities own their state transitions. `resume_session` calls `session.reopen()` rather than setting `session.status = "active"` externally.

### 4. `open_session` signature simplified — `turn_repo` parameter removed

**Plan said:** `open_session_for_user(user_id, session_repo, turn_repo)`.

**Resolution:** The use case only needs to close the previous session (no turns written). `turn_repo` was removed to keep the signature honest.

### 5. `OpenAIModel` construction uses `OpenAIProvider`, not `base_url`/`api_key` kwargs

**Plan said:** `OpenAIModel(model_name=..., base_url=..., api_key=...)`.

**What actually works in pydantic-ai 1.104.0:** `OpenAIModel.__init__` takes `provider` not `base_url`/`api_key`. Those kwargs are on `OpenAIProvider`.

**Resolution:** `OpenAIProvider(base_url=..., api_key=...)` passed as the `provider` argument to `OpenAIModel`.

### 6. `AgentRunResult.output` not `.data`

**Plan said:** The plan did not specify the attribute name.

**Verified:** `result.output` is the correct attribute in pydantic-ai 1.104.0. `result.data` does not exist on this version.

### 7. pyproject.toml: `pydantic.mypy` plugin added

**Why:** mypy strict mode reports missing required args on `Settings()` (the pydantic-settings constructor) because it cannot infer that fields are populated from env vars. The pydantic mypy plugin teaches mypy the correct semantics.

### 8. `tests/` fixtures use `tmp_path` not `:memory:`

**Why:** Each `aiosqlite.connect(":memory:")` opens a separate, isolated in-memory database. `init_db` would write the schema to one connection and the repository would open a different empty one. Using `tmp_path / "test.db"` (a real file) ensures all connections share the same state.

---

## Verification Checklist

| Item | Status |
|------|--------|
| `uv run mypy src/ tests/` — zero errors | ✅ |
| `uv run ruff check src/ tests/` — zero violations | ✅ |
| `uv run pytest tests/ -q` — 30 passed, 0 failed | ✅ |
| All domain entities own their invariants | ✅ |
| No business logic in handlers | ✅ |
| No SQL in application layer | ✅ |
| No pydantic_ai import in domain layer | ✅ |
| `AllowedUserMiddleware` is the single auth enforcement point | ✅ |
| Session status represented as `StrEnum`, not bare string | ✅ |
| All functions have complete type hints | ✅ |
| Structured logging used throughout; no `print()` | ✅ |
| No secrets in source code | ✅ |
