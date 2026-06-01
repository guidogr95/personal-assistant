# Phase 7: Google Calendar + Android Alarms

**Goal:** The agent can create Google Calendar events (with reminders) and set native Android clock alarms via Tasker + AutoRemote.  
**Prerequisites:** Phase 6 complete. **Phase 7a manual device test must pass before implementing alarm code** (see gate below).  
**Output:** "Schedule a dentist appointment on Thursday at 10am" → creates calendar event with reminder. "Set an alarm for 7am tomorrow labeled 'gym'" → native alarm fires on Android clock app even without internet.

---

## ⛔ Phase 7a Gate: Manual Device Test (Required Before Alarm Code)

**Do not skip this gate.** The Tasker + AutoRemote alarm flow is device-specific and cannot be tested in CI. Implementing alarm tools before verifying the flow works on your device wastes time if Tasker intents behave differently on your Android version.

**Estimated time: 30 minutes.**

### 7a Test Procedure

**Prerequisites:**
- Tasker ($3.49, one-time purchase from Google Play)
- AutoRemote (free, by João Dias — same developer as Tasker)

**Step 1: Verify Tasker can set a native alarm**
1. Open Tasker
2. Create a new Task: name it "Test Alarm"
3. Add Action → **System** → **Set Alarm**
4. Set: Hour=8, Minute=0, Message=Test Alarm, Vibrate=off, Skip UI=on (so the alarm sets silently)
5. Run the task manually from Tasker
6. Open the system Clock app → verify the alarm appears at 8:00 AM
7. Delete the test alarm

**Step 2: Verify AutoRemote can trigger Tasker**
1. Install AutoRemote from Google Play
2. Open AutoRemote → copy your **Personal URL** (looks like `https://autoremotejoaoapps.appspot.com/sendmessage?key=YOUR_KEY`)
3. In Tasker: create a new Profile → Event → Plugin → AutoRemote → Message Filter: `alarm=`
4. Link that profile to the "Test Alarm" task from Step 1
5. From your PC or WSL2 terminal, send a test message:
   ```bash
   curl "https://autoremotejoaoapps.appspot.com/sendmessage?key=YOUR_KEY&message=alarm=TestLabel&target=time=08:00"
   ```
6. Verify the alarm appears in the Android clock app with label "TestLabel"

**Step 3: Confirm offline behavior**
1. Enable airplane mode on the phone
2. Wait for the alarm to fire (you may use a 1-minute test alarm)
3. Confirm it fires with no internet

**Gate criteria (must be YES before proceeding to Phase 7b):**
- [ ] Step 1: Tasker successfully sets a silent alarm via `ACTION_SET_ALARM`
- [ ] Step 2: AutoRemote message triggers Tasker, which sets the alarm
- [ ] Step 3: Alarm fires in airplane mode

**If the test fails:** Do not implement alarm tools. Document which step failed and why. The calendar integration (Phase 7b) can proceed independently.

---

## Phase 7b: Google Calendar Setup

### Step 1 — Create Google Cloud Project and OAuth Credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project: "telegram-assistant"
3. Enable the **Google Calendar API**
4. Go to **Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON; copy values to `.env`:
   ```dotenv
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```

### Step 2 — One-Time OAuth Authorization

```python
# scripts/setup_google_oauth.py
"""Run this once locally to authorize Google Calendar access.
Writes a token file to GOOGLE_TOKEN_JSON_PATH for headless use afterwards.
"""
import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def setup_oauth() -> None:
    token_path = os.getenv("GOOGLE_TOKEN_JSON_PATH", "/data/google_token.json")
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    Path(token_path).parent.mkdir(parents=True, exist_ok=True)
    Path(token_path).write_text(creds.to_json())
    print(f"Token saved to {token_path}")

if __name__ == "__main__":
    setup_oauth()
```

Run this on a machine with a browser (WSL2 with browser access, or local PC):
```bash
uv run python scripts/setup_google_oauth.py
```

The token file must be copied to the Docker volume `/data/google_token.json` before the bot starts:
```bash
docker cp google_token.json <bot_container>:/data/google_token.json
```

### Step 3 — Google Calendar Client

```python
# calendar/infrastructure/google_calendar_client.py
from datetime import datetime
from typing import List, Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pathlib import Path
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
import json
import structlog

logger = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _load_credentials() -> Credentials:
    token_path = Path(settings.google_token_json_path)
    if not token_path.exists():
        raise InfrastructureError(
            f"Google Calendar token not found at {token_path}. "
            "Run scripts/setup_google_oauth.py first."
        )
    creds = Credentials.from_authorized_user_json(token_path.read_text(), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


class GoogleCalendarClient:
    def create_event(
        self,
        title: str,
        start_iso: str,
        end_iso: str,
        description: Optional[str] = None,
        reminder_minutes: int = 15,
    ) -> str:
        """Create a Google Calendar event. Returns the event HTML link."""
        creds = _load_credentials()
        service = build("calendar", "v3", credentials=creds)

        event_body = {
            "summary": title,
            "start": {"dateTime": start_iso, "timeZone": "UTC"},
            "end": {"dateTime": end_iso, "timeZone": "UTC"},
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": reminder_minutes}],
            },
        }
        if description:
            event_body["description"] = description

        try:
            event = service.events().insert(calendarId="primary", body=event_body).execute()
        except Exception as e:
            logger.error("google_calendar_create_failed", title=title, error=str(e))
            raise InfrastructureError("Failed to create Google Calendar event") from e

        link = event.get("htmlLink", "")
        logger.info("google_calendar_event_created", title=title, link=link)
        return link

    def list_upcoming_events(self, time_min_iso: str, max_results: int = 10) -> List[dict]:
        """List upcoming events starting from time_min_iso (ISO-8601 UTC)."""
        creds = _load_credentials()
        service = build("calendar", "v3", credentials=creds)

        try:
            result = service.events().list(
                calendarId="primary",
                timeMin=time_min_iso,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
        except Exception as e:
            logger.error("google_calendar_list_failed", error=str(e))
            raise InfrastructureError("Failed to list Google Calendar events") from e

        return result.get("items", [])
```

---

## Phase 7c: AutoRemote Alarm Client (only after Phase 7a gate passes)

### Step 4 — AutoRemote Client

```python
# alarms/infrastructure/autoremote_client.py
import httpx
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

AUTOREMOTE_URL = "https://autoremotejoaoapps.appspot.com/sendmessage"
AUTOREMOTE_TIMEOUT_SECONDS = 10


class AutoRemoteClient:
    async def send_alarm(self, time_hhmm: str, label: str) -> None:
        """Send a push to AutoRemote to trigger Tasker to set a native Android alarm.

        Args:
            time_hhmm: Alarm time in HH:MM format (24-hour, local phone time).
            label: Alarm label visible in the clock app.
        """
        params = {
            "key": settings.autoremote_key,
            "message": f"alarm={label}",
            "target": f"time={time_hhmm}",
        }
        try:
            async with httpx.AsyncClient(timeout=AUTOREMOTE_TIMEOUT_SECONDS) as client:
                response = await client.get(AUTOREMOTE_URL, params=params)
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("autoremote_alarm_failed", time=time_hhmm, label=label, error=str(e))
            raise InfrastructureError("Failed to send alarm via AutoRemote") from e

        logger.info("autoremote_alarm_sent", time=time_hhmm, label=label)
```

### Step 5 — Calendar and Alarm Tools

```python
# agent/tools/calendar_tools.py
from typing import Optional
from pydantic_ai import Agent, RunContext
from assistant.calendar.infrastructure.google_calendar_client import GoogleCalendarClient
import structlog

logger = structlog.get_logger()
_calendar = GoogleCalendarClient()


def register_calendar_tools(agent: Agent) -> None:

    @agent.tool
    def create_calendar_event(
        ctx: RunContext,
        title: str,
        start_iso: str,
        end_iso: str,
        description: Optional[str] = None,
    ) -> str:
        """Create a Google Calendar event.

        Args:
            title: Event title.
            start_iso: Start time in ISO-8601 format (e.g. '2025-01-17T10:00:00Z').
            end_iso: End time in ISO-8601 format.
            description: Optional event description.
        """
        link = _calendar.create_event(title, start_iso, end_iso, description)
        return f"Calendar event created: {link}"

    @agent.tool
    def list_upcoming_calendar_events(ctx: RunContext, days_ahead: int = 7) -> str:
        """List upcoming calendar events.

        Args:
            days_ahead: How many days ahead to look.
        """
        from datetime import datetime, timezone, timedelta
        time_min = datetime.now(timezone.utc).isoformat()
        events = _calendar.list_upcoming_events(time_min, max_results=10)
        if not events:
            return "No upcoming events."
        lines = []
        for e in events:
            start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", ""))
            lines.append(f"- {e.get('summary', 'Untitled')} — {start}")
        return "\n".join(lines)
```

```python
# agent/tools/alarm_tools.py
from pydantic_ai import Agent, RunContext
from assistant.alarms.infrastructure.autoremote_client import AutoRemoteClient
import structlog

logger = structlog.get_logger()
_autoremote = AutoRemoteClient()


def register_alarm_tools(agent: Agent) -> None:

    @agent.tool
    async def set_alarm(ctx: RunContext, time_hhmm: str, label: str) -> str:
        """Set a native Android clock alarm via Tasker + AutoRemote.

        The alarm fires on the phone even without internet at fire time.
        Requires Tasker + AutoRemote to be installed and configured (see Phase 7a).

        Args:
            time_hhmm: Alarm time in HH:MM format (24-hour, phone's local time zone).
                       e.g. '07:30' for 7:30 AM.
            label: Short label visible in the Android clock app.
        """
        await _autoremote.send_alarm(time_hhmm, label)
        return f"Alarm set for {time_hhmm} — '{label}'"
```

---

## Verification

### Calendar verification
- [ ] `scripts/setup_google_oauth.py` completes without errors and writes token file
- [ ] "Create a calendar event: team meeting on Friday at 3pm for 1 hour" → event appears in Google Calendar
- [ ] Event has a 15-minute popup reminder
- [ ] "What events do I have this week?" returns the list

### Alarm verification (only after Phase 7a gate passes)
- [ ] `AUTOREMOTE_KEY` set in `.env`
- [ ] "Set an alarm for 8am tomorrow called gym" → alarm appears in Android clock app
- [ ] Alarm fires when phone is in airplane mode

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
- [ ] No `except Exception: pass` — Google API errors and AutoRemote HTTP errors caught specifically and logged
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No `print()` in production paths — structlog used throughout
- [ ] `AUTOREMOTE_KEY` and Google OAuth tokens never logged
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `calendar/` is a **Generic subdomain** — application use cases + infrastructure client only; no domain entities
- [ ] `alarms/` is a **Generic subdomain** — application use case + AutoRemote HTTP client; no domain entities
- [ ] `calendar/infrastructure/google_calendar_client.py` — all `google-api-python-client` calls here; no business logic
- [ ] `alarms/infrastructure/autoremote_client.py` — single HTTP POST; raises `InfrastructureError` on failure
- [ ] Google OAuth token refresh handled transparently in the infrastructure client — use cases never handle token lifecycle
- [ ] Phase 7a gate was completed and all three criteria were confirmed before alarm code was written

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 8** (optional, lowest priority) adds a Docker code execution sandbox for running Python/shell snippets safely.
