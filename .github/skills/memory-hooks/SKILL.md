---
name: memory-hooks
description: Knowledge about the memory hooks system — tag prefixes, memory types, API endpoints, MCP tools, and content formats. Use when: working with memory hooks, modifying hook scripts, debugging memory storage, adding new tags or memory types, querying the memory server, storing or retrieving memories.
---

# Memory Hooks Skill

## MCP Server vs REST API

**Always prefer MCP memory tools over the REST API when operating in-session.** The MCP tools are available directly in the agent's tool set and provide the same functionality with better integration.

| When to use | Method | Why |
|-------------|--------|-----|
| **In-session (agent context)** | MCP tools | Direct tool access, no HTTP overhead, native integration |
| **Hook scripts (separate processes)** | REST API | Hooks run as separate Node.js processes with no MCP access |

### MCP Memory Tools (preferred in-session)

| Tool | Purpose |
|------|---------|
| `mcp_memory_store_memory` | Store a new memory with content, tags, memory_type, metadata |
| `mcp_memory_retrieve_memory` | Semantic search for memories by query |
| `mcp_memory_search_by_tag` | Search memories by specific tags |
| `mcp_memory_list_memories` | List memories with pagination and filtering |
| `mcp_memory_check_database_health` | Check memory server health and status |
| `mcp_memory_delete_memory` | Delete a specific memory by content hash |

### REST API Endpoints (for hook scripts only)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/memories` | POST | Store a memory |
| `/api/memories` | GET | List/filter memories (`?tag=prefix:value`) |
| `/api/search` | POST | Semantic search (`query`, `limit`, `memory_type`) |
| `/api/types` | GET | List valid memory types |

**Rule**: If you have access to MCP tools (i.e., you're the agent, not a hook script), use them. Only fall back to the REST API when running in a context where MCP tools are unavailable (hook scripts, test scripts, curl commands).

## Quick Reference

### Memory Types (set via `memory_type` field)

| Type | Constant | Description | Set By |
|------|----------|-------------|--------|
| `observation` | `MEMORY_TYPE_OBSERVATION` | Tool call/result observations (consolidatable) | `pre-tool-use-v1`, `post-tool-use-v1` |
| `note` | `MEMORY_TYPE_NOTE` | General notes and context | `user-prompt-submit-v1` (retrieval), `stop-v1` (via official hook) |
| `decision` | `MEMORY_TYPE_DECISION` | Architectural or design decisions | `user-prompt-submit-v1` (retrieval), `stop-v1` (via official hook) |
| `fact` | `MEMORY_TYPE_FACT` | Verified facts about the codebase or project | `user-prompt-submit-v1` (retrieval), `session-start-v1` (via official hook) |
| `reminder` | `MEMORY_TYPE_REMINDER` | Time-based or conditional reminders | Not yet used |

### Tag Prefixes (set via `tags` array)

| Prefix | Constant | Purpose | Example | Set By |
|--------|----------|---------|---------|--------|
| `project:` | `TAG_PREFIX_PROJECT` | Project identifier derived from cwd | `project:.claude-62ba6049` | All custom hooks |
| `session:` | `TAG_PREFIX_SESSION` | Session identifier for filtering | `session:55e9e0cc-...` | All custom hooks |
| `hook:` | `TAG_PREFIX_HOOK` | Hook event that created the memory | `hook:pre-tool-use` | Custom hooks |
| `tool:` | `TAG_PREFIX_TOOL` | Tool name that triggered the observation | `tool:read_file` | Pre/post-tool-use |
| `category:` | `TAG_PREFIX_CATEGORY` | Tool category for grouping | `category:file-read` | Pre/post-tool-use |
| `env:` | `TAG_PREFIX_ENV` | Client environment | `env:claude-cli` | All custom hooks |
| `status:` | `TAG_PREFIX_STATUS` | Tool result status | `status:success` | Post-tool-use |

### Tool Categories

| Category | Tools |
|----------|-------|
| `file-read` | read_file, list_dir, file_search, grep_search, semantic_search |
| `file-write` | replace_string_in_file, create_file, create_directory, multi_replace_string_in_file |
| `terminal` | run_in_terminal, send_to_terminal |
| `browser` | open_browser_page, click_element, type_in_page, screenshot_page, etc. |
| `memory` | store_memory, retrieve_memory, search_by_tag, list_memories, check_database_health |
| `search` | github_repo, github_text_search, fetch_webpage, mcp_com_atlassian_search |
| `notebook` | run_notebook_cell, edit_notebook_file |
| `vscode` | get_errors, create_new_workspace |
| `other` | Any unmapped tool |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/memories` | POST | Store a memory |
| `/api/memories` | GET | List/filter memories (`?tag=prefix:value`) |
| `/api/search` | POST | Semantic search (`query`, `limit`, `memory_type`) |
| `/api/types` | GET | List valid memory types |

### Hook Files (Current)

| File | Event | Source | Purpose |
|------|-------|--------|---------|
| `session-start-v1.js` | SessionStart | Official (CJS wrapper) | Multi-phase retrieval, git analysis, quality scoring, dedup |
| `stop-v1.js` | Stop | Official (CJS wrapper) | Conversation analysis, topic/decision/insight extraction |
| `pre-tool-use-v1.mjs` | PreToolUse | Custom | Store tool call observations with structured content and semantic tags |
| `post-tool-use-v1.mjs` | PostToolUse | Custom | Store tool result observations with success/failure detection |
| `user-prompt-submit-v1.mjs` | UserPromptSubmit | Custom | Per-prompt memory injection via `additionalContext` in `hookSpecificOutput` |
| `memory-client-v1.mjs` | — | Custom (shared) | Constants, types, normalization, categorization, server communication |

### Key Implementation Details

1. **`conversation_id` goes in `metadata`**, not top-level — server stores it there (Phase 1B finding)
2. **Search response format**: `results[].memory` — not `results[]` directly
3. **Environment detection**: camelCase properties in hook input → VS Code; snake_case only → Claude CLI
4. **Content truncation**: `MAX_CONTENT_LENGTH = 500` chars
5. **All constants** are in `~/.claude/hooks/memory-client-v1.mjs`
6. **`null` memory_type handling**: Pre-Phase-3 observations have `memory_type: null`. The `user-prompt-submit-v1` hook excludes these — only memories with explicit `note`, `decision`, or `fact` types are injected per-prompt
7. **Per-prompt injection**: `user-prompt-submit-v1` uses semantic search (`/api/search`) with the user's prompt as query, filters to `note`/`decision`/`fact` types, and limits to 5 results via `additionalContext`

### Content Formats

#### Pre-Tool-Use (stored as `memory_type: "observation"`)

```
Tool call: {toolName}
Input: {formattedInput}
Category: {category}
```

#### Post-Tool-Use (stored as `memory_type: "observation"`)

```
Tool result: {toolName}
Status: {success|failure}
Summary: {formattedOutput}
```

#### Per-Prompt Injection (retrieved, not stored)

```
[Memory context]
- [note] Memory content here
- [decision] Decision content here
- [fact] Fact content here
[End memory context]
```

### Metadata Fields

| Field | Type | Description | Set By |
|-------|------|-------------|--------|
| `conversation_id` | `string` | Session ID for server-native dedup | All custom hooks |
| `projectDir` | `string` | Original working directory path | All custom hooks |
| `toolName` | `string` | Tool name (redundant with `tool:` tag) | Pre/post-tool-use |
| `sessionId` | `string` | Session ID (redundant with `session:` tag) | All custom hooks |
| `hookEvent` | `string` | Hook event name (`PreToolUse`, `PostToolUse`) | Pre/post-tool-use |
| `environment` | `string` | Client environment (`claude-cli`, `vscode-copilot`) | All custom hooks |
| `category` | `string` | Tool category | Pre/post-tool-use |
| `isSuccess` | `boolean` | Whether tool call succeeded | Post-tool-use |
| `timestamp` | `string` | ISO 8601 timestamp | All custom hooks |

### Validation Rules

- `memory_type` must be a string matching one of the values from `GET /api/types`
- If `memory_type` is omitted or invalid, the server stores `memory_type: null`
- Custom hooks always set `memory_type` explicitly — never omit it
- The `observation` type is the default for tool call/result storage because it enables server-native consolidation

### Full Reference

For complete details including tag details, derivation rules, and query examples, see:
`~/.claude/local_code/docs/memory-hooks-poc/reference/tag-and-type-reference.md`

### Adding New Tags or Types

1. Add the constant to `memory-client-v1.mjs`
2. Update the reference document at `local_code/docs/memory-hooks-poc/reference/tag-and-type-reference.md`
3. Update this skill file
4. Update `TOOL_CATEGORIES` mapping if adding a new tool category