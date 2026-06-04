# Research: YouTube Bot Detection Fallback — June 2, 2026

## Context

The video transcription feature works well on residential IPs but fails on the VPS with:

```
ERROR: [youtube] <video_id>: Sign in to confirm you're not a bot.
```

This is YouTube's bot detection triggered by datacenter IPs. The existing flow:

1. `youtube-transcript-api` for captions → often blocked too
2. `yt-dlp --extract-audio` → fails with bot error
3. Local Whisper fallback → never reached because audio extraction fails

## Proposed Solution (Pre-Validation)

Add a **Playwright-based fallback** that:
1. Launches headless Chromium when yt-dlp reports bot detection
2. Navigates to the YouTube video page
3. Extracts `ytInitialPlayerResponse` JSON from the page
4. Parses metadata and finds the audio stream URL from `adaptiveFormats`
5. Downloads the audio via `aiohttp`
6. Feeds it into the existing Groq → Whisper transcription chain

## What Was Implemented

### New Files

| File | Purpose |
|------|---------|
| `src/assistant/video/infrastructure/playwright_youtube_client.py` | `PlaywrightYouTubeClient` class — headless Chromium extraction |
| `tests/video/test_playwright_youtube_client.py` | 10 unit tests for parsing, URL finding, download mocking |
| `tests/video/test_ytdlp_bot_detection.py` | 10 parametrized tests for bot detection heuristic |

### Modified Files

| File | Change |
|------|--------|
| `src/assistant/video/infrastructure/ytdlp_extractor.py` | Added `is_bot_detection_error()` + `_BOT_DETECTION_PATTERNS` |
| `src/assistant/video/infrastructure/youtube_adapter.py` | Added `_extract_audio_with_fallback()` — tries yt-dlp, falls back to Playwright |
| `tests/video/test_youtube_adapter.py` | Added `TestExtractAudioWithFallback` (4 tests) |

### Dependencies
- `rebrowser-playwright` (already in `pyproject.toml`)
- `aiohttp` (already present)

## Critical Discovery (Manual Testing)

**The core assumption was wrong.** Before deploying, a scratch script (`/tmp/test_playwright_youtube.py`) was run against a real YouTube video (`dQw4w9WgXcQ`).

### Findings

| Assumption | Reality |
|------------|---------|
| `ytInitialPlayerResponse.streamingData.adaptiveFormats[].url` contains direct audio URLs | **No `url` key exists in any format.** Only metadata (itag, mimeType, bitrate, initRange, indexRange, etc.) |
| URLs might load dynamically after page load | **Still 0 URLs after 3+ second wait** |
| `serverAbrStreamingUrl` could be fetched with browser cookies | **Returns 403 Forbidden** even with the browser's own cookies and `fetch` API |
| `signatureCipher` or `cipher` fields might contain encoded URLs | **Neither field present** |

### Root Cause

YouTube has moved to **SABR** (Server-side Adaptive Bitrate Streaming). The `adaptiveFormats` array now contains only stream metadata. Actual media segments are fetched via a proprietary protocol through `serverAbrStreamingUrl` that the YouTube player handles internally. The `serverAbrStreamingUrl` itself is tied to the player's internal state and cannot be accessed externally.

### What This Means

The Playwright fallback **cannot extract audio** from YouTube pages. The `_find_audio_url()` method would raise:

```
AudioExtractionError("No audio stream URL found in player response")
```

on every real YouTube video. The user experience would be identical to before — a failure — just with a more verbose error message.

## Revert

All Playwright-related code was reverted:

| File | Action |
|------|--------|
| `playwright_youtube_client.py` | **Deleted** |
| `test_playwright_youtube_client.py` | **Deleted** |
| `youtube_adapter.py` | **Restored to original** (removed `_extract_audio_with_fallback`, Playwright imports) |
| `test_youtube_adapter.py` | **Restored to original** (removed `TestExtractAudioWithFallback`) |
| `run_video_tests.py` | **Deleted** (temporary helper) |
| `ubprocess` | **Deleted** (accidental file) |

### What Was Kept

| File | Reason |
|------|--------|
| `ytdlp_extractor.py` — `is_bot_detection_error()` | Useful for **logging and monitoring** — distinguishes bot errors from genuine failures |
| `test_ytdlp_bot_detection.py` | Tests for the heuristic |

## Validation After Revert

- **236 tests pass** (14 Playwright tests removed)
- **Ruff: clean** on remaining files
- **mypy: clean** on remaining files (pre-existing `config.py` error only)

---

## Continued Research — June 2, 2026

### Goal

Find a viable, production-ready approach to bypass YouTube bot detection on a datacenter VPS. The constraint is the same: personal Telegram assistant, Docker deployment, no browser required at runtime, no manual credential rotation.

---

## The Actual Mechanism — `po_token` (Proof of Origin Token)

The Playwright fallback failed because it targeted the wrong layer (stream URLs). The actual mechanism behind the "Sign in to confirm you're not a bot" error is now well-understood.

### What `po_token` is

YouTube requires a **Proof of Origin Token** (POT) to be sent alongside media format requests from most clients. Without it, requests to Google Video Server (GVS) return HTTP 403, or the player API returns a bot-check gate.

**Key facts** (sourced from yt-dlp wiki, June 2025 revision):

| Client | POT enforcement | Notes |
|--------|----------------|-------|
| `web` | GVS + Subs | Only SABR formats available |
| `mweb` | GVS | **Current recommended client** |
| `android` | GVS or Player | Account cookies not supported |
| `android_vr` | **Not required** | "Made for kids" unavailable |
| `web_embedded` | **Not required** | Only embeddable videos |
| `ios` | GVS or Player | Account cookies not supported |
| `tv` | Not required | All formats DRM'd without cookies |

- POTs are **bound to the video ID** — a new token is needed per video
- POTs have a limited lifespan (~6 hours by default in the bgutil cache, possibly longer in practice)
- A POT generated on one platform (web) cannot be used on another (android)
- BotGuard (the attestation system that issues POTs) runs JavaScript and produces a token that attests the request comes from a real browser session

### The yt-dlp official recommendation (wiki, Jun 2025)

> "If you are having issues with the default clients, it is suggested to use the `mweb` client with a PO Token."

---

## Candidate Approaches

### Option A — `bgutil-ytdlp-pot-provider` + `mweb` client

**Mechanism**: Run a Node.js HTTP server (Docker image: `brainicism/bgutil-ytdlp-pot-provider`) that runs BotGuard attestation via [BgUtils](https://github.com/LuanRT/BgUtils) — an open-source reimplementation of YouTube's BotGuard JavaScript. Install the `bgutil-ytdlp-pot-provider` pip plugin in the assistant container. The plugin hooks into yt-dlp's PO Token Provider framework and automatically fetches a fresh token per video from the sidecar.

**What it looks like operationally:**
```
docker run -d brainicism/bgutil-ytdlp-pot-provider  # port 4416
pip install bgutil-ytdlp-pot-provider
# yt-dlp then works normally, plugin handles POT automatically
yt-dlp --extractor-args "youtube:player_client=mweb" <URL>
```

**Pros:**
- Official recommendation from yt-dlp core maintainers
- Docker image available, fits existing docker-compose structure
- Pip-installable plugin, no code changes to yt-dlp invocation
- Token generation is automated and cached (6h TTL)
- Maintained by a yt-dlp maintainer (Brainicism) — actively kept up to date
- Community-tested and reported working

**Cons:**
- Requires a persistent sidecar service — new SPOF
- Each video adds ~100–500ms latency for token generation (HTTP call to sidecar)
- BgUtils is a reimplementation; if YouTube changes BotGuard, the library may lag
- Docs explicitly caution: "does not guarantee bypassing 403 errors"
- Node.js runtime in the container adds image size if not using the Docker image

---

### Option B — `android_vr` client (no POT required)

**Mechanism**: Use yt-dlp's `android_vr` player client, which YouTube currently does not require POT for.

```python
# In yt-dlp options:
'extractor_args': {'youtube': {'player_client': ['android_vr']}}
```

**Pros:**
- Zero new infrastructure
- No sidecar, no plugin, no latency overhead
- Works immediately

**Cons:**
- "Made for kids" videos unavailable (edge case for this assistant's use)
- **Explicitly ephemeral**: This is a known gap in YouTube's enforcement, not a stable solution. YouTube is rolling out POT enforcement progressively — `android_vr` will likely be enforced next
- Not recommended by yt-dlp as a long-term strategy
- No community guarantee of longevity

---

### Option C — YouTube account cookies

**Mechanism**: Export a YouTube account's session cookies (incognito session, never re-opened in the browser) and pass them to yt-dlp via `--cookies /path/to/cookies.txt`.

**Pros:**
- Simple to set up initially
- Raises the request rate limit (~2000 videos/hour vs ~300 for guest)

**Cons:**
- **Account ban risk is real and documented**: YouTube actively bans accounts used aggressively with yt-dlp's web clients (confirmed by yt-dlp issue #10085, 2024)
- Cookies expire and require manual refresh — cannot be automated reliably
- OAuth login no longer works (YouTube disabled it for yt-dlp)
- Not viable for an unattended VPS assistant

---

### Option D — Residential proxy routing

**Mechanism**: Route YouTube requests through a residential IP (e.g., personal home VPN via WireGuard, or commercial residential proxy service).

**Pros:**
- Bypasses the IP-level block entirely; no token management needed
- Completely transparent to the code

**Cons:**
- Using personal home VPN: latency is variable, home ISP becomes a dependency
- Commercial proxies: $50–200/month, complicates deployment, ToS concerns
- A commenter in yt-dlp #10085 tried WireGuard to home network and still got bot errors — suggests YouTube's detection is not purely IP-based (session fingerprinting too)
- Adds an external paid dependency with no fallback

---

## Poc-Architect Phase 1 — Critique

### Concerns

| # | Category | Concern |
|---|----------|---------|
| 1 | **Assumption** | BgUtils generates tokens that YouTube accepts. The docs explicitly warn "does not guarantee bypassing 403 errors". If Google detects that the BotGuard challenge was solved by a Node.js reimplementation rather than a real browser, it may specifically block these tokens. |
| 2 | **Gap** | We do not know whether `youtube-transcript-api` (the first step in the transcription chain) is also failing on the VPS. If it is, fixing yt-dlp alone is insufficient. |
| 3 | **Risk** | The bgutil sidecar is a new SPOF. If it crashes or is OOM-killed, all YouTube transcription requests fail silently (the bot detection falls through to the existing error path). |
| 4 | **Gap** | We have not verified yt-dlp's current version on the VPS. The bgutil plugin requires `yt-dlp >= 2025.05.22`. If the VPS is running an older version, the plugin won't load. |
| 5 | **Missing Alternative** | `web_embedded` client requires no POT and is available for embeddable videos. Most public YouTube videos are embeddable. This has not been evaluated. |
| 6 | **Unclear Decision** | The plan does not address whether `android_vr` should be used as a short-term patch while bgutil is being set up. |
| 7 | **Risk** | BotGuard is an evolving target. YouTube updated enforcement in late 2024 and mid-2025. The bgutil library lagged for weeks during the Mar 2025 enforcement change. During that window, transcription would fail. |
| 8 | **Assumption** | The VPS Docker deployment can run the bgutil sidecar container without memory or resource constraints that would kill it. A personal VPS may have tight memory limits. |

---

## Poc-Architect Phase 2 — Research

### Concern 1: Does BgUtils actually work?

Community evidence (bgutil-ytdlp-pot-provider repo, ~550 stars, 29 releases as of Mar 2026):
- The plugin has been maintained and updated to track YouTube enforcement changes
- It is recommended in the official yt-dlp PO Token Guide (written by yt-dlp maintainers)
- 29 releases over ~1.5 years shows active maintenance following YouTube changes
- The lag risk (concern 7) is real but the lag has historically been days to weeks, not months

**Status**: ✅ Confirmed working in community, with documented caveats about guarantees.

### Concern 2: Is `youtube-transcript-api` also blocked?

`youtube-transcript-api` uses YouTube's timedtext API (`/api/timedtext`) which is a different endpoint from the video player API. Transcripts are fetched as plain JSON/XML, not as media streams. The bot detection that yt-dlp hits is specifically for the **player API** and **GVS media requests**.

However, some users have reported `youtube-transcript-api` also failing on datacenter IPs when YouTube requires a login to view the video (age-restricted, etc.). For publicly accessible videos, the timedtext API is generally accessible.

**Status**: ⚠️ Unconfirmed for this specific VPS. Needs a quick test: call `youtube-transcript-api` directly from the VPS against a non-restricted public video. If it fails, the problem is more fundamental (IP-level block on all YouTube endpoints).

### Concern 5: `web_embedded` client

Per the PO Token enforcement table, `web_embedded` requires no POT. However: "Only embeddable videos available" — this is a content restriction, not a technical one. Embedding is disabled by video creators per video, and is disabled by default for some categories (music, kids). For a general-purpose assistant that users might ask to transcribe any video, this is an unreliable fallback. But it is a valid secondary fallback path.

**Status**: ✅ Viable as a secondary fallback (not primary) given content restriction.

### Concern 8: Memory footprint of bgutil sidecar

The `bgutil-ytdlp-pot-provider` Docker image is Node.js-based (or Deno). A minimal Node.js HTTP server with the BgUtils library typically uses ~80–150MB RSS at idle. This is significant on a 1GB VPS but acceptable on a 2GB+ VPS.

**Status**: ⚠️ Unconfirmed — depends on VPS resources. Needs verification.

---

## Poc-Architect Phase 3 — Revised Plan

### Recommended Approach: Option A with `android_vr` as staged rollout

**Stage 1 (immediate, minimal risk): `android_vr` client**

Change the yt-dlp extractor config to use `android_vr` as the primary client:
```python
'extractor_args': {'youtube': {'player_client': ['android_vr', 'web']}}
```
This is a one-line code change to `ytdlp_extractor.py`. No new infrastructure. Likely resolves the bot detection immediately.

**Downside**: Not stable long-term. Use it to unblock the feature and buy time.

**Stage 2 (medium-term, production-ready): bgutil sidecar + `mweb` client**

Add `brainicism/bgutil-ytdlp-pot-provider` to `docker-compose.override.yml` (not the base compose, so it's VPS-only). Install the pip plugin in the assistant container. Switch to `mweb` client.

This is the proper solution. Dependent on VPS memory headroom.

**Staged rollout rationale**: Stage 1 can be deployed now (zero infrastructure change). Stage 2 requires Dockerfile changes, docker-compose changes, and VPS testing. Decoupling them avoids blocking on infrastructure work while providing an immediate fix.

---

## Poc-Architect Phase 4 — Verify

Re-reading the plan:

| Check | Status |
|-------|--------|
| Goal clearly stated and measurable? | ✅ Eliminate bot detection on VPS for public YouTube videos |
| All decisions explained with rationale? | ✅ |
| Every assumption validated or mitigated? | ⚠️ One open — `youtube-transcript-api` status on VPS |
| Any "TBD" remaining? | ⚠️ VPS memory headroom for bgutil (verify before Stage 2) |

### Open Questions (blocking Stage 2 only)

1. **Is `youtube-transcript-api` already failing on the VPS?** Test: SSH into VPS, run the scratch test (Step 3 above). Then test `youtube-transcript-api` directly.
2. **VPS memory available?** Run `free -h` on VPS — need ~200MB free for bgutil sidecar with headroom.
3. **Current yt-dlp version on VPS?** Need `>= 2025.05.22` for bgutil plugin. Verify with `yt-dlp --version` in the running container.
4. **Node ≥ 22 available on VPS?** The VPS Docker image currently has Node v20 (Dockerfile confirmed). The Node upgrade (Gap 2 above) must be deployed before the scratch test is run on the VPS.

---

## Decisions & Rationale

| Decision | Choice Made | Alternative Considered | Reason Rejected |
|----------|-------------|------------------------|-----------------|
| Primary approach | Option A (bgutil + mweb) | Option B (android_vr only) | android_vr is not stable; bgutil is the officially recommended path |
| Rollout strategy | Staged (android_vr first) | bgutil immediately | bgutil requires infra changes + VPS validation; android_vr unblocks immediately |
| Account cookies | Rejected | Cookies + mweb | Account ban risk unacceptable for unattended assistant |
| Residential proxy | Rejected | Commercial proxy service | Cost + complexity disproportionate to use case |
| Playwright approach | Rejected (already validated) | Playwright audio URL extraction | SABR makes direct URL extraction impossible |

---

## Assumptions Table

| Assumption | Category | Risk if Wrong | Status |
|------------|----------|---------------|--------|
| `android_vr` client is not currently blocked on this VPS | Technical | Stage 1 doesn't work; skip to Stage 2 | ⚠️ Unconfirmed — quick to verify |
| bgutil generates tokens YouTube accepts | Technical | Stage 2 doesn't work; investigate alternative clients | ✅ Confirmed working — scratch test passed locally (June 3, 2026) |
| `youtube-transcript-api` (timedtext API) is not IP-blocked | Technical | Must also add POT/proxy for transcript API | ⚠️ Unconfirmed — needs VPS test |
| VPS has ~200MB free RAM for bgutil sidecar | Operational | Stage 2 causes memory pressure | ⚠️ Unconfirmed — `free -h` on VPS |
| yt-dlp in Docker image is >= 2025.05.22 | Technical | bgutil plugin fails to load | ✅ Confirmed — yt-dlp 2026.03.17 in `pyproject.toml` |
| Node.js in Docker image is >= 22 | Technical | EJS JS challenge solving fails; zero formats available | ❌ **Confirmed broken** — Dockerfile installs Node v20.19.2 via Debian apt; EJS requires ≥ 22 |
| `yt-dlp-ejs` is installed in the container | Technical | JS runtimes: none; zero formats available | ❌ **Confirmed missing** — `pyproject.toml` uses bare `yt-dlp`, not `yt-dlp[default]` |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| YouTube enforces POT on `android_vr` | High (historical pattern) | Stage 1 breaks | Stage 2 (bgutil) is ready to deploy |
| BgUtils lags a YouTube enforcement change | Medium | Days-to-weeks of Stage 2 failure | `android_vr` re-enabled as fallback via `player_client` list |
| bgutil sidecar OOM-killed | Low (if VPS has ≥2GB) | All transcription fails | Health-check in compose; restart policy |
| bgutil sidecar is down/not reachable | Low | yt-dlp falls back to default client (which may fail) | Log the failure explicitly via existing `is_bot_detection_error()` |

---

## Implementation Scope (Planning Only)

### Stage 1 — `android_vr` client patch
**Files to change**: `src/assistant/video/infrastructure/ytdlp_extractor.py`
**Change**: Add `player_client=['android_vr', 'web']` to the yt-dlp options dict
**Tests**: Existing `test_ytdlp_bot_detection.py` remains valid; may add a config unit test
**Risk**: Low

### Stage 2 — bgutil sidecar + `mweb` client
**Files to change**:
- `deploy/docker-compose.override.yml` — add `bgutil-provider` service
- `Dockerfile` — add `pip install bgutil-ytdlp-pot-provider`
- `src/assistant/video/infrastructure/ytdlp_extractor.py` — switch to `mweb` client; configure bgutil base URL via env var
- Optionally: `deploy/docker-compose.yml` or `.env` — add `BGUTIL_BASE_URL` env var

**Pre-conditions before Stage 2**:
- [ ] Verify VPS yt-dlp version ≥ 2025.05.22
- [ ] Verify VPS has ≥ 200MB free RAM
- [ ] Stage 1 is deployed and confirmed working (validates the rest of the fix chain)
- [ ] Scratch test below passes on the VPS

### Scratch Test — Validate Option A Before Coding Stage 2

Do not write any production code for Stage 2 until this test passes manually on the VPS. This validates that the bgutil sidecar generates tokens YouTube accepts in this environment.

**Step 1 — Start the bgutil sidecar:**
```bash
docker run -d -p 4416:4416 --name bgutil-test brainicism/bgutil-ytdlp-pot-provider
# Verify it is responding:
curl http://localhost:4416/
```
Expected: any HTTP response (404 on `/` is normal — there is no root route).

**Step 2 — Install the plugin and EJS package:**
```bash
pip install bgutil-ytdlp-pot-provider yt-dlp-ejs
```

**Step 3 — Test yt-dlp with `mweb` client, EJS, and node path explicitly set:**
```bash
yt-dlp \
  --extractor-args "youtube:player_client=mweb" \
  --js-runtimes "node:$(which node)" \
  --verbose \
  --get-url \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```
Note: `--js-runtimes` must point to **Node ≥ 22**. Verify with `node --version` first. The `$(which node)` expansion handles both `/usr/bin/node` and version-manager paths.

**Success criteria — all must be true before proceeding to Stage 2 coding:**
- [x] Exit code 0 ✅ (confirmed June 3, 2026 — local dev machine)
- [x] No "Sign in to confirm you're not a bot" in stderr ✅
- [x] A valid `googlevideo.com` URL is printed to stdout ✅
- [x] Verbose output shows bgutil plugin was invoked to generate a PO Token ✅
- [x] Verbose output shows `[jsc:node] Solving JS challenges using node` ✅

**This test must also pass on the VPS before Stage 2 is deployed to production.** The local result confirms the mechanism works; the VPS result confirms the environment is correctly configured.

> ⚠️ **Critical finding from local test**: the test only passes when both `yt-dlp-ejs` is installed AND a valid `--js-runtimes node:...` path (Node ≥ 22) is supplied. Without either, yt-dlp reports `JS runtimes: none`, signature/n-challenge solving fails, and zero video/audio formats are returned — the same symptom as having no bgutil at all. Both gaps must be fixed in the Dockerfile and `pyproject.toml` before rebuilding the container image.

**Failure analysis:**

| What you see | What it means | What to do |
|---|---|---|
| "Sign in to confirm" despite plugin loaded | Token rejected by YouTube, or plugin not connecting to sidecar | Check `BGUTIL_PROXY_PORT` env var; check plugin version |
| Connection refused on port 4416 | Sidecar not started or mapped to different port | Verify `docker ps` and port binding |
| Plugin import error / not found | `pip install` failed or wrong Python env | Verify env; check `pip show bgutil-ytdlp-pot-provider` |
| Bot error with plugin loaded and sidecar running | bgutil lagging a YouTube enforcement change | Check plugin GitHub issues for recent reports |

If the test fails, **do not proceed to Stage 2**. Investigate the failure or fall back to Stage 1 (`android_vr`) only.

---

### Pre-existing EJS / Node.js Gaps — Fix in This Phase

Discovered during the scratch test: `_ytdlp_base_flags()` in `ytdlp_extractor.py` already tries to solve YouTube's n/sig challenge (URL parameter decryption — a separate problem from BotGuard/POT). But the code is broken in two ways. Both must be fixed before the container is rebuilt and deployed.

---

#### Gap 1 — `yt-dlp-ejs` is missing from the container

**What this is:**

`pyproject.toml` currently declares `"yt-dlp>=2024.0"`. This installs only the core yt-dlp Python package. It does NOT install `yt-dlp-ejs` — a separate companion package that contains the actual JavaScript challenge solver scripts (the code that decrypts YouTube's n-parameter and signature).

**Why this matters:**

Without `yt-dlp-ejs`, yt-dlp has no challenge solver scripts at all. The `--remote-components ejs:github` flag in `_ytdlp_base_flags()` is a fallback that tells yt-dlp to download these scripts from GitHub at runtime. This is unreliable: it requires outbound GitHub access on every cold start, adds latency, and fails entirely if GitHub is unreachable or rate-limits the request.

**The exact failure mode (from the scratch test):**

When `yt-dlp-ejs` is NOT installed, yt-dlp's debug output shows:
```
[debug] Optional libraries: certifi-2026.05.20, requests-2.34.2, ... (no yt_dlp_ejs)
```

Then, even with a valid JS runtime available, yt-dlp reports:
```
[debug] [youtube] [jsc] JS Challenge Providers: bun (unavailable), deno (unavailable), node (unavailable), quickjs (unavailable)
```

The result: the n/sig challenge is never solved. YouTube either throttles the download to ~50 kbps or rejects the URL entirely. The user sees the same "bot detection" symptom even though the real problem is missing solver scripts.

**The fix:**

Change `pyproject.toml` from:
```toml
"yt-dlp>=2024.0"
```
to:
```toml
"yt-dlp[default]>=2024.0"
```

The `[default]` extras group explicitly includes `yt-dlp-ejs` as a pinned, version-matched dependency. It gets installed into the container image at build time — no runtime downloads needed.

---

#### Gap 2 — Node.js v20 in the container; EJS requires Node ≥ 22

**What this is:**

The Dockerfile installs `nodejs` via `apt-get` from Debian bookworm's default apt repository. **Confirmed by building the image and running `node --version` inside it on June 3, 2026**: the container has **Node v20.19.2**.

EJS (the External JS Script system) has a hard minimum requirement of **Node ≥ 22**. When yt-dlp scans for available JS runtimes, it checks the version of each binary found. If the version is below the minimum, that runtime is silently skipped.

**Why this matters:**

Even after fixing Gap 1 (installing `yt-dlp-ejs`), the container still cannot solve JS challenges because the only Node binary available is v20 — below EJS's minimum. yt-dlp will report `JS runtimes: none` and the exact same failure occurs.

**The exact failure mode (from the scratch test):**

With `yt-dlp-ejs` installed but Node v20 as the only runtime, yt-dlp's debug output shows:
```
[debug] JS runtimes: none
```

And then:
```
WARNING: [youtube] dQw4w9WgXcQ: Signature solving failed: Some formats may be missing.
WARNING: [youtube] dQw4w9WgXcQ: n challenge solving failed: Some formats may be missing.
WARNING: Only images are available for download.
ERROR: [youtube] dQw4w9WgXcQ: Requested format is not available.
```

Zero video or audio formats are returned. The download fails completely.

**Contrast with the working case:**

When Node ≥ 22 is explicitly provided (via `--js-runtimes node:/path/to/node24`), the output shows:
```
[debug] JS runtimes: node-24.14.0
[debug] [youtube] [jsc:node] Solving JS challenges using node
[debug] [youtube] [jsc:node] Using challenge solver lib script v0.8.0
```

And a valid `googlevideo.com` download URL is returned.

**The fix:**

Replace the `apt-get nodejs` line in the Dockerfile with the NodeSource 22.x setup. NodeSource is the official Node.js distribution channel that provides current LTS versions via apt. The change is:

```dockerfile
# BEFORE (Debian repo — gives Node v20)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ... nodejs ...

# AFTER (NodeSource repo — gives Node 22 LTS)
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs ...
```

This is a single-section change in the Dockerfile. No other part of the image is affected.

**Benefits of this change:**

| Benefit | Explanation |
|---------|-------------|
| EJS works | Node 22 is the minimum EJS accepts; yt-dlp can now solve n/sig challenges |
| yt-dlp audio downloads work | Without JS solving, all formats are filtered out; with it, valid `googlevideo.com` URLs are returned |
| No runtime GitHub downloads | `--remote-components ejs:github` fallback is no longer needed; everything is baked into the image |
| Security | NodeSource GPG-signed packages vs Debian repo; explicit key pinning in the Dockerfile |
| Future-proof | Node 22 is the current LTS; EJS may raise minimum again; NodeSource makes upgrading to 24/26 trivial |

**Drawbacks of this change:**

| Drawback | Explanation |
|----------|-------------|
| Larger Dockerfile RUN layer | The NodeSource setup adds `curl`, `gpg`, keyring creation, and a second `apt-get update` — ~5–10MB extra in the layer, a few seconds longer build time |
| External dependency at build time | The build fetches a GPG key and apt source from `deb.nodesource.com` — if NodeSource is down, the build fails. Mitigation: the key and source can be vendored into the repo if needed |
| Node 22 is newer than Debian's default | If any other tool in the image relied on Debian's specific Node v20 patches or ABI, it could break. Verified: the only Node consumer in the image is yt-dlp's EJS system, which explicitly requires ≥22 |
| One more apt source to trust | Adding a third-party apt source increases supply-chain surface area. Mitigation: NodeSource is the official distribution channel used by the Node.js project; GPG key is pinned |

---

#### Why both gaps must be fixed together

These two gaps are **independent but both required**:

| Gap | What it provides | What fails if missing |
|-----|------------------|----------------------|
| Gap 1 (`yt-dlp-ejs`) | The JS challenge solver scripts | yt-dlp has no code to run, even with a valid runtime |
| Gap 2 (Node ≥ 22) | A JS runtime that EJS accepts | yt-dlp has scripts but no engine to execute them |

Fixing only one leaves the system in the exact same broken state: `JS runtimes: none`, no formats available, download fails. Both must be deployed together as part of the standard push → VPS pull → rebuild cycle.

---

## Lesson Learned

**Validate assumptions on real systems before writing production code.** A 5-minute scratch script against a real YouTube page would have revealed the SABR issue immediately, saving the entire implementation effort.

## Remaining Work (Not Started)

**Research actual working solutions for YouTube bot detection on VPS/datacenter IPs.**

This conversation ended before researching what approaches actually work. The following avenues need investigation:

1. **PoToken + Visitor Data** — YouTube's current anti-bot mechanism. Requires generating valid proof-of-origin tokens via headless browser JS execution. `youtube-transcript-api` has been updated to support this.

2. **`--cookies-from-browser`** — yt-dlp can read cookies from Chrome/Firefox. Requires a real logged-in session on the VPS (impractical) or periodic cookie export from a local machine.

3. **Residential proxy / VPN** — Route traffic through a residential IP. Costs money, adds latency, requires proxy management.

4. **Third-party services** — Use APIs like `yt.lemnoslife.com`, `returnyoutubedislikeapi.com`, or similar that proxy YouTube data. Reliability and rate limits unknown.

5. **yt-dlp extractor args** — Try `--extractor-args youtube:player_client=web` or other client configurations that may bypass bot detection.

6. **Accept the limitation** — Document that YouTube transcription requires a residential IP and suggest users run the bot locally or use a VPN.

**Next step:** Run experiments with yt-dlp flags, check `youtube-transcript-api` PoToken support, and research community solutions (GitHub issues, Reddit, yt-dlp documentation) for what actually works in 2026.
