"""Tests for system prompt persistence."""

from __future__ import annotations

import pytest

from assistant.conversation.infrastructure.sqlite_repositories import init_db
from assistant.prompts.application.get_system_prompt import get_system_prompt
from assistant.prompts.application.update_system_prompt import update_system_prompt
from assistant.prompts.infrastructure.sqlite_prompt_repository import SQLitePromptRepository


class TestPromptRepository:
    async def test_get_active_returns_default_after_init(
        self, tmp_path: pytest.TempPathFactory
    ) -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        repo = SQLitePromptRepository(db_path)
        prompt = await get_system_prompt(repo)
        assert "TIME AWARENESS" in prompt
        assert "RESPONSE REVIEW" in prompt

    async def test_update_changes_prompt(self, tmp_path: pytest.TempPathFactory) -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        repo = SQLitePromptRepository(db_path)
        await update_system_prompt("You are a pirate", repo)
        prompt = await get_system_prompt(repo)
        assert prompt == "You are a pirate"

    async def test_update_is_persistent(self, tmp_path: pytest.TempPathFactory) -> None:
        db_path = str(tmp_path / "test.db")
        await init_db(db_path)
        repo = SQLitePromptRepository(db_path)
        await update_system_prompt("Be concise", repo)
        # Fresh repository instance reads from same DB
        repo2 = SQLitePromptRepository(db_path)
        prompt = await get_system_prompt(repo2)
        assert prompt == "Be concise"
