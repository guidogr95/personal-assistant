# Architecture Overview

## System Context

```
┌─────────────┐     Telegram      ┌─────────────┐
│   User      │ ◄──────────────► │   Bot       │
│  (Phone)    │                  │  (aiogram)  │
└─────────────┘                  └──────┬──────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  run_turn    │   │ Transcription│   │  Scheduler   │
            │  (LOCKED)    │   │    Queue     │   │ (APScheduler)│
            └──────┬───────┘   └──────┬───────┘   └──────────────┘
                   │                  │
                   ▼                  ▼
            ┌──────────────┐   ┌──────────────┐
            │  pydantic-ai │   │   Worker     │
            │    Agent     │   │ (1 consumer) │
            └──────┬───────┘   └──────┬───────┘
                   │                  │
                   ▼                  ▼
            ┌──────────────┐   ┌──────────────┐
            │   Tools      │   │  YouTube     │
            │ (notes, etc) │   │  Adapter     │
            └──────────────┘   └──────┬───────┘
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                        ┌──────────┐       ┌──────────┐
                        │  yt-dlp  │       │  Groq    │
                        │ Extract  │       │  Whisper │
                        └──────────┘       └────┬─────┘
                                                  │
                                            ┌─────┴─────┐
                                            ▼           ▼
                                      ┌────────┐   ┌────────┐
                                      │  Local │   │  Notes │
                                      │Whisper │   │  Vault │
                                      │(tiny)  │   │        │
                                      └────────┘   └────────┘
```

## Component Responsibilities

| Component | Layer | Responsibility |
|-----------|-------|--------------|
| `run_turn` | Application | Serialize session access per user via `asyncio.Lock` |
| `TranscriptionQueue` | Application | FIFO queue, single worker, status tracking |
| `YouTubeTranscriptAdapter` | Infrastructure | Fetch captions via `youtube-transcript-api` |
| `YtDlpAudioExtractor` | Infrastructure | Extract audio via `asyncio.create_subprocess_exec` |
| `GroqTranscriptAdapter` | Infrastructure | Transcribe via Groq Whisper API |
| `LocalWhisperAdapter` | Infrastructure | Fallback transcription via `faster-whisper` tiny |
| `extract_video_transcript` | Application | Route to correct adapter chain |
| `video_tools.py` | Presentation | Agent tool wrappers |
| `video_commands.py` | Presentation | Telegram `/transcribe` command |

## Data Flow

### YouTube with Captions (Happy Path)

```
User sends URL
  → get_video_transcript tool
    → enqueue job
    → return "Queued #1"
  → Worker picks up job
    → YouTubeTranscriptAdapter
      → youtube-transcript-api (asyncio.to_thread)
      → return transcript + metadata
    → Save note to vault
    → bot.send_message("Done: filename.md")
```

### TikTok / Instagram (Audio Extraction Path)

```
User sends URL
  → get_video_transcript tool
    → enqueue job
    → return "Queued #1"
  → Worker picks up job
    → YtDlpAudioExtractor
      → asyncio.create_subprocess_exec(yt-dlp)
      → return audio file path + metadata
    → GroqTranscriptAdapter
      → AsyncGroq.audio.transcriptions.create
      → return transcript
    → (if Groq fails) LocalWhisperAdapter
      → asyncio.to_thread(WhisperModel.transcribe)
      → return transcript
    → Save note to vault
    → bot.send_message("Done: filename.md")
```

## Concurrency Model

| Concern | Mechanism | Purpose |
|---------|-----------|---------|
| Session race | `asyncio.Lock` per user in `run_turn` | Prevent read-modify-write corruption |
| Transcription sequencing | `asyncio.Queue` + single worker | Process one video at a time |
| CPU-bound work | `asyncio.to_thread` | Run Whisper without blocking event loop |
| Subprocess I/O | `asyncio.create_subprocess_exec` | Run yt-dlp asynchronously |

## Note Format

```markdown
---
url: https://...
platform: youtube
title: "Video Title"
upload_date: 2026-05-15
service: groq / local-whisper / youtube-captions
transcription_time_seconds: 8.3
language: en
---

# Transcript: Video Title

## Description
[description from video metadata]

## Transcript
[transcript text]
```
