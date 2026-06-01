from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite

from assistant.conversation.domain.repositories import SessionRepository, TurnRepository
from assistant.conversation.domain.session import Session, SessionStatus
from assistant.conversation.domain.turn import Turn, TurnRole
from assistant.shared.exceptions import InfrastructureError

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id                   TEXT PRIMARY KEY,
    user_id              INTEGER NOT NULL,
    title                TEXT,
    status               TEXT NOT NULL DEFAULT 'active',
    created_at           TEXT NOT NULL,
    last_active          TEXT NOT NULL,
    message_history_json BLOB
);

CREATE TABLE IF NOT EXISTS turns (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    ts          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_checkins (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    cron_expr    TEXT NOT NULL,
    instructions TEXT NOT NULL,
    enabled      INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_sessions_user  ON sessions(user_id, last_active DESC);
"""


async def init_db(sqlite_path: str) -> None:
    """Create all tables and indexes if they do not exist.

    Also applies any pending column-rename migrations so existing databases
    are kept in sync with schema changes.

    Must be called once at startup before any repository is used.
    """
    try:
        async with aiosqlite.connect(sqlite_path) as db:
            await db.executescript(_SCHEMA_SQL)
            await _migrate_checkin_instructions_column(db)
            await db.commit()
    except Exception as exc:
        raise InfrastructureError("Failed to initialise SQLite schema") from exc


async def _migrate_checkin_instructions_column(db: aiosqlite.Connection) -> None:
    """Rename the system_prompt column to instructions if the old name still exists.

    Applies once on databases created before Phase 6 column rename. Safe to
    run on databases that already have the 'instructions' column — SQLite
    raises an error only if the column being renamed does not exist.
    """
    async with db.execute("PRAGMA table_info(scheduled_checkins)") as cursor:
        columns = [row[1] async for row in cursor]
    if "system_prompt" in columns:
        await db.execute(
            "ALTER TABLE scheduled_checkins RENAME COLUMN system_prompt TO instructions"
        )


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 string stored in SQLite back to an aware datetime."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _row_to_session(row: aiosqlite.Row) -> Session:
    return Session(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        status=SessionStatus(row["status"]),
        created_at=_parse_datetime(row["created_at"]),
        last_active=_parse_datetime(row["last_active"]),
        message_history_json=row["message_history_json"],
    )


def _row_to_turn(row: aiosqlite.Row) -> Turn:
    return Turn(
        id=row["id"],
        session_id=row["session_id"],
        role=TurnRole(row["role"]),
        content=row["content"],
        ts=_parse_datetime(row["ts"]),
    )


class SQLiteSessionRepository(SessionRepository):
    """aiosqlite-backed implementation of SessionRepository."""

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path

    async def save(self, session: Session) -> None:
        """Upsert a session record."""
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(
                    """
                    INSERT INTO sessions
                        (id, user_id, title, status, created_at, last_active, message_history_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title                = excluded.title,
                        status               = excluded.status,
                        last_active          = excluded.last_active,
                        message_history_json = excluded.message_history_json
                    """,
                    (
                        session.id,
                        session.user_id,
                        session.title,
                        str(session.status),
                        session.created_at.isoformat(),
                        session.last_active.isoformat(),
                        session.message_history_json,
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to save session {session.id}") from exc

    async def get_by_id(self, session_id: str) -> Session | None:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return _row_to_session(row) if row else None
        except Exception as exc:
            raise InfrastructureError(f"Failed to fetch session {session_id}") from exc

    async def get_active_for_user(self, user_id: int) -> Session | None:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM sessions WHERE user_id = ? AND status = 'active' LIMIT 1",
                    (user_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    return _row_to_session(row) if row else None
        except Exception as exc:
            raise InfrastructureError(f"Failed to fetch active session for user {user_id}") from exc

    async def list_recent(self, user_id: int, limit: int = 10) -> list[Session]:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT * FROM sessions
                    WHERE user_id = ?
                    ORDER BY last_active DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [_row_to_session(r) for r in rows]
        except Exception as exc:
            raise InfrastructureError(f"Failed to list sessions for user {user_id}") from exc


class SQLiteTurnRepository(TurnRepository):
    """aiosqlite-backed implementation of TurnRepository."""

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path

    async def save(self, turn: Turn) -> None:
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(
                    "INSERT INTO turns (id, session_id, role, content, ts) VALUES (?, ?, ?, ?, ?)",
                    (
                        turn.id,
                        turn.session_id,
                        str(turn.role),
                        turn.content,
                        turn.ts.isoformat(),
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to save turn {turn.id}") from exc

    async def list_for_session(self, session_id: str) -> list[Turn]:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM turns WHERE session_id = ? ORDER BY ts ASC",
                    (session_id,),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [_row_to_turn(r) for r in rows]
        except Exception as exc:
            raise InfrastructureError(f"Failed to list turns for session {session_id}") from exc
