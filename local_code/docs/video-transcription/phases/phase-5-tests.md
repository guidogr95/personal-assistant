# Phase 5 — Tests

## Goal

Verify all components with unit and integration tests.

---

## Step 15 — Test Suite

**Files to create:**
- `tests/video/__init__.py`
- `tests/video/test_extract_video_transcript.py`
- `tests/video/test_transcription_queue.py`
- `tests/video/test_youtube_adapter.py`
- `tests/video/test_ytdlp_extractor.py`

### Test Categories

#### URL Detection Tests

```python
def test_should_detect_youtube_from_watch_url() -> None:
def test_should_detect_youtube_from_short_url() -> None:
def test_should_detect_tiktok_url() -> None:
def test_should_detect_instagram_url() -> None:
def test_should_reject_unknown_platform() -> None:
```

#### Queue Sequencing Tests

```python
async def test_should_process_jobs_in_fifo_order() -> None:
async def test_should_track_status_transitions() -> None:
async def test_should_evict_completed_jobs_after_24h() -> None:
```

#### Use Case Routing Tests (mocked)

```python
async def test_should_use_youtube_captions_when_available() -> None:
async def test_should_fallback_to_groq_when_no_captions() -> None:
async def test_should_fallback_to_local_whisper_when_groq_fails() -> None:
async def test_should_raise_on_unsupported_platform() -> None:
```

#### Adapter Tests (mocked I/O)

```python
async def test_youtube_adapter_returns_metadata() -> None:
async def test_ytdlp_extractor_calls_subprocess() -> None:
async def test_groq_adapter_returns_transcript() -> None:
async def test_local_whisper_loads_model_lazily() -> None:
```

---

## Phase 5 Review

### Requirements Check
- [ ] All tests pass (`uv run pytest tests/video -q`)
- [ ] URL detection covers all platforms + unknown
- [ ] Queue sequencing verified
- [ ] Fallback chain tested (captions → Groq → local)
- [ ] Status tracking tested

### Code Quality (senior-engineer-python)
- [ ] Tests follow Arrange/Act/Assert
- [ ] Test names follow `test_should_[behaviour]_when_[condition]`
- [ ] Type hints in test functions
- [ ] No `print()` in tests
- [ ] Proper use of `pytest-asyncio`

### poc-architect Critique
- [ ] Are tests mocking I/O boundaries only? → Yes: yt-dlp subprocess, Groq API, filesystem
- [ ] Are domain objects mocked? → No, never mock domain objects
- [ ] Is the fallback chain fully tested? → Yes, all three tiers
- [ ] Are error paths tested? → Yes, unsupported platform, Groq failure, extraction failure

### Next Phase
→ [Phase 6 — Final Verification](phase-6-verification.md)
