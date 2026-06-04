#!/usr/bin/env python3
"""
Instagram transcription flow test — mimics the actual bot pipeline.
RUN THIS FROM INSIDE THE BOT CONTAINER.

What it does:
    1. Detects Instagram platform from URL
    2. Calls the real production use case: extract_video_transcript(url)
    3. yt-dlp extracts audio from Instagram Reel (may fail if login required)
    4. Groq Whisper transcribes (or local Whisper fallback)
    5. Formats the result as a Markdown note
    6. Reports timing, service used, transcript preview

Usage (from host):
    docker cp development/playground/test_instagram_transcription.py deploy-bot-1:/tmp/
    docker exec -it deploy-bot-1 /app/.venv/bin/python3 /tmp/test_instagram_transcription.py "<INSTAGRAM_URL>"

Usage (from inside container):
    /app/.venv/bin/python3 /tmp/test_instagram_transcription.py "<INSTAGRAM_URL>"
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

import structlog

from assistant.shared.config import settings
from assistant.video.application.extract_video_transcript import (
    detect_platform,
    extract_video_transcript,
    format_transcript_note,
)
from assistant.video.domain.video_metadata import Platform, VideoMetadata

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# A known public Instagram Reel — replace with any URL you want to test
_DEFAULT_URL = "https://www.instagram.com/reel/C1xYzAbC2dE/"


def _print_banner() -> None:
    print("=" * 60)
    print("INSTAGRAM TRANSCRIPTION FLOW TEST")
    print("Mimics the actual bot pipeline — no Telegram involved")
    print("=" * 60)


def _print_config() -> None:
    print("\n--- Configuration ---")
    print(f"Node path: {settings.node_path or '(auto-detect)'}")
    print(f"Groq API key: {'set' if settings.groq_api_key else 'NOT SET (will use local Whisper)'}")
    print("Groq model: whisper-large-v3-turbo")
    print("Local Whisper model: tiny")
    print("\nNOTE: Instagram requires login for ~40-60% of public Reels.")
    print("      If extraction fails, try a different Reel or use YouTube.")


def _print_result(metadata: VideoMetadata, total_elapsed: float) -> None:
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Platform:        {metadata.platform}")
    print(f"Service used:    {metadata.service_used}")
    print(f"Title:           {metadata.title}")
    print(f"Upload date:     {metadata.upload_date or 'unknown'}")
    print(f"Transcript len:  {len(metadata.transcript):,} chars")
    print(f"Transcript time: {metadata.transcription_seconds:.1f}s")
    print(f"Total elapsed:   {total_elapsed:.1f}s")
    print(f"Language:        {metadata.language}")
    print("\n--- Transcript ---")
    print(metadata.transcript)


def _print_note(note_content: str) -> None:
    print("\n" + "=" * 60)
    print("FORMATTED NOTE (as would be saved to vault)")
    print("=" * 60)
    print(note_content)


def _print_error(error: Exception) -> None:
    print("\n" + "=" * 60)
    print("ERROR")
    print("=" * 60)
    print(f"Type: {type(error).__name__}")
    print(f"Message: {error}")
    if hasattr(error, "__cause__") and error.__cause__:
        print(f"Caused by: {type(error.__cause__).__name__}: {error.__cause__}")
    print("\n--- Troubleshooting ---")
    print("Instagram frequently requires login for Reels. Try:")
    print("  1. A different Instagram Reel (some are public)")
    print("  2. A YouTube URL instead (most reliable)")
    print("  3. Check if yt-dlp needs an update: yt-dlp --update")


async def _run_test(url: str) -> int:
    """Run the Instagram transcription flow and return exit code."""
    _print_banner()
    print(f"\nURL: {url}")

    _print_config()

    # Step 1: Platform detection
    print("\n--- Step 1: Detecting platform ---")
    platform = detect_platform(url)
    if platform is None:
        print("FAIL: Unsupported URL. Only YouTube, TikTok, and Instagram are supported.")
        return 1
    if platform != Platform.INSTAGRAM:
        print(f"WARNING: URL detected as {platform}, not Instagram. Continuing anyway.")
    print(f"OK: Detected platform = {platform}")

    # Step 2: Extract transcript
    print("\n--- Step 2: Extracting transcript via extract_video_transcript() ---")
    print("This will: download audio → transcribe with Groq/Whisper")
    print("Expected time: 30–120 seconds depending on video length...")
    start = time.monotonic()
    try:
        metadata = await extract_video_transcript(url)
    except Exception as exc:
        _print_error(exc)
        return 1
    total_elapsed = time.monotonic() - start

    # Step 3: Report results
    _print_result(metadata, total_elapsed)

    # Step 4: Format as note
    print("\n--- Step 3: Formatting as Markdown note ---")
    note_content = format_transcript_note(metadata)
    _print_note(note_content)

    print("\n" + "=" * 60)
    print("✅ INSTAGRAM TRANSCRIPTION FLOW TEST PASSED")
    print("=" * 60)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test the Instagram video transcription pipeline inside the container",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=_DEFAULT_URL,
        help="Instagram Reel URL to transcribe",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(_run_test(args.url))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
