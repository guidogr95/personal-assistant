# Phase 2 — Infrastructure Layer (Adapters)

## Goal

Build all infrastructure adapters: YouTube captions, yt-dlp audio extraction, Groq ASR, local Whisper fallback.

---

## Step 6 — YouTubeTranscriptAdapter

**Files to create:**
- `src/assistant/video/infrastructure/__init__.py`
- `src/assistant/video/infrastructure/youtube_adapter.py`

**Interface:**
```python
async def fetch(url: str) -> VideoMetadata:
    """Fetch YouTube video metadata and transcript.

    Tries youtube-transcript-api first for captions. Falls back to
    yt-dlp audio extraction + Groq if no captions available.

    Args:
        url: YouTube video URL.

    Returns:
        VideoMetadata with transcript and metadata.

    Raises:
        ValueError: If URL is not a valid YouTube URL.
        TranscriptionError: If transcription fails after all retries.
    """
```

**Implementation notes:**
- `youtube_transcript_api` is synchronous → wrap in `asyncio.to_thread`
- On `NoTranscriptFound`, fall through to audio extraction path
- Use yt-dlp `--skip-download --dump-json` for metadata (title, description, date)
- Set `service_used = TranscriptionService.YOUTUBE_CAPTIONS` on caption path

---

## Step 7 — YtDlpAudioExtractor

**File to create:** `src/assistant/video/infrastructure/ytdlp_extractor.py`

**Interface:**
```python
async def extract_audio(url: str) -> tuple[str, dict[str, Any]]:
    """Extract audio from a video URL using yt-dlp.

    Args:
        url: Video URL (YouTube, TikTok, Instagram).

    Returns:
        Tuple of (audio_file_path, metadata_dict).

    Raises:
        AudioExtractionError: If yt-dlp fails or returns no audio.
    """
```

**Implementation notes:**
- Use `asyncio.create_subprocess_exec` (fully async, no thread pool)
- Arguments: `--format bestaudio --extract-audio --audio-format mp3 --output %(id)s.%(ext)s`
- Output to `tempfile.TemporaryDirectory` (guaranteed cleanup)
- Parse yt-dlp JSON output for metadata

---

## Step 8 — GroqTranscriptAdapter

**File to create:** `src/assistant/video/infrastructure/groq_adapter.py`

**Interface:**
```python
async def transcribe(audio_path: str) -> tuple[str, float]:
    """Transcribe audio file using Groq Whisper API.

    Args:
        audio_path: Path to audio file (mp3, wav, etc.).

    Returns:
        Tuple of (transcript_text, elapsed_seconds).

    Raises:
        TranscriptionError: If Groq API fails.
    """
```

**Implementation notes:**
- Use `AsyncGroq` client
- Model: `whisper-large-v3-turbo`
- Record `transcription_seconds` for metadata
- Check `settings.groq_api_key` at call time; raise if empty

---

## Step 9 — LocalWhisperAdapter

**File to create:** `src/assistant/video/infrastructure/local_whisper_adapter.py`

**Interface:**
```python
async def transcribe(audio_path: str) -> tuple[str, float]:
    """Transcribe audio file using local faster-whisper tiny model.

    Fallback when Groq is unavailable or fails.

    Args:
        audio_path: Path to audio file.

    Returns:
        Tuple of (transcript_text, elapsed_seconds).

    Raises:
        TranscriptionError: If model fails to load or transcribe.
    """
```

**Implementation notes:**
- Load model lazily on first call (module-level singleton)
- Model: `tiny` (39MB weights)
- Call via `asyncio.to_thread` (CPU-bound sync code)
- Model cache dir: `/data/whisper-models` (Docker volume)

---

## Phase 2 Review

### Requirements Check
- [ ] `YouTubeTranscriptAdapter` fetches captions
- [ ] `YtDlpAudioExtractor` extracts audio via subprocess
- [ ] `GroqTranscriptAdapter` calls Groq API
- [ ] `LocalWhisperAdapter` loads tiny model, transcribes via thread
- [ ] All adapters have complete type hints
- [ ] No blocking I/O in async context

### Code Quality (senior-engineer-python)
- [ ] `asyncio.create_subprocess_exec` for yt-dlp (not `subprocess.run`)
- [ ] `asyncio.to_thread` for Whisper (CPU-bound sync code)
- [ ] `TemporaryDirectory` guarantees cleanup on exception
- [ ] Specific exception types (not bare `Exception`)
- [ ] `structlog` with context (url, platform, etc.)
- [ ] No `print()` in production paths

### poc-architect Critique
- [ ] Is `create_subprocess_exec` correct for yt-dlp? → Yes, fully async
- [ ] Is `to_thread` correct for Whisper? → Yes, CPU-bound sync in async context
- [ ] What if yt-dlp subprocess hangs? → Add timeout to `create_subprocess_exec`
- [ ] What if Groq rate limits? → Catch specific exception, fall to local Whisper
- [ ] Is lazy model loading safe? → Yes, module-level singleton with `None` check

### Next Phase
→ [Phase 3 — Application Layer](phase-3-application.md)
