# ADR 004: Transcript Storage Format

## Status
Accepted

## Context

Completed transcripts must be persistent, searchable, and usable by other tools (e.g., "summarize this transcript and add to note X").

## Decision

Save transcripts as Markdown notes in the existing notes vault with YAML frontmatter.

```markdown
---
url: https://www.youtube.com/watch?v=...
platform: youtube
title: "Video Title"
upload_date: 2026-05-15
service: groq
transcription_time_seconds: 8.3
language: en
---

# Transcript: Video Title

## Description
[description from video metadata]

## Transcript
[transcript text]
```

## Consequences

**Positive:**
- Reuses existing `notes` infrastructure (no new storage layer)
- Self-contained: metadata and content in one file
- Searchable via existing `search_notes` tool
- Synced to phone via Syncthing automatically

**Negative:**
- YAML frontmatter parsing required if tools need structured metadata
- Filename must be slugified (handled by existing `save_note` use case)

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| SQLite table for transcripts | Would require new repository, schema, queries; notes vault already exists and works |
| Separate file + DB metadata | Duplicates storage; more complex than single file |
| JSON instead of Markdown | Not human-readable in Obsidian; Markdown is the vault's native format |

## Related

- [ADR 003: ASR Tier Strategy](003-asr-tier-strategy.md) — `service` field in frontmatter records which ASR was used
