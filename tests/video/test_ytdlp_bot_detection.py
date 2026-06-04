"""Tests for yt-dlp bot detection heuristics."""

from __future__ import annotations

import pytest

from assistant.video.infrastructure.ytdlp_extractor import is_bot_detection_error


class TestIsBotDetectionError:
    @pytest.mark.parametrize(
        "stderr_text,expected",
        [
            ("Sign in to confirm you're not a bot", True),
            ("Please sign in to confirm you are not a bot", True),
            ("Unable to extract uploader id", True),
            ("HTTP Error 403: Forbidden", True),
            ("Bot detection triggered", True),
            ("Video unavailable", False),
            ("Private video", False),
            ("This video is not available", False),
            ("", False),
        ],
    )
    def test_detects_bot_patterns(self, stderr_text: str, expected: bool) -> None:
        assert is_bot_detection_error(stderr_text) is expected

    def test_case_insensitive(self) -> None:
        assert is_bot_detection_error("SIGN IN TO CONFIRM") is True
        assert is_bot_detection_error("Http Error 403") is True
