# Acceptance Checklist

Maps 1:1 to the acceptance criteria in [spec.md](../spec.md).  
Complete all items in a phase before marking that phase as done.

---

## AC-1: Conversational AI via Telegram

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1.1 | User sends a Telegram message and receives an intelligent response | ⬜ | Phase 1 |
| 1.2 | Response references information from prior turns in the current session | ⬜ | Phase 1 |
| 1.3 | Agent calls appropriate tools when the request requires them | ⬜ | Phase 2+ |
| 1.4 | Responses use Markdown formatting | ⬜ | Phase 1 |
| 1.5 | Bot handles Telegram message edits and connection drops gracefully | ⬜ | Phase 1 |

---

## AC-2: Session Management

| # | Criterion | Status | Notes |
|---|---|---|---|
| 2.1 | `/new` starts a fresh session; previous active session auto-closed | ⬜ | Phase 1 |
| 2.2 | `/sessions` shows inline keyboard with last 10 sessions | ⬜ | Phase 1 |
| 2.3 | Tapping a session resumes it (loads turn history) | ⬜ | Phase 1 |
| 2.4 | `/close` closes session and generates descriptive title (≤7 words) | ⬜ | Phase 6 |
| 2.5 | Message with no active session auto-creates one | ⬜ | Phase 1 |
| 2.6 | Message to closed session is rejected with prompt | ⬜ | Phase 1 |
| 2.7 | Context window managed: last 20 turns verbatim; older compressed | ⬜ | Phase 6 |

---

## AC-3: Long-Term Memory

| # | Criterion | Status | Notes |
|---|---|---|---|
| 3.1 | Agent stores a fact at user request | ⬜ | Phase 2 |
| 3.2 | Stored memories retrievable in future sessions | ⬜ | Phase 2 |
| 3.3 | Memory persists across bot restarts and redeployments | ⬜ | Phase 2 |

---

## AC-4: Notes

| # | Criterion | Status | Notes |
|---|---|---|---|
| 4.1 | Agent creates a note from Telegram message as Markdown file | ⬜ | Phase 4 |
| 4.2 | Note appears in vault immediately | ⬜ | Phase 4 |
| 4.3 | Note syncs to phone within 30 seconds via Syncthing | ⬜ | Phase 4 |
| 4.4 | Note syncs to PC within 30 seconds | ⬜ | Phase 4 |
| 4.5 | Phone/PC edits sync back to VPS (bidirectional) | ⬜ | Phase 4 |
| 4.6 | Agent can search notes by content | ⬜ | Phase 4 |
| 4.7 | Agent can read full content of a specific note | ⬜ | Phase 4 |

---

## AC-5: Web Research

| # | Criterion | Status | Notes |
|---|---|---|---|
| 5.1 | Agent searches web using SearXNG (no API key) | ⬜ | Phase 3 |
| 5.2 | Agent fetches and summarises a URL using Jina Reader | ⬜ | Phase 3 |
| 5.3 | Jina failure falls back to rebrowser-Playwright | ⬜ | Phase 3 |
| 5.4 | Agent states clearly when page is inaccessible | ⬜ | Phase 3 |

---

## AC-6: Task Management

| # | Criterion | Status | Notes |
|---|---|---|---|
| 6.1 | Agent creates a task with title and optional due date | ⬜ | Phase 5 |
| 6.2 | Agent lists open tasks | ⬜ | Phase 5 |
| 6.3 | Agent marks a task complete | ⬜ | Phase 5 |
| 6.4 | Tasks visible in Vikunja web UI and mobile app | ⬜ | Phase 5 |
| 6.5 | Vikunja runs fully self-hosted in Docker | ⬜ | Phase 0/5 |

---

## AC-7: Google Calendar

| # | Criterion | Status | Notes |
|---|---|---|---|
| 7.1 | Agent creates calendar event with title, date/time, optional description | ⬜ | Phase 7 |
| 7.2 | Event appears in Google Calendar within 2 minutes | ⬜ | Phase 7 |
| 7.3 | Event includes popup reminder | ⬜ | Phase 7 |
| 7.4 | Reminder fires offline (via Calendar app local cache) | ⬜ | Phase 7 |
| 7.5 | Agent lists upcoming events for a given time range | ⬜ | Phase 7 |

---

## AC-8: Android Alarms

| # | Criterion | Status | Notes |
|---|---|---|---|
| 8.1 | **Phase 7a device test passed** (Tasker + AutoRemote flow verified) | ⬜ | Manual gate |
| 8.2 | Agent sets native clock alarm for specified time and label | ⬜ | Phase 7 |
| 8.3 | Alarm fires without internet at fire time | ⬜ | Phase 7 — device test |
| 8.4 | Alarm is created silently (no clock UI opened) | ⬜ | Phase 7 — device test |

---

## AC-9: Proactive Check-ins

| # | Criterion | Status | Notes |
|---|---|---|---|
| 9.1 | User defines a check-in via Telegram (`/checkin add`) | ⬜ | Phase 6 |
| 9.2 | Check-in fires at scheduled time and sends message to Telegram | ⬜ | Phase 6 |
| 9.3 | Check-in schedules survive bot restarts | ⬜ | Phase 6 |
| 9.4 | User can list, enable, disable, and delete check-ins | ⬜ | Phase 6 |

---

## AC-10: Deployment and Portability

| # | Criterion | Status | Notes |
|---|---|---|---|
| 10.1 | `docker compose up -d` starts entire stack | ⬜ | Phase 0 |
| 10.2 | Works identically in WSL2 (dev) and Linux VPS (prod) | ⬜ | Phase 0 |
| 10.3 | No secrets in source code; all in `.env` | ⬜ | Phase 0 |
| 10.4 | Bot restarts automatically on crash | ⬜ | Phase 0 |
| 10.5 | Code changes in dev are live without container rebuild | ⬜ | Phase 0 |

---

## Status Key

| Symbol | Meaning |
|---|---|
| ⬜ | Not yet started |
| 🔄 | In progress |
| ✅ | Verified passing |
| ❌ | Known failure — needs fix |
| ⏸️ | Blocked by gate or dependency |
