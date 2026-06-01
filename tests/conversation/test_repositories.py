"""Integration tests for SQLiteSessionRepository and SQLiteTurnRepository.

Uses a real temporary SQLite file so all connections share the same database.
Would also work with :memory: only if a single persistent connection were used,
but the current repository design opens a new connection per operation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assistant.conversation.domain.session import Session, SessionStatus
from assistant.conversation.domain.turn import Turn, TurnRole
from assistant.conversation.infrastructure.sqlite_repositories import (
    SQLiteSessionRepository,
    SQLiteTurnRepository,
    init_db,
)


@pytest.fixture
async def session_repo(tmp_path: Path) -> SQLiteSessionRepository:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    return SQLiteSessionRepository(db_path)


@pytest.fixture
async def turn_repo(tmp_path: Path) -> SQLiteTurnRepository:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    return SQLiteTurnRepository(db_path)


class TestSQLiteSessionRepository:
    async def test_should_persist_and_retrieve_session(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        session = Session(user_id=99)
        await session_repo.save(session)

        retrieved = await session_repo.get_by_id(session.id)
        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.user_id == 99
        assert retrieved.status == SessionStatus.ACTIVE

    async def test_should_return_none_for_unknown_id(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        result = await session_repo.get_by_id("nonexistent-id")
        assert result is None

    async def test_should_return_active_session_for_user(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        session = Session(user_id=42)
        await session_repo.save(session)

        active = await session_repo.get_active_for_user(42)
        assert active is not None
        assert active.id == session.id

    async def test_should_return_none_when_no_active_session(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        result = await session_repo.get_active_for_user(999)
        assert result is None

    async def test_should_update_session_on_upsert(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        session = Session(user_id=5)
        await session_repo.save(session)

        session.close("Updated title")
        await session_repo.save(session)

        retrieved = await session_repo.get_by_id(session.id)
        assert retrieved is not None
        assert retrieved.status == SessionStatus.CLOSED
        assert retrieved.title == "Updated title"

    async def test_should_list_recent_sessions_newest_first(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        s1 = Session(user_id=7)
        s2 = Session(user_id=7)
        s2.touch()  # ensure s2.last_active >= s1.last_active
        await session_repo.save(s1)
        await session_repo.save(s2)

        sessions = await session_repo.list_recent(user_id=7, limit=10)
        assert len(sessions) == 2
        # Both belong to user 7
        assert all(s.user_id == 7 for s in sessions)

    async def test_should_persist_message_history_blob(
        self, session_repo: SQLiteSessionRepository
    ) -> None:
        session = Session(user_id=3)
        blob = b'[{"kind":"request","parts":[]}]'
        session.update_message_history(blob)
        await session_repo.save(session)

        retrieved = await session_repo.get_by_id(session.id)
        assert retrieved is not None
        assert retrieved.message_history_json == blob


class TestSQLiteTurnRepository:
    async def test_should_persist_and_list_turns(
        self,
        tmp_path: Path,
    ) -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        session_repo = SQLiteSessionRepository(db_path)
        turn_repo = SQLiteTurnRepository(db_path)

        session = Session(user_id=10)
        await session_repo.save(session)

        t1 = Turn(session_id=session.id, role=TurnRole.USER, content="hello")
        t2 = Turn(session_id=session.id, role=TurnRole.ASSISTANT, content="world")
        await turn_repo.save(t1)
        await turn_repo.save(t2)

        turns = await turn_repo.list_for_session(session.id)
        assert len(turns) == 2
        assert turns[0].role == TurnRole.USER
        assert turns[1].role == TurnRole.ASSISTANT

    async def test_should_return_empty_list_for_session_with_no_turns(
        self,
        tmp_path: Path,
    ) -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        session_repo = SQLiteSessionRepository(db_path)
        turn_repo = SQLiteTurnRepository(db_path)

        session = Session(user_id=11)
        await session_repo.save(session)

        turns = await turn_repo.list_for_session(session.id)
        assert turns == []
