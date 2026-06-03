# Phase 7 — Telegram Message Formatting Overhaul

## Goal

Fix the root cause of "message too long" errors, unify all text-sending paths, and enable proper Markdown rendering for note content by converting the system prompt from HTML to Markdown and adding a boundary conversion layer.

---

## Background

### The Problem

The bot's system prompt instructed the LLM to produce HTML (`<b>`, `<i>`, `<code>`) for Telegram rendering. This worked for short LLM-generated responses but failed for:

1. **Note display**: Notes are Markdown files. When the LLM included raw Markdown in an HTML response, Telegram rendered `# heading` as literal text, not as a heading.
2. **Message length**: The `/tools` command built a single message that exceeded Telegram's 4096-character limit as the tool count grew.
3. **Fragmented send paths**: Six different methods sent text to Telegram, none with unified length protection.

### The Error (Cognitive Bias)

The existing HTML system prompt was treated as immutable architecture. This was **status quo bias** — assuming existing code is correct/unchangeable without questioning whether the original decision still holds. The senior-engineer-python skill now includes a rule to prevent this:

> "Existing code is not immutable architecture. When a design choice is causing friction, evaluate whether changing the choice is simpler than working around it."

---

## Approach

### High-Level Flow

```
User message → LLM → Markdown response → Telegram boundary → HTML conversion → Telegram API
                                    ↑
                                    └── Note content: raw Markdown from disk
```

The LLM produces Markdown. The Telegram layer converts Markdown→HTML before sending. Notes are read from disk as Markdown, converted at the boundary, and rendered correctly.

---

## Step 1 — Add `mistune` Dependency

**File:** `pyproject.toml`

**Change:** Add `mistune>=3.0` to `[project.dependencies]`.

**Why:** Lightweight (~50KB), correct Markdown→HTML conversion. Handles standard syntax including code blocks, lists, and strikethrough.

---

## Step 2 — Create Markdown→Telegram-HTML Converter

**File:** `src/assistant/telegram/markdown_to_html.py` (new)

**Responsibilities:**
- Convert Markdown to HTML using `mistune`
- Map unsupported HTML tags to Telegram-safe equivalents:
  - `<h1>`–`<h6>` → `<b>text</b>`
  - `<ul>` / `<ol>` → plain text with `-` / `1.` prefixes
  - `<li>` → item text
  - `<blockquote>` → `<i>text</i>`
  - `<br>` → `\n`
  - `<p>` → `\n\n`
- Strip any remaining unsupported tags (defensive)

**Interface:**
```python
def convert_markdown_to_telegram_html(markdown_text: str) -> str:
    """Convert Markdown to Telegram-safe HTML.
    
    Uses mistune for parsing, then maps unsupported tags to
    Telegram's supported subset.
    """
```

---

## Step 3 — Unified Telegram Sender Gateway

**File:** `src/assistant/telegram/formatting.py` (modify)

**Current state:**
- `answer_markdown()` — replies to a Message with HTML parse mode
- `send_markdown()` — sends via Bot with HTML parse mode
- `send_long_text()` — splits text across multiple messages

**New unified sender:**
```python
async def send_message(
    message_or_bot: Message | Bot,
    text: str,
    chat_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> list[Message]:
    """Unified sender: converts Markdown to HTML, handles length, sends.
    
    Accepts either a Message (for replies) or a Bot + chat_id (for
    background jobs). Converts Markdown to Telegram-safe HTML,
    checks length, and either sends as a single message or truncates
    with a "Get full file" button.
    """
```

**Behavior:**
1. Convert `text` (Markdown) → HTML via `convert_markdown_to_telegram_html()`
2. If HTML length ≤ 3,800 chars: send as single message
3. If HTML length > 3,800 chars:
   - Truncate to last safe boundary (end of line, end of tag)
   - Append "… (truncated)"
   - Add inline keyboard button: `📄 Get full content as file`
   - Send message with button
4. Catch `TelegramBadRequest` → fallback to plain text

**Why 3,800:** Telegram limit is 4,096 chars. Safety margin for HTML tag overhead.

---

## Step 4 — Update System Prompt to Markdown

**File:** `src/assistant/agent/domain/agent.py`

**Current:**
```markdown
Telegram renders HTML. Use these tags — no Markdown syntax at all.
- <b>text</b> for bold
...
Never use Markdown: no *bold*, no **bold**, no `backticks`...
```

**New:**
```markdown
=== RESPONSE FORMAT ===
Respond in Markdown. Use standard Markdown syntax:

- **bold** for emphasis
- *italic* for secondary emphasis
- `code` for inline code
- ```fences``` for code blocks
- [text](url) for links
- - item for bullet lists
- 1. item for numbered lists

I will convert your Markdown to Telegram's HTML before sending.
```

**Why:** The LLM is natively trained on Markdown. Notes are Markdown. One format everywhere. Conversion happens at the boundary.

---

## Step 5 — Update Formatting Helpers

**File:** `src/assistant/telegram/formatting.py`

**Current helpers produce HTML:**
```python
def bold(text: str) -> str:
    return f"<b>{html.escape(text)}</b>"
```

**New helpers produce Markdown:**
```python
def bold(text: str) -> str:
    escaped = text.replace("*", "\\*").replace("_", "\\_")
    return f"**{escaped}**"
```

**Helpers updated:** `bold()`, `italic()`, `code()`, `pre()`, `link()`

---

## Step 6 — Migrate All Handlers

**Files to update:**

| File | Changes |
|------|---------|
| `telegram/handlers/message.py` | Replace `answer_markdown()` with `send_message()` |
| `telegram/handlers/session_commands.py` | Update `_HELP_TEXT` to Markdown; replace `answer_markdown()` |
| `telegram/handlers/checkin_commands.py` | Update string building to Markdown; replace `answer_markdown()` |
| `telegram/handlers/prompt_commands.py` | Update `bold()`, `pre()` usage; replace `answer_markdown()` |
| `telegram/handlers/tool_commands.py` | Update tool listing to Markdown; replace `answer_markdown()` |
| `telegram/handlers/callbacks.py` | Update `edit_text()` calls; add file request handler |
| `telegram/handlers/errors.py` | Replace `bot.send_message()` with `send_message()` |
| `scheduler/application/run_checkin.py` | Replace `send_markdown()` with `send_message()` |
| `video/application/transcription_queue.py` | Replace `bot.send_message()` with `send_message()` |

**Mechanical changes:** HTML tags → Markdown syntax in all string literals.

---

## Step 7 — Add File Request Callback Handler

**File:** `src/assistant/telegram/handlers/callbacks.py`

**Callback data format:** `file:note:{hash}` (16 bytes — well under 64-byte limit)

**State storage:** `src/assistant/telegram/pending_state.py`

```python
_pending_file_requests: dict[str, tuple[str, datetime]] = {}
# hash → (filename, created_at)
_MAX_FILE_REQUEST_AGE: timedelta = timedelta(hours=1)

def store_file_request(hash: str, filename: str) -> None:
    _pending_file_requests[hash] = (filename, datetime.now(UTC))

def get_file_request(hash: str) -> str | None:
    entry = _pending_file_requests.get(hash)
    if entry is None:
        return None
    filename, created_at = entry
    if datetime.now(UTC) - created_at > _MAX_FILE_REQUEST_AGE:
        del _pending_file_requests[hash]
        return None
    return filename
```

**Flow:**
1. Unified sender detects long text → stores file request → sends message with button
2. User taps button → callback handler reads hash → re-reads note from disk
3. Sends note as `.txt` document via `bot.send_document()`
4. Clears entry

**Why re-read from disk:** Source of truth. Note may have been edited since the button was created.

---

## Step 8 — Context Token Warning (Optional)

**File:** `src/assistant/agent/application/run_turn.py`

**Change:** After `agent.run()`, estimate token count:
```python
history_json = ModelMessagesTypeAdapter.dump_json(result.all_messages())
token_estimate = len(history_json) // 4  # rough: 4 chars per token
if token_estimate > 100_000:  # ~80% of 128K
    # Append subtle warning to reply or send as follow-up
```

**Why:** Informs user when long notes push context toward the limit. Non-blocking.

---

## Step 9 — Tests

**Files:**
- `tests/telegram/test_markdown_to_html.py` (new)
- `tests/telegram/test_formatting.py` (update)

**Test cases:**
- Markdown→HTML conversion for all standard syntax
- Telegram-unsafe tag mapping (`<h1>` → `<b>`, etc.)
- Unified sender: short text, long text (truncation + button), HTML fallback
- File request callback: store, retrieve, expiration
- Token estimation accuracy

---

## Decisions & Rationale

| Decision | Choice | Alternative | Reason |
|----------|--------|-------------|--------|
| System prompt format | Markdown | Keep HTML | Markdown is native to LLM training; notes are Markdown; one format everywhere |
| Conversion location | Telegram boundary | Tool layer, LLM layer | Tools must return raw Markdown for editing; LLM shouldn't handle display formatting |
| Large text handling | Truncate + file button | Split messages | Button is cleaner UX; document preserves exact formatting |
| Callback state | Hash + module dict with TTL | Full filename in callback, conversation storage | 64-byte limit makes filename risky; conversation storage impractical for callbacks; TTL prevents stale entries |
| Unsupported HTML tags | Mapped to Telegram equivalents | Stripped | Mapped preserves structure (headings as bold, lists as plain text); stripped would lose all formatting |
| Context warning | Token estimate, warn at 80% | Hard limit, no warning | Warning informs without blocking; user explicitly wants literal content |

---

## Assumptions

| Assumption | Category | Risk if Wrong | Status |
|------------|----------|---------------|--------|
| `mistune` handles user's note syntax | Technical | Some notes render incorrectly | ⚠️ Test with actual vault notes |
| LLM adapts quickly to Markdown prompt | Technical | Temporary quality degradation | ✅ Base model trained on Markdown; adaptation within few turns |
| Most notes are < 3,800 chars | Operational | File button appears frequently | ⚠️ Check actual note sizes |
| User prefers document download over split messages | UX | User finds button annoying | ✅ Standard Telegram UX |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Markdown prompt causes worse output quality | Low | Medium | Monitor first few messages; rollback is `git revert` |
| `mistune` adds dependency just for display | Low | Low | 50KB, no transitive deps |
| Unified sender bug breaks all messaging | Medium | High | Test independently before migration; migrate one handler at a time |
| HTML tag mapping is incomplete | Low | Medium | Defensive: strip any remaining unsupported tags |
| Stale file request entries accumulate | Low | Low | 1-hour TTL; dict is small (one entry per long message) |

---

## Open Questions

*(empty — all concerns resolved)*

---

## Success Criteria

- [ ] All handlers use unified `send_message()` — no direct `message.answer()` or `bot.send_message()`
- [ ] Note display renders Markdown correctly (headings, lists, code blocks)
- [ ] Messages > 3,800 chars show "Get full file" button, not crash
- [ ] `/tools` command uses category browser, never exceeds length limit
- [ ] Error messages include specific error type (not generic "Something went wrong")
- [ ] 191 tests pass, ruff clean, mypy clean
- [ ] First few live messages after prompt change show acceptable quality
