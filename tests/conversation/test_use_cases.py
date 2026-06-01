"""Integration tests for conversation use cases.

Uses real temporary SQLite repositories. No LLM calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assistant.conversation.application.close_session import close_active_session
from assistant.conversation.application.list_sessions import list_recent_sessions
from assistant.conversation.application.open_session import open_session_for_user
from assistant.conversation.application.resume_session import resume_session
from assistant.conversation.domain.session import SessionStatus
from assistant.conversation.infrastructure.sqlite_repositories import (
    SQLiteSessionRepository,
    SQLiteTurnRepository,
    init_db,
)
from assistant.shared.exceptions import NoActiveSessionError, SessionNotFoundError


@pytest.fixture
async def repos(tmp_path: Path) -> tuple[SQLiteSessionRepository, SQLiteTurnRepository]:
    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    return SQLiteSessionRepository(db_path), SQLiteTurnRepository(db_path)


class TestOpenSession:
    async def test_should_create_new_active_session(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        session = await open_session_for_user(user_id=1, session_repo=session_repo)
        assert session.is_active
        assert session.user_id == 1

    async def test_should_close_previous_session_when_opening_new_one(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        first = await open_session_for_user(user_id=2, session_repo=session_repo)
        await open_session_for_user(user_id=2, session_repo=session_repo)

        closed = await session_repo.get_by_id(first.id)
        assert closed is not None
        assert closed.status == SessionStatus.CLOSED

        active = await session_repo.get_active_for_user(2)
        assert active is not None
        assert active.id != first.id


class TestCloseSession:
    async def test_should_raise_when_no_active_session(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, turn_repo = repos
        # Use a lightweight stub agent that won't be called since there's no session
        from unittest.mock import AsyncMock

        mock_agent = AsyncMock()

        with pytest.raises(NoActiveSessionError):
            await close_active_session(
                user_id=99,
                session_repo=session_repo,
                turn_repo=turn_repo,
                agent=mock_agent,
            )


class TestListSessions:
    async def test_should_return_empty_list_for_user_with_no_sessions(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        sessions = await list_recent_sessions(user_id=77, session_repo=session_repo)
        assert sessions == []

    async def test_should_return_sessions_for_user(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        await open_session_for_user(user_id=8, session_repo=session_repo)
        sessions = await list_recent_sessions(user_id=8, session_repo=session_repo)
        assert len(sessions) == 1


class TestResumeSession:
    async def test_should_raise_for_nonexistent_session(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        with pytest.raises(SessionNotFoundError):
            await resume_session(user_id=1, session_id="does-not-exist", session_repo=session_repo)

    async def test_should_reopen_a_closed_session(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        session = await open_session_for_user(user_id=20, session_repo=session_repo)
        session.close("old title")
        await session_repo.save(session)

        resumed = await resume_session(user_id=20, session_id=session.id, session_repo=session_repo)
        assert resumed.is_active

    async def test_should_close_current_active_and_resume_target(
        self, repos: tuple[SQLiteSessionRepository, SQLiteTurnRepository]
    ) -> None:
        session_repo, _ = repos
        first = await open_session_for_user(user_id=30, session_repo=session_repo)
        first.close("first")
        await session_repo.save(first)

        second = await open_session_for_user(user_id=30, session_repo=session_repo)

        # Now resume the first (closed) session — second should be closed automatically
        await resume_session(user_id=30, session_id=first.id, session_repo=session_repo)

        second_in_db = await session_repo.get_by_id(second.id)
        assert second_in_db is not None
        assert second_in_db.status == SessionStatus.CLOSED

        active = await session_repo.get_active_for_user(30)
        assert active is not None
        assert active.id == first.id
