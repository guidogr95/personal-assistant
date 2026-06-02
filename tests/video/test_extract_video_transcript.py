"""Tests for the extract_video_transcript use case and URL detection."""

from __future__ import annotations

import pytest

from assistant.shared.exceptions import UnsupportedPlatformError
from assistant.video.application.extract_video_transcript import (
    _detect_platform,
    detect_platform,
    format_transcript_note,
)
from assistant.video.domain.video_metadata import Platform, TranscriptionService, VideoMetadata


class TestDetectPlatform:
    """URL detection for supported and unsupported platforms."""

    def test_should_detect_youtube_from_watch_url(self) -> None:
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert _detect_platform(url) == Platform.YOUTUBE

    def test_should_detect_youtube_from_short_url(self) -> None:
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert _detect_platform(url) == Platform.YOUTUBE

    def test_should_detect_tiktok_url(self) -> None:
        url = "https://www.tiktok.com/@user/video/1234567890"
        assert _detect_platform(url) == Platform.TIKTOK

    def test_should_detect_instagram_url(self) -> None:
        url = "https://www.instagram.com/reel/ABC123/"
        assert _detect_platform(url) == Platform.INSTAGRAM

    def test_should_reject_unknown_platform(self) -> None:
        with pytest.raises(UnsupportedPlatformError):
            _detect_platform("https://vimeo.com/12345")

    def test_should_return_none_for_unknown_platform(self) -> None:
        assert detect_platform("https://vimeo.com/12345") is None


class TestFormatTranscriptNote:
    """Note formatting with YAML frontmatter."""

    def test_should_include_yaml_frontmatter(self) -> None:
        metadata = VideoMetadata(
            url="https://youtu.be/test",
            platform=Platform.YOUTUBE,
            title="Test Video",
            description="A test description.",
            upload_date="2026-05-15",
            transcript="Hello world.",
            language="en",
            service_used=TranscriptionService.YOUTUBE_CAPTIONS,
            transcription_seconds=2.5,
        )
        note = format_transcript_note(metadata)
        assert "---" in note
        assert "url: https://youtu.be/test" in note
        assert "platform: youtube" in note
        assert "upload_date: 2026-05-15" in note
        assert "service: youtube-captions" in note
        assert "transcription_time_seconds: 2.5" in note
        assert "# Transcript: Test Video" in note
        assert "## Description" in note
        assert "A test description." in note
        assert "## Transcript" in note
        assert "Hello world." in note

    def test_should_handle_missing_upload_date(self) -> None:
        metadata = VideoMetadata(
            url="https://youtu.be/test",
            platform=Platform.YOUTUBE,
            title="Test Video",
            description="",
            upload_date=None,
            transcript="Hello.",
            language="en",
            service_used=TranscriptionService.GROQ,
            transcription_seconds=5.0,
        )
        note = format_transcript_note(metadata)
        assert "upload_date: unknown" in note
