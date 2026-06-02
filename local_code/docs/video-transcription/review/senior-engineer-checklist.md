# Senior Engineer — Python Enforcement Checklist

## Global Standards

For every file created or modified in this feature, verify:

### Type Safety
- [ ] All functions have complete type hints (parameters + return type)
- [ ] `T | None` used for nullable values — never implicit `None`
- [ ] No bare `Any` — use specific types or `TypeVar`
- [ ] `TypedDict` for dicts with known structure
- [ ] `Enum` (or `StrEnum`) for fixed sets of string values
- [ ] `Protocol` for structural interfaces — prefer over ABC
- [ ] `@dataclass(frozen=True)` for value objects — validate in `__post_init__`

### Error Handling
- [ ] No `except Exception: pass` anywhere
- [ ] Specific exception types for each failure mode
- [ ] Wrap infrastructure exceptions to preserve cause chain: `raise DomainError(...) from e`
- [ ] Include relevant identifiers in error messages

### Code Style
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT (only WHY)
- [ ] No docstrings that restate the function name
- [ ] No `print()` in production paths — use `structlog`
- [ ] No vague intermediate variables (`result`, `data`, `info`)

### Imports
- [ ] All imports at top of file
- [ ] Grouped: stdlib → third-party → local → relative
- [ ] Alphabetically sorted within each group
- [ ] Never `from module import *`
- [ ] Never mid-file imports

### Async
- [ ] No blocking I/O in async context
- [ ] `asyncio.to_thread` for CPU-bound sync code
- [ ] `asyncio.create_subprocess_exec` for subprocesses
- [ ] Always await coroutines — never fire-and-forget without tracking

### Security
- [ ] No secrets in source code
- [ ] No sensitive data in logs
- [ ] Config loaded from environment, validated at startup

---

## Per-Phase Checklist

### Phase 0 — Prerequisites
- [ ] `_user_locks: dict[int, asyncio.Lock]` typed correctly
- [ ] `groq_api_key: str = ""` in Settings (empty string = optional)
- [ ] `ffmpeg` added to Dockerfile without breaking existing packages

### Phase 1 — Domain
- [ ] `Platform(StrEnum)` — not plain string
- [ ] `TranscriptionService(StrEnum)` — not plain string
- [ ] `VideoMetadata` is `@dataclass(frozen=True)`
- [ ] All fields typed, no bare `Any`

### Phase 2 — Infrastructure
- [ ] `youtube_adapter.py`: `asyncio.to_thread` for sync `youtube_transcript_api`
- [ ] `ytdlp_extractor.py`: `asyncio.create_subprocess_exec` for yt-dlp
- [ ] `groq_adapter.py`: `AsyncGroq` client, not sync client
- [ ] `local_whisper_adapter.py`: `asyncio.to_thread` for `WhisperModel.transcribe`
- [ ] All adapters return specific types, not `Any`
- [ ] All adapters use `structlog` with context

### Phase 3 — Application
- [ ] `JobStatus(StrEnum)` — not plain string
- [ ] `TranscriptionJob` dataclass with complete types
- [ ] `QueueStatus` is `TypedDict` or dataclass
- [ ] Worker catches exceptions and sends proactive notification
- [ ] `configure_transcription_queue` follows injection pattern

### Phase 4 — Tools & Commands
- [ ] Tool functions have complete type hints
- [ ] No `Any` in tool signatures
- [ ] Docstrings describe behavior, preconditions, exceptions
- [ ] `/transcribe` handler typed correctly

### Phase 5 — Tests
- [ ] Test functions have type hints
- [ ] Test names follow `test_should_[behaviour]_when_[condition]`
- [ ] Mock I/O boundaries only, not domain objects
- [ ] Proper use of `pytest-asyncio`

### Phase 6 — Verification
- [ ] `mypy --strict` passes
- [ ] `ruff check` passes
- [ ] All tests pass

---

## Anti-Patterns to Catch

| Anti-Pattern | Location to Check | Correct Pattern |
|--------------|-------------------|-----------------|
| `except Exception: pass` | All `try/except` blocks | Specific exception types + log + re-raise |
| `def func(data: dict) -> Any:` | All function signatures | `TypedDict` input, specific return type |
| `if condition: return True else: return False` | All conditional returns | `return condition` or guard clauses |
| `result = get_data(); process(result)` | All variable assignments | Name after what it represents |
| `import *` | All import sections | Explicit imports only |
| `subprocess.run()` in async | `ytdlp_extractor.py` | `asyncio.create_subprocess_exec` |
| `model.transcribe()` in async | `local_whisper_adapter.py` | `asyncio.to_thread` |

---

## Sign-Off

**Implementer:** _________________ Date: _______

**Reviewer:** _________________ Date: _______

Both must check all boxes before feature is declared complete.
