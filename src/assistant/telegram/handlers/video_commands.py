"""Telegram /transcribe command handler."""

from __future__ import annotations

import re

import structlog
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from assistant.shared.config import settings
from assistant.video.application.extract_video_transcript import detect_platform
from assistant.video.application.transcription_queue import enqueue

logger = structlog.get_logger()

router = Router()

_URL_PATTERN = re.compile(r"https?://\S+")


@router.message(Command("transcribe"))
async def cmd_transcribe(message: Message) -> None:
    """Queue a video URL for background transcription.

    Usage:
      /transcribe https://youtube.com/watch?v=...
      Reply to a message containing a URL with /transcribe.
    """
    if not message.text:
        return

    url = _extract_url(message)
    if url is None:
        await message.reply(
            "Please provide a video URL.\n\nUsage: /transcribe https://youtube.com/watch?v=..."
        )
        return

    platform = detect_platform(url)
    if platform is None:
        await message.reply(
            "Unsupported URL. Only YouTube, TikTok, and Instagram links are supported."
        )
        return

    job_id, position = await enqueue(
        url=url,
        user_id=settings.telegram_allowed_user_id,
        platform=platform,
    )
    logger.info(
        "transcribe_command_enqueued",
        job_id=job_id,
        url=url,
        platform=platform,
    )
    await message.reply(
        f"Queued #{position} (job {job_id}).\n"
        f"I'll send you the note filename when the transcript is ready."
    )


def _extract_url(message: Message) -> str | None:
    """Extract a video URL from the message text or a replied-to message."""
    # Check command argument: /transcribe <url>
    text = message.text or ""
    args = text.removeprefix("/transcribe").strip()
    if args:
        match = _URL_PATTERN.search(args)
        if match:
            return match.group(0)

    # Check replied-to message body
    if message.reply_to_message and message.reply_to_message.text:
        match = _URL_PATTERN.search(message.reply_to_message.text)
        if match:
            return match.group(0)

    return None
