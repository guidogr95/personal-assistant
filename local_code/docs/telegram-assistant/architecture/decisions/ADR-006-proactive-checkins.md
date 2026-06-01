# ADR-006: APScheduler + SQLAlchemyJobStore for Proactive Check-ins

**Date:** 2025  
**Status:** Accepted

## Context

The assistant needs to fire proactive messages on user-defined cron schedules (e.g., "every morning at 9am, summarise my open tasks"). Schedules must:
- Survive bot restarts (stored in persistent storage)
- Be configurable at runtime from within the Telegram bot (no config file edits)
- Not require an additional service

## Decision

Use **APScheduler 3.x** running in-process within the bot service, with a `SQLAlchemyJobStore` pointing at the same SQLite file used for conversation history (`/data/assistant.db`).

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url="sqlite:////data/assistant.db")},
    timezone="UTC",
)
scheduler.start()
```

Each check-in job calls `run_checkin(checkin_id)`, which:
1. Loads the `ScheduledCheckIn` entity from the DB
2. Runs the agent with the check-in's system prompt
3. Sends the result to the configured Telegram chat

Check-in metadata (name, cron_expr, system_prompt, enabled) is stored in a `scheduled_checkins` table managed by the `scheduler` bounded context, separate from APScheduler's internal job table.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **Celery Beat** | Requires a separate Celery worker container + Redis or RabbitMQ broker. 2 additional services for a feature that can run in-process. |
| **systemd timers** | Lives outside the Docker container; not configurable from within the bot at runtime; doesn't restart with the container |
| **Telegram-native bot commands that trigger tasks** | Reactive, not proactive — user must manually initiate; defeats the purpose of scheduled check-ins |
| **Cron on the host OS** | Same issues as systemd timers; not portable; not configurable from within the bot |

## Consequences

- APScheduler's internal job table shares the SQLite file with conversation data; no isolation concern since table names don't conflict
- The `scheduler` bounded context maintains its own `scheduled_checkins` table with human-readable metadata; APScheduler's table only stores job execution metadata
- Timezone: all cron expressions stored and evaluated in UTC; bot presents them to the user with the configured display timezone
- If the bot crashes mid-check-in, APScheduler will re-fire missed jobs based on `misfire_grace_time` configuration
- Maximum concurrent check-ins per minute is bounded by SQLite's write throughput; sufficient for personal use (< 10 active check-ins)
