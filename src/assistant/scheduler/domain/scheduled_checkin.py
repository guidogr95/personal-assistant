from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

_CRON_FIELD_COUNT = 5


@dataclass
class ScheduledCheckIn:
    """A named check-in that fires on a cron schedule and runs the agent.

    Entity: owns its own state transitions (enabled/disabled). Cron expression
    format and required fields are validated at construction — invalid check-ins
    cannot be created.
    """

    name: str
    cron_expr: str
    instructions: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Check-in name cannot be blank")
        if not self.instructions.strip():
            raise ValueError("Check-in instructions cannot be blank")
        parts = self.cron_expr.strip().split()
        if len(parts) != _CRON_FIELD_COUNT:
            raise ValueError(
                f"Invalid cron expression '{self.cron_expr}': "
                f"expected {_CRON_FIELD_COUNT} fields, got {len(parts)}"
            )

    def disable(self) -> None:
        """Prevent this check-in from firing on its next scheduled time."""
        self.enabled = False

    def enable(self) -> None:
        """Resume firing this check-in on its schedule."""
        self.enabled = True
