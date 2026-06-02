# Getting Started

## Prerequisites

- Docker and Docker Compose installed
- Telegram bot token configured in `.env`
- Groq API key (optional but recommended) — get one at [groq.com](https://groq.com)

## Local Development

### 1. Add Groq API Key

```bash
# .env
groq_api_key="gsk_..."
```

Without this, the system falls back to local Whisper (slower, lower accuracy).

### 2. Install Dependencies

```bash
uv sync
```

### 3. Run Type Checks

```bash
uv run mypy src/
```

### 4. Run Tests

```bash
uv run pytest tests/video -q
```

### 5. Start the Bot

```bash
uv run python -m assistant.main
```

## Docker Deployment

### 1. Build Image

```bash
docker build -t assistant:latest .
```

### 2. Verify ffmpeg

```bash
docker run --rm assistant:latest ffmpeg -version
```

### 3. Deploy

```bash
docker compose up -d
```

## Testing the Feature

### Test 1: YouTube with Captions

Send to your bot:
```
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Expected: "Queued #1. I'll notify you when the transcript is ready." (< 5s)

### Test 2: Queue Status

Send:
```
check transcription status
```

Expected: Shows running job with elapsed time.

### Test 3: Direct Command

Send:
```
/transcribe https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Expected: Same as Test 1, no LLM round-trip.

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "ffmpeg not found" | Missing system package | Add `ffmpeg` to Dockerfile `apt-get install` |
| "Groq API key missing" | Key not set | Add `groq_api_key` to `.env` |
| "Transcription failed: platform blocked" | TikTok/Instagram anti-scraping | Retry later or use YouTube |
| "Queue lost on restart" | In-memory queue | Re-request transcription |
| "OOM during transcription" | RAM exhausted | Ensure only 1 worker; check `tiny` model is used |
