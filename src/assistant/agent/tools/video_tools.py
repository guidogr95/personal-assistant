"""Agent tools for video transcript extraction."""

from __future__ import annotations

import structlog
from pydantic_ai import Agent, RunContext

from assistant.shared.config import settings
from assistant.video.application.extract_video_transcript import detect_platform
from assistant.video.application.transcription_queue import enqueue, get_queue_status

logger = structlog.get_logger()


def register_video_tools(agent: Agent[None, str]) -> None:
    """Register video transcription tools on the agent."""

    @agent.tool
    async def get_video_transcript(ctx: RunContext[None], url: str) -> str:
        """Queue a video URL for background transcription.

        Supports YouTube, TikTok, and Instagram (public videos only).
        Returns immediately with a queue position — transcription runs in the
        background and a notification arrives when complete.

        YouTube videos with captions are processed in under 5 seconds total.
        TikTok and Instagram require audio extraction and may take 30–120 seconds
        depending on video length and whether Groq or local Whisper is used.

        Only public videos are supported. Login-gated or private content will fail.

        Args:
            url: Full video URL including scheme (https://...).

        Returns:
            Acknowledgment with queue position, e.g. "Queued #1. I'll notify
            you when the transcript is ready."
        """
        platform = detect_platform(url)
        if platform is None:
            return (
                "Unsupported URL. Please provide a YouTube, TikTok, or Instagram link. "
                "Examples: https://youtube.com/watch?v=..., https://tiktok.com/@user/video/..."
            )

        # user_id is not available in RunContext[None] — the worker uses the
        # allowed user ID from settings since this is a single-user bot.
        job_id, position = await enqueue(
            url=url,
            user_id=settings.telegram_allowed_user_id,
            platform=platform,
        )
        logger.info("video_transcript_tool_enqueued", job_id=job_id, url=url)
        return (
            f"Queued #{position} (job {job_id}). "
            f"I'll send you the note filename when the transcript is ready."
        )

    @agent.tool
    async def get_transcription_queue_status(ctx: RunContext[None]) -> str:
        """Check the current status of the transcription queue.

        Returns a summary of: the currently running job (if any) with elapsed
        time, the number of pending jobs, and up to 5 recently completed or
        failed jobs with note filenames or error messages.

        Returns:
            Human-readable queue status formatted for Telegram.
        """
        status = get_queue_status()

        lines: list[str] = []

        running = status.get("running_job")
        if running and isinstance(running, dict):
            lines.append(
                f"**Running:** {running['url']} "
                f"({running['platform']}, {running['elapsed_seconds']}s elapsed)"
            )
        else:
            lines.append("**Running:** nothing")

        pending_count = status.get("pending_count", 0)
        lines.append(f"**Pending:** {pending_count} job(s)")

        recent = status.get("recent_jobs", [])
        if recent and isinstance(recent, list):
            lines.append("**Recent:**")
            for job in recent:
                if not isinstance(job, dict):
                    continue
                job_status = job.get("status", "")
                if job_status == "completed":
                    lines.append(
                        f"  ✅ {job.get('url', '')} → `{job.get('note_filename', 'unknown')}`"
                    )
                else:
                    lines.append(f"  ❌ {job.get('url', '')} — {job.get('error', 'unknown error')}")
        else:
            lines.append("**Recent:** no completed jobs")

        return "\n".join(lines)
