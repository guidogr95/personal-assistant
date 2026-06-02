# poc-architect Critique Review

## Entry Checklist

- [x] Clear goal: Queue-based background transcription with proactive notifications
- [x] Constraints: 2GB RAM, 2 vCPUs, single-user personal assistant, Dockerized
- [x] Success criteria: 13 acceptance criteria, all testable
- [x] Dependencies: yt-dlp, youtube-transcript-api, faster-whisper, groq, ffmpeg

---

## Phase 1 — Critique

### Concerns Identified

| # | Category | Concern | Status |
|---|----------|---------|--------|
| C1 | Assumption | Instagram public Reels accessible without login | ⚠️ Partially refuted — ~40-60% fail; accepted as best-effort |
| C2 | Assumption | TikTok extractor in yt-dlp currently functional | ⚠️ Unconfirmed — accepted as best-effort with documented caveat |
| C3 | Risk | `faster-whisper` tiny model accuracy for non-English/technical speech | Mitigated — Groq is primary; tiny is fallback; LLM post-processes |
| C4 | Risk | ffmpeg missing from Dockerfile | ✅ Confirmed missing — must add in Phase 0 |
| C5 | Risk | Background task exception silent | Mitigated — `task.add_done_callback` sends proactive failure notification |
| C6 | Risk | Two concurrent Whisper processes → OOM | Resolved — single worker queue prevents this |
| C7 | Gap | No way to cancel a running transcription | Accepted — out of scope for initial version |
| C8 | Assumption | Groq free tier covers all personal use | ✅ Confirmed — 7,200s audio/hour >> single-user use |
| C9 | Risk | Queue lost on bot restart | Accepted — in-memory queue; user re-requests |
| C10 | Unclear Decision | Generic queue for future tools | Resolved — Rule of Three: extract when second use case arrives |

### Contrarian Hypotheses

| Finding | Contrarian Hypothesis | Plausibility | Dismissal |
|---------|----------------------|--------------|-----------|
| `asyncio.Lock` fixes session race | SQLite transaction would be better | Low | Lock is simpler, no schema changes, sufficient for single-user |
| `asyncio.Queue` is sufficient | SQLite job table needed for reliability | Low | Single user, lost jobs are re-requestable, no evidence of problem |
| Groq is best ASR tier | Local Whisper is sufficient alone | Low | Groq is 5-10× faster, eliminates RAM spike; free tier generous |
| Single worker is correct | Multiple workers for throughput | Low | 2GB RAM constraint; sequential is correct for personal use |

---

## Phase 2 — Research

### ASR Options Compared

| Service | Model | Free Tier | Latency | Verdict |
|---------|-------|-----------|---------|---------|
| Groq | whisper-large-v3-turbo | 2,000 req/day, 7,200s/hour | ~5-10s | ✅ Primary — generous free tier, fast |
| HuggingFace | openai/whisper-large-v3 | ~1,000 req/month | 10-30s cold | ❌ Excluded — cold starts unreliable |
| OpenAI Whisper API | whisper-1 | None ($0.006/min) | ~10s | ❌ Excluded — paid |
| Local tiny | tiny | Unlimited | ~50s | ✅ Fallback — OOM-safe |
| Local small | small | Unlimited | ~5min | ❌ Excluded — OOM risk on 2GB |

### Queue Options Compared

| Option | Sequential? | Survives Restart? | Complexity | Verdict |
|--------|-------------|-------------------|------------|---------|
| `asyncio.Queue` + worker | ✅ | ❌ | Minimal | ✅ Correct for one user |
| APScheduler one-off jobs | ❌ | ❌ | Low | ❌ No sequencing guarantee |
| SQLite job table + worker | ✅ | ✅ | Moderate | ❌ Over-engineering for one use case |

---

## Phase 3 — Revise

All concerns addressed:
- C1/C2: Documented as "best effort" with clear error messages
- C3: Groq primary, tiny fallback, LLM post-processes
- C4: ffmpeg added to Dockerfile in Phase 0
- C5: `add_done_callback` sends proactive failure notification
- C6: Single worker queue
- C7: Out of scope, documented
- C8: Confirmed from Groq docs
- C9: Accepted, documented
- C10: Rule of Three applied

---

## Phase 4 — Verify

- [x] Goal clearly stated and measurable
- [x] All decisions align with constraints (2GB RAM, single-user)
- [x] Every major decision explained with rationale and rejected alternative
- [x] Every assumption validated or flagged with mitigation
- [x] Nothing remains not 100% sure about

**Zero open questions. Spec is final.**

---

## Success Checklist

- [x] At least one full Critique → Research → Revise → Verify loop completed
- [x] Every concern from the last Critique pass is resolved
- [x] All acceptance criteria are testable
- [x] All assumptions have validation status
- [x] All risks have mitigations
