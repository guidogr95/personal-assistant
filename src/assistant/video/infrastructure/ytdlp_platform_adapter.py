"""yt-dlp adapter for TikTok and Instagram — audio extraction + ASR."""

from __future__ import annotations

import re
from typing import Any

import structlog

from assistant.shared.exceptions import TranscriptionError
from assistant.video.domain.video_metadata import (
    Platform,
    TranscriptionService,
    VideoMetadata,
)
from assistant.video.infrastructure.groq_adapter import GroqTranscriptAdapter
from assistant.video.infrastructure.local_whisper_adapter import LocalWhisperAdapter
from assistant.video.infrastructure.ytdlp_extractor import (
    YtDlpAudioExtractor,
    create_audio_temp_dir,
)

logger = structlog.get_logger()

_TIKTOK_ERROR_PATTERNS = [
    re.compile(r"login", re.IGNORECASE),
    re.compile(r"private", re.IGNORECASE),
]
_INSTAGRAM_ERROR_PATTERNS = [
    re.compile(r"login", re.IGNORECASE),
    re.compile(r"not available", re.IGNORECASE),
]


class YtDlpPlatformAdapter:
    """Transcribes TikTok and Instagram videos via yt-dlp audio extraction.

    Both platforms have unreliable public access:
    - TikTok: yt-dlp extractor works but may break after platform updates.
    - Instagram: requires login for ~40–60% of public Reels (2026 state).

    Platform-specific error messages guide the user when access is blocked.
    """

    def __init__(self) -> None:
        self._groq = GroqTranscriptAdapter()
        self._local_whisper = LocalWhisperAdapter()
        self._ytdlp = YtDlpAudioExtractor()

    async def fetch(self, url: str, platform: Platform) -> VideoMetadata:
        """Extract audio from a TikTok or Instagram URL and transcribe it.

        Args:
            url: Full video URL.
            platform: Platform enum value for the URL.

        Returns:
            VideoMetadata with transcript and best-effort metadata.

        Raises:
            TranscriptionError: If audio extraction or transcription fails.
                The error message includes platform-specific guidance.
        """
        with create_audio_temp_dir() as tmp_dir:
            try:
                audio_path, raw_metadata = await self._ytdlp.extract_audio(url, tmp_dir)
            except Exception as exc:
                friendly_error = self._platform_error_message(platform, str(exc))
                raise TranscriptionError(friendly_error) from exc

            transcript, elapsed, service = await self._transcribe_audio(audio_path, platform)

        # Language is not available from yt-dlp metadata; Whisper detects it
        # during transcription but we don't capture it here.  "en" is a safe
        # default for the majority of content; the transcript itself is what
        # matters for downstream use.
        return VideoMetadata(
            url=url,
            platform=platform,
            title=self._extract_title(raw_metadata),
            description=raw_metadata.get("description", ""),
            upload_date=raw_metadata.get("upload_date"),
            transcript=transcript,
            language="en",
            service_used=service,
            transcription_seconds=elapsed,
        )

    async def _transcribe_audio(
        self,
        audio_path: str,
        platform: Platform,
    ) -> tuple[str, float, TranscriptionService]:
        """Transcribe audio via Groq, falling back to local Whisper on failure."""
        if self._groq.is_available():
            try:
                transcript, elapsed = await self._groq.transcribe(audio_path)
                return transcript, elapsed, TranscriptionService.GROQ
            except TranscriptionError as exc:
                logger.warning(
                    "groq_transcription_failed_falling_back",
                    platform=platform,
                    audio_path=audio_path,
                    error=str(exc),
                )

        transcript, elapsed = await self._local_whisper.transcribe(audio_path)
        return transcript, elapsed, TranscriptionService.LOCAL_WHISPER_TINY

    def _platform_error_message(self, platform: Platform, raw_error: str) -> str:
        """Return a user-friendly error message based on platform and raw yt-dlp error."""
        if platform == Platform.TIKTOK:
            if any(p.search(raw_error) for p in _TIKTOK_ERROR_PATTERNS):
                return (
                    "TikTok blocked access to this video — it may be private or "
                    "TikTok's anti-scraping has changed. Try a YouTube link instead."
                )
            return (
                f"TikTok audio extraction failed. This may be a temporary yt-dlp "
                f"compatibility issue. Error: {raw_error[:200]}"
            )
        if platform == Platform.INSTAGRAM:
            if any(p.search(raw_error) for p in _INSTAGRAM_ERROR_PATTERNS):
                return (
                    "Instagram requires a login to access this content. "
                    "Only fully public posts without login prompts are supported."
                )
            return f"Instagram audio extraction failed. Error: {raw_error[:200]}"
        return f"Audio extraction failed for {platform}: {raw_error[:200]}"

    def _extract_title(self, metadata: dict[str, Any]) -> str:
        """Extract best-available title from yt-dlp metadata."""
        return metadata.get("title") or metadata.get("description", "")[:80] or "Unknown"
