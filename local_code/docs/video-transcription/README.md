# Video Transcript Extraction — Implementation Documentation

**Feature:** Background video transcription from YouTube, TikTok, and Instagram URLs  
**Status:** Ready for implementation  
**Created:** 2026-06-01

---

## Quick Navigation

| Document | Purpose | Audience |
|----------|---------|----------|
| [Architecture Overview](architecture/overview.md) | System design, data flow, component diagram | Implementer, Reviewer |
| [Architecture Decisions](architecture/decisions/) | ADRs for every major technical choice | Implementer, Future maintainers |
| [Phase Guides](phases/) | Step-by-step implementation instructions | Implementer |
| [API Specification](api/tool-spec.md) | Agent tool signatures and behavior | Implementer |
| [Getting Started](guides/getting-started.md) | How to run and test locally | Implementer |
| [Review Checklists](review/) | poc-architect critique + senior-engineer-python enforcement | Reviewer |

---

## Goal

Allow the user to send a YouTube, TikTok, or Instagram video URL; work is queued and processed sequentially in the background; the user can continue chatting; a proactive notification arrives with the note filename when done. Also fixes the existing session history race condition when two messages arrive concurrently.

---

## Acceptance Criteria

- [ ] Two messages sent rapidly in sequence: both get responses, neither turn is lost from session history
- [ ] `get_video_transcript(url)` tool returns immediate acknowledgment with queue position
- [ ] Bot remains responsive to other messages immediately after queueing
- [ ] Transcriptions from multiple URLs are processed **one at a time, in order**
- [ ] YouTube with captions: transcript-api path, result in < 5s total
- [ ] YouTube without captions / TikTok / Instagram: Groq ASR, fallback to local tiny Whisper if Groq key absent or API fails
- [ ] Completed transcript saved as a note with YAML frontmatter (URL, platform, upload date, service used, time taken)
- [ ] Proactive bot message sent on completion with note filename
- [ ] Proactive bot message sent on failure with error reason
- [ ] Temp audio files cleaned up even on exception
- [ ] `get_transcription_queue_status()` tool returns: running job (with elapsed time), pending count, last 5 completed/failed jobs
- [ ] `/transcribe <url>` command enqueues directly without LLM round-trip
- [ ] Unknown URL format returns a clear error, nothing enqueued

---

## Implementation Order

1. **Phase 0** — Prerequisites & Foundation (race fix, dependencies, config)
2. **Phase 1** — Domain Layer (value objects, enums)
3. **Phase 2** — Infrastructure Layer (adapters: YouTube, yt-dlp, Groq, Whisper)
4. **Phase 3** — Application Layer (use case, queue, worker)
5. **Phase 4** — Agent Tools & Telegram Commands
6. **Phase 5** — Tests
7. **Phase 6** — Final Verification (type check, lint, test, manual)

---

## Constraints

- 2GB RAM, 2 vCPUs (DigitalOcean droplet)
- Single-user personal assistant
- Dockerized deployment
- No paid external services required for primary use case (YouTube)

---

## Out of Scope

- Private/login-gated videos
- Timestamp-level transcripts
- Queue persistence across bot restarts
- Generic background job abstraction (extract when second use case arrives)
- HuggingFace as a middle tier
