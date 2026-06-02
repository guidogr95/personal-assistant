"""YouTube transcript adapter — caption-first, audio-fallback."""

from __future__ import annotations

import asyncio
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


class YouTubeTranscriptAdapter:
    """Fetches transcripts for YouTube videos.

    Strategy:
    1. Try youtube-transcript-api for native captions (~2 seconds).
    2. On NoTranscriptFound, extract audio via yt-dlp and transcribe with Groq.
    3. If Groq is unavailable or fails, fall back to local Whisper tiny.
    """

    def __init__(self) -> None:
        self._groq = GroqTranscriptAdapter()
        self._local_whisper = LocalWhisperAdapter()
        self._ytdlp = YtDlpAudioExtractor()

    async def fetch(self, url: str) -> VideoMetadata:
        """Fetch YouTube video transcript and metadata.

        Args:
            url: YouTube video URL (youtube.com/watch or youtu.be short link).

        Returns:
            VideoMetadata with transcript, title, description, and upload date.

        Raises:
            TranscriptionError: If all transcription paths fail.
        """
        metadata = await self._fetch_yt_metadata(url)

        try:
            transcript, language = await self._fetch_captions(url)
            logger.info("youtube_captions_success", url=url, language=language)
            return VideoMetadata(
                url=url,
                platform=Platform.YOUTUBE,
                title=metadata.get("title", "Unknown"),
                description=metadata.get("description", ""),
                upload_date=metadata.get("upload_date"),
                transcript=transcript,
                language=language,
                service_used=TranscriptionService.YOUTUBE_CAPTIONS,
                transcription_seconds=0.0,
            )
        except _NoTranscriptAvailableError:
            logger.info("youtube_captions_unavailable_falling_back_to_audio", url=url)

        return await self._transcribe_via_audio(url, metadata)

    async def _fetch_captions(self, url: str) -> tuple[str, str]:
        """Fetch captions using youtube-transcript-api.

        Returns:
            Tuple of (transcript_text, language_code).

        Raises:
            _NoTranscriptAvailableError: If no captions exist for this video.
        """
        try:
            transcript_text, language = await asyncio.to_thread(_fetch_captions_sync, url)
        except _NoTranscriptAvailableError:
            raise
        except Exception as exc:
            # Unexpected failure from the transcript API — treat as no captions
            logger.warning(
                "youtube_transcript_api_unexpected_error",
                url=url,
                error=str(exc),
            )
            raise _NoTranscriptAvailableError(str(exc)) from exc
        return transcript_text, language

    async def _fetch_yt_metadata(self, url: str) -> dict[str, Any]:
        """Fetch title, description, upload_date via yt-dlp --dump-json."""
        return await self._ytdlp._fetch_metadata(url)

    async def _transcribe_via_audio(
        self,
        url: str,
        metadata: dict[str, Any],
    ) -> VideoMetadata:
        """Extract audio and transcribe via Groq → local Whisper fallback."""
        with create_audio_temp_dir() as tmp_dir:
            try:
                audio_path, _ = await self._ytdlp.extract_audio(url, tmp_dir)
            except Exception as exc:
                raise TranscriptionError(f"Audio extraction failed for {url}: {exc}") from exc

            transcript, elapsed, service = await self._transcribe_audio(audio_path)

        return VideoMetadata(
            url=url,
            platform=Platform.YOUTUBE,
            title=metadata.get("title", "Unknown"),
            description=metadata.get("description", ""),
            upload_date=metadata.get("upload_date"),
            transcript=transcript,
            language="en",
            service_used=service,
            transcription_seconds=elapsed,
        )

    async def _transcribe_audio(
        self,
        audio_path: str,
    ) -> tuple[str, float, TranscriptionService]:
        """Transcribe audio via Groq, falling back to local Whisper on failure."""
        if self._groq.is_available():
            try:
                transcript, elapsed = await self._groq.transcribe(audio_path)
                return transcript, elapsed, TranscriptionService.GROQ
            except TranscriptionError as exc:
                logger.warning(
                    "groq_transcription_failed_falling_back",
                    audio_path=audio_path,
                    error=str(exc),
                )

        transcript, elapsed = await self._local_whisper.transcribe(audio_path)
        return transcript, elapsed, TranscriptionService.LOCAL_WHISPER_TINY


class _NoTranscriptAvailableError(Exception):
    """Internal signal: no captions exist for this YouTube video."""


def _fetch_captions_sync(url: str) -> tuple[str, str]:
    """Synchronous inner function — called via asyncio.to_thread.

    Prefers English; accepts any language as a fallback.

    Returns:
        Tuple of (joined_transcript_text, language_code).

    Raises:
        _NoTranscriptAvailableError: If no transcript of any kind exists.
    """
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        IpBlocked,
        NoTranscriptFound,
        PoTokenRequired,
        RequestBlocked,
        TranscriptsDisabled,
    )

    video_id = _extract_video_id(url)
    if not video_id:
        raise _NoTranscriptAvailableError(f"Could not extract video ID from: {url}")

    api = YouTubeTranscriptApi()

    # Try English first, then fall back to any available language.
    for languages in (["en"], []):
        try:
            fetched = api.fetch(video_id, languages=languages)
            transcript_text = " ".join(s.text for s in fetched.snippets)
            return transcript_text, fetched.language_code
        except NoTranscriptFound:
            continue
        except TranscriptsDisabled as exc:
            raise _NoTranscriptAvailableError("Transcripts are disabled for this video") from exc
        except (IpBlocked, RequestBlocked, PoTokenRequired) as exc:
            # YouTube is blocking this IP — fall through to audio extraction
            # immediately rather than retrying the caption API.
            raise _NoTranscriptAvailableError(
                f"YouTube blocked captions ({type(exc).__name__}) — "
                "falling back to audio extraction"
            ) from exc

    raise _NoTranscriptAvailableError("No transcript available in any language")


def _extract_video_id(url: str) -> str | None:
    """Extract the YouTube video ID from a watch or short URL."""
    # youtube.com/watch?v=VIDEO_ID
    watch_match = re.search(r"[?&]v=([\w-]{11})", url)
    if watch_match:
        return watch_match.group(1)
    # youtu.be/VIDEO_ID
    short_match = re.search(r"youtu\.be/([\w-]{11})", url)
    if short_match:
        return short_match.group(1)
    return None
