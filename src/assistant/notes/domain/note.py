"""Note value object — pure Python, no I/O or framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Note:
    """An immutable snapshot of a Markdown note read from the vault.

    ``content`` may be a truncated excerpt when returned by agent-facing use
    cases (the application layer controls the cap, not this object).
    """

    filename: str
    title: str
    content: str
    created_at: datetime
    modified_at: datetime
