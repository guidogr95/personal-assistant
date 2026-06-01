# Phase 6 Summary: Proactive Check-ins + Session Management UX

**Status:** ✅ Complete and live-verified (2026-06-01)  
**Tests:** 101/101 pass | mypy: 0 errors (81 files) | ruff: 0 violations

---

## What Was Built

APScheduler-based proactive check-ins that fire on cron schedules and send agent-generated Telegram messages without any user prompt. Session management UX completed: inline keyboard session list, LLM title generation on `/close`.

Natural language check-in management was added beyond the original spec (approved mid-session): the agent can schedule, list, and remove check-ins via plain conversation instead of requiring cron syntax.

---

## Plan vs Implementation

| File | Status | Notes |
|------|--------|-------|
| `scheduler/domain/scheduled_checkin.py` | ✅ | Entity with `__post_init__` validation |
| `scheduler/domain/repositories.py` | ✅ Added beyond plan | DDD requires the ABC interface |
| `scheduler/infrastructure/sqlite_checkin_repository.py` | ✅ Deviated | Plan said add to `sqlite_repositories.py`; separate file chosen for better separation |
| `scheduler/infrastructure/apscheduler_registry.py` | ✅ Deviated | MemoryJobStore instead of SQLAlchemy — re-register from DB at startup; same persistence guarantee, less complexity |
| `scheduler/application/run_checkin.py` | ✅ | `configure_checkin_runner` instead of `inject_dependencies` |
| `scheduler/application/register_checkin.py` | ✅ | |
| `scheduler/application/list_checkins.py` | ✅ | |
| `scheduler/application/delete_checkin.py` | ✅ | |
| `telegram/handlers/checkin_commands.py` | ✅ | `/checkin add name \| cron \| instructions` |
| `agent/tools/checkin_tools.py` | ✅ Added beyond plan | Natural language interface via three agent tools |
| `conversation/application/close_session.py` | ✅ | LLM title generation (was already in place from Phase 2) |
| `main.py` | ✅ | Scheduler start/stop, job re-registration, deps injected into polling data |
| `toggle_checkin.py` | ⚠️ Skipped | Listed in spec file tree but referenced in zero steps and zero verification criteria — YAGNI. Entity has `enable()`/`disable()` ready. |
| `telegram/handlers/session_commands.py` | ✅ Added beyond plan | `/help` command added; `set_my_commands` registered so Telegram autocomplete menu shows all commands |

---

## Deviations from Plan

| # | Plan said | What was built | Reason |
|---|-----------|----------------|--------|
| 1 | Field named `system_prompt` | Renamed to `instructions` | `agent.run()` first arg is a user turn, not a system prompt. Naming it `system_prompt` was misleading. DB migration added to `init_db`. |
| 2 | SQLAlchemy job store for APScheduler | In-memory scheduler, re-register from DB on startup | SQLAlchemy job store adds a dependency and schema complexity. Re-reading enabled check-ins from the SQLite DB at startup achieves identical persistence. |
| 3 | `sqlite_repositories.py` extended | `sqlite_checkin_repository.py` as a new file | Single-responsibility; `sqlite_repositories.py` already handles sessions and turns |
| 4 | No natural language interface | `checkin_tools.py` added | User requested it mid-phase; LLM handles cron translation so user never needs to write cron expressions |
| 5 | `toggle_checkin.py` | Not implemented | YAGNI — nothing in the spec steps or verification criteria requires it |

---

## Architecture Notes

- `ScheduledCheckIn` is a **mutable entity** (not `frozen=True`) — it owns its own `enable()`/`disable()` state transitions with invariant enforcement in `__post_init__`.
- APScheduler lives entirely in infrastructure (`apscheduler_registry.py`). Domain and application layers have no APScheduler imports.
- `run_checkin.py` uses a **lazy import** of `agent` (`from assistant.agent.domain.agent import agent` inside the function body) to break a circular dependency: `checkin_tools → register_checkin → run_checkin → agent → checkin_tools`.
- `configure_checkin_tools(scheduler, checkin_repo)` and `configure_checkin_runner(bot, checkin_repo)` are both called at startup in `main.py` before `scheduler.start()`.

---

## Gaps and Known Limitations

| Gap | Severity | Notes |
|-----|----------|-------|
| `toggle_checkin` (enable/disable without deleting) | Low | Entity supports it; no handler or tool exposes it. Add when needed. |
| Context window summarization | Low | Spec called for LLM-generated summaries of older turns. Current implementation truncates to last 20 turns. Sufficient for now; a dedicated summarization step can be added later. |
| `acceptance-checklist.md` not updated | Cosmetic | All items remain `⬜` across all phases. The checklist has not been maintained as phases completed. |
| `/help` command | ✅ Resolved | Added post-phase. `/help` handler added to `session_commands.py`; `bot.set_my_commands()` called in `main.py` startup so Telegram autocomplete shows all commands. |
| Check-in times are UTC only | Low | No timezone conversion. User must specify times in UTC or know the offset. |

---

## Verification Results

| Test | Result |
|------|--------|
| Natural language schedule: "Set up a morning check-in every weekday at 9am…" | ✅ |
| Natural language list: "What check-ins do I have?" | ✅ |
| `/checkin list` slash command fallback | ✅ |
| Proactive fire: check-in with `* * * * *` sends message unprompted | ✅ |
| Natural language removal: "Remove the Morning Tasks check-in" | ✅ |
| `uv run mypy src/` | ✅ 0 errors, 81 files |
| `uv run pytest tests/ -q` | ✅ 101/101 pass |
| `/help` lists all commands; Telegram autocomplete populated | ✅ |
| `uv run ruff check src/ tests/` | ✅ 0 violations |

---

## Post-Phase: VPS Deployment + Notes Sync Infrastructure (2026-06-01)

After feature work was complete, the following fixes and infrastructure changes were made to bring the bot live on a remote VPS and enable cross-device notes sync.

### Bug fix — delete-note sentinel not surfaced to Telegram

`run_turn.py` was returning `result.output` as the reply string. pydantic-ai's `result.output` is always the LLM's generated text — when the delete-note confirmation keyboard triggered and the tool returned `DELETE_CONFIRM_SENTINEL`, the sentinel never reached the Telegram message handler. Fixed by scanning `result.new_messages()` for a `ToolReturnPart` whose content equals the sentinel and using it as the reply when found. `result.output` is used as the fallback for all normal turns.

### VPS deployment

Bot deployed to `~/Github/personal-assistant/` on the VPS. Production uses `deploy/docker-compose.yml` only (no override). Issues encountered and resolved:

| Problem | Fix |
|---------|-----|
| `notes/` gitignore pattern excluded the source package | Added `!/src/**/notes/` negation to `.gitignore` |
| `ModuleNotFoundError: assistant.notes` on VPS | `git pull && docker compose up -d --build bot` |
| Vikunja SSH tunnel "connection refused" | Added `ports: ["127.0.0.1:3456:3456"]` to Vikunja service |
| Syncthing UI publicly accessible | Changed `8384:8384` → `127.0.0.1:8384:8384` |
| SearXNG `secret_key` hardcoded in `settings.yml` | Moved to `SEARXNG_SECRET` env var; `settings.yml` references it; added to `.env.example` |

VPS Syncthing UI is only reachable via SSH tunnel: `ssh -L 8386:localhost:8384 root@<vps-ip>`.

### Notes sync — Syncthing .stignore as infrastructure-as-code

Syncthing syncs the `notes_data` Docker volume (mounted at `/var/syncthing/` inside the container). The `config/` subdirectory lives at that same root and must not be synced to other devices. A `.stignore` file containing `config` was added at `deploy/syncthing/.stignore` and bind-mounted into the container at `/var/syncthing/.stignore`. This ensures the ignore rule survives volume recreation and is version-controlled.

Windows Syncthing paired with VPS; notes folder syncing and in sync.

---

## Next: Phase 7 — Google Calendar + Android Alarms

**Gate required before writing any code:** 30-minute manual device test (Tasker + AutoRemote on Android). See `phase-7-calendar-alarms.md` for exact steps. Do not skip.
