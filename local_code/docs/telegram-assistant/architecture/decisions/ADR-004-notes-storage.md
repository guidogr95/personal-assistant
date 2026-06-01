# ADR-004: Markdown Files + Syncthing for Notes

**Date:** 2025  
**Status:** Accepted

## Context

The assistant needs to save, read, and search notes on behalf of the user. Notes must be accessible from the phone and PC — both for reading and editing. Edits from phone/PC must be visible to the bot on the next read. The operator uses Obsidian and/or Logseq for reading notes. No cloud intermediary is acceptable (privacy constraint). No additional server-side database for notes is desirable (keep services minimal).

## Decision

Store notes as **plain Markdown files** in `/srv/notes/` on the VPS. Sync to all devices using **Syncthing** (P2P, no cloud, Docker container).

- Note format: `<slug>.md` or `<YYYY-MM-DD>-<slug>.md` in `/srv/notes/`
- Agent reads/writes files directly via `NoteRepository` (filesystem implementation)
- Syncthing watches `/srv/notes/` and syncs changes to all connected devices within ~5–30 seconds
- Phone: Syncthing Android app syncs to `~/notes/`; Obsidian or Logseq opens that folder as vault
- PC: Syncthing desktop syncs to `~/notes/` or chosen folder; same Obsidian/Logseq vault

Search implementation: `grep`-based full-text search across `.md` files in the vault. Sufficient for personal-scale notes (hundreds to low thousands of files).

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **Notion** | Cloud dependency; privacy concern; no self-hosted option; API rate limits |
| **Joplin** | Requires a Joplin sync server (extra service); Joplin's file format is not plain Markdown + is not directly readable by Obsidian without export |
| **Standard Notes** | Encrypted at rest (good for security but makes agent read/write impossible without custom extensions); extra server |
| **Git-based notes (Foam/Dendron)** | Requires git commit + push workflow per note; too slow for conversational note-taking; merge conflicts on concurrent edits |
| **Database-backed notes (SQLite/Postgres)** | Not readable by Obsidian/Logseq; loses format independence; cannot be edited natively on phone |

## Consequences

- Adding or editing a note on phone/PC triggers Syncthing sync to VPS; bot sees the change on next read
- Vault is a Docker named volume (`notes_data`) mapped to `/srv/notes/`; same volume mounted by Syncthing container
- Note naming and folder structure is flexible (not enforced by the system); see implementation plan for conventions
- Full-text search is `grep`-based; fast enough for personal use but not semantically rich — a future improvement would add a vector index (e.g., ChromaDB) over note embeddings
- If the operator switches from Obsidian to another Markdown editor, nothing in the system changes
