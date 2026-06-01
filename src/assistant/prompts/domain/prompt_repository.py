"""Prompt repository interface."""

from __future__ import annotations

from typing import Protocol


class PromptRepository(Protocol):
    """Persistence contract for the active system prompt."""

    async def get_active(self) -> str:
        """Return the current system prompt text."""
        ...

    async def update(self, text: str) -> None:
        """Replace the active system prompt with ``text``."""
        ...
