# Phase 5 Implementation Summary

**Status:** Complete  
**Date:** 2026-06-01

---

## Goal

Connect the agent to Vikunja so it can create, list, and complete tasks. Tasks created via
the bot appear immediately in the Vikunja web UI.

**Acceptance criterion:** "Add a task: buy groceries" → task appears in Vikunja; "What are my
open tasks?" returns the list; "Mark task N as done" completes it in the UI; Vikunja being
unreachable returns a user-facing error message — bot does not crash.

**Outcome:** ✅ Goal met. All four live Telegram tests passed. One mid-session bug fix was
required: the `GET /api/v1/tasks/all` endpoint was removed in Vikunja v2; replaced with
`GET /api/v1/projects/1/views/1/tasks` (the per-view endpoint that Vikunja v2 uses).

---

## What Was Built

### New package: `tasks/`

| File | What it contains |
|------|-----------------|
| `tasks/__init__.py` | Empty package marker. |
| `tasks/application/__init__.py` | Empty package marker. |
| `tasks/infrastructure/__init__.py` | Empty package marker. |
| `tasks/infrastructure/vikunja_client.py` | `VikunjaTask` — `@dataclass(frozen=True)` DTO with `id`, `title`, `done`, `due_date: str \| None`. `_parse_task` normalises Go's zero-time sentinel (`0001-01-01T00:00:00Z`) to `None`. `VikunjaClient` — thin `httpx`-based REST client with `create_task`, `list_open_tasks`, `complete_task`; raises `InfrastructureError` on any HTTP or network failure. |
| `tasks/application/create_task.py` | `create_task(title, due_date, client)` — single-responsibility delegation to `VikunjaClient.create_task`. |
| `tasks/application/list_tasks.py` | `list_open_tasks(client)` — single-responsibility delegation to `VikunjaClient.list_open_tasks`. |
| `tasks/application/complete_task.py` | `complete_task(task_id, client)` — single-responsibility delegation to `VikunjaClient.complete_task`. |

### New file: `agent/tools/task_tools.py`

| What it contains |
|-----------------|
| `register_task_tools(agent)` — registers three tools: `add_task`, `get_open_tasks`, `mark_task_done`. A module-level `_client = VikunjaClient()` instance is shared. Each tool guards against a missing `VIKUNJA_API_TOKEN` and catches `InfrastructureError` to return a user-facing error string instead of propagating the exception. |

### Modified: `agent/domain/agent.py`

- Added `from assistant.agent.tools.task_tools import register_task_tools`.
- Added `register_task_tools(agent)` call after `register_notes_tools(agent)`.

### Modified: `deploy/docker-compose.yml`

| Change | Why |
|--------|-----|
| `vikunja_db` health check (`healthcheck.sh --connect`) | Without it, `vikunja` starts before MariaDB accepts connections, causing a crash loop on first run. |
| `vikunja` depends on `vikunja_db: condition: service_healthy` | Guarantees the database is ready before Vikunja starts. |
| `vikunja_init` service (`alpine chown -R 1000:1000 /app/data`) | Docker creates named volumes as root; Vikunja runs as uid=1000. Without the chown, file writes fail with `permission denied`. Runs once before Vikunja via `service_completed_successfully`. |
| `VIKUNJA_SERVICE_PUBLICURL` env var | Vikunja v2 requires this when CORS is enabled — omitting it causes the service to refuse to start. |
| `VIKUNJA_FILES_BASEPATH=/app/data/files` | The default path (`/app/vikunja/files`) is outside the mounted volume, so uploaded files are lost on container restart. |
| `bot` depends on `vikunja: condition: service_started` | Bot container starts after Vikunja is up. |

### New tests: `tests/tasks/`

| File | What it covers |
|------|---------------|
| `tests/tasks/__init__.py` | Empty package marker. |
| `tests/tasks/test_use_cases.py` | `_parse_task` (zero-date normalisation, valid date, empty string, fields, immutability); `VikunjaClient` HTTP mocking (create, due-date payload, `HTTPStatusError`, `RequestError`, list, empty list, complete, complete failure); use cases (create delegate, due-date passthrough, error propagation, list delegate, empty list, complete delegate, complete error). 20 tests total. |

---

## Deviations from the Original Plan

| # | Plan said | What actually happened | Reason |
|---|-----------|----------------------|--------|
| 1 | `_client = VikunjaClient()` in each use case file | `client: VikunjaClient` parameter; single `_client` in `task_tools.py` | Consistent with the notes pattern — application layer stays testable without hitting the network. |
| 2 | `VikunjaTask.due_date: Optional[datetime]` | `due_date: str \| None` | Vikunja returns ISO-8601 strings. Parsing to `datetime` adds complexity with no benefit — the field is displayed but never used for arithmetic. |
| 3 | `except httpx.HTTPError` (single catch) | Separate `httpx.HTTPStatusError` and `httpx.RequestError` handlers | More specific log context per phase review checklist. |
| 4 | Tools let `InfrastructureError` propagate | Tools catch `InfrastructureError` and return user-facing string | Phase review checklist: "Vikunja being unreachable returns a user-facing error message — bot does not crash". |
| 5 | No token guard | `if not settings.vikunja_api_token` check at tool entry | Clear "not configured" message instead of a 401 traceback when the token is missing. |
| 6 | `_VIKUNJA_ZERO_DATE` handling not in plan | Added normalisation in `_parse_task` | Vikunja returns `"0001-01-01T00:00:00Z"` as the Go zero-time sentinel for unset dates. Without this, all tasks would appear to have a year-1 due date. |
| 7 | `GET /api/v1/tasks/all` endpoint | `GET /api/v1/projects/1/views/1/tasks` | Vikunja v2 removed the global `tasks/all` endpoint. Tasks are now fetched per project view. The default "List" view (ID 1) already has `done = false` baked into its filter, so no query params are needed. Discovered and fixed during live testing (400 Bad Request). |

---

## Infrastructure Debugging Log

Several Docker issues had to be resolved before the live tests could run. These are recorded
here so they do not need to be rediscovered.

| Problem | Symptom | Fix |
|---------|---------|-----|
| `VIKUNJA_DB_*` env vars blank | `vikunja_db` crash loop on first start | Always pass `--env-file .env` from project root. Docker Compose looks in the compose file's directory by default. |
| `VIKUNJA_SERVICE_PUBLICURL` missing | Vikunja refused to start | Added `VIKUNJA_SERVICE_PUBLICURL: ${VIKUNJA_SERVICE_PUBLICURL:-http://localhost:3456}` to Compose. |
| Volume owned by root | `permission denied` writing files | `vikunja_init` init container runs `chown -R 1000:1000 /app/data` before Vikunja. |
| Files written outside volume | Uploaded files lost on restart | Set `VIKUNJA_FILES_BASEPATH=/app/data/files`. |
| `restart` doesn't reload `.env` | Token update not picked up | Use `up -d --force-recreate <service>` — `restart` keeps the environment from container creation time. |

---

## Verification Results

| Check | Result |
|-------|--------|
| `uv run mypy src/` | ✅ 0 errors, 67 files |
| `uv run ruff check src/ tests/` | ✅ 0 violations |
| `uv run pytest tests/ -q` | ✅ 76/76 pass (20 new) |
| Vikunja web UI accessible | ✅ `http://localhost:3456` |
| Admin account registered | ✅ |
| API token in `.env` | ✅ `tk_91f4...` |
| Bot creates task → appears in UI | ✅ |
| "What are my open tasks?" returns list | ✅ (after v2 endpoint fix) |
| "Mark task N as done" completes in UI | ✅ |
| Vikunja unreachable → user-facing error | ✅ bot does not crash |
