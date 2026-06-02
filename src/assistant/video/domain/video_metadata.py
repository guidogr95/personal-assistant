"""Domain value objects for the video transcript feature."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Platform(StrEnum):
    """Supported video platforms."""

    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class TranscriptionService(StrEnum):
    """ASR service used to produce the transcript."""

    YOUTUBE_CAPTIONS = "youtube-captions"
    GROQ = "groq"
    LOCAL_WHISPER_TINY = "local-whisper-tiny"


@dataclass(frozen=True)
class VideoMetadata:
    """Immutable snapshot of a transcribed video.

    Created by infrastructure adapters and consumed by application use cases.
    All fields are populated before the object is constructed — adapters own
    the assembly; nothing mutates this after creation.
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
