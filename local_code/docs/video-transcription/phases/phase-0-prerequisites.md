# Phase 0 — Prerequisites & Foundation

## Goal

Fix the session race condition and add all new dependencies before building the video module.

---

## Step 1 — Fix Session Race Condition

**File:** `src/assistant/agent/application/run_turn.py` (modify)

**What to change:**

Add at module level:
```python
import asyncio

_user_locks: dict[int, asyncio.Lock] = {}
```

Wrap the body of `run_turn`:
```python
async def run_turn(
    user_id: int,
    user_message: str,
    session_repo: SessionRepository,
    turn_repo: TurnRepository,
    prompt_repo: PromptRepository,
) -> str:
    lock = _user_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        # ... existing body ...
```

**Why:** Without this, concurrent messages corrupt session history. This is a prerequisite for any reliable multi-turn interaction.

**Verification:**
- [ ] `get_errors()` returns clean
- [ ] Two rapid messages in test: both responses arrive, both turns persisted

---

## Step 2 — Add Dependencies

**File:** `pyproject.toml` (modify)

**What to change:**

Add to `[project.dependencies]`:
```toml
dependencies = [
    # ... existing deps ...
    "yt-dlp>=2024.0",
    "youtube-transcript-api>=0.6",
    "faster-whisper>=1.0",
    "groq>=0.9",
]
```

**Why:** Infrastructure adapters need these packages at import time.

**Verification:**
- [ ] `uv sync` resolves without conflicts
- [ ] `uv run python -c "import yt_dlp, youtube_transcript_api, faster_whisper, groq"` succeeds

---

## Step 3 — Add groq_api_key to Settings

**File:** `src/assistant/shared/config.py` (modify)

**What to change:**

Add to `Settings` class:
```python
groq_api_key: str = ""
```

**Why:** Groq adapter needs the API key at runtime. Empty string = optional; tool checks presence.

**Verification:**
- [ ] `get_errors()` returns clean
- [ ] `settings.groq_api_key` accessible without error

---

## Step 4 — Add ffmpeg to Dockerfile

**File:** `Dockerfile` (modify)

**What to change:**

Add `ffmpeg` to the `apt-get install` list:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 ... \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

**Why:** yt-dlp requires ffmpeg for audio extraction/muxing.

**Verification:**
- [ ] `docker build` succeeds
- [ ] `ffmpeg -version` inside container

---

## Phase 0 Review

### Requirements Check
- [ ] Session race fix implemented
- [ ] All 4 new dependencies added
- [ ] `groq_api_key` in Settings
- [ ] `ffmpeg` in Dockerfile

### Code Quality (senior-engineer-python)
- [ ] Type hints on `_user_locks`: `dict[int, asyncio.Lock]`
- [ ] No bare `Any`
- [ ] `structlog` used for any new logging

### poc-architect Critique
- [ ] Does the lock deadlock on exception? → No, `async with` releases on exception
- [ ] Does `uv sync` handle the new deps? → Yes, standard uv behavior
- [ ] Is ffmpeg the only new system package? → Yes, confirmed

### Next Phase
→ [Phase 1 — Domain Layer](phase-1-domain.md)
