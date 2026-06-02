# API Specification — Video Transcription Tools

## Agent Tools

### `get_video_transcript`

**Signature:**
```python
async def get_video_transcript(ctx: RunContext[None], url: str) -> str
```

**Description:**
Queue a video URL for background transcription. Supports YouTube, TikTok, and Instagram (public videos only). Returns immediately with queue position. A proactive message will arrive when transcription is complete.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `url` | `str` | Yes | Full video URL including scheme (https://...) |

**Returns:**
`str` — Acknowledgment with queue position (e.g. "Queued #1. I'll notify you when the transcript is ready.")

**Error Cases:**
- Invalid URL format → "Invalid URL format. Please provide a valid YouTube, TikTok, or Instagram URL."
- Unsupported platform → "Unsupported platform. Supported: YouTube, TikTok, Instagram."
- Queue full (rare) → "Queue is currently full. Please try again in a moment."

**Examples for LLM:**
```
User: "transcribe this video https://youtube.com/watch?v=abc123"
→ get_video_transcript(url="https://youtube.com/watch?v=abc123")
→ "Queued #1. I'll notify you when the transcript is ready."

User: "take this tiktok and summarize it https://tiktok.com/@user/video/123"
→ get_video_transcript(url="https://tiktok.com/@user/video/123")
→ "Queued #1. I'll notify you when the transcript is ready."
```

---

### `get_transcription_queue_status`

**Signature:**
```python
async def get_transcription_queue_status(ctx: RunContext[None]) -> str
```

**Description:**
Check the status of the transcription queue. Returns running job, pending count, and recent history.

**Returns:**
`str` — Formatted status message:
```
<b>Transcription Queue</b>

<i>Running</i>
youtube.com/... (2m 15s elapsed)

<i>Pending</i>
3 jobs waiting

<i>Recently Completed</i>
✅ tiktok.com/... — saved as 2026-06-01-video-title.md (Groq, 4.2s)
❌ instagram.com/... — login required
```

**Examples for LLM:**
```
User: "is my video done?"
→ get_transcription_queue_status()
→ "Your video is still processing (2m 15s elapsed). 3 jobs ahead of it."
```

---

## Telegram Commands

### `/transcribe <url>`

**Description:**
Directly enqueue a video URL for transcription without LLM round-trip.

**Usage:**
```
/transcribe https://youtube.com/watch?v=abc123
```

**Response:**
Same as `get_video_transcript` tool — immediate acknowledgment.

**Alternative Usage:**
Reply to a message containing a URL with `/transcribe`.

---

## Data Flow

```
User message
  → aiogram handler
    → If /transcribe: call enqueue() directly
    → If natural language: agent.run() → get_video_transcript tool → enqueue()
      → Return acknowledgment immediately
  → Background worker (asyncio.Queue)
    → extract_video_transcript(url)
      → Route to adapter chain
      → Return VideoMetadata
    → save_note(title, content, repo)
      → Save to notes vault
    → bot.send_message(user_id, "Done: filename.md")
```
