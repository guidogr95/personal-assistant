# Ubiquitous Language

These terms are used consistently across all code, documentation, and conversation.
When a concept appears in requirements or user requests, it maps directly to a code symbol.

---

## Core Domain Terms

| Term | Definition in This System | Never Use Instead |
|---|---|---|
| **Session** | A named conversation thread with a lifecycle (`active` or `closed`). Identified by UUID. Has a generated title (set on close). | `chat`, `thread`, `conversation`, `context` |
| **Turn** | One exchange within a session: a single user message + all tool calls made in response + the final assistant reply. Stored as a sequence of messages. | `message_pair`, `exchange`, `interaction`, `round` |
| **Memory** | A long-term fact stored in mcp-memory-service, persisting across sessions indefinitely. Distinct from conversation turn history. | `knowledge`, `persistent_context` |
| **Note** | A single Markdown file in the Vault representing a piece of information saved by the user via the bot. | `document`, `entry`, `record`, `memo`, `page` |
| **Vault** | The synced folder containing all Notes (`/srv/notes/` on the VPS, `~/notes/` on PC, synced folder on Android). | `notes_folder`, `notes_dir`, `notes_storage` |
| **CheckIn** | A proactively scheduled agent run that produces a message delivered to Telegram without user initiation. Defined by a name, cron expression, and system prompt. | `cron_job`, `scheduled_task`, `proactive_reminder`, `job` |
| **Tool** | A Python async function decorated with `@agent.tool` or passed as `Tool(func)` that the LLM can invoke to interact with an external system. | `action`, `capability`, `plugin`, `skill` |
| **Alarm** | A native clock alarm set on the Android device via Tasker. Fires at a specified time even without internet. | `notification`, `reminder` (those are Calendar-only) |
| **Reminder** | A Google Calendar popup notification attached to an event. Delivered via the Calendar app's local alarm scheduler. Distinct from Alarm. | `alarm` (reserved for Tasker alarms), `push_notification` |

---

## Layer Terms

| Term | Definition |
|---|---|
| **Repository** | An interface in `*/domain/` abstracting persistence. Returns domain objects — never raw SQLAlchemy rows, dicts, or ORM models. |
| **Use Case** | A single file in `*/application/` implementing one user-facing action. Named as `verb_noun.py`. |
| **Client** | An infrastructure class in `*/infrastructure/` wrapping a third-party API or service. Named `<service>_client.py`. Contains no domain logic. |
| **Context Window** | The assembled list of Turn messages injected into the LLM prompt for a given request. Managed by `ContextWindow` domain service. |

---

## Status Values

These string values appear in the database and in domain logic. Use exactly as written.

| Entity | Field | Allowed Values |
|---|---|---|
| Session | `status` | `"active"`, `"closed"` |
| Turn | `role` | `"user"`, `"assistant"`, `"tool_call"`, `"tool_result"`, `"summary"` |
| ScheduledCheckIn | `enabled` | `True`, `False` (boolean, not string) |

---

## Naming Rules for Code

- **Files:** `snake_case.py`
- **Classes:** `PascalCase` — named after domain concepts, not technical roles
  - `Session`, `Turn`, `ScheduledCheckIn`, `Note`, `Alarm` — not `SessionModel`, `TurnData`, `JobEntity`
- **Use case files:** verb-noun: `open_session.py`, `close_session.py`, `save_note.py`
  - Never: `session_manager.py`, `session_handler.py`, `session_service.py`
- **Constants:** `UPPER_SNAKE_CASE`
- **Repository interfaces:** `<Entity>Repository` — e.g. `SessionRepository`, `TurnRepository`
- **Infrastructure clients:** `<Service>Client` — e.g. `VikunjaClient`, `JinaClient`
- **Booleans:** always read as questions: `is_active`, `has_pending_items`, `can_be_closed`
- **Collections:** plural of element type: `sessions`, `turns` — never `session_list`, `turns_array`

---

## Anti-Patterns

| Anti-Pattern | Why Forbidden |
|---|---|
| Class named `*Manager`, `*Handler`, `*Service`, `*Helper`, `*Util` | Vague; hides what the class actually does; signals an anemic model |
| Variable named `data`, `result`, `info`, `temp`, `obj` | Names nothing; reader must read the value to understand meaning |
| `ConversationService` doing both persistence and LLM calls | Violates Single Responsibility; split into repository + use case |
| Domain entity importing `sqlalchemy` or `httpx` | Violates layer dependency rule; domain must have zero infrastructure deps |
