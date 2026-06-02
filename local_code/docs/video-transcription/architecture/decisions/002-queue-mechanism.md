# ADR 002: Transcription Queue Mechanism

## Status
Accepted

## Context

Transcription is a long-running background task (10s–5min). The user must be able to continue chatting while it runs. Multiple transcription requests should be processed sequentially to prevent OOM on a 2GB RAM server.

## Decision

Use `asyncio.Queue` with a single worker coroutine.

```python
_queue: asyncio.Queue[TranscriptionJob] = asyncio.Queue()
_jobs: dict[str, TranscriptionJob] = {}  # status tracking

async def _worker():
    while True:
        job = await _queue.get()
        # ... process job ...
        _queue.task_done()
```

## Consequences

**Positive:**
- No external dependencies (Python stdlib)
- Single consumer = inherently race-safe
- FIFO ordering guarantees sequential processing
- In-memory = fast, no I/O overhead

**Negative:**
- Queue lost on bot restart (acceptable: user re-requests)
- Status tracking dict grows until eviction (mitigated: 24h TTL)

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| APScheduler one-off jobs | No sequencing guarantee; jobs fire simultaneously if scheduled at same time |
| SQLite job table + worker | Over-engineering for one use case / one user; adds schema, repository, polling logic |
| Generic background job framework | Rule of Three: only one background task type exists today; interface would be wrong |

## Related

- [ADR 001: Session Race Fix](001-session-race-fix.md) — orthogonal: lock fixes session access, queue fixes background task UX
