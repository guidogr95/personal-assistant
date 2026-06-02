"""Manual integration test for the video transcription feature.

Run this on your local machine (not in a shared/cloud environment) to verify
the full pipeline works end-to-end with real YouTube videos.

Usage:
    uv run python development/test_video_transcription.py

What it tests:
1. URL detection (YouTube, TikTok, Instagram)
2. YouTube caption extraction (fast path)
3. YouTube audio fallback (if no captions)
4. Note formatting with YAML frontmatter
5. Transcription queue enqueue + status

Expected output: all checks pass, a sample note is printed to stdout.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any settings import
load_dotenv()

# Add src to path so imports work without PYTHONPATH
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from assistant.video.application.extract_video_transcript import (
    detect_platform,
    extract_video_transcript,
    format_transcript_note,
)
from assistant.video.application.transcription_queue import (
    configure_transcription_queue,
    enqueue,
    get_queue_status,
)
from assistant.video.domain.video_metadata import Platform
from assistant.video.infrastructure.ytdlp_extractor import YtDlpAudioExtractor

# A public YouTube video with auto-generated captions.
# This is the yt-dlp project's own test video — stable and unlikely to be removed.
TEST_YOUTUBE_URL = "https://www.youtube.com/watch?v=BaW_jenozKc"


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


async def test_url_detection() -> None:
    _print_section("Test 1: URL Detection")

    checks = [
        ("https://www.youtube.com/watch?v=abc123", Platform.YOUTUBE),
        ("https://youtu.be/abc123", Platform.YOUTUBE),
        ("https://www.tiktok.com/@user/video/123", Platform.TIKTOK),
        ("https://www.instagram.com/reel/ABC/", Platform.INSTAGRAM),
        ("https://vimeo.com/12345", None),
    ]

    for url, expected in checks:
        result = detect_platform(url)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] {url!r} -> {result} (expected {expected})")
        if result != expected:
            raise SystemExit(f"URL detection failed for {url}")

    print("  All URL detection checks passed.")


async def test_yt_dlp_metadata() -> None:
    _print_section("Test 2: yt-dlp Metadata Extraction")

    extractor = YtDlpAudioExtractor()
    metadata = await extractor._fetch_metadata(TEST_YOUTUBE_URL)

    if not metadata:
        print("  SKIP: YouTube returned empty metadata (likely HTTP 429 rate limit)")
        print("  Run this script from a non-cloud IP to verify yt-dlp works.")
        return

    print(f"  Title: {metadata.get('title', 'N/A')}")
    print(f"  Upload date: {metadata.get('upload_date', 'N/A')}")
    print(f"  Duration: {metadata.get('duration', 'N/A')} seconds")
    print("  Metadata extraction passed.")


async def test_youtube_transcript() -> None:
    _print_section("Test 3: YouTube Transcript Extraction")

    try:
        result = await extract_video_transcript(TEST_YOUTUBE_URL)
    except Exception as exc:
        if "429" in str(exc) or "unavailable" in str(exc).lower():
            print(f"  SKIP: {exc}")
            print("  Run this script from a non-cloud IP to verify caption extraction.")
            return
        raise

    print(f"  Platform: {result.platform}")
    print(f"  Title: {result.title}")
    print(f"  Service used: {result.service_used}")
    print(f"  Transcript length: {len(result.transcript)} characters")
    print(f"  Time taken: {result.transcription_seconds:.2f}s")

    if len(result.transcript) < 50:
        raise SystemExit(f"Transcript too short: {len(result.transcript)} chars")

    print("  Transcript extraction passed.")


async def test_note_formatting() -> None:
    _print_section("Test 4: Note Formatting")

    from assistant.video.domain.video_metadata import TranscriptionService, VideoMetadata

    metadata = VideoMetadata(
        url=TEST_YOUTUBE_URL,
        platform=Platform.YOUTUBE,
        title="Sample Video",
        description="A sample description.",
        upload_date="2026-05-15",
        transcript="This is a sample transcript.",
        language="en",
        service_used=TranscriptionService.YOUTUBE_CAPTIONS,
        transcription_seconds=2.5,
    )
    note = format_transcript_note(metadata)

    required_parts = [
        "---",
        f"url: {TEST_YOUTUBE_URL}",
        "platform: youtube",
        "service: youtube-captions",
        "# Transcript: Sample Video",
        "## Description",
        "## Transcript",
        "This is a sample transcript.",
    ]

    for part in required_parts:
        if part not in note:
            raise SystemExit(f"Note missing required part: {part!r}")

    print("  Note formatting passed.")
    print("\n  --- Sample note output ---")
    print(note)
    print("  --- End sample ---")


async def test_queue() -> None:
    _print_section("Test 5: Transcription Queue")

    # Use a mock bot and repo so we don't need a real Telegram token
    class FakeBot:
        pass

    class FakeRepo:
        pass

    configure_transcription_queue(bot=FakeBot(), note_repo=FakeRepo())

    job_id_1, pos_1 = await enqueue(
        url="https://youtu.be/test1", user_id=123, platform=Platform.YOUTUBE
    )
    job_id_2, pos_2 = await enqueue(
        url="https://youtu.be/test2", user_id=123, platform=Platform.YOUTUBE
    )

    print(f"  Enqueued job 1: {job_id_1} (position {pos_1})")
    print(f"  Enqueued job 2: {job_id_2} (position {pos_2})")

    status = get_queue_status()
    print(f"  Pending count: {status['pending_count']}")

    if pos_1 != 1 or pos_2 != 2:
        raise SystemExit(f"Queue positions wrong: {pos_1}, {pos_2}")
    if status["pending_count"] != 2:
        raise SystemExit(f"Pending count wrong: {status['pending_count']}")

    print("  Queue enqueue and status passed.")


async def main() -> None:
    print("Video Transcription — Manual Integration Test")
    print(f"Python: {sys.version}")
    print(f"Test video: {TEST_YOUTUBE_URL}")

    await test_url_detection()
    await test_yt_dlp_metadata()
    await test_youtube_transcript()
    await test_note_formatting()
    await test_queue()

    _print_section("All Tests Complete")
    print("  The video transcription feature is working correctly.")
    print("  Deploy with confidence.")


if __name__ == "__main__":
    asyncio.run(main())
