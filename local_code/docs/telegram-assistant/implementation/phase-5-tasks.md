# Phase 5: Task Management via Vikunja

**Goal:** The agent can create, list, and complete tasks in Vikunja. Tasks appear in the Vikunja mobile app and web UI independently of the bot.  
**Prerequisites:** Phase 4 complete. Vikunja Docker container is running from Phase 0.  
**Output:** "Add a task: buy groceries by Friday" → task appears in Vikunja app with due date.

---

## Critique Review

**What could go wrong?**
- Vikunja API token not set up: requires a one-time manual step (create token in Vikunja UI); documented below
- Vikunja container failing to connect to MariaDB: timing issue on first start; use `depends_on` with `service_healthy` in Compose
- Due date parsing: the bot receives natural language ("by Friday"); the LLM must convert this to ISO-8601 before calling the tool; documented in tool docstring
- API token expiry: use a long-lived token (or API token with no expiry); documented below

**Simplification applied:** No project/namespace management in this phase. All tasks go to the default namespace. No subtasks, labels, or priorities. These can be added later.

---

## Files to Create / Modify

```
src/assistant/
├── tasks/
│   ├── __init__.py
│   ├── application/
│   │   ├── __init__.py
│   │   ├── create_task.py
│   │   ├── list_tasks.py
│   │   └── complete_task.py
│   └── infrastructure/
│       ├── __init__.py
│       └── vikunja_client.py
├── agent/
│   └── tools/
│       └── task_tools.py
```

---

## Step-by-Step Implementation

### Step 1 — First-time Vikunja Setup

After Phase 0 brings the stack up:

1. Open Vikunja web UI: `http://localhost:3456` (in dev) or `http://your-vps-ip:3456` (expose port in Compose if needed)
2. Register an admin account (first registration creates admin)
3. Go to **Settings → API Tokens → Create Token** — set expiry to "Never" (or a very long duration)
4. Copy the token → add to `.env` as `VIKUNJA_API_TOKEN=<token>`
5. Note the default project/list ID (usually `1`) — this is where tasks will be created

### Step 2 — Health check for Vikunja in Compose

Add a health check to avoid bot starting before Vikunja's DB is ready:

```yaml
# deploy/docker-compose.yml (vikunja_db section)
  vikunja_db:
    image: mariadb:10
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect"]
      interval: 10s
      timeout: 5s
      retries: 5

  vikunja:
    depends_on:
      vikunja_db:
        condition: service_healthy
```

### Step 3 — Vikunja Client

```python
# tasks/infrastructure/vikunja_client.py
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
import httpx
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

VIKUNJA_TIMEOUT_SECONDS = 15
DEFAULT_PROJECT_ID = 1  # first project created in Vikunja


@dataclass
class VikunjaTask:
    id: int
    title: str
    done: bool
    due_date: Optional[datetime]


class VikunjaClient:
    def __init__(self) -> None:
        self._base_url = settings.vikunja_url
        self._headers = {
            "Authorization": f"Bearer {settings.vikunja_api_token}",
            "Content-Type": "application/json",
        }

    async def create_task(self, title: str, due_date: Optional[str] = None) -> VikunjaTask:
        """Create a task in Vikunja.

        Args:
            title: Task title.
            due_date: Optional ISO-8601 date string (e.g. '2025-01-17T00:00:00Z').
        """
        payload: dict = {"title": title}
        if due_date:
            payload["due_date"] = due_date

        try:
            async with httpx.AsyncClient(timeout=VIKUNJA_TIMEOUT_SECONDS) as client:
                response = await client.put(
                    f"{self._base_url}/api/v1/projects/{DEFAULT_PROJECT_ID}/tasks",
                    json=payload,
                    headers=self._headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("vikunja_create_task_failed", title=title, error=str(e))
            raise InfrastructureError("Failed to create task in Vikunja") from e

        data = response.json()
        logger.info("vikunja_task_created", task_id=data["id"], title=title)
        return VikunjaTask(id=data["id"], title=data["title"], done=data["done"], due_date=None)

    async def list_open_tasks(self) -> List[VikunjaTask]:
        """Fetch all open (not done) tasks."""
        try:
            async with httpx.AsyncClient(timeout=VIKUNJA_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{self._base_url}/api/v1/tasks/all",
                    params={"filter_by": "done", "filter_value": "false", "per_page": "50"},
                    headers=self._headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("vikunja_list_tasks_failed", error=str(e))
            raise InfrastructureError("Failed to list tasks from Vikunja") from e

        tasks = response.json()
        return [
            VikunjaTask(
                id=t["id"],
                title=t["title"],
                done=t["done"],
                due_date=t.get("due_date"),
            )
            for t in tasks
        ]

    async def complete_task(self, task_id: int) -> None:
        """Mark a task as done."""
        try:
            async with httpx.AsyncClient(timeout=VIKUNJA_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self._base_url}/api/v1/tasks/{task_id}",
                    json={"done": True},
                    headers=self._headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("vikunja_complete_task_failed", task_id=task_id, error=str(e))
            raise InfrastructureError(f"Failed to complete task {task_id}") from e

        logger.info("vikunja_task_completed", task_id=task_id)
```

### Step 4 — Use Cases

```python
# tasks/application/create_task.py
from typing import Optional
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient, VikunjaTask

_client = VikunjaClient()


async def create_task(title: str, due_date: Optional[str] = None) -> VikunjaTask:
    """Create a task in Vikunja."""
    return await _client.create_task(title, due_date)
```

```python
# tasks/application/list_tasks.py
from typing import List
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient, VikunjaTask

_client = VikunjaClient()


async def list_open_tasks() -> List[VikunjaTask]:
    return await _client.list_open_tasks()
```

```python
# tasks/application/complete_task.py
from assistant.tasks.infrastructure.vikunja_client import VikunjaClient

_client = VikunjaClient()


async def complete_task(task_id: int) -> None:
    await _client.complete_task(task_id)
```

### Step 5 — Task Tools

```python
# agent/tools/task_tools.py
from typing import Optional
from pydantic_ai import Agent, RunContext
from assistant.tasks.application import create_task, list_tasks, complete_task
import structlog

logger = structlog.get_logger()


def register_task_tools(agent: Agent) -> None:

    @agent.tool
    async def add_task(ctx: RunContext, title: str, due_date: Optional[str] = None) -> str:
        """Create a task in Vikunja.

        Args:
            title: Short, actionable task description.
            due_date: Optional due date in ISO-8601 format (e.g. '2025-01-17T00:00:00Z').
                      Convert natural language dates to ISO-8601 before calling this tool.
        """
        task = await create_task.create_task(title, due_date)
        logger.info("add_task_tool", task_id=task.id)
        due_str = f" (due: {due_date})" if due_date else ""
        return f"Task created: '{task.title}'{due_str} (ID: {task.id})"

    @agent.tool
    async def get_open_tasks(ctx: RunContext) -> str:
        """List all open (incomplete) tasks from Vikunja."""
        tasks = await list_tasks.list_open_tasks()
        if not tasks:
            return "No open tasks."
        lines = [f"- [{t.id}] {t.title}" for t in tasks]
        return "\n".join(lines)

    @agent.tool
    async def mark_task_done(ctx: RunContext, task_id: int) -> str:
        """Mark a task as complete by its ID.

        Use get_open_tasks first to find the task ID if you don't have it.

        Args:
            task_id: The integer task ID from Vikunja.
        """
        await complete_task.complete_task(task_id)
        return f"Task {task_id} marked as done."
```

---

## Verification

- [ ] Vikunja web UI accessible and admin account created
- [ ] `VIKUNJA_API_TOKEN` set in `.env`
- [ ] Bot creates a task: "Add a task: buy groceries" → task appears in Vikunja web UI
- [ ] "What are my open tasks?" returns the task list from Vikunja
- [ ] "Mark task 1 as done" marks it complete in Vikunja UI
- [ ] Bot handles Vikunja being unreachable with a clear error message (not a crash)
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create / Modify**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values (e.g. `due_date: Optional[datetime]`)
- [ ] No `except Exception: pass` — Vikunja HTTP errors caught as `httpx.HTTPStatusError` or `httpx.RequestError` and logged
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No `print()` in production paths — structlog used throughout
- [ ] `VIKUNJA_API_TOKEN` never logged
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `tasks/` is a **Generic subdomain** — application use cases + infrastructure client only; no domain entities or repository interfaces
- [ ] `tasks/infrastructure/vikunja_client.py` — all HTTP calls here; no business logic; raises `InfrastructureError` on failure
- [ ] `tasks/application/` — use cases call `vikunja_client` only; no raw httpx in use case files
- [ ] `agent/tools/task_tools.py` — calls use cases only; tool docstrings document that due dates must be ISO-8601
- [ ] Vikunja being unreachable returns a user-facing error message — bot does not crash

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 6** adds proactive check-ins (APScheduler) and the session management Telegram UX (`/sessions`, session title generation, inline keyboard).
