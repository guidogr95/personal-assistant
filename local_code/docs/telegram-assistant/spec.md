# Project Specification

## Goal

A self-hosted personal AI assistant reachable via Telegram, with persistent memory,
structured note storage, task management, calendar integration, and Android alarms.
Runs on a Linux VPS. Developed locally on Windows via WSL2. Single-user.

---

## Acceptance Criteria

### AC-1: Conversational AI via Telegram
- [ ] User sends a Telegram message and receives an intelligent response
- [ ] Response references information from prior turns in the current session
- [ ] Agent calls appropriate tools (search, notes, tasks, calendar, alarms) when the request requires them
- [ ] Responses use Markdown formatting where it improves readability
- [ ] Bot handles Telegram message edits and connection drops gracefully

### AC-2: Session Management
- [ ] `/new` starts a fresh session; previous active session is auto-closed and titled
- [ ] `/sessions` sends a Telegram inline keyboard listing the last 10 sessions with generated titles
- [ ] Tapping a session in the list resumes it (loads its turn history as context)
- [ ] `/close` closes the active session and generates a descriptive title (≤7 words, via LLM)
- [ ] A message sent with no active session auto-creates one
- [ ] A message sent to a closed session is rejected with a prompt to open or resume a session
- [ ] Context window is managed: last 20 turns injected verbatim; older turns compressed to summaries

### AC-3: Long-Term Memory
- [ ] Agent can explicitly store a fact at user request ("remember that my server IP is X")
- [ ] Stored memories are retrievable in future sessions ("what's my server IP?")
- [ ] Memory persists across bot restarts and redeployments

### AC-4: Notes
- [ ] Agent creates a note from a Telegram message, saving it as a Markdown file in the vault
- [ ] Note appears in the vault on the VPS immediately
- [ ] Note syncs to the user's phone (Obsidian/Logseq) within 30 seconds via Syncthing
- [ ] Note syncs to the user's PC within 30 seconds
- [ ] User can edit a note on phone or PC; edit syncs back to VPS and is readable by the agent
- [ ] Agent can search notes by content and return matching results
- [ ] Agent can read the full content of a specific note

### AC-5: Web Research
- [ ] Agent searches the web given a natural-language query using SearXNG
- [ ] Agent fetches and summarizes a specific URL using Jina Reader
- [ ] When Jina Reader returns empty or blocked content, agent falls back to rebrowser-Playwright
- [ ] Agent clearly states when a page is inaccessible after all fallbacks exhausted
- [ ] No external search API key required for operation

### AC-6: Task Management
- [ ] Agent creates a task with a title and optional due date in Vikunja
- [ ] Agent lists open tasks
- [ ] Agent marks a task as complete
- [ ] Tasks are visible in the Vikunja web UI and mobile app
- [ ] Vikunja runs fully self-hosted in Docker

### AC-7: Google Calendar
- [ ] Agent creates a calendar event with title, date/time, and optional description
- [ ] Event appears in the user's Google Calendar within 2 minutes
- [ ] Event includes a popup reminder notification
- [ ] Reminder fires on the phone even when offline (via Calendar app local cache)
- [ ] Agent lists upcoming events for a given time range

### AC-8: Android Alarms
- [ ] Agent sets a native clock alarm on the Android device for a specified time and label
- [ ] Alarm fires on the phone even without internet connection at fire time
- [ ] Alarm is created silently (no phone clock UI opened)
- [ ] Requires Tasker ($3.49) + AutoRemote (free) installed on the device

### AC-9: Proactive Check-ins
- [ ] User defines a check-in via Telegram: name, cron expression, system prompt
- [ ] Check-in fires at the scheduled time and sends an agent-generated message to Telegram
- [ ] Check-in schedules survive bot restarts (stored in SQLite via APScheduler job store)
- [ ] User can list, enable, disable, and delete check-ins via Telegram commands

### AC-10: Deployment and Portability
- [ ] Entire stack starts with a single `docker compose up -d`
- [ ] Works identically in WSL2 (local dev) and Linux VPS (production)
- [ ] No secrets in source code; all configured via `.env` file
- [ ] Bot restarts automatically on crash (`restart: unless-stopped` Docker policy)
- [ ] Code changes in dev are live without container rebuild (override bind-mount)

---

## Out of Scope

| Item | Reason |
|---|---|
| Multi-user support | Personal assistant; single Telegram user ID enforced at handler level |
| Voice message transcription | Whisper integration deferred to future feature |
| CAPTCHA relay | Deferred — see Future Features in README |
| Telegram group support | Out of scope for personal use |
| Web UI / admin dashboard | Telegram is the only interface |
| Email integration | Deferred |
| Code execution sandbox (Phase 8) | Lowest priority; may not be built in initial version |

---

## Constraints

| Constraint | Impact |
|---|---|
| Single Linux VPS (Hetzner CX22 class: 2 vCPU / 4GB RAM / 40GB SSD) | All Docker services must fit within ~3GB RAM combined |
| Development on Windows via WSL2 | Project must live inside WSL2 filesystem; no `/mnt/c/` volume mounts in Docker |
| No paid external services beyond $3.49 Tasker | All search, storage, sync must be self-hosted or free-tier |
| OpenCode Go as LLM provider | `base_url=https://opencode.ai/zen/go/v1`; OpenAI-compatible format |
| Offline alarm requirement | ntfy.sh and similar push-only solutions disqualified; must use native device alarm |
