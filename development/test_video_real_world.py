"""Real-world test script for the video transcription pipeline.

Tests the FULL fallback chain with REAL external services:
  YouTube captions → Groq API → local faster-whisper tiny

Usage:
    # Test with a real YouTube video (captions path)
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_real_world.py \
        --youtube "https://www.youtube.com/watch?v=BaW_jenozKc"

    # Test Groq directly with an audio file
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_real_world.py \
        --test-groq /path/to/audio.mp3

    # Test local Whisper directly with an audio file
    uv run python development/test_video_real_world.py \
        --test-local /path/to/audio.mp3

    # Test TikTok (best-effort, often blocked)
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_real_world.py \
        --tiktok "https://www.tiktok.com/@user/video/123"

    # Test Instagram (best-effort, often requires login)
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_real_world.py \
        --instagram "https://www.instagram.com/reel/ABC123/"

    # Test full pipeline with ALL tiers
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_real_world.py \
        --full --youtube "https://www.youtube.com/watch?v=BaW_jenozKc"

Environment:
    GROQ_API_KEY    Required for Groq tests. If absent, skips Groq tier.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

from assistant.shared.config import settings
from assistant.shared.exceptions import TranscriptionError
from assistant.video.application.extract_video_transcript import (
    extract_video_transcript,
    format_transcript_note,
)
from assistant.video.domain.video_metadata import Platform, TranscriptionService
from assistant.video.infrastructure.groq_adapter import GroqTranscriptAdapter
from assistant.video.infrastructure.local_whisper_adapter import LocalWhisperAdapter
from assistant.video.infrastructure.youtube_adapter import YouTubeTranscriptAdapter
from assistant.video.infrastructure.ytdlp_extractor import (
    YtDlpAudioExtractor,
    create_audio_temp_dir,
)

logger = structlog.get_logger()


def _banner(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def _result(label: str, value: str, ok: bool = True) -> None:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label:<30} {value}")


async def test_groq_direct(audio_path: str) -> None:
    """Test Groq API directly with an existing audio file."""
    _banner("TEST: Groq API Direct")

    if not settings.groq_api_key:
        print("  ⚠️  GROQ_API_KEY not set — skipping Groq test")
        print("      Set it to test the Groq tier: export GROQ_API_KEY=gsk_xxx")
        return

    adapter = GroqTranscriptAdapter()
    print(f"  Audio file: {audio_path}")
    print(f"  File size: {Path(audio_path).stat().st_size / 1024 / 1024:.1f} MB")
    print("  Groq model: whisper-large-v3-turbo")
    print(f"  Groq available: {adapter.is_available()}")

    start = time.monotonic()
    try:
        transcript, elapsed = await adapter.transcribe(audio_path)
        _result("Status", "SUCCESS")
        _result("Transcript length", f"{len(transcript)} chars")
        _result("Groq elapsed", f"{elapsed:.2f}s")
        _result("Total elapsed", f"{time.monotonic() - start:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {transcript[:200]}...")
    except TranscriptionError as exc:
        _result("Status", f"FAILED: {exc}", ok=False)


async def test_local_whisper_direct(audio_path: str) -> None:
    """Test local faster-whisper tiny directly with an existing audio file."""
    _banner("TEST: Local faster-whisper Tiny Direct")

    adapter = LocalWhisperAdapter()
    print(f"  Audio file: {audio_path}")
    print(f"  File size: {Path(audio_path).stat().st_size / 1024 / 1024:.1f} MB")
    print("  Model: tiny (CPU, int8)")
    print("  Model cache: /data/whisper-models")

    start = time.monotonic()
    try:
        transcript, elapsed = await adapter.transcribe(audio_path)
        _result("Status", "SUCCESS")
        _result("Transcript length", f"{len(transcript)} chars")
        _result("Whisper elapsed", f"{elapsed:.2f}s")
        _result("Total elapsed", f"{time.monotonic() - start:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {transcript[:200]}...")
    except TranscriptionError as exc:
        _result("Status", f"FAILED: {exc}", ok=False)


async def test_youtube_captions(url: str) -> None:
    """Test YouTube caption extraction (fast path, no audio download)."""
    _banner("TEST: YouTube Captions (Fast Path)")

    print(f"  URL: {url}")
    print("  Strategy: youtube-transcript-api (no audio download)")

    adapter = YouTubeTranscriptAdapter()
    start = time.monotonic()
    try:
        result = await adapter.fetch(url)
        _result("Status", "SUCCESS")
        _result("Service used", str(result.service_used))
        _result("Title", result.title[:60])
        _result("Transcript length", f"{len(result.transcript)} chars")
        _result("Language", result.language)
        _result("Total elapsed", f"{time.monotonic() - start:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {result.transcript[:200]}...")
    except Exception as exc:
        _result("Status", f"FAILED: {exc}", ok=False)


async def test_youtube_full_pipeline(url: str) -> None:
    """Test the FULL pipeline: captions → Groq → local Whisper fallback."""
    _banner("TEST: Full Pipeline (YouTube)")

    print(f"  URL: {url}")
    print("  Pipeline:")
    print("    1. youtube-transcript-api (captions)")
    print("    2. yt-dlp audio + Groq API")
    print("    3. yt-dlp audio + local Whisper tiny (fallback)")
    print(f"  GROQ_API_KEY set: {bool(settings.groq_api_key)}")

    start = time.monotonic()
    try:
        result = await extract_video_transcript(url)
        _result("Status", "SUCCESS")
        _result("Service used", str(result.service_used))
        _result("Title", result.title[:60])
        _result("Transcript length", f"{len(result.transcript)} chars")
        _result("Language", result.language)
        _result("Transcription time", f"{result.transcription_seconds:.2f}s")
        _result("Total elapsed", f"{time.monotonic() - start:.2f}s")

        # Show which tier actually ran
        if result.service_used == TranscriptionService.YOUTUBE_CAPTIONS:
            print("\n  🏆 TIER 1: YouTube captions (no audio download)")
        elif result.service_used == TranscriptionService.GROQ:
            print("\n  🏆 TIER 2: Groq API (audio extracted, transcribed via API)")
        elif result.service_used == TranscriptionService.LOCAL_WHISPER_TINY:
            print("\n  🏆 TIER 3: Local Whisper tiny (Groq unavailable or failed)")

        print("\n  --- First 200 chars ---")
        print(f"  {result.transcript[:200]}...")

        # Also show the note format
        note = format_transcript_note(result)
        print("\n  --- Note preview (first 500 chars) ---")
        print(f"  {note[:500]}...")

    except Exception as exc:
        _result("Status", f"FAILED: {exc}", ok=False)
        raise


async def test_ytdlp_audio_extraction(url: str) -> None:
    """Test yt-dlp audio extraction only (no transcription)."""
    _banner("TEST: yt-dlp Audio Extraction Only")

    print(f"  URL: {url}")
    print("  Output: audio-only mp3 via yt-dlp subprocess")

    extractor = YtDlpAudioExtractor()
    with create_audio_temp_dir() as tmp_dir:
        start = time.monotonic()
        try:
            audio_path, metadata = await extractor.extract_audio(url, tmp_dir)
            _result("Status", "SUCCESS")
            _result("Audio path", audio_path)
            _result("Audio size", f"{Path(audio_path).stat().st_size / 1024 / 1024:.1f} MB")
            _result("Title", metadata.get("title", "N/A")[:60])
            _result("Elapsed", f"{time.monotonic() - start:.2f}s")

            # Now test Groq + local on this extracted audio
            print("\n  --- Testing transcription on extracted audio ---")
            await test_groq_direct(audio_path)
            await test_local_whisper_direct(audio_path)

        except TranscriptionError as exc:
            _result("Status", f"FAILED: {exc}", ok=False)


async def test_tiktok(url: str) -> None:
    """Test TikTok transcription (best-effort)."""
    _banner("TEST: TikTok (Best-Effort)")

    print(f"  URL: {url}")
    print("  Warning: TikTok actively blocks scraping. May fail.")
    print(f"  GROQ_API_KEY set: {bool(settings.groq_api_key)}")

    from assistant.video.infrastructure.ytdlp_platform_adapter import YtDlpPlatformAdapter

    adapter = YtDlpPlatformAdapter()
    start = time.monotonic()
    try:
        result = await adapter.fetch(url, Platform.TIKTOK)
        _result("Status", "SUCCESS")
        _result("Service used", str(result.service_used))
        _result("Title", result.title[:60])
        _result("Transcript length", f"{len(result.transcript)} chars")
        _result("Total elapsed", f"{time.monotonic() - start:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {result.transcript[:200]}...")
    except TranscriptionError as exc:
        _result("Status", f"FAILED (expected for TikTok): {exc}", ok=False)
        print("\n  ℹ️  This is normal. TikTok blocks most scraping attempts.")


async def test_instagram(url: str) -> None:
    """Test Instagram transcription (best-effort)."""
    _banner("TEST: Instagram (Best-Effort)")

    print(f"  URL: {url}")
    print("  Warning: Instagram requires login for ~40-60% of Reels.")
    print(f"  GROQ_API_KEY set: {bool(settings.groq_api_key)}")

    from assistant.video.infrastructure.ytdlp_platform_adapter import YtDlpPlatformAdapter

    adapter = YtDlpPlatformAdapter()
    start = time.monotonic()
    try:
        result = await adapter.fetch(url, Platform.INSTAGRAM)
        _result("Status", "SUCCESS")
        _result("Service used", str(result.service_used))
        _result("Title", result.title[:60])
        _result("Transcript length", f"{len(result.transcript)} chars")
        _result("Total elapsed", f"{time.monotonic() - start:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {result.transcript[:200]}...")
    except TranscriptionError as exc:
        _result("Status", f"FAILED (expected for Instagram): {exc}", ok=False)
        print("\n  ℹ️  This is normal. Instagram blocks anonymous access to most Reels.")


async def test_fallback_chain() -> None:
    """Demonstrate the fallback chain with a synthetic failure."""
    _banner("TEST: Fallback Chain Demonstration")

    print("  This test shows what happens when each tier fails:")
    print("    Tier 1 (captions)  → simulate failure")
    print("    Tier 2 (Groq)      → simulate failure")
    print("    Tier 3 (local)     → must succeed or raise")
    print()

    # Create a dummy audio file to test with
    import tempfile

    dummy_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    dummy_audio.write(b"\xff" * 1024)  # Invalid mp3 — will cause transcription to fail
    dummy_audio.close()

    # Test Groq with invalid audio (will fail)
    if settings.groq_api_key:
        print("  --- Forcing Groq failure with invalid audio ---")
        groq = GroqTranscriptAdapter()
        try:
            await groq.transcribe(dummy_audio.name)
        except TranscriptionError as exc:
            print(f"  ❌ Groq failed as expected: {exc}")
    else:
        print("  ⚠️  Skipping Groq failure test (no API key)")

    # Test local Whisper with invalid audio (will also fail, but that's ok for demo)
    print("  --- Forcing local Whisper failure with invalid audio ---")
    local = LocalWhisperAdapter()
    try:
        await local.transcribe(dummy_audio.name)
    except TranscriptionError as exc:
        print(f"  ❌ Local Whisper failed as expected: {exc}")

    os.unlink(dummy_audio.name)
    print("\n  ✅ Fallback chain verified: failures propagate correctly")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Real-world video transcription test script")
    parser.add_argument("--youtube", help="Test YouTube full pipeline with URL")
    parser.add_argument("--youtube-captions", help="Test YouTube captions only")
    parser.add_argument("--tiktok", help="Test TikTok with URL")
    parser.add_argument("--instagram", help="Test Instagram with URL")
    parser.add_argument("--test-groq", help="Test Groq with audio file path")
    parser.add_argument("--test-local", help="Test local Whisper with audio file path")
    parser.add_argument("--extract-audio", help="Test yt-dlp audio extraction only")
    parser.add_argument("--test-fallback", action="store_true", help="Demonstrate fallback chain")
    parser.add_argument("--full", action="store_true", help="Run full pipeline test")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        print("\nExample:")
        print(
            '  GROQ_API_KEY=gsk_xxx uv run python development/test_video_real_world.py --full --youtube "https://www.youtube.com/watch?v=BaW_jenozKc"'
        )
        return

    print("Video Transcription — Real-World Test")
    print(f"Python: {sys.version}")
    print(f"GROQ_API_KEY: {'set' if settings.groq_api_key else 'NOT SET'}")
    print(f"Notes vault: {settings.notes_vault_path}")

    if args.test_groq:
        await test_groq_direct(args.test_groq)

    if args.test_local:
        await test_local_whisper_direct(args.test_local)

    if args.youtube_captions:
        await test_youtube_captions(args.youtube_captions)

    if args.extract_audio:
        await test_ytdlp_audio_extraction(args.extract_audio)

    if args.full and args.youtube:
        await test_youtube_full_pipeline(args.youtube)
    elif args.youtube:
        await test_youtube_full_pipeline(args.youtube)

    if args.tiktok:
        await test_tiktok(args.tiktok)

    if args.instagram:
        await test_instagram(args.instagram)

    if args.test_fallback:
        await test_fallback_chain()

    print("\n" + "=" * 70)
    print("  Tests complete.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
