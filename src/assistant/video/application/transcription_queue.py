"""Transcription queue and single-consumer worker.

Jobs are stored in-memory; queue is not persisted across bot restarts.
Completed jobs are evicted after 24 hours to prevent unbounded growth.
Follows the same module-level dependency injection pattern as run_checkin.py.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import structlog
from aiogram import Bot

from assistant.notes.application.save_note import save_note
from assistant.notes.infrastructure.markdown_repository import MarkdownNoteRepository
from assistant.video.application.extract_video_transcript import (
    extract_video_transcript,
    format_transcript_note,
)
from assistant.video.domain.video_metadata import Platform

logger = structlog.get_logger()

_COMPLETED_JOB_TTL = timedelta(hours=24)
_MAX_RECENT_JOBS = 5


class JobStatus(StrEnum):
    """Life-cycle states for a transcription job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranscriptionJob:
    """Mutable state for a single transcription job.

    ``job_id`` is a short 8-character UUID prefix — unique enough for
    a personal assistant with negligible collision risk.
    """

    url: str
    platform: Platform
    user_id: int
    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: JobStatus = field(default=JobStatus.PENDING)
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result_note_filename: str | None = None


# Module-level state — set once at startup by configure_transcription_queue.
_bot: Bot | None = None
_note_repo: MarkdownNoteRepository | None = None
_queue: asyncio.Queue[TranscriptionJob] = asyncio.Queue()

# All known jobs (pending, running, completed, failed) keyed by job_id.
# Completed jobs older than 24 hours are evicted on each status query.
_jobs: dict[str, TranscriptionJob] = {}


def configure_transcription_queue(
    *,
    bot: Bot,
    note_repo: MarkdownNoteRepository,
) -> None:
    """Inject runtime dependencies before the worker starts.

    Must be called exactly once during application startup, before
    ``asyncio.create_task(start_worker())`` is called.
    """
    global _bot, _note_repo
    _bot = bot
    _note_repo = note_repo


async def enqueue(url: str, user_id: int, platform: Platform) -> tuple[str, int]:
    """Add a transcription job to the FIFO queue.

    Args:
        url: Video URL to transcribe.
        user_id: Telegram user ID to notify on completion.
        platform: Detected platform for the URL.

    Returns:
        Tuple of (job_id, queue_position) where position 1 = next to process.
    """
    job = TranscriptionJob(url=url, platform=platform, user_id=user_id)
    _jobs[job.job_id] = job
    await _queue.put(job)

    queue_position = _queue.qsize()
    logger.info(
        "transcription_job_enqueued",
        job_id=job.job_id,
        url=url,
        platform=platform,
        queue_position=queue_position,
    )
    return job.job_id, queue_position


def get_queue_status() -> dict[str, object]:
    """Return a snapshot of the current queue state.

    Evicts completed/failed jobs older than 24 hours before building the snapshot.

    Returns:
        Dict with keys: running_job, pending_count, recent_jobs.
    """
    _evict_stale_jobs()

    running_job = None
    pending_jobs = []
    recent_jobs = []

    for job in _jobs.values():
        if job.status == JobStatus.RUNNING:
            elapsed = (datetime.now(UTC) - job.started_at).total_seconds() if job.started_at else 0
            running_job = {
                "job_id": job.job_id,
                "url": job.url,
                "platform": str(job.platform),
                "elapsed_seconds": round(elapsed),
            }
        elif job.status == JobStatus.PENDING:
            pending_jobs.append({"job_id": job.job_id, "url": job.url})
        elif job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            recent_jobs.append(job)

    recent_jobs.sort(key=lambda j: j.completed_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    recent_summary = [
        {
            "job_id": j.job_id,
            "url": j.url,
            "status": str(j.status),
            "note_filename": j.result_note_filename,
            "error": j.error,
        }
        for j in recent_jobs[:_MAX_RECENT_JOBS]
    ]

    return {
        "running_job": running_job,
        "pending_count": len(pending_jobs),
        "recent_jobs": recent_summary,
    }


async def start_worker() -> None:
    """Single-consumer worker that drains the transcription queue sequentially.

    Processes one job at a time to prevent OOM on the 2GB droplet.
    Runs indefinitely until the event loop is stopped.
    """
    logger.info("transcription_worker_started")
    while True:
        job = await _queue.get()
        await _process_job(job)
        _queue.task_done()


async def _process_job(job: TranscriptionJob) -> None:
    """Process one transcription job end-to-end and notify the user."""
    bot = _bot
    note_repo = _note_repo
    if bot is None or note_repo is None:
        raise RuntimeError("configure_transcription_queue must be called before the worker starts")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    logger.info("transcription_job_started", job_id=job.job_id, url=job.url)

    try:
        metadata = await extract_video_transcript(job.url)
        note_content = format_transcript_note(metadata)
        note_title = f"Transcript: {metadata.title}"
        note = await save_note(note_title, note_content, note_repo)

        job.result_note_filename = note.filename
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)

        logger.info(
            "transcription_job_completed",
            job_id=job.job_id,
            url=job.url,
            note_filename=note.filename,
            service=metadata.service_used,
        )
        from assistant.telegram.formatting import send_message

        await send_message(
            bot,
            f"✅ Transcript ready: `{note.filename}`",
            chat_id=job.user_id,
        )
    except Exception as exc:  # noqa: BLE001 — worker must not crash; all errors reported to user
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.completed_at = datetime.now(UTC)

        logger.error(
            "transcription_job_failed",
            job_id=job.job_id,
            url=job.url,
            error=str(exc),
        )
        try:
            from assistant.telegram.formatting import send_message

            await send_message(
                bot,
                f"❌ Transcription failed: {exc}",
                chat_id=job.user_id,
            )
        except Exception as notify_exc:
            logger.error(
                "transcription_failure_notification_error",
                job_id=job.job_id,
                error=str(notify_exc),
            )


def _evict_stale_jobs() -> None:
    """Remove completed/failed jobs older than 24 hours from the tracking dict."""
    cutoff = datetime.now(UTC) - _COMPLETED_JOB_TTL
    stale_ids = [
        job_id
        for job_id, job in _jobs.items()
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED)
        and job.completed_at is not None
        and job.completed_at < cutoff
    ]
    for job_id in stale_ids:
        del _jobs[job_id]

    if stale_ids:
        logger.debug("transcription_jobs_evicted", count=len(stale_ids))
