from __future__ import annotations

from datetime import UTC, datetime

import aiosqlite

from assistant.scheduler.domain.repositories import ScheduledCheckInRepository
from assistant.scheduler.domain.scheduled_checkin import ScheduledCheckIn
from assistant.shared.exceptions import InfrastructureError


def _row_to_checkin(row: aiosqlite.Row) -> ScheduledCheckIn:
    created_at = datetime.fromisoformat(row["created_at"])
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return ScheduledCheckIn(
        id=row["id"],
        name=row["name"],
        cron_expr=row["cron_expr"],
        instructions=row["instructions"],
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
                        (id, name, cron_expr, instructions, enabled, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name         = excluded.name,
                        cron_expr    = excluded.cron_expr,
                        instructions = excluded.instructions,
                        enabled      = excluded.enabled
                    """,
                    (
                        checkin.id,
                        checkin.name,
                        checkin.cron_expr,
                        checkin.instructions,
                        int(checkin.enabled),
                        checkin.created_at.isoformat(),
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

    async def delete(self, checkin_id: str) -> None:
        try:
            async with aiosqlite.connect(self._path) as db:
                await db.execute("DELETE FROM scheduled_checkins WHERE id = ?", (checkin_id,))
                await db.commit()
        except Exception as exc:
            raise InfrastructureError(f"Failed to delete check-in {checkin_id}") from exc
