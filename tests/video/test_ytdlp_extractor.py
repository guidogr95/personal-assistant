"""Tests for the yt-dlp audio extractor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from assistant.shared.exceptions import AudioExtractionError
from assistant.video.infrastructure.ytdlp_extractor import YtDlpAudioExtractor

_TEST_DIR = "/dev/shm/assistant_test"  # noqa: S108 — test fixture path


class TestYtDlpAudioExtractor:
    """Audio extraction via yt-dlp subprocess."""

    @pytest.fixture
    def extractor(self) -> YtDlpAudioExtractor:
        return YtDlpAudioExtractor()

    @patch("asyncio.create_subprocess_exec")
    async def test_should_return_audio_path_and_metadata(
        self, mock_exec: MagicMock, extractor: YtDlpAudioExtractor
    ) -> None:
        """Happy path: yt-dlp succeeds and writes an mp3 file."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_proc

        test_path = Path(f"{_TEST_DIR}/test.mp3")
        with patch.object(Path, "glob", return_value=[test_path]):
            audio_path, metadata = await extractor.extract_audio(
                "https://youtu.be/test123", _TEST_DIR
            )

        assert audio_path == str(test_path)
        assert metadata == {}

    @patch("asyncio.create_subprocess_exec")
    async def test_should_raise_on_nonzero_exit(
        self, mock_exec: MagicMock, extractor: YtDlpAudioExtractor
    ) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b"ERROR: Video unavailable"))
        mock_exec.return_value = mock_proc

        with pytest.raises(AudioExtractionError) as exc_info:
            await extractor.extract_audio("https://youtu.be/test123", _TEST_DIR)

        assert "exited with code 1" in str(exc_info.value)
        assert "Video unavailable" in str(exc_info.value)

    @patch("asyncio.create_subprocess_exec")
    async def test_should_raise_on_timeout(
        self, mock_exec: MagicMock, extractor: YtDlpAudioExtractor
    ) -> None:
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError)
        mock_exec.return_value = mock_proc

        with pytest.raises(AudioExtractionError) as exc_info:
            await extractor.extract_audio("https://youtu.be/test123", _TEST_DIR)

        assert "timed out" in str(exc_info.value)

    @patch("asyncio.create_subprocess_exec")
    async def test_should_return_empty_metadata_on_failure(
        self, mock_exec: MagicMock, extractor: YtDlpAudioExtractor
    ) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_exec.return_value = mock_proc

        metadata = await extractor._fetch_metadata("https://youtu.be/test123")
        assert metadata == {}

    @patch("asyncio.create_subprocess_exec")
    async def test_should_parse_json_metadata(
        self, mock_exec: MagicMock, extractor: YtDlpAudioExtractor
    ) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(
                b'{"title": "Test Video", "upload_date": "20260101"}',
                b"",
            )
        )
        mock_exec.return_value = mock_proc

        metadata = await extractor._fetch_metadata("https://youtu.be/test123")
        assert metadata["title"] == "Test Video"
        assert metadata["upload_date"] == "20260101"
