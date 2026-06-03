# Session Summary — June 2, 2026

## Original Goal

The session began as a follow-up to the completed 6-phase video transcription implementation. The user asked:

> "Was the tool registered and given an appropriate name, summary, and instructions for use?"

This led to a deep analysis of the Telegram message formatting system, which uncovered systemic issues beyond the video transcription feature.

---

## What Was Built (6 Phases — Completed Before This Session)

### Phase 0 — Bootstrap
- Session race fix: per-user `asyncio.Lock` in `run_turn.py`
- Dependencies: `yt-dlp`, `youtube-transcript-api`, `faster-whisper`, `groq`
- Docker: `ffmpeg`, `nodejs`, `/data/whisper-models` volume

### Phase 1 — Domain
- `VideoMetadata` value object (`@dataclass(frozen=True)`)
- `Platform` and `TranscriptionService` enums

### Phase 2 — Infrastructure (5 adapters)
- `YouTubeTranscriptAdapter` — captions first, audio fallback
- `YtDlpAudioExtractor` — `asyncio.create_subprocess_exec`
- `GroqTranscriptAdapter` — `AsyncGroq.audio.transcriptions.create()`
- `LocalWhisperAdapter` — `faster-whisper` tiny, lazy-loaded singleton
- `YtDlpPlatformAdapter` — TikTok/Instagram routing

### Phase 3 — Application
- `extract_video_transcript()` use case — platform detection, routing
- `TranscriptionQueue` — `asyncio.Queue`, single worker, in-memory status tracking
- `configure_transcription_queue()` injection pattern

### Phase 4 — Tools & Commands
- `register_video_tools()` — `get_video_transcript`, `get_transcription_queue_status`
- `/transcribe` command handler
- Wired into `main.py`

### Phase 5 — Tests
- 34 video-specific tests
- All 191 tests pass

### Phase 6 — Verification
- mypy clean, ruff clean
- Real-world validation on mobile hotspot
- YouTube 429 bypassed with JS challenge solver
- Notes tool duplicate prevention added

---

## What Was Discovered in This Session

### Finding 1: `/tools` Command Crashes with "Message Too Long"

**Symptom:** `TelegramBadRequest: message is too long`

**Root cause:** The `/tools` command asked the LLM to summarize all tools in a single message. As tools grew, the response exceeded Telegram's 4096-character limit.

**Fix implemented:**
- Replaced LLM-based summary with category inline keyboard browser
- `/tools` → shows category buttons (📝 Notes, 🔍 Research, etc.)
- Tap category → shows tools in that category with descriptions
- "📋 Show All" → compact text listing, split if needed
- Added `send_long_text()` utility for safe message splitting

**Files changed:**
- `src/assistant/telegram/handlers/tool_commands.py`
- `src/assistant/telegram/handlers/callbacks.py`
- `src/assistant/telegram/keyboards.py`
- `src/assistant/telegram/formatting.py`
- `tests/telegram/test_tool_commands.py`

### Finding 2: Error Messages Are Too Generic

**Symptom:** User sees "Something went wrong while processing your request. Please try again." for all errors.

**Root cause:** The global error handler mapped all exceptions to the same generic message.

**Fix implemented:**
- `TelegramBadRequest` → forwards Telegram's actual error message
- `AssistantError` subclasses → forwards domain error message
- Unexpected exceptions → generic message + error type hint
- Logs full traceback for unexpected exceptions

**Files changed:**
- `src/assistant/telegram/handlers/errors.py`

### Finding 3: Note Content Renders as Raw Markdown

**Symptom:** When user says "show me note X", they see literal `# heading` and `- item` instead of formatted text.

**Root cause:** The system prompt instructs HTML output. Notes are Markdown files. The LLM includes raw Markdown in its HTML response. Telegram's HTML parser renders `#` as a literal hash character.

**Analysis:** This is a **systemic design issue**, not a bug. The HTML system prompt was a choice that conflicts with Markdown note content.

### Finding 4: Text Sending Is Fragmented

**Discovery:** Six different methods send text to Telegram, none with unified length protection:
- `message.answer(text)` — no parse mode, no length check
- `message.answer(text, parse_mode="HTML")` — HTML, no length check
- `answer_markdown()` — HTML, no length check
- `send_markdown()` — HTML, no length check
- `bot.send_message()` — no parse mode, no length check
- `bot.send_message(..., parse_mode="MarkdownV2")` — different parse mode

**This is the root cause of Finding 1.** No single point of control for message safety.

---

## The Error: Status Quo Bias

When proposing fixes for Finding 3, I initially suggested:
- Complex sentinel-based bypass (`<pre class="note">`)
- LLM cooperation for note display
- Workarounds that preserved the HTML system prompt

**The error:** I treated the existing HTML system prompt as immutable architecture. I proposed complex workarounds instead of questioning whether the original decision (HTML output) was still correct.

**The user correctly identified:** "Why can't we simply CHANGE the system prompt?"

**Lesson learned:** Existing code is not immutable. When a design choice causes friction, evaluate changing the choice before building workarounds. This has been added to the `senior-engineer-python` skill:

> "Existing code is not immutable architecture. When a design choice (parse mode, data format, API style, module structure) is causing friction, evaluate whether changing the choice is simpler than working around it."

---

## The Revised Plan

### Phase 7 — Telegram Formatting Overhaul

**Goal:** Change system prompt to Markdown, add boundary conversion layer, unify all send paths.

**Key decisions:**
1. **System prompt:** HTML → Markdown. LLM produces Markdown. Boundary converts to Telegram HTML.
2. **Unified sender:** Single `send_message()` gateway. All handlers use it. Length protection automatic.
3. **Note display:** No special handling needed. Notes are Markdown. LLM returns Markdown. Boundary converts.
4. **Large messages:** Truncate + "📄 Get full file" inline keyboard button. No message spam.
5. **Callback state:** Hash + module-level dict with 1-hour TTL. Avoids 64-byte callback data limit.

**Full plan:** See `phase-7-telegram-formatting.md`

---

## Decisions Made in This Session

| # | Decision | Context |
|---|----------|---------|
| 1 | Category browser for `/tools` | Replaces LLM summary; scales infinitely; native Telegram UX |
| 2 | Specific error messages | `TelegramBadRequest` and `AssistantError` forwarded; unexpected get type hint |
| 3 | Markdown system prompt | Replaces HTML prompt; notes work natively; one format everywhere |
| 4 | Boundary conversion | Markdown→HTML happens in Telegram layer, not in LLM or tools |
| 5 | Unified sender gateway | All text goes through `send_message()`; length protection automatic |
| 6 | File button for long content | Truncate + inline keyboard; document upload on tap |
| 7 | Hybrid callback state | Short hash in callback data + module dict with TTL |
| 8 | Mapped tag conversion | `<h1>`→`<b>`, `<ul>`→plain text; preserves structure vs. stripping |
| 9 | Context warning (optional) | Token estimate at 80%; non-blocking; informs user |
| 10 | `mistune` for conversion | 50KB, no deps, correct; vs. manual regex or heavier libraries |

---

## Files Modified in This Session

### Implemented Changes
- `src/assistant/telegram/handlers/tool_commands.py` — Category browser
- `src/assistant/telegram/handlers/callbacks.py` — Tool category tap handler
- `src/assistant/telegram/handlers/errors.py` — Specific error messages
- `src/assistant/telegram/keyboards.py` — Tool category keyboards
- `src/assistant/telegram/formatting.py` — `send_long_text()` utility
- `tests/telegram/test_tool_commands.py` — Updated for new tool listing
- `.github/skills/senior-engineer-python/SKILL.md` — Added "question existing assumptions" rule

### Planned Changes (Phase 7)
- `pyproject.toml` — Add `mistune`
- `src/assistant/telegram/markdown_to_html.py` — New converter
- `src/assistant/telegram/formatting.py` — Unified sender, Markdown helpers
- `src/assistant/agent/domain/agent.py` — Markdown system prompt
- `src/assistant/telegram/pending_state.py` — File request state with TTL
- All handler files — Migrate to unified sender
- `tests/telegram/test_markdown_to_html.py` — New tests

---

## Open Questions from This Session

*(none — all resolved through critique loop)*

---

## Next Steps

1. **Implement Phase 7** — Markdown system prompt, unified sender, boundary conversion
2. **Test live messages** — Verify LLM adapts to Markdown prompt; monitor first few responses
3. **Check note sizes** — Validate "most notes are small" assumption against actual vault
4. **Document in ADR** — Record the HTML→Markdown decision with rationale and rejected alternatives
