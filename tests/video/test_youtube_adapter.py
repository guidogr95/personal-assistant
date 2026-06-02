"""Tests for the YouTube transcript adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from assistant.video.domain.video_metadata import Platform, TranscriptionService, VideoMetadata
from assistant.video.infrastructure.youtube_adapter import (
    YouTubeTranscriptAdapter,
    _extract_video_id,
    _fetch_captions_sync,
)


class TestExtractVideoId:
    """YouTube URL parsing."""

    def test_should_extract_from_watch_url(self) -> None:
        assert _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_should_extract_from_short_url(self) -> None:
        assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_should_return_none_for_invalid_url(self) -> None:
        assert _extract_video_id("https://example.com") is None


class TestFetchCaptionsSync:
    """Caption fetching via youtube-transcript-api."""

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_should_return_transcript_and_language(self, mock_api_class: MagicMock) -> None:
        mock_fetched = MagicMock()
        mock_fetched.snippets = [
            MagicMock(text="Hello world"),
            MagicMock(text="This is a test"),
        ]
        mock_fetched.language_code = "en"

        mock_api = MagicMock()
        mock_api.fetch.return_value = mock_fetched
        mock_api_class.return_value = mock_api

        text, lang = _fetch_captions_sync("https://youtu.be/dQw4w9WgXcQ")
        assert text == "Hello world This is a test"
        assert lang == "en"

    @patch("youtube_transcript_api.YouTubeTranscriptApi")
    def test_should_raise_no_transcript_when_disabled(self, mock_api_class: MagicMock) -> None:
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api = MagicMock()
        mock_api.fetch.side_effect = TranscriptsDisabled("dQw4w9WgXcQ")
        mock_api_class.return_value = mock_api

        with pytest.raises(Exception) as exc_info:
            _fetch_captions_sync("https://youtu.be/dQw4w9WgXcQ")
        assert "disabled" in str(exc_info.value).lower()


class TestYouTubeTranscriptAdapterFetch:
    """Integration of caption path and audio fallback."""

    @pytest.fixture
    def adapter(self) -> YouTubeTranscriptAdapter:
        return YouTubeTranscriptAdapter()

    @patch.object(YouTubeTranscriptAdapter, "_fetch_captions")
    async def test_should_use_captions_when_available(self, mock_fetch_captions: MagicMock) -> None:
        mock_fetch_captions.return_value = ("Hello world", "en")

        adapter = YouTubeTranscriptAdapter()
        with patch.object(
            adapter,
            "_fetch_yt_metadata",
            return_value={
                "title": "Test Video",
                "description": "A test",
                "upload_date": "2026-05-01",
            },
        ):
            result = await adapter.fetch("https://youtu.be/test123")

        assert isinstance(result, VideoMetadata)
        assert result.transcript == "Hello world"
        assert result.service_used == TranscriptionService.YOUTUBE_CAPTIONS
        assert result.platform == Platform.YOUTUBE

    @patch.object(YouTubeTranscriptAdapter, "_fetch_captions")
    async def test_should_fallback_to_audio_when_no_captions(
        self, mock_fetch_captions: MagicMock
    ) -> None:
        from assistant.video.infrastructure.youtube_adapter import _NoTranscriptAvailableError

        mock_fetch_captions.side_effect = _NoTranscriptAvailableError("no captions")

        adapter = YouTubeTranscriptAdapter()
        with patch.object(
            adapter,
            "_fetch_yt_metadata",
            return_value={
                "title": "Test Video",
                "description": "A test",
                "upload_date": "2026-05-01",
            },
        ):
            with patch.object(
                adapter,
                "_transcribe_via_audio",
                return_value=VideoMetadata(
                    url="https://youtu.be/test123",
                    platform=Platform.YOUTUBE,
                    title="Test Video",
                    description="A test",
                    upload_date="2026-05-01",
                    transcript="Audio transcript",
                    language="en",
                    service_used=TranscriptionService.GROQ,
                    transcription_seconds=3.0,
                ),
            ):
                result = await adapter.fetch("https://youtu.be/test123")

        assert result.service_used == TranscriptionService.GROQ
        assert result.transcript == "Audio transcript"
