"""Integration tests for video transcription adapters.

These tests verify the real adapter code paths. Tests that hit external
services (YouTube, yt-dlp) may be skipped or may fail with rate-limiting
(HTTP 429) in shared/cloud environments — this is an infrastructure
limitation, not a code bug.

Run selectively with:

    uv run pytest tests/video/test_integration.py -v
"""

from __future__ import annotations

import pytest

from assistant.shared.exceptions import TranscriptionError
from assistant.video.application.extract_video_transcript import (
    detect_platform,
    format_transcript_note,
)
from assistant.video.domain.video_metadata import Platform, TranscriptionService
from assistant.video.infrastructure.ytdlp_extractor import YtDlpAudioExtractor

# Public test video used by the yt-dlp project itself.
_TEST_YOUTUBE_URL = "https://www.youtube.com/watch?v=BaW_jenozKc"


class TestPlatformDetection:
    """Pure logic — no network required."""

    def test_should_detect_youtube_watch_url(self) -> None:
        platform = detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert platform == Platform.YOUTUBE

    def test_should_detect_youtube_short_url(self) -> None:
        platform = detect_platform("https://youtu.be/dQw4w9WgXcQ")
        assert platform == Platform.YOUTUBE

    def test_should_detect_tiktok_url(self) -> None:
        platform = detect_platform("https://www.tiktok.com/@user/video/123456")
        assert platform == Platform.TIKTOK

    def test_should_detect_instagram_url(self) -> None:
        platform = detect_platform("https://www.instagram.com/reel/ABC123/")
        assert platform == Platform.INSTAGRAM

    def test_should_return_none_for_unknown_url(self) -> None:
        assert detect_platform("https://vimeo.com/12345") is None


@pytest.mark.integration
class TestYtDlpMetadataExtraction:
    """Real yt-dlp subprocess call — may 429 in shared environments."""

    async def test_should_fetch_youtube_metadata_or_fail_gracefully(self) -> None:
        extractor = YtDlpAudioExtractor()
        metadata = await extractor._fetch_metadata(_TEST_YOUTUBE_URL)

        # In shared/cloud environments YouTube may return 429.
        # The adapter must NOT crash — empty dict is the graceful fallback.
        if metadata:
            assert "title" in metadata
            assert isinstance(metadata["title"], str)
        else:
            pytest.skip("YouTube rate-limited (HTTP 429) — try again later")


@pytest.mark.integration
class TestYouTubeCaptionExtraction:
    """Real youtube-transcript-api call — may 429 in shared environments."""

    async def test_should_fetch_captions_or_fail_gracefully(self) -> None:
        from assistant.video.application.extract_video_transcript import (
            extract_video_transcript,
        )

        try:
            result = await extract_video_transcript(_TEST_YOUTUBE_URL)
        except TranscriptionError as exc:
            # Rate-limiting or video unavailable — skip, don't fail
            if "429" in str(exc) or "unavailable" in str(exc).lower():
                pytest.skip(f"External service error: {exc}")
            raise

        assert result.platform == Platform.YOUTUBE
        assert result.title != "Unknown"
        assert len(result.transcript) > 50
        assert result.service_used in {
            TranscriptionService.YOUTUBE_CAPTIONS,
            TranscriptionService.GROQ,
            TranscriptionService.LOCAL_WHISPER_TINY,
        }
        assert result.transcription_seconds >= 0.0


class TestNoteFormatting:
    """Pure logic — no network required."""

    def test_should_format_note_with_yaml_frontmatter(self) -> None:
        from assistant.video.domain.video_metadata import VideoMetadata

        metadata = VideoMetadata(
            url=_TEST_YOUTUBE_URL,
            platform=Platform.YOUTUBE,
            title="Test Video",
            description="A description.",
            upload_date="2026-05-15",
            transcript="Hello world.",
            language="en",
            service_used=TranscriptionService.YOUTUBE_CAPTIONS,
            transcription_seconds=1.5,
        )
        note = format_transcript_note(metadata)

        assert note.startswith("---\n")
        assert "url: " in note
        assert "platform: youtube" in note
        assert "service: youtube-captions" in note
        assert "# Transcript: Test Video" in note
        assert "## Transcript" in note
        assert "Hello world." in note
