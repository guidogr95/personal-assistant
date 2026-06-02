# Phase 3 — Application Layer

## Goal

Build the use case that orchestrates adapters, and the queue + worker that processes jobs sequentially.

---

## Step 10 — extract_video_transcript Use Case

**Files to create:**
- `src/assistant/video/application/__init__.py`
- `src/assistant/video/application/extract_video_transcript.py`

**Interface:**
```python
async def extract_video_transcript(url: str) -> VideoMetadata:
    """Extract transcript and metadata from a video URL.

    Detects platform from URL and routes to the correct adapter chain:
    - YouTube: youtube-transcript-api → yt-dlp + Groq → local Whisper
    - TikTok/Instagram: yt-dlp + Groq → local Whisper

    Args:
        url: Video URL to process.

    Returns:
        VideoMetadata with transcript and metadata.

    Raises:
        UnsupportedPlatformError: If URL does not match a known platform.
        TranscriptionError: If all transcription methods fail.
    """
```

**Implementation notes:**
- Detect platform via regex: `youtube.com|youtu.be`, `tiktok.com`, `instagram.com`
- For YouTube: try `YouTubeTranscriptAdapter` first
- For all platforms without captions: `YtDlpAudioExtractor` → `GroqTranscriptAdapter` → `LocalWhisperAdapter`
- Format result into `VideoMetadata` with YAML frontmatter-ready fields

---

## Step 11 — TranscriptionQueue + Worker

**File to create:** `src/assistant/video/application/transcription_queue.py`

**Data model:**
```python
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
import uuid

class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TranscriptionJob:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str = ""
    platform: Platform = Platform.YOUTUBE
    user_id: int = 0
    status: JobStatus = JobStatus.PENDING
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result_note_filename: str | None = None
```

**Queue interface:**
```python
async def enqueue(url: str, user_id: int) -> str:
    """Add a transcription job to the queue.

    Returns:
        Job ID for status tracking.
    """

async def get_status() -> QueueStatus:
    """Get current queue status.

    Returns:
        QueueStatus with running job, pending count, and recent history.
    """

def configure_transcription_queue(*, bot: Bot, note_repo: NoteRepository) -> None:
    """Inject runtime dependencies. Must be called once at startup."""

async def start_worker() -> None:
    """Start the single-consumer worker coroutine."""
```

**Worker logic:**
```python
async def _worker() -> None:
    while True:
        job = await _queue.get()
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)

        try:
            metadata = await extract_video_transcript(job.url)
            note = await _save_transcript_note(metadata, _note_repo)
            job.result_note_filename = note.filename
            job.status = JobStatus.COMPLETED
            await _bot.send_message(
                chat_id=job.user_id,
                text=f"Transcript ready: {note.filename}",
            )
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            logger.error("transcription_failed", job_id=job.job_id, error=str(e))
            await _bot.send_message(
                chat_id=job.user_id,
                text=f"Transcription failed: {str(e)}",
            )
        finally:
            job.completed_at = datetime.now(UTC)
            _queue.task_done()
```

**Implementation notes:**
- 24-hour eviction for completed jobs (prevent unbounded growth)
- Proactive notification on both success and failure
- `configure_transcription_queue` follows same pattern as `configure_checkin_runner`

---

## Phase 3 Review

### Requirements Check
- [ ] `extract_video_transcript` routes to correct adapter
- [ ] `TranscriptionQueue` enqueues jobs FIFO
- [ ] Single worker processes one job at a time
- [ ] Status tracking works (pending → running → completed/failed)
- [ ] Proactive notification sent on completion
- [ ] Proactive notification sent on failure
- [ ] 24h eviction for completed jobs

### Code Quality (senior-engineer-python)
- [ ] `Enum` for `JobStatus`
- [ ] `QueueStatus` is `TypedDict` or dataclass with complete type hints
- [ ] Worker handles exceptions and sends proactive failure notification
- [ ] No `print()` in production paths
- [ ] `structlog` throughout
- [ ] No boolean trap parameters

### poc-architect Critique
- [ ] Is 24h eviction sufficient? → Yes, user cares about "now" and "just finished"
- [ ] What if worker crashes? → Queue is in-memory; restart = queue lost. Acceptable for personal use.
- [ ] Is `configure_transcription_queue` pattern consistent? → Yes, same as `configure_checkin_runner`
- [ ] Does the worker block on `save_note`? → `save_note` is async I/O, not blocking

### Next Phase
→ [Phase 4 — Agent Tools & Telegram Commands](phase-4-tools-commands.md)
