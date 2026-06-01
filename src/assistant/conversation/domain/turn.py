from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class TurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SUMMARY = "summary"


@dataclass(frozen=True)
class Turn:
    """One message within a session, identified by role and content.

    Immutable after creation — represents a historical fact about the conversation.
    """

    session_id: str
    role: TurnRole
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))
