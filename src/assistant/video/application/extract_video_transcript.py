"""Use case: extract transcript and metadata from a video URL."""

from __future__ import annotations

import re

import structlog

from assistant.shared.exceptions import UnsupportedPlatformError
from assistant.video.domain.video_metadata import Platform, VideoMetadata
from assistant.video.infrastructure.youtube_adapter import YouTubeTranscriptAdapter
from assistant.video.infrastructure.ytdlp_platform_adapter import YtDlpPlatformAdapter

logger = structlog.get_logger()

_YOUTUBE_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/", re.IGNORECASE)
_TIKTOK_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/", re.IGNORECASE)
_INSTAGRAM_PATTERN = re.compile(r"(?:https?://)?(?:www\.)?instagram\.com/", re.IGNORECASE)

_youtube_adapter = YouTubeTranscriptAdapter()
_platform_adapter = YtDlpPlatformAdapter()


async def extract_video_transcript(url: str) -> VideoMetadata:
    """Extract transcript and metadata from a YouTube, TikTok, or Instagram URL.

    Routes to the correct adapter chain based on URL pattern:
    - YouTube: youtube-transcript-api → yt-dlp + Groq → local Whisper
    - TikTok/Instagram: yt-dlp + Groq → local Whisper

    Args:
        url: Full video URL including scheme (https://...).

    Returns:
        VideoMetadata containing transcript, title, description, and upload date.

    Raises:
        UnsupportedPlatformError: If the URL does not match any supported platform.
        TranscriptionError: If all transcription methods fail.
        AudioExtractionError: If yt-dlp fails to extract audio.
    """
    platform = _detect_platform(url)
    logger.info("extract_video_transcript_start", url=url, platform=platform)

    if platform == Platform.YOUTUBE:
        metadata = await _youtube_adapter.fetch(url)
    else:
        metadata = await _platform_adapter.fetch(url, platform)

    logger.info(
        "extract_video_transcript_complete",
        url=url,
        platform=platform,
        service=metadata.service_used,
        elapsed_seconds=metadata.transcription_seconds,
    )
    return metadata


def detect_platform(url: str) -> Platform | None:
    """Return the Platform for ``url``, or None if unsupported.

    Public helper for callers that need to validate URLs before enqueuing.
    """
    try:
        return _detect_platform(url)
    except UnsupportedPlatformError:
        return None


def _detect_platform(url: str) -> Platform:
    """Return the Platform for ``url``.

    Raises:
        UnsupportedPlatformError: If the URL does not match any known platform.
    """
    if _YOUTUBE_PATTERN.search(url):
        return Platform.YOUTUBE
    if _TIKTOK_PATTERN.search(url):
        return Platform.TIKTOK
    if _INSTAGRAM_PATTERN.search(url):
        return Platform.INSTAGRAM
    raise UnsupportedPlatformError(
        f"URL does not match any supported platform (YouTube, TikTok, Instagram): {url}"
    )


def format_transcript_note(metadata: VideoMetadata) -> str:
    """Format a VideoMetadata into Markdown note content with YAML frontmatter.

    The format is readable by both the notes vault search and the LLM.
    """
    upload_date = metadata.upload_date or "unknown"
    return (
        f"---\n"
        f"url: {metadata.url}\n"
        f"platform: {metadata.platform}\n"
        f"upload_date: {upload_date}\n"
        f"service: {metadata.service_used}\n"
        f"transcription_time_seconds: {metadata.transcription_seconds:.1f}\n"
        f"---\n\n"
        f"# Transcript: {metadata.title}\n\n"
        f"## Description\n\n"
        f"{metadata.description or '_No description available._'}\n\n"
        f"## Transcript\n\n"
        f"{metadata.transcript}\n"
    )
