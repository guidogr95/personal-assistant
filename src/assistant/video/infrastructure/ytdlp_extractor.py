"""yt-dlp audio extractor — downloads audio via an async subprocess."""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import structlog

from assistant.shared.config import settings
from assistant.shared.exceptions import AudioExtractionError

logger = structlog.get_logger()

# yt-dlp subprocess timeout: 10 minutes covers large videos while preventing
# an indefinitely hanging process from blocking the worker forever.
_SUBPROCESS_TIMEOUT_SECONDS = 600


def _detect_node_path() -> str | None:
    """Return the absolute path to a node binary, or None if not found."""
    configured = settings.node_path.strip()
    if configured:
        return configured
    found = shutil.which("node")
    return found


def _ytdlp_base_flags() -> list[str]:
    """Build shared yt-dlp flags for bypassing YouTube bot detection.

    Uses the remote EJS challenge solver and a local Node.js runtime to
    solve JavaScript challenges that YouTube serves to bot-flagged IPs.
    """
    flags: list[str] = ["--remote-components", "ejs:github"]
    node_path = _detect_node_path()
    if node_path:
        flags.extend(["--js-runtimes", f"node:{node_path}"])
    return flags


class YtDlpAudioExtractor:
    """Extracts audio-only from a video URL using yt-dlp.

    All output is written to a managed temporary directory so files are always
    cleaned up, even if the caller raises an exception.  Callers must use the
    returned temporary directory as a context manager:

        async with YtDlpAudioExtractor().extract(url) as (path, meta):
            ...  # path is valid here
        # temp dir is deleted here
    """

    async def extract_audio(
        self,
        url: str,
        output_dir: str,
    ) -> tuple[str, dict[str, Any]]:
        """Download a small MP4 with audio from ``url`` into ``output_dir``.

        Uses ``best[ext=mp4][height<=360]/best[ext=mp4]/best`` to get the
        smallest MP4 that contains audio (~5–10MB).  faster-whisper can
        decode audio directly from MP4 — no ffmpeg extraction needed.
        Metadata is fetched in a separate ``--dump-json`` pass to avoid
        mixing JSON output with yt-dlp download progress lines.

        Args:
            url: Video URL (YouTube, TikTok, Instagram, etc.).
            output_dir: Directory to write the audio file to.

        Returns:
            Tuple of (absolute audio file path, metadata dict from yt-dlp).

        Raises:
            AudioExtractionError: If yt-dlp exits non-zero or produces no file.
        """
        audio_path = await self._download_audio(url, output_dir)
        metadata = await self._fetch_metadata(url)
        return audio_path, metadata

    async def _download_audio(self, url: str, output_dir: str) -> str:
        """Run yt-dlp to download a small MP4 and return the output file path."""
        output_template = str(Path(output_dir) / "%(id)s.%(ext)s")
        # Download the smallest MP4 that contains audio (<=360p) so the file is
        # small but still has usable audio for Whisper.  faster-whisper can
        # decode audio directly from MP4 — no ffmpeg extraction needed.
        cmd = [
            "yt-dlp",
            *_ytdlp_base_flags(),
            "--format",
            "best[ext=mp4][height<=360]/best[ext=mp4]/best",
            "--output",
            output_template,
            "--no-playlist",
            "--quiet",
            url,
        ]
        logger.info("ytdlp_audio_download_start", url=url, output_dir=output_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise AudioExtractionError(
                f"yt-dlp timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s for URL: {url}"
            ) from exc

        if proc.returncode != 0:
            error_output = stderr.decode(errors="replace").strip()
            logger.error(
                "ytdlp_audio_download_failed",
                url=url,
                returncode=proc.returncode,
                stderr=error_output[:500],
            )
            raise AudioExtractionError(
                f"yt-dlp exited with code {proc.returncode}: {error_output[:200]}"
            )

        # Find the media file written to output_dir (MP4, WEBM, etc.)
        media_files = list(Path(output_dir).glob("*.*"))
        if not media_files:
            raise AudioExtractionError(f"yt-dlp succeeded but no media file found in {output_dir}")

        media_path = str(media_files[0])
        logger.info("ytdlp_audio_download_complete", url=url, path=media_path)
        return media_path

    async def _fetch_metadata(self, url: str) -> dict[str, Any]:
        """Fetch video metadata (title, description, upload_date) via --dump-json."""
        cmd = [
            "yt-dlp",
            *_ytdlp_base_flags(),
            "--skip-download",
            "--dump-json",
            "--no-playlist",
            "--quiet",
            url,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=60,
            )
        except TimeoutError:
            logger.warning("ytdlp_metadata_timeout", url=url)
            return {}

        if proc.returncode != 0 or not stdout:
            error_output = stderr.decode(errors="replace").strip()
            logger.warning(
                "ytdlp_metadata_failed",
                url=url,
                returncode=proc.returncode,
                stderr=error_output[:200],
            )
            return {}

        try:
            return json.loads(stdout.decode())  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.warning("ytdlp_metadata_parse_failed", url=url)
            return {}


def create_audio_temp_dir() -> tempfile.TemporaryDirectory[str]:
    """Create a managed temporary directory for audio extraction.

    Callers are responsible for entering and exiting the context manager
    to guarantee cleanup regardless of exceptions.
    """
    return tempfile.TemporaryDirectory(prefix="assistant_video_")
