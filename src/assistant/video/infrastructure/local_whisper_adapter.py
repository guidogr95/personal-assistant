"""Local faster-whisper adapter — CPU-based fallback when Groq is unavailable."""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING

import structlog

from assistant.shared.exceptions import TranscriptionError

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

logger = structlog.get_logger()

_MODEL_SIZE = "tiny"
# Docker volume for model weight caching — survives container restarts.
# Falls back to the default HuggingFace cache dir (~/.cache/huggingface)
# when /data is not writable (e.g. local dev machine).
_DEFAULT_MODEL_CACHE_DIR = "/data/whisper-models"


def _model_cache_dir() -> str | None:
    """Return the model cache directory, or None to use the default."""
    if os.path.isdir(_DEFAULT_MODEL_CACHE_DIR) and os.access(_DEFAULT_MODEL_CACHE_DIR, os.W_OK):
        return _DEFAULT_MODEL_CACHE_DIR
    return None


# Module-level singleton: loaded lazily on first call to avoid ~400MB RAM
# allocation at import time. None until first transcription request.
_whisper_model: WhisperModel | None = None


def _load_model() -> WhisperModel:
    """Load the tiny Whisper model on first call, then return the singleton.

    CPU-only; compute_type="int8" minimises memory consumption on constrained
    hardware (2GB droplet) while maintaining acceptable accuracy.
    """
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel  # noqa: PLC0415 — lazy import by design

        cache_dir = _model_cache_dir()
        logger.info(
            "local_whisper_model_loading",
            model_size=_MODEL_SIZE,
            cache_dir=cache_dir or "default",
        )
        _whisper_model = WhisperModel(
            _MODEL_SIZE,
            device="cpu",
            compute_type="int8",
            download_root=cache_dir,
        )
        logger.info("local_whisper_model_loaded", model_size=_MODEL_SIZE)
    return _whisper_model


def _transcribe_sync(audio_path: str) -> str:
    """Synchronous transcription — called via asyncio.to_thread."""
    model = _load_model()
    segments, _info = model.transcribe(audio_path, beam_size=5)
    return " ".join(segment.text for segment in segments).strip()


class LocalWhisperAdapter:
    """Transcribes audio files using a locally loaded faster-whisper tiny model.

    Intended as a fallback when Groq is unavailable or rate-limited.
    Runs inference via asyncio.to_thread to avoid blocking the event loop.
    """

    @staticmethod
    def model_cache_dir() -> str | None:
        """Return the model cache directory, or None to use the default."""
        return _model_cache_dir()

    async def transcribe(self, audio_path: str) -> tuple[str, float]:
        """Transcribe an audio file using the local Whisper tiny model.

        Args:
            audio_path: Absolute path to an audio file supported by ffmpeg.

        Returns:
            Tuple of (transcript_text, elapsed_seconds).

        Raises:
            TranscriptionError: If the model fails to load or transcribe.
        """
        logger.info("local_whisper_transcription_start", audio_path=audio_path)
        start = time.monotonic()

        try:
            transcript = await asyncio.to_thread(_transcribe_sync, audio_path)
        except Exception as exc:
            logger.error(
                "local_whisper_transcription_failed",
                audio_path=audio_path,
                error=str(exc),
            )
            raise TranscriptionError(f"Local Whisper transcription failed: {exc}") from exc

        elapsed = time.monotonic() - start
        logger.info(
            "local_whisper_transcription_complete",
            audio_path=audio_path,
            transcript_chars=len(transcript),
            elapsed_seconds=round(elapsed, 2),
        )
        return transcript, elapsed
