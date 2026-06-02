# Phase 1 — Domain Layer

## Goal

Define the value objects and enums that the rest of the feature depends on.

---

## Step 5 — Define VideoMetadata Value Object

**Files to create:**
- `src/assistant/video/__init__.py`
- `src/assistant/video/domain/__init__.py`
- `src/assistant/video/domain/video_metadata.py`

**Content for `video_metadata.py`:**

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Platform(StrEnum):
    """Supported video platforms."""

    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class TranscriptionService(StrEnum):
    """ASR service used for transcription."""

    YOUTUBE_CAPTIONS = "youtube-captions"
    GROQ = "groq"
    LOCAL_WHISPER_TINY = "local-whisper-tiny"


@dataclass(frozen=True)
class VideoMetadata:
    """Immutable snapshot of a transcribed video.

    Created by infrastructure adapters, consumed by application use cases.
    """

    url: str
    platform: Platform
    title: str
    description: str
    upload_date: str | None
    transcript: str
    language: str
    service_used: TranscriptionService
    transcription_seconds: float
```

**Why:** Frozen dataclass = immutable value object per DDD. `StrEnum` for fixed value sets per senior-engineer-python guidelines.

**Verification:**
- [ ] `get_errors()` returns clean
- [ ] `VideoMetadata` instantiates without error
- [ ] `Platform.YOUTUBE == "youtube"` evaluates True

---

## Phase 1 Review

### Requirements Check
- [ ] `VideoMetadata` value object created
- [ ] `Platform` enum created
- [ ] `TranscriptionService` enum created
- [ ] All fields typed, no bare `Any`

### Code Quality (senior-engineer-python)
- [ ] `@dataclass(frozen=True)` for value object
- [ ] `StrEnum` for fixed value sets
- [ ] Docstrings describe behavior, not just restate name
- [ ] All imports at top, grouped properly

### poc-architect Critique
- [ ] Is `platform` a string or enum? → `StrEnum`, validated
- [ ] Should `upload_date` be `datetime` instead of `str`? → `str` is fine; comes from yt-dlp JSON as string
- [ ] Is `transcription_seconds` the right type? → `float` for sub-second precision

### Next Phase
→ [Phase 2 — Infrastructure Layer](phase-2-infrastructure.md)
