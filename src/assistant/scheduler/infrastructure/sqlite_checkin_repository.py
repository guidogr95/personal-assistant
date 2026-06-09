from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import aiosqlite

from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.shared.exceptions import InfrastructureError


def _row_to_checkin(row: aiosqlite.Row) -> ScheduledCheckIn:
    created_at = datetime.fromisoformat(row["created_at"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)

    def _get(col: str) -> str | None:
        try:
            val = row[col]
            return val if val is not None else None
        except (KeyError, IndexError):
            return None

    fire_at_raw = _get("fire_at")
    fire_at = datetime.fromisoformat(fire_at_raw) if fire_at_raw else None
    if fire_at and fire_at.tzinfo is None:
        fire_at = fire_at.replace(tzinfo=UTC)

    max_runs_raw = _get("max_runs")
    run_count_raw = _get("run_count")
    cron_timezone_raw = _get("cron_timezone")

    return ScheduledCheckIn(
        id=row["id"],
        name=row["name"],
        cron_expr=_get("cron_expr") or "",
        instructions=_get("instructions") or "",
        message=_get("message") or "",
        fire_at=fire_at,
        max_runs=int(max_runs_raw) if max_runs_raw is not None else None,
        run_count=int(run_count_raw) if run_count_raw is not None else 0,
        cron_timezone=cron_timezone_raw,
        enabled=bool(row["enabled"]),
        created_at=created_at,
    )


class SQLiteScheduledCheckInRepository(ScheduledCheckInRepository):
    """aiosqlite-backed implementation of ScheduledCheckInRepository."""

    def __init__(self, sqlite_path: str) -> None:
        self._path = sqlite_path

    async def save(self, checkin: ScheduledCheckIn) -> None:
        """Upsert a check-in record."""
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(
                    """
                    INSERT INTO scheduled_checkins
                        (id, name, cron_expr, instructions, message,
                         fire_at, max_runs, run_count, enabled, created_at,
                         cron_timezone)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name          = excluded.name,
                        cron_expr     = excluded.cron_expr,
                        instructions  = excluded.instructions,
                        message       = excluded.message,
                        fire_at       = excluded.fire_at,
                        max_runs      = excluded.max_runs,
                        run_count     = excluded.run_count,
                        enabled       = excluded.enabled,
                        cron_timezone = excluded.cron_timezone
                    """,
                    (
                        checkin.id,
                        checkin.name,
                        checkin.cron_expr,
                        checkin.instructions,
                        checkin.message,
                        checkin.fire_at.isoformat() if checkin.fire_at else None,
                        checkin.max_runs,
                        checkin.run_count,
                        int(checkin.enabled),
                        checkin.created_at.isoformat(),
                        checkin.cron_timezone,
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to save check-in {checkin.id}") from exc

    async def get_by_id(self, checkin_id: str) -> ScheduledCheckIn | None:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM scheduled_checkins WHERE id = ?", (checkin_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return _row_to_checkin(row) if row else None
        except Exception as exc:
            raise InfrastructureError(f"Failed to fetch check-in {checkin_id}") from exc

    async def find_by_name(self, name: str) -> ScheduledCheckIn | None:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM scheduled_checkins WHERE name = ?", (name,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return _row_to_checkin(row) if row else None
        except Exception as exc:
            raise InfrastructureError(f"Failed to find check-in by name '{name}'") from exc

    async def list_all(self) -> list[ScheduledCheckIn]:
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM scheduled_checkins ORDER BY created_at ASC"
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [_row_to_checkin(r) for r in rows]
        except Exception as exc:
            raise InfrastructureError("Failed to list check-ins") from exc

    async def update(self, checkin: ScheduledCheckIn) -> None:
        """Update an existing check-in record."""
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(
                    """
                    UPDATE scheduled_checkins SET
                        name         = ?,
                        cron_expr    = ?,
                        instructions = ?,
                        message      = ?,
                        fire_at      = ?,
                        max_runs     = ?,
                        run_count    = ?,
                        enabled      = ?
                    WHERE id = ?
                    """,
                    (
                        checkin.name,
                        checkin.cron_expr,
                        checkin.instructions,
                        checkin.message,
                        checkin.fire_at.isoformat() if checkin.fire_at else None,
                        checkin.max_runs,
                        checkin.run_count,
                        int(checkin.enabled),
                        checkin.id,
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to update check-in {checkin.id}") from exc

    async def delete(self, checkin_id: str) -> None:
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute("DELETE FROM scheduled_checkins WHERE id = ?", (checkin_id,))
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to delete check-in {checkin_id}") from exc

    async def log_execution(
        self,
        execution_id: str,
        checkin_id: str,
        checkin_name: str,
        fired_at: datetime,
        status: str,
        error_message: str | None,
        output_text: str | None,
    ) -> None:
        """Record a check-in execution attempt."""
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute(
                    """
                    INSERT INTO checkin_executions
                        (id, checkin_id, checkin_name, fired_at, status,
                         error_message, output_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        execution_id,
                        checkin_id,
                        checkin_name,
                        fired_at.isoformat(),
                        status,
                        error_message,
                        output_text,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to log execution {execution_id}") from exc

    async def get_execution_history(
        self,
        checkin_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return recent executions for a check-in, newest first."""
        try:
            async with aiosqlite.connect(self._path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    """
                    SELECT * FROM checkin_executions
                    WHERE checkin_id = ?
                    ORDER BY fired_at DESC
                    LIMIT ?
                    """,
                    (checkin_id, limit),
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]
        except Exception as exc:
            raise InfrastructureError(
                f"Failed to fetch execution history for check-in {checkin_id}"
            ) from exc
