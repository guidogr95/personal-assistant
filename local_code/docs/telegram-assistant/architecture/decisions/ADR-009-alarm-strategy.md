# ADR-009: Hybrid Alarm Strategy — Google Calendar + Tasker

**Date:** 2025  
**Status:** Accepted

## Context

The assistant needs to set time-based alerts for the user. There are two distinct concepts:

1. **Reminder** — a notification attached to a calendar event. Fires via the phone's calendar app, which caches event data locally. Works offline at fire time (as long as the phone was online when the event synced).

2. **Alarm** — a native Android clock alarm. Works even if internet is unavailable at fire time and even if Google Calendar is not installed. Appears in the system clock app like an alarm set manually.

A naive push-notification approach (ntfy.sh, Pushover, FCM directly) fails the offline requirement: if the phone has no internet at the exact fire time, the push is lost.

## Decision

Implement a **hybrid two-tier approach**:

**Tier 1 — Calendar Reminders (primary, for all time-based alerts):**
- Bot creates a Google Calendar event via the Google Calendar API
- Event includes a popup reminder (e.g., 0 minutes before)
- Google Calendar app on the phone caches events locally and fires reminders using local alarm scheduler
- **Works offline** as long as the phone synced the event while online at least once

**Tier 2 — Native Android Alarms (for alarm-critical requests):**
- Bot sends an HTTP POST to AutoRemote's URL: `https://autoremotejoaoapps.appspot.com/sendmessage?key=<KEY>&message=alarm=<label>&target=time=<HH:MM>`
- AutoRemote delivers the push to the phone via GCM (requires internet at delivery time)
- Tasker receives the AutoRemote event and fires `AlarmClock.ACTION_SET_ALARM` intent with the specified time and label
- The alarm is now stored in the system clock app — it fires at the specified time even with no internet

**Phase 7a Gate:** Before implementing alarm tools in code, the operator must perform a 30-minute manual device test confirming the full Tasker → AutoRemote → alarm flow works on their specific device. See `implementation/phase-7-calendar-alarms.md` for the test procedure.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **ntfy.sh push-only** | Push notification at delivery time, not at fire time. If phone is offline when the alarm should fire, the push is lost. Does not set a native alarm. |
| **Pushover** | Same issue as ntfy.sh — push at delivery, not at fire time. Not a native alarm. |
| **FCM direct** | Requires implementing a Firebase project and Android app. Disproportionate effort. Same push-at-delivery problem. |
| **Tasker-only without AutoRemote** | No HTTP endpoint on the phone; cannot push from server to Tasker without a push intermediary |
| **Termux + SSH tunnel** | Too fragile for production; SSH tunnel drops on network changes; battery optimization kills Termux |

## Consequences

- Tasker ($3.49 one-time) is a **required purchase** for native alarm functionality
- AutoRemote requires internet on the phone at the moment the alarm is *set* (not at fire time); this is acceptable — setting an alarm while online is the normal use case
- Google Calendar requires one-time OAuth setup (`scripts/setup_google_oauth.py`) before the bot can create events
- The `AUTOREMOTE_KEY` env var must be set for alarm tools; if missing, alarm tool returns a descriptive error
- Phase 7 calendar + alarm code must not be implemented until the Phase 7a device test is confirmed passing by the operator
