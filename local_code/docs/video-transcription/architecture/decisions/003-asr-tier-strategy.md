# ADR 003: ASR Tier Strategy

## Status
Accepted

## Context

We need automatic speech recognition (ASR) for videos without captions. The server has 2GB RAM and 2 vCPUs. We want to avoid paid services if possible, but reliability matters.

## Decision

**Tier 1: Groq Whisper API** (primary)  
**Tier 2: local `faster-whisper` tiny** (fallback)

### Tier 1 — Groq

- Model: `whisper-large-v3-turbo`
- Free tier: 2,000 req/day, 7,200s audio/hour
- Latency: ~5–10s for 10-min video
- Requires: `GROQ_API_KEY` env var

### Tier 2 — Local Whisper

- Model: `tiny` (39MB weights)
- Peak RAM: ~400–600MB
- Latency: ~50s for 10-min video on CPU
- Requires: `faster-whisper`, `ffmpeg`

## Consequences

**Positive:**
- Groq eliminates RAM spike risk entirely
- Groq is 5–10× faster than local CPU inference
- Free tier generous for personal use
- Local fallback ensures feature works without Groq key

**Negative:**
- Groq requires account signup (free, but extra step)
- Local tiny model has lower accuracy for accented/technical speech
- `faster-whisper` adds ~39MB to Docker image (tiny model weights)

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| `faster-whisper` small (244MB) | OOM risk on 2GB RAM server (~1.2–1.8GB peak) |
| `faster-whisper` base (74MB) | Borderline RAM usage; tiny is safer with acceptable accuracy loss |
| HuggingFace Inference API | Unreliable cold starts (~10–30s); adds complexity for near-zero benefit |
| OpenAI Whisper API | Paid ($0.006/min); violates "no paid service" constraint for primary path |
| AssemblyAI / Deepgram | Paid; same reason |

## Related

- [ADR 004: Storage Format](004-storage-format.md) — transcripts saved as notes with metadata
