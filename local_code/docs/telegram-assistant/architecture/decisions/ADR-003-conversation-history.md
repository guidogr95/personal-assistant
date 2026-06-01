# ADR-003: Custom SQLite Schema for Conversation History

**Date:** 2025  
**Status:** Accepted

## Context

The agent needs persistent conversation history to support session resumption across bot restarts. The history must be queryable (to list sessions, build context windows, generate titles). The storage must survive container restarts and be portable (single file for backups). The system is single-user, so throughput is not a concern. APScheduler also needs a persistent job store — the same SQLite file can serve both needs.

## Decision

Use a **custom SQLite schema** accessed via `aiosqlite` + `SQLAlchemy Core`.

Schema:
```sql
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,       -- UUID
    user_id     INTEGER NOT NULL,       -- Telegram user_id
    title       TEXT,                   -- generated on close (NULL while active)
    status      TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'closed'
    created_at  TEXT NOT NULL,          -- ISO-8601 UTC
    last_active TEXT NOT NULL
);

CREATE TABLE turns (
    id          TEXT PRIMARY KEY,       -- UUID
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    role        TEXT NOT NULL,          -- 'user' | 'assistant' | 'tool_call' | 'tool_result' | 'summary'
    content     TEXT NOT NULL,          -- raw message text or JSON for tool calls
    ts          TEXT NOT NULL           -- ISO-8601 UTC
);
```

APScheduler uses `SQLAlchemyJobStore` pointing at the same file via `sqlite:////data/assistant.db`.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **LangGraph checkpointer** | Stores graph execution state (nodes, edges, checkpoints) — not queryable conversation messages. Cannot list sessions or render turn history without LangGraph runtime. Couples storage to framework. |
| **Zep (hosted memory)** | Requires PostgreSQL + Redis + Zep server. 3 additional services for a single-user bot. Overkill. |
| **PostgreSQL** | Extra service (container + volume + init scripts). SQLite is sufficient for one user; switching later is straightforward since the schema is simple and accessed through repository interfaces. |
| **JSON files per session** | No transactional integrity; cannot query across sessions; difficult to implement session listing or context window selection. |

## Consequences

- All SQL is in `conversation/infrastructure/sqlite_repositories.py` — domain layer has no SQL awareness
- Context window assembly (`build_context.py`) queries the last N turns and older turns for summarization
- The APScheduler job store references the same DB file; no schema conflict (separate table namespace)
- Backup = copy `/data/assistant.db`; trivial with `docker cp` or volume backup
- If load ever warrants PostgreSQL: repository interfaces in `*/domain/` remain unchanged; only `sqlite_repositories.py` needs replacing
