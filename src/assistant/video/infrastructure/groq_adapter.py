"""Groq Whisper API adapter for audio transcription."""

from __future__ import annotations

import time
from pathlib import Path

import structlog
from groq import APIError as GroqAPIError
from groq import APIStatusError as GroqAPIStatusError
from groq import AsyncGroq

from assistant.shared.config import settings
from assistant.shared.exceptions import TranscriptionError

logger = structlog.get_logger()

_GROQ_MODEL = "whisper-large-v3-turbo"
# Groq's file size limit for audio uploads
_MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class GroqTranscriptAdapter:
    """Transcribes audio files using the Groq Whisper API.

    Falls through to LocalWhisperAdapter when the Groq key is absent or the
    API call fails — callers are responsible for that fallback logic.
    """

    def is_available(self) -> bool:
        """Return True if a Groq API key is configured."""
        return bool(settings.groq_api_key)

    async def transcribe(self, audio_path: str) -> tuple[str, float]:
        """Transcribe an audio file via Groq's Whisper API.

        Args:
            audio_path: Absolute path to an mp3 (or other supported) audio file.

        Returns:
            Tuple of (transcript_text, elapsed_seconds).

        Raises:
            TranscriptionError: If the Groq API rejects the request or returns
                an error. Does NOT raise if the key is absent — check
                ``is_available()`` before calling.
        """
        if not settings.groq_api_key:
            raise TranscriptionError(
                "Groq API key is not configured; cannot transcribe via Groq"
            )

        path = Path(audio_path)
        file_size = path.stat().st_size
        if file_size > _MAX_AUDIO_SIZE_BYTES:
            raise TranscriptionError(
                f"Audio file {path.name} is {file_size // (1024 * 1024)}MB, "
                f"exceeding Groq's {_MAX_AUDIO_SIZE_BYTES // (1024 * 1024)}MB limit"
            )

        logger.info(
            "groq_transcription_start",
            audio_path=str(path),
            size_bytes=file_size,
            model=_GROQ_MODEL,
        )

        start = time.monotonic()
        try:
            client = AsyncGroq(api_key=settings.groq_api_key)
            async with client:
                with path.open("rb") as audio_file:
                    response = await client.audio.transcriptions.create(
                        file=(path.name, audio_file),
                        model=_GROQ_MODEL,
                    )
        except GroqAPIStatusError as exc:
            logger.error(
                "groq_api_status_error",
                audio_path=str(path),
                status_code=exc.status_code,
                message=str(exc.message),
            )
            raise TranscriptionError(
                f"Groq API returned HTTP {exc.status_code}: {exc.message}"
            ) from exc
        except GroqAPIError as exc:
            logger.error(
                "groq_api_error",
                audio_path=str(path),
                error=str(exc),
            )
            raise TranscriptionError(f"Groq API error: {exc}") from exc

        elapsed = time.monotonic() - start
        transcript = response.text.strip()
        logger.info(
            "groq_transcription_complete",
            audio_path=str(path),
            transcript_chars=len(transcript),
            elapsed_seconds=round(elapsed, 2),
        )
        return transcript, elapsed
