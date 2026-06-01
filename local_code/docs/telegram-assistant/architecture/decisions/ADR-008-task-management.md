# ADR-008: Vikunja for Task Management

**Date:** 2025  
**Status:** Accepted

## Context

The assistant needs to create, list, and complete tasks. Tasks must be accessible from a mobile app and a web UI, independent of the bot. The solution must be self-hosted (no SaaS), free, and have a stable REST API that the bot can call as a tool.

## Decision

Use **Vikunja** as the task management backend.

- Docker image: `vikunja/vikunja`
- Backing DB: MariaDB 10 (required by Vikunja; lighter than Postgres)
- Integration: Vikunja REST API, authenticated via long-lived API token
- Bot creates an API token via `POST /api/v1/tokens` during setup

The bot's interaction is limited to:
- `POST /api/v1/tasks` — create task
- `GET /api/v1/namespaces/default/tasks/all?filter_by=done&filter_value=false` — list open tasks
- `POST /api/v1/tasks/{id}` with `{"done": true}` — complete task

All Vikunja API calls go through `VikunjaClient` in `tasks/infrastructure/vikunja_client.py`. The domain layer has no Vikunja awareness.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **Todoist** | SaaS; data is stored on Doist's servers; privacy concern; cost for advanced features |
| **Notion Tasks** | SaaS; heavy API rate limits; far more than a task manager |
| **Plane** | Overkill (project management, sprints, issues, cycles); designed for teams; excessive RAM footprint for personal use |
| **Taskwarrior** | CLI-only; no mobile app; JSON file storage not suitable for REST API access |
| **Custom SQLite tasks table** | No mobile app; no web UI; operator wanted a real task app accessible independently from the bot |

## Consequences

- Requires `VIKUNJA_URL` and `VIKUNJA_API_TOKEN` in `.env`
- Vikunja MariaDB adds ~150MB RAM to the stack; acceptable within the 3GB VPS budget
- If Vikunja is unreachable, the task tool returns a descriptive error; the bot does not crash
- Vikunja's mobile apps (Android/iOS) and web UI work independently of the bot — tasks can be managed from anywhere
- CalDAV support in Vikunja enables optional calendar client sync (future feature, not in scope)
