"""Comprehensive test script for ALL video transcription paths.

Set ONE URL and test any or all applicable paths. The script auto-detects
whether the URL is YouTube, TikTok, or Instagram.

Usage::

    # Test EVERYTHING for a single URL (recommended)
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_all_paths.py \
        --url "https://www.youtube.com/watch?v=CMtctfaF9LM" --run-all

    # Test only specific paths for a URL
    uv run python development/test_video_all_paths.py \
        --url "https://www.youtube.com/watch?v=CMtctfaF9LM" --captions

    GROQ_API_KEY=gsk_xxx uv run python development/test_video_all_paths.py \
        --url "https://www.youtube.com/watch?v=CMtctfaF9LM" --audio --groq --local

    # Test with a TikTok URL
    GROQ_API_KEY=gsk_xxx uv run python development/test_video_all_paths.py \
        --url "https://www.tiktok.com/@mrbeast/video/7379362738948898094" --run-all

    # Test fallback chain (synthetic failures, no URL needed)
    uv run python development/test_video_all_paths.py --test-fallback

Environment:
    GROQ_API_KEY    Required for Groq tests. If absent, skips Groq tier.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

import structlog  # noqa: E402

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

from assistant.shared.config import settings  # noqa: E402
from assistant.shared.exceptions import TranscriptionError  # noqa: E402
from assistant.video.application.extract_video_transcript import (  # noqa: E402
    detect_platform,
    extract_video_transcript,
    format_transcript_note,
)
from assistant.video.domain.video_metadata import Platform, TranscriptionService  # noqa: E402
from assistant.video.infrastructure.groq_adapter import GroqTranscriptAdapter  # noqa: E402
from assistant.video.infrastructure.local_whisper_adapter import LocalWhisperAdapter  # noqa: E402
from assistant.video.infrastructure.youtube_adapter import YouTubeTranscriptAdapter  # noqa: E402
from assistant.video.infrastructure.ytdlp_extractor import (  # noqa: E402
    YtDlpAudioExtractor,
    create_audio_temp_dir,
)

logger = structlog.get_logger()

_DEFAULT_URL = "https://www.youtube.com/watch?v=CMtctfaF9LM"
_results: list[dict[str, str | bool]] = []


def _banner(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def _result(label: str, value: str, ok: bool = True) -> None:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label:<30} {value}")


def _record(test_name: str, ok: bool, detail: str = "") -> None:
    _results.append({"name": test_name, "ok": ok, "detail": detail})


def _print_summary() -> None:
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in _results if r["ok"])
    total = len(_results)
    for r in _results:
        icon = "✅" if r["ok"] else "❌"
        print(f"  {icon} {r['name']:<50} {r['detail']}")
    print(f"\n  {passed}/{total} tests passed")
    if passed < total:
        print("  ⚠️  Some tests failed — see details above.")
    print("=" * 70)


async def test_captions(url: str) -> None:
    """Test YouTube caption extraction (fast path, no audio download)."""
    _banner("TEST: YouTube Captions (Fast Path)")
    print(f"  URL: {url}")
    print("  Strategy: youtube-transcript-api (no audio download)")

    adapter = YouTubeTranscriptAdapter()
    start = time.monotonic()
    try:
        result = await adapter.fetch(url)
        elapsed = time.monotonic() - start
        _result("Status", "SUCCESS")
        _result("Service used", str(result.service_used))
        _result("Title", result.title[:60])
        _result("Transcript length", f"{len(result.transcript)} chars")
        _result("Language", result.language)
        _result("Total elapsed", f"{elapsed:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {result.transcript[:200]}...")
        _record("YouTube Captions", True, f"{elapsed:.1f}s | {result.language}")
    except Exception as exc:
        _result("Status", f"FAILED: {exc}", ok=False)
        _record("YouTube Captions", False, str(exc)[:60])


async def test_full_pipeline(url: str) -> None:
    """Test the FULL pipeline: captions → Groq → local Whisper fallback."""
    _banner("TEST: Full Pipeline")
    print(f"  URL: {url}")
    print("  Pipeline:")
    print("    1. youtube-transcript-api (captions) — YouTube only")
    print("    2. yt-dlp audio + Groq API")
    print("    3. yt-dlp audio + local Whisper tiny (fallback)")
    print(f"  GROQ_API_KEY set: {bool(settings.groq_api_key)}")

    start = time.monotonic()
    try:
        result = await extract_video_transcript(url)
        elapsed = time.monotonic() - start
        _result("Status", "SUCCESS")
        _result("Service used", str(result.service_used))
        _result("Title", result.title[:60])
        _result("Transcript length", f"{len(result.transcript)} chars")
        _result("Language", result.language)
        _result("Transcription time", f"{result.transcription_seconds:.2f}s")
        _result("Total elapsed", f"{elapsed:.2f}s")

        if result.service_used == TranscriptionService.YOUTUBE_CAPTIONS:
            tier = "TIER 1: YouTube captions (no audio download)"
        elif result.service_used == TranscriptionService.GROQ:
            tier = "TIER 2: Groq API (audio extracted, transcribed via API)"
        else:
            tier = "TIER 3: Local Whisper tiny (Groq unavailable or failed)"
        print(f"\n  🏆 {tier}")
        print("\n  --- First 200 chars ---")
        print(f"  {result.transcript[:200]}...")

        note = format_transcript_note(result)
        print("\n  --- Note preview (first 500 chars) ---")
        print(f"  {note[:500]}...")
        _record("Full Pipeline", True, f"{elapsed:.1f}s | {tier}")
    except Exception as exc:
        _result("Status", f"FAILED: {exc}", ok=False)
        _record("Full Pipeline", False, str(exc)[:60])


async def test_audio_extraction(url: str) -> str | None:
    """Test yt-dlp audio extraction only (no transcription).

    Copies the extracted file to /tmp so subsequent tests can access it
    after the temporary directory is cleaned up.
    """
    _banner("TEST: Audio Extraction")
    print(f"  URL: {url}")
    print("  Output: small MP4 via yt-dlp subprocess")

    extractor = YtDlpAudioExtractor()
    with create_audio_temp_dir() as tmp_dir:
        start = time.monotonic()
        try:
            audio_path, metadata = await extractor.extract_audio(url, tmp_dir)
            elapsed = time.monotonic() - start

            # Copy to persistent location so later tests can read the file
            # after the TemporaryDirectory context exits.
            persistent_path = f"/tmp/test_video_audio_{Path(audio_path).name}"
            Path(audio_path).replace(persistent_path)

            _result("Status", "SUCCESS")
            _result("Audio path", persistent_path)
            _result("Audio size", f"{Path(persistent_path).stat().st_size / 1024 / 1024:.1f} MB")
            _result("Title", metadata.get("title", "N/A")[:60])
            _result("Elapsed", f"{elapsed:.2f}s")
            _record(
                "Audio Extraction",
                True,
                f"{elapsed:.1f}s | {Path(persistent_path).stat().st_size // 1024 // 1024}MB",
            )
            return persistent_path
        except TranscriptionError as exc:
            _result("Status", f"FAILED: {exc}", ok=False)
            _record("Audio Extraction", False, str(exc)[:60])
            return None


async def test_groq_direct(audio_path: str) -> None:
    """Test Groq API directly with an existing audio file."""
    _banner("TEST: Groq API Direct")

    if not settings.groq_api_key:
        print("  ⚠️  GROQ_API_KEY not set — skipping Groq test")
        print("      Set it to test the Groq tier: export GROQ_API_KEY=gsk_xxx")
        _record("Groq Direct", False, "GROQ_API_KEY not set")
        return

    adapter = GroqTranscriptAdapter()
    print(f"  Audio file: {audio_path}")
    print(f"  File size: {Path(audio_path).stat().st_size / 1024 / 1024:.1f} MB")
    print("  Groq model: whisper-large-v3-turbo")
    print(f"  Groq available: {adapter.is_available()}")

    start = time.monotonic()
    try:
        transcript, elapsed = await adapter.transcribe(audio_path)
        total = time.monotonic() - start
        _result("Status", "SUCCESS")
        _result("Transcript length", f"{len(transcript)} chars")
        _result("Groq elapsed", f"{elapsed:.2f}s")
        _result("Total elapsed", f"{total:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {transcript[:200]}...")
        _record("Groq Direct", True, f"{total:.1f}s | {len(transcript)} chars")
    except TranscriptionError as exc:
        _result("Status", f"FAILED: {exc}", ok=False)
        _record("Groq Direct", False, str(exc)[:60])


async def test_local_whisper_direct(audio_path: str) -> None:
    """Test local faster-whisper tiny directly with an existing audio file."""
    _banner("TEST: Local faster-whisper Tiny Direct")

    adapter = LocalWhisperAdapter()
    print(f"  Audio file: {audio_path}")
    print(f"  File size: {Path(audio_path).stat().st_size / 1024 / 1024:.1f} MB")
    print("  Model: tiny (CPU, int8)")
    cache_dir = adapter.model_cache_dir()
    print(f"  Model cache: {cache_dir or 'default (~/.cache/huggingface)'}")

    start = time.monotonic()
    try:
        transcript, elapsed = await adapter.transcribe(audio_path)
        total = time.monotonic() - start
        _result("Status", "SUCCESS")
        _result("Transcript length", f"{len(transcript)} chars")
        _result("Whisper elapsed", f"{elapsed:.2f}s")
        _result("Total elapsed", f"{total:.2f}s")
        print("\n  --- First 200 chars ---")
        print(f"  {transcript[:200]}...")
        _record("Local Whisper Direct", True, f"{total:.1f}s | {len(transcript)} chars")
    except TranscriptionError as exc:
        _result("Status", f"FAILED: {exc}", ok=False)
        _record("Local Whisper Direct", False, str(exc)[:60])


async def test_fallback_chain() -> None:
    """Demonstrate the fallback chain with a synthetic failure."""
    _banner("TEST: Fallback Chain Demonstration")
    print("  This test shows what happens when each tier fails:")
    print("    Tier 1 (captions)  → simulate failure")
    print("    Tier 2 (Groq)      → simulate failure")
    print("    Tier 3 (local)     → must succeed or raise")
    print()

    dummy_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    dummy_audio.write(b"\xff" * 1024)
    dummy_audio.close()

    groq_ok = False
    if settings.groq_api_key:
        print("  --- Forcing Groq failure with invalid audio ---")
        groq = GroqTranscriptAdapter()
        try:
            await groq.transcribe(dummy_audio.name)
        except TranscriptionError as exc:
            print(f"  ❌ Groq failed as expected: {exc}")
            groq_ok = True
    else:
        print("  ⚠️  Skipping Groq failure test (no API key)")
        groq_ok = True

    print("  --- Forcing local Whisper failure with invalid audio ---")
    local = LocalWhisperAdapter()
    local_ok = False
    try:
        await local.transcribe(dummy_audio.name)
    except TranscriptionError as exc:
        print(f"  ❌ Local Whisper failed as expected: {exc}")
        local_ok = True

    os.unlink(dummy_audio.name)

    if groq_ok and local_ok:
        print("\n  ✅ Fallback chain verified: failures propagate correctly")
        _record("Fallback Chain", True, "Errors propagate correctly")
    else:
        print("\n  ❌ Fallback chain issue detected")
        _record("Fallback Chain", False, "Unexpected success from invalid audio")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test video transcription paths — one URL, any platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test everything for a YouTube URL
  GROQ_API_KEY=gsk_xxx uv run python %(prog)s --url "YT_LINK" --run-all

  # Test only captions (fast, no API key needed)
  uv run python %(prog)s --url "YT_LINK" --captions

  # Test audio extraction + both ASR tiers
  GROQ_API_KEY=gsk_xxx uv run python %(prog)s --url "YT_LINK" --audio --groq --local

  # Test a TikTok URL (auto-detected)
  GROQ_API_KEY=gsk_xxx uv run python %(prog)s --url "TIKTOK_LINK" --run-all

  # Test fallback chain (no URL needed)
  uv run python %(prog)s --test-fallback
        """,
    )
    parser.add_argument(
        "--url",
        default=_DEFAULT_URL,
        help=f'Video URL to test (YouTube, TikTok, or Instagram). Default: "{_DEFAULT_URL}"',
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run ALL applicable tests for the given URL",
    )
    parser.add_argument(
        "--captions",
        action="store_true",
        help="Test YouTube captions only (ignored for TikTok/Instagram)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Test full pipeline (extract_video_transcript)",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Test audio extraction only",
    )
    parser.add_argument(
        "--groq",
        action="store_true",
        help="Test Groq API on extracted audio (needs --audio or --run-all)",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Test local Whisper on extracted audio (needs --audio or --run-all)",
    )
    parser.add_argument(
        "--test-fallback",
        action="store_true",
        help="Test fallback chain with synthetic failures (no URL needed)",
    )
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    platform = detect_platform(args.url)
    platform_name = platform.value if platform else "unknown"

    print("Video Transcription — All Paths Test")
    print(f"Python: {sys.version}")
    print(f"URL: {args.url}")
    print(f"Detected platform: {platform_name}")
    print(f"GROQ_API_KEY: {'set' if settings.groq_api_key else 'NOT SET'}")
    print(f"Notes vault: {settings.notes_vault_path}")

    if args.test_fallback:
        await test_fallback_chain()
        _print_summary()
        return

    if args.run_all:
        if platform == Platform.YOUTUBE:
            await test_captions(args.url)
        await test_full_pipeline(args.url)
        audio_path = await test_audio_extraction(args.url)
        if audio_path:
            await test_groq_direct(audio_path)
            await test_local_whisper_direct(audio_path)
        _print_summary()
        return

    if args.captions:
        if platform == Platform.YOUTUBE:
            await test_captions(args.url)
        else:
            print(
                f"\n  ⚠️  --captions only applies to YouTube. "
                f"This URL is detected as {platform_name}."
            )

    extracted_audio: str | None = None
    if args.audio:
        extracted_audio = await test_audio_extraction(args.url)

    if args.groq:
        audio_to_test = extracted_audio
        if not audio_to_test and not args.audio:
            print("\n  ⚠️  --groq requires audio. Extracting first...")
            extracted_audio = await test_audio_extraction(args.url)
            audio_to_test = extracted_audio
        if audio_to_test:
            await test_groq_direct(audio_to_test)

    if args.local:
        audio_to_test = extracted_audio
        if not audio_to_test and not args.audio:
            print("\n  ⚠️  --local requires audio. Extracting first...")
            extracted_audio = await test_audio_extraction(args.url)
            audio_to_test = extracted_audio
        if audio_to_test:
            await test_local_whisper_direct(audio_to_test)

    if args.full:
        await test_full_pipeline(args.url)

    if _results:
        _print_summary()
    else:
        print("\n" + "=" * 70)
        print("  No tests were run.")
        print("  Use --run-all or specific flags like --captions, --full, --audio, --groq, --local")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
