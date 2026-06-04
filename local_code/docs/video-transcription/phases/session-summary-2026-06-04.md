# Session Summary — June 4, 2026

## Context

This session started as a continuation of the YouTube bot detection research from `research-youtube-bot-detection-fallback.md`. The goal was to validate and fix the production container so that the video transcription feature works on the VPS (DigitalOcean droplet, datacenter IP).

---

## Problem Statement

The video transcription feature worked on the developer's local WSL machine (residential IP) but failed on the VPS with:

```
ERROR: [youtube] <video_id>: Sign in to confirm you're not a bot.
```

This is YouTube's bot detection triggered by datacenter IPs. The existing `yt-dlp` extraction path had no bypass mechanism.

---

## Failed Approach: Playwright Browser Fallback

### What was tried
A Playwright-based fallback that would:
1. Launch headless Chromium when yt-dlp reports bot detection
2. Navigate to the YouTube video page
3. Extract `ytInitialPlayerResponse` JSON
4. Parse `adaptiveFormats` for audio stream URLs
5. Download audio via `aiohttp`

### Why it failed
YouTube has moved to **SABR** (Server-side Adaptive Bitrate Streaming). The `adaptiveFormats` array contains only metadata — no direct `url` fields. Actual media segments are fetched via a proprietary protocol through `serverAbrStreamingUrl` that the YouTube player handles internally. This URL is tied to the player's internal state and cannot be accessed externally.

**Result:** All Playwright-related code was reverted. See `research-youtube-bot-detection-fallback.md` for full details.

---

## Solution: Option A — bgutil + mweb + EJS

### Components

| Component | Purpose | Version |
|-----------|---------|---------|
| `bgutil-ytdlp-pot-provider` | Docker sidecar that generates PO Tokens (POT) for YouTube | v1.3.1 |
| `mweb` player client | yt-dlp extractor client officially recommended with POT | yt-dlp built-in |
| `yt-dlp-ejs` | External JS Scripts for solving n/sig decryption challenges | v0.8.0 |
| Node.js ≥ 22 | Runtime for EJS challenge solver scripts | v22.22.3 |

### How it works
1. **POT Generation:** `bgutil` sidecar generates a per-video PO Token (attestation token)
2. **Client Selection:** `mweb` player client requests the player response in a way that accepts POT
3. **JS Challenges:** YouTube serves obfuscated JS challenges (n/sig decryption). EJS solves them via Node.js
4. **URL Construction:** yt-dlp constructs a valid `googlevideo.com` URL with `pot=` and `sig=` parameters
5. **Download:** Direct HTTP download from Google's CDN succeeds

---

## Gaps Discovered and Fixed

### Gap 1: `yt-dlp-ejs` not installed

**Problem:** `pyproject.toml` had `"yt-dlp>=2024.0"` (bare package). The EJS solver scripts are in the optional `default` extra.

**Fix:** Changed to `"yt-dlp[default]>=2024.0"` which pulls in `yt-dlp-ejs`.

**File:** `pyproject.toml`

### Gap 2: Node v20 in container (EJS requires ≥ 22)

**Problem:** Debian Bookworm ships Node v20.19.2 via `apt-get install nodejs`. EJS silently skips runtimes < 22, reporting `JS runtimes: none`.

**Fix:** Replaced Debian `nodejs` with NodeSource 22.x setup in the Dockerfile.

**File:** `Dockerfile`

```dockerfile
# Before
ffmpeg nodejs \

# After
ca-certificates curl gnupg \
# ... (NodeSource GPG key + repo setup) ...
nodejs \
```

### Gap 3: No `bgutil` service in docker-compose

**Problem:** The bot container had no sidecar to talk to for POT generation.

**Fix:** Added `bgutil` service to `deploy/docker-compose.yml` on `assistant_net`.

**File:** `deploy/docker-compose.yml`

```yaml
bgutil:
  image: brainicism/bgutil-ytdlp-pot-provider:latest
  restart: unless-stopped
  ports:
    - "127.0.0.1:4416:4416"
  networks:
    - assistant_net
```

### Gap 4: `yt-dlp` not in PATH inside container

**Problem:** Production code calls `yt-dlp` directly, but it lives at `/app/.venv/bin/yt-dlp` which was not in the container's `PATH`.

**Fix:** Added `ENV PATH="/app/.venv/bin:$PATH"` to Dockerfile.

**File:** `Dockerfile`

### Gap 5: No `mweb` player client in production code

**Problem:** `_ytdlp_base_flags()` only added `--remote-components ejs:github` and `--js-runtimes`. It did not set `--extractor-args youtube:player_client=mweb`, which is required for bgutil POT to work.

**Fix:** Added `mweb` client to `_ytdlp_base_flags()`.

**File:** `src/assistant/video/infrastructure/ytdlp_extractor.py`

### Gap 6: No `bgutil_base_url` in production code

**Problem:** The bgutil plugin defaults to `http://127.0.0.1:4416`. Inside a container, the sidecar is at `http://bgutil:4416` via Docker DNS.

**Fix:** Added `--extractor-args youtube:bgutil_base_url=http://bgutil:4416` to `_ytdlp_base_flags()`.

**File:** `src/assistant/video/infrastructure/ytdlp_extractor.py`

---

## Production Code Changes

### `src/assistant/video/infrastructure/ytdlp_extractor.py`

**Before:**
```python
def _ytdlp_base_flags() -> list[str]:
    flags: list[str] = ["--remote-components", "ejs:github"]
    node_path = _detect_node_path()
    if node_path:
        flags.extend(["--js-runtimes", f"node:{node_path}"])
    return flags
```

**After:**
```python
_BGUTIL_BASE_URL: str = "http://bgutil:4416"

def _ytdlp_base_flags() -> list[str]:
    flags: list[str] = [
        "--extractor-args", "youtube:player_client=mweb",
        "--extractor-args", f"youtube:bgutil_base_url={_BGUTIL_BASE_URL}",
        "--remote-components", "ejs:github",
    ]
    node_path = _detect_node_path()
    if node_path:
        flags.extend(["--js-runtimes", f"node:{node_path}"])
    return flags
```

### `Dockerfile`

**Added:**
```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
```

And NodeSource 22.x setup (see Gap 2).

### `pyproject.toml`

**Changed:**
```toml
# Before
"yt-dlp>=2024.0",

# After
"yt-dlp[default]>=2024.0",
"bgutil-ytdlp-pot-provider>=1.0",
```

### `deploy/docker-compose.yml`

**Added:** `bgutil` service (see Gap 3).

---

## Test Scripts Created

All tests are designed to run **inside the container** using `/app/.venv/bin/python3`.

### 1. `test_youtube_bot_detection.py`

**Purpose:** Validate the bot detection bypass stack (Node 22, EJS, bgutil, mweb, download, ffprobe).

**What it checks:**
- Node ≥ 22
- `yt_dlp_ejs` importable
- `bgutil_ytdlp_pot_provider` plugin present
- bgutil sidecar responding on `http://bgutil:4416`
- Downloads a small MP4 from YouTube
- Verifies file is valid media via ffprobe

**Usage:**
```bash
docker cp development/playground/test_youtube_bot_detection.py deploy-bot-1:/tmp/
docker exec -it deploy-bot-1 /app/.venv/bin/python3 /tmp/test_youtube_bot_detection.py
```

### 2. `test_full_transcription.py`

**Purpose:** Test the complete YouTube transcription pipeline (URL → transcript → note).

**What it does:**
- Detects platform from URL
- Calls `extract_video_transcript(url)` (the real production use case)
- For YouTube: tries `youtube-transcript-api` captions first, falls back to yt-dlp + ASR
- Formats result as Markdown note with YAML frontmatter
- Reports timing, service used, transcript preview

**Usage:**
```bash
docker cp development/playground/test_full_transcription.py deploy-bot-1:/tmp/
docker exec -it deploy-bot-1 /app/.venv/bin/python3 /tmp/test_full_transcription.py \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

**Tested URL:** `dQw4w9WgXcQ` (Rick Astley)
**Result:** ✅ 5.4s, `youtube-captions` path, 2,089 chars

### 3. `test_tiktok_transcription.py`

**Purpose:** Test TikTok transcription flow.

**What it does:**
- Same pipeline as YouTube but via `YtDlpPlatformAdapter`
- Audio extraction + Groq/Whisper fallback
- Includes troubleshooting for TikTok-specific errors

**Usage:**
```bash
docker cp development/playground/test_tiktok_transcription.py deploy-bot-1:/tmp/
docker exec -it deploy-bot-1 /app/.venv/bin/python3 /tmp/test_tiktok_transcription.py \
  "https://www.tiktok.com/@cinecut_888/video/7637823230027304206"
```

**Tested URL:** `@cinecut_888/video/7637823230027304206`
**Result:** ✅ 23.4s, `local-whisper-tiny` path (Groq rejected: 31MB > 25MB limit), 2,689 chars

**Key finding:** Groq's 25MB file size limit was hit. Local Whisper tiny handled it correctly.

### 4. `test_instagram_transcription.py`

**Purpose:** Test Instagram Reel transcription flow.

**What it does:**
- Same pipeline as TikTok
- Includes troubleshooting for Instagram login-wall errors

**Usage:**
```bash
docker cp development/playground/test_instagram_transcription.py deploy-bot-1:/tmp/
docker exec -it deploy-bot-1 /app/.venv/bin/python3 /tmp/test_instagram_transcription.py \
  "https://www.instagram.com/reel/DWEbXY-NTcq/"
```

**Tested URL:** `DWEbXY-NTcq`
**Result:** ✅ Successful extraction and transcription

---

## Container-First Rule File

Created `.github/copilot-instructions.md` to enforce container-first development:

- Never assume local execution
- Always assume Docker
- Verify in containers
- `/app/.venv/bin/` must be in PATH
- No hardcoded `127.0.0.1` for cross-container communication

This prevents the class of bugs where code works on the host but fails in the container.

---

## Local Whisper Accuracy Research

### Current Setup
- Model: `tiny` (39MB)
- Compute: `int8` (aggressive quantization)
- Device: CPU
- RAM at load: ~400MB

### Findings from TikTok Test
The Spanish-language TikTok video produced some garbled text:
- "andojo" (likely "ando yo")
- "lleme" (likely "allí me")
- "miyer" (likely "mujer")

This is consistent with `tiny` model limitations on non-English, rapid speech, and code-switching.

### Improvement Options (Ranked)

| Priority | Change | Effort | Impact | Risk |
|----------|--------|--------|--------|------|
| 1 | `tiny` → `small` model | 1 line | **~30% WER reduction** | RAM: ~1.2GB (may OOM on 2GB droplet) |
| 2 | `int8` → `int8_float16` | 1 line | Better precision | Minimal RAM increase |
| 3 | Enable `vad_filter=True` | 1 line | Less music/silence | Minimal |
| 4 | `beam_size=5` → `10` | 1 line | Marginal gain | Slower |
| 5 | Audio normalization | Small refactor | Low-Medium | Adds dependency |

**Recommendation:** `small` + `int8_float16` is the best bang-for-buck, but requires monitoring RAM usage on the 2GB droplet.

---

## Files Modified in This Session

| File | Change |
|------|--------|
| `pyproject.toml` | `yt-dlp` → `yt-dlp[default]`, added `bgutil-ytdlp-pot-provider` |
| `uv.lock` | Re-locked with new dependencies |
| `Dockerfile` | NodeSource 22.x, added `ffmpeg`, added `PATH` env |
| `deploy/docker-compose.yml` | Added `bgutil` service, fixed env var loading for Vikunja/MariaDB |
| `Makefile` | Created — production deployment commands with `--env-file .env` |
| `src/assistant/video/infrastructure/ytdlp_extractor.py` | Added `mweb` client, `bgutil_base_url`, `_BGUTIL_BASE_URL` constant |
| `.github/copilot-instructions.md` | Created — container-first development rules |
| `development/playground/test_youtube_bot_detection.py` | Created — bot detection bypass validation |
| `development/playground/test_full_transcription.py` | Created — full YouTube transcription flow |
| `development/playground/test_tiktok_transcription.py` | Created — TikTok transcription flow |
| `development/playground/test_instagram_transcription.py` | Created — Instagram Reel transcription flow |

---

## Verification Results

| Check | Result |
|-------|--------|
| Container build | ✅ 124s, no errors |
| Node version | ✅ v22.22.3 |
| `yt-dlp` in PATH | ✅ `/app/.venv/bin/yt-dlp` |
| `yt_dlp_ejs` importable | ✅ |
| bgutil plugin present | ✅ |
| bgutil sidecar reachable | ✅ HTTP 404 (server up) |
| YouTube download test | ✅ 11.8MB MP4, valid media |
| YouTube transcription test | ✅ 5.4s, captions path |
| TikTok transcription test | ✅ 23.4s, Whisper fallback |
| Instagram transcription test | ✅ Successful |
| Full test suite | ✅ 242 passed, 2 skipped |
| mypy type check | ✅ Clean (1 pre-existing error in config.py) |

---

## Open Questions / Future Work

1. **Whisper model upgrade:** Should we move from `tiny` to `small`? Requires RAM monitoring.
2. **Groq file size limit:** 25MB limit hits longer videos. Should we compress audio before upload?
3. **Instagram reliability:** ~40-60% of Reels require login. Is there a better approach?
4. **Queue persistence:** Jobs are in-memory only. Should they survive bot restarts?
5. **VAD filtering:** Should we enable `vad_filter=True` in faster-whisper to skip music/silence?

---

## Production Deployment

### Correct command

Always run from the **project root** with `--env-file .env`:

```bash
cd /path/to/telegram-assistant
docker compose --env-file .env -f deploy/docker-compose.yml up -d
```

Or use the `Makefile`:

```bash
make deploy
```

### Why `--env-file .env` is required

Docker Compose looks for `.env` in the directory containing the compose file (`deploy/`). Since `.env` lives at the project root (and is gitignored), the `--env-file .env` flag tells Compose to look in the current directory instead.

**Do NOT use a symlink** — it won't survive `git push`/`git pull` on the VPS.

### Vikunja env var fix

The `docker-compose.yml` was updated to:
- Load `.env` via `env_file: ../.env` for all services that need secrets
- Map `VIKUNJA_DB_PASSWORD` → `MARIADB_PASSWORD` for MariaDB 10.11 compatibility
- Map `VIKUNJA_DB_ROOT_PASSWORD` → `MARIADB_ROOT_PASSWORD` for MariaDB 10.11 compatibility

This ensures passwords are available both for `${...}` substitution (via `--env-file`) and for container env var loading (via `env_file`).

---

## Key Lesson

**The container is the source of truth.** A feature that works on the host (WSL, local dev machine) but fails in the container is broken. All verification must happen inside the container via `docker exec`. The `.github/copilot-instructions.md` file now enforces this rule for all future development.
