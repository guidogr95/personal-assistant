from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

_CRON_FIELD_COUNT = 5


@dataclass
class ScheduledCheckIn:
    """A named check-in that fires on a schedule and sends output to Telegram.

    Entity: owns its own state transitions (enabled/disabled) and run-count
    tracking.  Supports both recurring cron schedules and one-off datetime
    triggers.  Output can be either a direct message (no LLM cost) or an
    agent-run with instructions.

    Validation enforces:
    - At least one of ``instructions`` or ``message`` is set.
    - Exactly one of ``cron_expr`` or ``fire_at`` is set.
    - ``fire_at`` must be in the future.
    - ``max_runs`` must be >= 1 if set.
    """

    name: str
    instructions: str = ""
    message: str = ""
    cron_expr: str = ""
    fire_at: datetime | None = None
    max_runs: int | None = None
    run_count: int = 0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Check-in name cannot be blank")

        # At least one output mechanism
        has_instructions = bool(self.instructions.strip())
        has_message = bool(self.message.strip())
        if not has_instructions and not has_message:
            raise ValueError("At least one of instructions or message must be set")

        # Exactly one scheduling mechanism
        has_cron = bool(self.cron_expr.strip())
        has_fire_at = self.fire_at is not None
        if has_cron == has_fire_at:
            raise ValueError("Exactly one of cron_expr or fire_at must be set")

        if has_cron:
            parts = self.cron_expr.strip().split()
            if len(parts) != _CRON_FIELD_COUNT:
                raise ValueError(
                    f"Invalid cron expression '{self.cron_expr}': "
                    f"expected {_CRON_FIELD_COUNT} fields, got {len(parts)}"
                )

        if self.max_runs is not None and self.max_runs < 1:
            raise ValueError("max_runs must be >= 1")

    def disable(self) -> None:
        """Prevent this check-in from firing on its next scheduled time."""
        self.enabled = False

    def enable(self) -> None:
        """Resume firing this check-in on its schedule."""
        self.enabled = True

    def increment_run(self) -> None:
        """Record that this check-in has fired once."""
        self.run_count += 1

    def has_reached_max_runs(self) -> bool:
        """Return True if this check-in has fired its maximum allowed times."""
        if self.max_runs is None:
            return False
        return self.run_count >= self.max_runs
