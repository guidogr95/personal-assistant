"""Domain entity tests for Session and Turn."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from assistant.conversation.domain.context_window import MAX_VERBATIM_TURNS, build_verbatim_window
from assistant.conversation.domain.session import Session, SessionStatus
from assistant.conversation.domain.turn import Turn, TurnRole
from assistant.shared.exceptions import InvalidSessionStateError


class TestSession:
    def test_should_be_active_when_created(self) -> None:
        session = Session(user_id=1)
        assert session.is_active
        assert session.status == SessionStatus.ACTIVE

    def test_should_transition_to_closed_when_close_called(self) -> None:
        session = Session(user_id=1)
        session.close("My title")
        assert not session.is_active
        assert session.status == SessionStatus.CLOSED
        assert session.title == "My title"

    def test_should_raise_when_closing_already_closed_session(self) -> None:
        session = Session(user_id=1)
        session.close("title")
        with pytest.raises(InvalidSessionStateError):
            session.close("title again")

    def test_should_transition_to_active_when_reopen_called(self) -> None:
        session = Session(user_id=1)
        session.close("title")
        session.reopen()
        assert session.is_active

    def test_should_raise_when_reopening_already_active_session(self) -> None:
        session = Session(user_id=1)
        with pytest.raises(InvalidSessionStateError):
            session.reopen()

    def test_should_update_last_active_on_touch(self) -> None:
        session = Session(user_id=1)
        before = session.last_active
        session.touch()
        assert session.last_active >= before

    def test_should_store_message_history_blob(self) -> None:
        session = Session(user_id=1)
        blob = b'[{"kind": "request"}]'
        session.update_message_history(blob)
        assert session.message_history_json == blob


class TestTurn:
    def test_should_be_immutable(self) -> None:
        turn = Turn(session_id="s1", role=TurnRole.USER, content="hello")
        with pytest.raises(FrozenInstanceError):
            turn.content = "changed"  # type: ignore[misc]

    def test_should_have_unique_id_by_default(self) -> None:
        t1 = Turn(session_id="s1", role=TurnRole.USER, content="a")
        t2 = Turn(session_id="s1", role=TurnRole.USER, content="b")
        assert t1.id != t2.id

    def test_should_accept_all_defined_roles(self) -> None:
        for role in TurnRole:
            turn = Turn(session_id="s1", role=role, content="test")
            assert turn.role == role


class TestContextWindow:
    def test_should_return_only_user_and_assistant_turns(self) -> None:
        turns = [
            Turn(session_id="s", role=TurnRole.USER, content="q"),
            Turn(session_id="s", role=TurnRole.TOOL_CALL, content="call"),
            Turn(session_id="s", role=TurnRole.TOOL_RESULT, content="result"),
            Turn(session_id="s", role=TurnRole.ASSISTANT, content="a"),
            Turn(session_id="s", role=TurnRole.SUMMARY, content="summary"),
        ]
        window = build_verbatim_window(turns)
        assert all(t.role in (TurnRole.USER, TurnRole.ASSISTANT) for t in window)
        assert len(window) == 2

    def test_should_cap_at_max_verbatim_turns(self) -> None:
        turns = [
            Turn(
                session_id="s",
                role=TurnRole.USER if i % 2 == 0 else TurnRole.ASSISTANT,
                content=str(i),
            )
            for i in range(MAX_VERBATIM_TURNS + 10)
        ]
        window = build_verbatim_window(turns)
        assert len(window) == MAX_VERBATIM_TURNS

    def test_should_return_empty_list_for_no_turns(self) -> None:
        assert build_verbatim_window([]) == []
