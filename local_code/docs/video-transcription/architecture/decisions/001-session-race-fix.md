# ADR 001: Session Race Fix with asyncio.Lock

## Status
Accepted

## Context

When two messages arrive rapidly in sequence, aiogram dispatches each as a concurrent asyncio task. Both tasks call `run_turn`, which:

1. Reads the session blob from SQLite
2. Calls `agent.run()` (yields to event loop)
3. Writes the updated session blob back

The second write silently overwrites the first, losing one turn from message history.

## Decision

Add a per-user `asyncio.Lock` in `run_turn` that serializes the read-modify-write critical section.

```python
_user_locks: dict[int, asyncio.Lock] = {}

async def run_turn(...):
    lock = _user_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        # ... existing body ...
```

## Consequences

**Positive:**
- 3-line fix, minimal complexity
- No SQLite schema changes needed
- Messages from the same user are processed sequentially
- Other users (irrelevant for single-user bot) still concurrent

**Negative:**
- Slightly reduces throughput for the same user (acceptable for personal use)
- Lock is in-memory only; lost on restart (irrelevant, new lock created)

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| `asyncio.Queue` for all messages | Would block simple messages behind slow LLM calls; requires restructuring aiogram dispatch |
| SQLite transaction with `BEGIN IMMEDIATE` | Would block the SQLite connection for all users; overkill for single-user bot |
| Refactor to message queue architecture | Too invasive; the race is a 3-line fix, not an architectural problem |

## Related

- [ADR 002: Queue Mechanism](002-queue-mechanism.md) — orthogonal concern (background tasks, not session access)
