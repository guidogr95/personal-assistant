# Phase 6 — Final Verification

## Goal

Run all automated checks and manual integration tests to confirm the feature is complete and correct.

---

## Step 16 — Automated Checks

### Type Checking
```bash
uv run mypy src/
```
**Expected:** 0 errors

### Linting
```bash
uv run ruff check src/ tests/
```
**Expected:** 0 violations

### Full Test Suite
```bash
uv run pytest tests/ -q
```
**Expected:** All tests pass

### Docker Build
```bash
docker build -t assistant:test .
```
**Expected:** Build succeeds, ffmpeg available inside container

---

## Step 17 — Manual Integration Test

### Test 1: YouTube with Captions
1. Send a YouTube URL with captions
2. **Verify:** Response arrives in < 5s with "Queued #1"
3. **Verify:** Proactive "Done!" message arrives with note filename
4. **Verify:** Note exists in vault with correct YAML frontmatter

### Test 2: Two URLs Queued Sequentially
1. Send first YouTube URL
2. Immediately send second YouTube URL
3. **Verify:** Both get "Queued #1" and "Queued #2"
4. **Verify:** Both complete, both notify, in order

### Test 3: Normal Message During Transcription
1. Send a YouTube URL (longer video, or force delay)
2. While processing, send "what's the weather"
3. **Verify:** Bot responds to "weather" immediately
4. **Verify:** Transcription still completes and notifies

### Test 4: /transcribe Command
1. Send `/transcribe https://youtube.com/...`
2. **Verify:** Same behavior as agent tool (no LLM round-trip)

### Test 5: Queue Status Tool
1. Send a YouTube URL
2. Ask agent "check transcription status"
3. **Verify:** Status shows running job with elapsed time

### Test 6: Two Messages Rapidly
1. Send "hello"
2. Immediately send "what's 2+2"
3. **Verify:** Both get responses
4. **Verify:** Both turns appear in session history (`/sessions` → resume → check context)

---

## Phase 6 Review

### Requirements Check (All Acceptance Criteria)
- [ ] Two messages rapidly: both responses, no lost turns
- [ ] `get_video_transcript` returns immediate acknowledgment
- [ ] Bot responsive during transcription
- [ ] Multiple URLs processed sequentially
- [ ] YouTube captions: < 5s
- [ ] Fallback chain works (Groq → local Whisper)
- [ ] Note saved with YAML frontmatter
- [ ] Proactive completion message
- [ ] Proactive failure message
- [ ] Temp files cleaned up
- [ ] `get_transcription_queue_status` works
- [ ] `/transcribe` command works
- [ ] Unknown URL returns clear error

### Code Quality (senior-engineer-python)
- [ ] All functions have complete type hints
- [ ] No bare `Any`
- [ ] `Enum` used for fixed value sets
- [ ] `Protocol` for interfaces
- [ ] `@dataclass(frozen=True)` for value objects
- [ ] No `except Exception: pass`
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] `structlog` throughout, no `print()`
- [ ] All imports at top, properly grouped

### poc-architect Final Critique
- [ ] Re-read the plan from scratch — any concerns?
- [ ] Are all decisions still justified?
- [ ] Is there anything not 100% sure about?
- [ ] Does the feature meet the stated goal?
- [ ] Are all acceptance criteria testable and tested?

### Post-Implementation Review Template

Fill this out and save to `review/post-implementation.md`:

```markdown
## Plan vs Implementation

| File | Status | Notes |
|------|--------|-------|
| video/domain/video_metadata.py | ⬜ | |
| video/infrastructure/youtube_adapter.py | ⬜ | |
| video/infrastructure/ytdlp_extractor.py | ⬜ | |
| video/infrastructure/groq_adapter.py | ⬜ | |
| video/infrastructure/local_whisper_adapter.py | ⬜ | |
| video/application/extract_video_transcript.py | ⬜ | |
| video/application/transcription_queue.py | ⬜ | |
| agent/tools/video_tools.py | ⬜ | |
| telegram/handlers/video_commands.py | ⬜ | |
| agent/application/run_turn.py (lock fix) | ⬜ | |
| shared/config.py (groq_api_key) | ⬜ | |
| Dockerfile (ffmpeg) | ⬜ | |
| pyproject.toml (deps) | ⬜ | |

## Deviations from Plan

| # | Plan said | What was built | Reason |
|---|-----------|----------------|--------|
| 1 | | | |

## Test Results

- `uv run mypy src/` → ⬜ errors, ⬜ files
- `uv run ruff check src/ tests/` → ⬜ violations
- `uv run pytest tests/ -q` → ⬜/⬜ pass

## Manual Verification

- ⬜ YouTube with captions: < 5s response
- ⬜ Two URLs queued sequentially
- ⬜ Normal message during transcription: immediate response
- ⬜ Proactive "Done!" message arrives
- ⬜ `/transcribe <url>` command works
- ⬜ `get_transcription_queue_status()` returns accurate status
```

---

## Feature Complete

When all checkboxes above are checked, the feature is done.
