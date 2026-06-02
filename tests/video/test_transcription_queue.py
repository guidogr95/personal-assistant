"""Tests for the transcription queue and worker."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from assistant.video.application.transcription_queue import (
    JobStatus,
    TranscriptionJob,
    _evict_stale_jobs,
    configure_transcription_queue,
    enqueue,
    get_queue_status,
)
from assistant.video.domain.video_metadata import Platform


@pytest.fixture(autouse=True)
def reset_queue_state() -> None:
    """Reset module-level queue state before each test."""
    from assistant.video.application import transcription_queue as tq

    tq._queue = asyncio.Queue()
    tq._jobs.clear()
    tq._bot = None
    tq._note_repo = None


class TestEnqueue:
    """Job enqueueing and queue position tracking."""

    async def test_should_return_job_id_and_position(self) -> None:
        job_id, position = await enqueue(
            url="https://youtu.be/test1",
            user_id=123,
            platform=Platform.YOUTUBE,
        )
        assert isinstance(job_id, str)
        assert len(job_id) == 8
        assert position == 1

    async def test_should_increment_queue_position(self) -> None:
        await enqueue("https://youtu.be/test1", 123, Platform.YOUTUBE)
        _, position = await enqueue("https://youtu.be/test2", 123, Platform.YOUTUBE)
        assert position == 2


class TestGetQueueStatus:
    """Queue status reporting."""

    async def test_should_show_pending_count(self) -> None:
        await enqueue("https://youtu.be/test1", 123, Platform.YOUTUBE)
        await enqueue("https://youtu.be/test2", 123, Platform.YOUTUBE)
        status = get_queue_status()
        assert status["pending_count"] == 2
        assert status["running_job"] is None

    async def test_should_show_recent_completed_jobs(self) -> None:
        job = TranscriptionJob(
            url="https://youtu.be/test",
            platform=Platform.YOUTUBE,
            user_id=123,
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(UTC),
            result_note_filename="2026-06-01-test.md",
        )
        from assistant.video.application import transcription_queue as tq

        tq._jobs[job.job_id] = job
        status = get_queue_status()
        recent = status["recent_jobs"]
        assert len(recent) == 1
        assert recent[0]["status"] == "completed"
        assert recent[0]["note_filename"] == "2026-06-01-test.md"

    async def test_should_show_recent_failed_jobs(self) -> None:
        job = TranscriptionJob(
            url="https://tiktok.com/test",
            platform=Platform.TIKTOK,
            user_id=123,
            status=JobStatus.FAILED,
            completed_at=datetime.now(UTC),
            error="TikTok blocked access",
        )
        from assistant.video.application import transcription_queue as tq

        tq._jobs[job.job_id] = job
        status = get_queue_status()
        recent = status["recent_jobs"]
        assert len(recent) == 1
        assert recent[0]["status"] == "failed"
        assert "TikTok blocked access" in recent[0]["error"]


class TestEvictStaleJobs:
    """24-hour eviction of completed/failed jobs."""

    def test_should_evict_jobs_older_than_24_hours(self) -> None:
        old_job = TranscriptionJob(
            url="https://youtu.be/old",
            platform=Platform.YOUTUBE,
            user_id=123,
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(UTC) - timedelta(hours=25),
        )
        fresh_job = TranscriptionJob(
            url="https://youtu.be/fresh",
            platform=Platform.YOUTUBE,
            user_id=123,
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(UTC) - timedelta(hours=1),
        )
        from assistant.video.application import transcription_queue as tq

        tq._jobs[old_job.job_id] = old_job
        tq._jobs[fresh_job.job_id] = fresh_job

        _evict_stale_jobs()

        assert old_job.job_id not in tq._jobs
        assert fresh_job.job_id in tq._jobs

    def test_should_not_evict_running_or_pending_jobs(self) -> None:
        running = TranscriptionJob(
            url="https://youtu.be/running",
            platform=Platform.YOUTUBE,
            user_id=123,
            status=JobStatus.RUNNING,
            started_at=datetime.now(UTC) - timedelta(hours=25),
        )
        from assistant.video.application import transcription_queue as tq

        tq._jobs[running.job_id] = running
        _evict_stale_jobs()
        assert running.job_id in tq._jobs


class TestConfigureTranscriptionQueue:
    """Dependency injection setup."""

    def test_should_set_bot_and_repo(self) -> None:
        mock_bot = MagicMock()
        mock_repo = MagicMock()
        configure_transcription_queue(bot=mock_bot, note_repo=mock_repo)
        from assistant.video.application import transcription_queue as tq

        assert tq._bot is mock_bot
        assert tq._note_repo is mock_repo
