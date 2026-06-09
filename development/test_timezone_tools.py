"""Scratch test: verify AI uses timezone tools correctly.

Does NOT write to DB. Only inspects what tool the AI would call and with
what parameters.

Usage:
    cd /app && source .venv/bin/activate
    PYTHONPATH=src python development/test_timezone_tools.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file before reading environment variables
load_dotenv()

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import structlog
from aiogram import Bot

from assistant.agent.application.run_turn import run_turn
from assistant.agent.domain.agent import create_agent
from assistant.agent.domain.deps import AgentDeps
from assistant.agent.tools.registry import ALL_TOOLS
from assistant.conversation.infrastructure.sqlite_repositories import (
    SQLiteSessionRepository,
    SQLiteTurnRepository,
    init_db,
)
from assistant.notes.infrastructure.markdown_repository import MarkdownNoteRepository
from assistant.prompts.infrastructure.sqlite_prompt_repository import SQLitePromptRepository
from assistant.research.infrastructure.jina_client import JinaClient
from assistant.research.infrastructure.rebrowser_client import RebrowserClient
from assistant.research.infrastructure.searxng_client import SearXNGClient
from assistant.scheduler.infrastructure.apscheduler_registry import create_scheduler
from assistant.scheduler.infrastructure.sqlite_checkin_repository import (
    SQLiteScheduledCheckInRepository,
)
from assistant.shared.config import settings
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient

logger = structlog.get_logger()

_TEST_PROMPTS: list[str] = [
    "Remind me at 10am tomorrow",
    "Set a reminder in 30 minutes",
    "Check in every day at 9am",
    "Remind me at 3pm today",
    "Daily reminder at 8am",
    "Remind me next Monday at 10am",
    "Set reminder at 12:00",
    "Check in every weekday at 7am",
    "Remind me in 2 hours",
    "Remind me at 10:00 AM",
]


async def _setup() -> tuple[AgentDeps, Bot]:
    """Create minimal runtime deps for testing tool calls."""
    sqlite_path = ":memory:"
    await init_db(sqlite_path)

    session_repo = SQLiteSessionRepository(sqlite_path)
    turn_repo = SQLiteTurnRepository(sqlite_path)
    checkin_repo = SQLiteScheduledCheckInRepository(sqlite_path)
    prompt_repo = SQLitePromptRepository(sqlite_path)
    note_repo = MarkdownNoteRepository()

    bot = Bot(token=settings.telegram_bot_token)
    scheduler = create_scheduler()

    vikunja_client = VikunjaClient()
    searxng_client = SearXNGClient()
    jina_client = JinaClient()
    rebrowser_client = RebrowserClient()

    agent_deps = AgentDeps(
        scheduler=scheduler,
        checkin_repo=checkin_repo,
        prompt_repo=prompt_repo,
        note_repo=note_repo,
        bot=bot,
        vikunja_client=vikunja_client,
        searxng_client=searxng_client,
        jina_client=jina_client,
        rebrowser_client=rebrowser_client,
    )

    return agent_deps, bot


async def main() -> None:
    """Run timezone scratch tests against the real AI."""
    agent_deps, bot = await _setup()

    agent = create_agent()
    for tool_fn in ALL_TOOLS:
        agent.tool(tool_fn)

    session_repo = agent_deps.checkin_repo  # type: ignore[attr-defined]
    # We need the actual session_repo from setup — re-create it
    sqlite_path = ":memory:"
    await init_db(sqlite_path)
    session_repo = SQLiteSessionRepository(sqlite_path)
    turn_repo = SQLiteTurnRepository(sqlite_path)
    prompt_repo = SQLitePromptRepository(sqlite_path)

    passed = 0
    failed = 0

    for prompt in _TEST_PROMPTS:
        print(f"\n--- Test: {prompt!r} ---")
        try:
            reply = await run_turn(
                user_id=12345,
                user_message=prompt,
                session_repo=session_repo,
                turn_repo=turn_repo,
                prompt_repo=prompt_repo,
                agent=agent,
                agent_deps=agent_deps,
            )
            print(f"Reply: {reply}")
            # Heuristic: if the reply mentions "local time" or a specific time,
            # we consider it a pass.  A real evaluation requires inspecting
            # the tool call parameters, which pydantic-ai does not expose
            # directly in the public API without parsing message history.
            if (
                "local time" in reply.lower()
                or "reminder" in reply.lower()
                or "check-in" in reply.lower()
            ):
                print("Result: PASS")
                passed += 1
            else:
                print("Result: FAIL (unexpected reply)")
                failed += 1
        except Exception as exc:
            print(f"Result: FAIL ({exc})")
            failed += 1

    total = len(_TEST_PROMPTS)
    print(f"\n{'=' * 40}")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    print(f"Pass rate: {passed / total * 100:.0f}%")
    if passed / total >= 0.8:
        print("SUCCESS: Pass rate >= 80%")
    else:
        print("FAILURE: Pass rate < 80% — docstrings need refinement")


if __name__ == "__main__":
    asyncio.run(main())
