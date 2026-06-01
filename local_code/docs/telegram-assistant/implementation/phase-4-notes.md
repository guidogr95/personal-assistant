# Phase 4: Markdown Notes + Syncthing

**Goal:** The agent can save, read, search, and list Markdown notes in a synced vault. Notes created via the bot appear on the user's phone and PC within ~30 seconds.  
**Prerequisites:** Phase 3 complete. Syncthing container is already running from Phase 0.  
**Output:** "Save a note: ideas for the weekend" creates a `.md` file; it appears in Obsidian on the phone automatically.

---

## Critique Review

**What could go wrong?**
- Filename collisions from the agent generating the same slug twice: include a timestamp prefix in all filenames
- File write race conditions: unlikely in single-user setup; `aiofiles` async writes are sufficient
- Syncthing not syncing the `/srv/notes/` volume: must verify the Docker volume is the same volume mounted by both `bot` and `syncthing` containers — they must share the `notes_data` named volume
- Search returning too many results: cap at 10 results; return title + first 2 lines of each match
- Note content too large for context window: cap notes read by agent at 4000 characters

**Simplification applied:** No folder hierarchy in Phase 4. All notes go in the root of the vault. Subdirectory organization is a future feature.

---

## Files to Create / Modify

```
src/assistant/
├── notes/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── note.py               (Note value object)
│   │   └── note_repository.py    (NoteRepository interface)
│   ├── application/
│   │   ├── __init__.py
│   │   ├── save_note.py
│   │   ├── read_note.py
│   │   ├── find_notes.py         (grep-based full-text search)
│   │   └── list_notes.py
│   └── infrastructure/
│       ├── __init__.py
│       └── markdown_repository.py
├── agent/
│   └── tools/
│       └── notes_tools.py
```

---

## Step-by-Step Implementation

### Step 1 — Verify shared Docker volume

Both `bot` and `syncthing` must share the same `notes_data` volume. Confirm in `deploy/docker-compose.yml`:

```yaml
services:
  bot:
    volumes:
      - notes_data:/srv/notes    # bot reads/writes here

  syncthing:
    volumes:
      - notes_data:/var/syncthing  # syncthing watches same volume
```

After starting both containers, confirm the volume is shared:
```bash
docker compose exec bot ls /srv/notes/
docker compose exec syncthing ls /var/syncthing/
# Both should show the same directory contents
```

### Step 2 — Configure Syncthing

First run: access Syncthing web UI at `http://localhost:8384` (port exposed in `docker-compose.override.yml` for dev):

1. Add a folder: path `/var/syncthing` (which is the `notes_data` volume)
2. Add your phone as a device (get device ID from Syncthing Android app)
3. Share the folder with the phone
4. On phone: accept the share in Syncthing app; set local folder to `~/notes/`
5. Open Obsidian on phone: add vault → point to `~/notes/`

**Production VPS note:** Expose Syncthing port 22000 publicly for device-to-device sync. Use Nginx to password-protect port 8384 (admin UI should not be public).

### Step 3 — Note Domain Model

```python
# notes/domain/note.py
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Note:
    filename: str        # e.g. "2025-01-15-ideas-for-weekend.md"
    title: str           # extracted from first H1 or filename slug
    content: str         # full Markdown content
    created_at: datetime
    modified_at: datetime
```

### Step 4 — NoteRepository Interface

```python
# notes/domain/note_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional
from assistant.notes.domain.note import Note


class NoteRepository(ABC):
    @abstractmethod
    async def save(self, filename: str, content: str) -> Note: ...

    @abstractmethod
    async def read(self, filename: str) -> Optional[Note]: ...

    @abstractmethod
    async def search(self, query: str) -> List[Note]: ...

    @abstractmethod
    async def list_all(self) -> List[str]: ...  # returns filenames
```

### Step 5 — Markdown Repository (filesystem)

```python
# notes/infrastructure/markdown_repository.py
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import aiofiles
import aiofiles.os
from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository
from assistant.shared.config import settings
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

MAX_NOTE_READ_CHARS = 4_000
MAX_SEARCH_RESULTS = 10


class MarkdownNoteRepository(NoteRepository):
    def __init__(self, vault_path: str = settings.notes_vault_path) -> None:
        self._vault = Path(vault_path)
        self._vault.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content: str) -> Note:
        path = self._vault / filename
        try:
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(content)
        except OSError as e:
            logger.error("note_save_failed", filename=filename, error=str(e))
            raise InfrastructureError(f"Failed to save note {filename}") from e

        stat = await aiofiles.os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        title = self._extract_title(filename, content)
        logger.info("note_saved", filename=filename)
        return Note(filename=filename, title=title, content=content, created_at=ts, modified_at=ts)

    async def read(self, filename: str) -> Optional[Note]:
        path = self._vault / filename
        if not path.exists():
            return None
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        stat = await aiofiles.os.stat(path)
        ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return Note(
            filename=filename,
            title=self._extract_title(filename, content),
            content=content[:MAX_NOTE_READ_CHARS],
            created_at=ts,
            modified_at=ts,
        )

    async def search(self, query: str) -> List[Note]:
        """grep-based full-text search across all .md files."""
        query_lower = query.lower()
        results: List[Note] = []
        for path in sorted(self._vault.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            if query_lower in content.lower():
                stat = path.stat()
                ts = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                results.append(Note(
                    filename=path.name,
                    title=self._extract_title(path.name, content),
                    content=content[:MAX_NOTE_READ_CHARS],
                    created_at=ts,
                    modified_at=ts,
                ))
                if len(results) >= MAX_SEARCH_RESULTS:
                    break
        return results

    async def list_all(self) -> List[str]:
        return sorted(
            [p.name for p in self._vault.glob("*.md")],
            reverse=True,
        )

    @staticmethod
    def _extract_title(filename: str, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return filename.removesuffix(".md").replace("-", " ")
```

### Step 6 — Use Cases

```python
# notes/application/save_note.py
from datetime import datetime, timezone
from assistant.notes.domain.note import Note
from assistant.notes.domain.note_repository import NoteRepository
import re


async def save_note(title: str, content: str, repo: NoteRepository) -> Note:
    """Save a note to the vault with a timestamped filename."""
    date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = re.sub(r"[^\w\s-]", "", title.lower()).strip().replace(" ", "-")[:50]
    filename = f"{date_prefix}-{slug}.md"
    full_content = f"# {title}\n\n{content}\n"
    return await repo.save(filename, full_content)
```

### Step 7 — Notes Tools

```python
# agent/tools/notes_tools.py
from pydantic_ai import Agent, RunContext
from assistant.notes.application.save_note import save_note
from assistant.notes.infrastructure.markdown_repository import MarkdownNoteRepository
import structlog

logger = structlog.get_logger()

_repo = MarkdownNoteRepository()


def register_notes_tools(agent: Agent) -> None:

    @agent.tool
    async def create_note(ctx: RunContext, title: str, content: str) -> str:
        """Create a new Markdown note in the vault.

        Args:
            title: Short descriptive title for the note (becomes the H1 heading and filename).
            content: Note body in Markdown format.
        """
        note = await save_note(title, content, _repo)
        logger.info("create_note_tool", filename=note.filename)
        return f"Note saved: {note.filename}"

    @agent.tool
    async def search_notes(ctx: RunContext, query: str) -> str:
        """Search notes by content.

        Args:
            query: Word or phrase to search for across all notes.
        """
        results = await _repo.search(query)
        if not results:
            return f"No notes found matching '{query}'."
        return "\n\n".join(
            f"**{n.title}** (`{n.filename}`)\n{n.content[:200]}..."
            for n in results
        )

    @agent.tool
    async def read_note(ctx: RunContext, filename: str) -> str:
        """Read the full content of a specific note by filename.

        Args:
            filename: The note filename (e.g. '2025-01-15-my-note.md').
        """
        note = await _repo.read(filename)
        if note is None:
            return f"Note not found: {filename}"
        return note.content

    @agent.tool
    async def list_notes(ctx: RunContext) -> str:
        """List all notes in the vault, newest first."""
        filenames = await _repo.list_all()
        if not filenames:
            return "No notes saved yet."
        return "\n".join(f"- {f}" for f in filenames[:20])
```

---

## Verification

- [ ] Bot creates a note when asked: "Save a note titled 'Weekend ideas' with content: go hiking, read more"
- [ ] The `.md` file appears at `/srv/notes/` inside the bot container
- [ ] The file appears in Syncthing Android app within 30 seconds
- [ ] The file is visible in Obsidian on the phone
- [ ] Editing the file on the phone causes the change to sync back to the VPS (verify with `docker compose exec bot cat /srv/notes/<filename>`)
- [ ] "Search my notes for hiking" returns the weekend ideas note
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create / Modify**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] `Note` is a `@dataclass(frozen=True)` value object — not a raw dict
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] No `except Exception: pass` — filesystem errors caught as `OSError`/`FileNotFoundError` and logged
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No `print()` in production paths — structlog used throughout
- [ ] No secrets in source code or logs
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `notes/` is a **Supporting bounded context** — `Note` is a value object; `NoteRepository` is an interface in the domain layer
- [ ] `notes/domain/note.py` — pure Python dataclass; no aiofiles, no os, no filesystem calls
- [ ] `notes/domain/note_repository.py` — `Protocol` or `ABC` interface; no implementation details
- [ ] `notes/application/` — use cases call repository interface only; no direct `aiofiles` or `os.path` calls
- [ ] `notes/infrastructure/markdown_repository.py` — all filesystem I/O here; implements `NoteRepository`
- [ ] Filenames include a timestamp prefix to prevent collisions
- [ ] Notes read by the agent are capped at 4000 characters (enforced in application layer, not infrastructure)

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What the next phase will build on top of

---

## What Comes Next

**Phase 5** adds Vikunja task management: create, list, and complete tasks via the Vikunja REST API.
