from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from assistant.shared.exceptions import InvalidSessionStateError


class SessionStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"


@dataclass
class Session:
    """A named conversation thread with an active or closed lifecycle.

    Owns its own state transitions. Business rules are enforced here,
    not in the application layer.
    """

    user_id: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Serialized pydantic-ai ModelMessage list for LLM context continuity.
    # Stored as raw bytes so the domain layer stays free of pydantic_ai imports.
    message_history_json: bytes | None = None

    @property
    def is_active(self) -> bool:
        return self.status == SessionStatus.ACTIVE

    def close(self, title: str) -> None:
        """Transition session to CLOSED with a generated title.

        Raises InvalidSessionStateError if session is already closed.
        """
        if self.status == SessionStatus.CLOSED:
            raise InvalidSessionStateError(f"Session {self.id} is already closed")
        self.status = SessionStatus.CLOSED
        self.title = title

    def reopen(self) -> None:
        """Transition a CLOSED session back to ACTIVE.

        Raises InvalidSessionStateError if session is already active.
        """
        if self.status == SessionStatus.ACTIVE:
            raise InvalidSessionStateError(f"Session {self.id} is already active")
        self.status = SessionStatus.ACTIVE
        self.touch()

    def touch(self) -> None:
        """Update last_active to the current UTC time."""
        self.last_active = datetime.now(UTC)

    def update_message_history(self, history_json: bytes) -> None:
        """Replace the stored pydantic-ai message history blob."""
        self.message_history_json = history_json
