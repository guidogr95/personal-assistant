# Phase 4 Implementation Summary

**Status:** Complete  
**Date:** 2026-06-01

---

## Goal

Add a Markdown notes vault so the agent can save, read, search, and list notes. Notes created
via the bot are written to a shared Docker volume that is also watched by Syncthing for
phone/PC sync.

**Acceptance criterion:** Agent can save a note from natural language ("Save a note titled X
with content Y"), the `.md` file appears in `/srv/notes/` inside the bot container, and the
same file is visible in Obsidian on the user's PC.

**Outcome:** ✅ Goal met. Agent creates `.md` files via the `create_note` tool. File appears
immediately at `~/notes/` in WSL (bind-mounted), accessible from Windows at
`\\wsl$\Ubuntu\home\guidogr95\notes`. Live test confirmed: "Save a note titled 'Weekend
ideas'" created `2026-06-01-weekend-ideas.md` with correct H1 heading and content.

---

## What Was Built

### New package: `notes/`

| File | What it contains |
|------|-----------------|
| `notes/__init__.py` | Empty package marker. |
| `notes/domain/__init__.py` | Empty package marker. |
| `notes/domain/note.py` | `Note` — `@dataclass(frozen=True)` value object with `filename`, `title`, `content`, `created_at`, `modified_at`. Pure Python, zero I/O imports. |
| `notes/domain/note_repository.py` | `NoteRepository` — `Protocol` defining `save`, `read`, `search`, `list_all`. No implementation details. |
| `notes/application/__init__.py` | Empty package marker. |
| `notes/application/save_note.py` | `save_note(title, content, repo)` — generates a timestamped slug filename (`YYYY-MM-DD-<slug>.md`), wraps content with an H1 heading, delegates to the repository. |
| `notes/application/read_note.py` | `read_note(filename, repo)` — returns the note or `None`; caps content at `MAX_NOTE_READ_CHARS = 4_000` to protect the LLM context window. |
| `notes/application/find_notes.py` | `find_notes(query, repo)` — returns up to `MAX_SEARCH_RESULTS = 10` matching notes, each capped at 4000 chars. |
| `notes/application/list_notes.py` | `list_notes(repo)` — thin delegation to `repo.list_all()`. |
| `notes/infrastructure/__init__.py` | Empty package marker. |
| `notes/infrastructure/markdown_repository.py` | `MarkdownNoteRepository` — reads/writes `.md` files under `settings.notes_vault_path` using `aiofiles`. Returns full untruncated content; all caps are the application layer's responsibility. Title is extracted from the first H1 heading or humanised from the filename. |

### New file: `agent/tools/notes_tools.py`

| What it contains |
|-----------------|
| `register_notes_tools(agent)` — registers four tools: `create_note`, `search_notes`, `read_note_by_name`, `list_notes_in_vault`. A module-level `_repo = MarkdownNoteRepository()` instance is shared across all tool invocations. |

### Modified: `agent/domain/agent.py`

- Added `from assistant.agent.tools.notes_tools import register_notes_tools`.
- Added `register_notes_tools(agent)` call after `register_research_tools(agent)`.

### Modified: `pyproject.toml`

- Added `types-aiofiles>=23.0` to `[dependency-groups] dev`. Required because `mypy --strict`
  reports `import-untyped` for `aiofiles` without the stubs package.

### Modified: `deploy/docker-compose.override.yml`

Added a `volumes` override that replaces the `notes_data` named volume with a bind mount
pointing to `${HOME}/notes` on the WSL host. This makes notes visible from Windows at
`\\wsl$\Ubuntu\home\guidogr95\notes` without Syncthing being required locally.

### New tests: `tests/notes/`

| File | What it covers |
|------|---------------|
| `tests/notes/__init__.py` | Empty package marker. |
| `tests/notes/test_domain.py` | `Note` value object: field storage, immutability (`FrozenInstanceError`), value equality. |
| `tests/notes/test_use_cases.py` | `MarkdownNoteRepository` (save, read, search, list — full coverage including title extraction, case-insensitive search, no-match empty return, untruncated content from infra layer); `save_note` (timestamped filename, H1 wrap, special-char stripping, 50-char slug cap); `read_note` (cap enforcement, under-cap passthrough, missing note `None`); `find_notes` (result cap, per-note content cap, no-match empty); `list_notes` (all filenames, empty vault). |

---

## Deviations from the Original Plan

| # | Plan said | What actually happened | Reason |
|---|-----------|----------------------|--------|
| 1 | `NoteRepository(ABC)` | `NoteRepository(Protocol)` | Coding standards: prefer `Protocol` for structural interfaces without shared state. No functional difference — `MarkdownNoteRepository` satisfies the Protocol structurally. |
| 2 | `MAX_NOTE_READ_CHARS` and `MAX_SEARCH_RESULTS` defined in `markdown_repository.py` | Moved to `read_note.py` and `find_notes.py` (application layer) | Phase review checklist: content caps and result limits are application-layer concerns, not infrastructure. The repository returns full untruncated data; callers decide what to surface to the LLM. |
| 3 | `types-aiofiles` not listed in dev deps | Added `types-aiofiles>=23.0` | `mypy --strict` (`import-untyped` error) requires the stubs package. Zero impact on production. |
| 4 | `read_note` tool named `read_note` | Named `read_note_by_name` | The use-case function is also called `read_note` (imported at the top of the module). Naming the tool the same would shadow the import at the point `@agent.tool` is applied, causing a `NameError` at runtime. |
| 5 | Named Docker volume `notes_data` in production and dev | Dev: bind mount to `~/notes` via `docker-compose.override.yml` override | Named volume data lives inside the Docker Desktop WSL2 VM and is not directly accessible from Windows. Bind mount exposes notes at a predictable WSL path for immediate Obsidian access without Syncthing. Production `docker-compose.yml` is unchanged — it still uses the named volume + Syncthing for remote VPS deployment. |
| 6 | Test: title fallback = `"2025-01-15-weekend-ideas"` | Actual value = `"2025 01 15 weekend ideas"` | `_extract_title` calls `.replace("-", " ")` on the stem, replacing all hyphens with spaces. The initial test assertion was wrong; corrected to match the actual (correct) implementation. |

---

## Verification Results

| Check | Result |
|-------|--------|
| `uv run mypy src/` | ✅ 0 errors, 59 files |
| `uv run ruff check src/ tests/` | ✅ 0 violations |
| `uv run pytest tests/ -q` | ✅ 56/56 pass |
| Docker image rebuild | ✅ No new dependencies required in the image |
| Bot restart (no rebuild) | ✅ `mcp_servers_connected` confirmed in logs |
| Agent live test — create note | ✅ `2026-06-01-weekend-ideas.md` created with correct content |
| File visible at `~/notes/` | ✅ Confirmed via `docker compose exec bot ls /srv/notes/` and `ls ~/notes/` |
| Bind mount active | ✅ `docker volume inspect` shows `device:/home/guidogr95/notes o:bind` |

---

## Outstanding Items

- **Obsidian vault setup** — Manual step: open Obsidian on Windows, add vault pointing to
  `\\wsl$\Ubuntu\home\guidogr95\notes`. No code change needed.
- **Phone sync** — ✅ Resolved (Phase 6 post-phase). Syncthing on the VPS syncs `notes_data` to Windows. Android setup pending (Phase 7 gate). See phase 6 summary for Syncthing `.stignore` IaC details.
- **Security note** — Notes are plain-text `.md` files. The agent can read and return their full
  content in Telegram messages. Passwords and secrets must not be stored in notes. Use a
  dedicated encrypted vault (e.g. Vaultwarden) for sensitive credentials.
