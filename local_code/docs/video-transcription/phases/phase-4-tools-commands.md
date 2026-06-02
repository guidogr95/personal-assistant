# Phase 4 — Agent Tools & Telegram Commands

## Goal

Expose the transcription feature to the agent and as a direct Telegram command.

---

## Step 12 — register_video_tools

**File to create:** `src/assistant/agent/tools/video_tools.py`

**Tools to register:**

### `get_video_transcript`

```python
@agent.tool
async def get_video_transcript(ctx: RunContext[None], url: str) -> str:
    """Queue a video URL for background transcription.

    Supports YouTube, TikTok, and Instagram (public videos only).
    Returns immediately with queue position. A proactive message will
    arrive when transcription is complete.

    YouTube videos with captions are processed in under 5 seconds.
    TikTok and Instagram may take 30–60 seconds due to audio extraction.

    Args:
        url: Full video URL including scheme (https://...).

    Returns:
        Acknowledgment with queue position (e.g. "Queued #1").
    """
```

### `get_transcription_queue_status`

```python
@agent.tool
async def get_transcription_queue_status(ctx: RunContext[None]) -> str:
    """Check the status of the transcription queue.

    Returns:
        Formatted status: running job, pending count, recent history.
    """
```

**Implementation notes:**
- `get_video_transcript` validates URL platform, calls `enqueue()`, returns acknowledgment
- `get_transcription_queue_status` queries `_jobs` dict, formats for LLM consumption
- No `asyncio.create_task` in tool — queue worker is already running

---

## Step 13 — /transcribe Command

**File to create:** `src/assistant/telegram/handlers/video_commands.py`

**Handler:**

```python
from aiogram import Router
from aiogram.types import Message

router = Router()

@router.message(Command("transcribe"))
async def transcribe_command(message: Message) -> None:
    """Handle /transcribe <url> or reply-to-message with URL."""
```

**Behavior:**
- Parse `/transcribe <url>` or extract URL from reply-to-message
- Validate platform (YouTube, TikTok, Instagram)
- Call `enqueue()`, return acknowledgment
- Error if no URL provided or unsupported platform

---

## Step 14 — Wire into main.py

**File to modify:** `src/assistant/main.py`

**Changes:**

1. Import and call `configure_transcription_queue`:
```python
from assistant.video.application.transcription_queue import (
    configure_transcription_queue,
    start_worker,
)

configure_transcription_queue(bot=bot, note_repo=_repo)
```

2. Start worker:
```python
asyncio.create_task(start_worker())
```

3. Register video tools:
```python
from assistant.agent.tools.video_tools import register_video_tools

register_video_tools(agent)
```

4. Include video commands router:
```python
from assistant.telegram.handlers.video_commands import router as video_router

dp.include_router(video_router)
```

5. Add `/transcribe` to bot command menu:
```python
BotCommand(command="transcribe", description="Transcribe a video URL"),
```

---

## Phase 4 Review

### Requirements Check
- [ ] `get_video_transcript` tool returns immediate acknowledgment
- [ ] `get_transcription_queue_status` tool returns accurate status
- [ ] `/transcribe <url>` command works
- [ ] `/transcribe` appears in bot command menu
- [ ] Unknown URL format returns clear error

### Code Quality (senior-engineer-python)
- [ ] Tool functions have complete type hints
- [ ] No `Any` in tool signatures
- [ ] Docstrings describe behavior, preconditions, exceptions
- [ ] Proper import grouping

### poc-architect Critique
- [ ] Does `get_video_transcript` block? → No, returns immediately after enqueue
- [ ] Does the queue worker have access to `bot`? → Yes, injected via `configure_transcription_queue`
- [ ] What if user sends `/transcribe` while transcription is running? → Enqueued, processed sequentially
- [ ] Is the command menu updated? → Yes, `set_my_commands` includes `/transcribe`

### Next Phase
→ [Phase 5 — Tests](phase-5-tests.md)
