# Container-First Development Rule

## Always-On Constraint

This project is **exclusively containerized**. The bot, all services, and every runtime dependency run inside Docker containers. There is no "local" execution path.

## What This Means

**1. NEVER assume local execution**
- Do not assume `python`, `node`, `yt-dlp`, or any tool is available on the host PATH
- Do not assume host environment variables are accessible to the bot
- Do not assume host filesystem paths (e.g., `~/notes`, `/tmp`) are the same inside containers
- Do not assume `localhost` or `127.0.0.1` resolves to anything meaningful inside a container

**2. ALWAYS assume Docker**
- The bot runs in a container named `bot` on the `assistant_net` Docker network
- Services communicate via container names: `http://bgutil:4416`, `http://memory:8080`, etc.
- Python packages are in `/app/.venv/bin/`, not system PATH
- Node.js is installed in the container image, not on the host
- All runtime dependencies must be declared in `Dockerfile`, `pyproject.toml`, or `docker-compose.yml`

**3. VERIFY in containers**
- If a fix or feature involves a runtime dependency, test it from INSIDE the container
- Use `docker exec` to run verification scripts, not the host shell
- If a tool works on the host but not in the container, the container is the source of truth

**4. PATH and binaries**
- `/app/.venv/bin/` must be in PATH, or binaries must be referenced by absolute path
- `yt-dlp`, `python`, `node`, `ffprobe` — all live in `/app/.venv/bin/` or `/usr/bin/`
- Never assume `shutil.which("yt-dlp")` returns a path without verifying the container layout

**5. Network assumptions**
- Sidecars (bgutil, memory, searxng) are separate containers on `assistant_net`
- `127.0.0.1` inside the bot container is the bot itself, not the host
- Service discovery uses Docker DNS names: `bgutil`, `memory`, `searxng`, `vikunja`

## Why This Matters

The bot deploys to a VPS where the only runtime environment is Docker. Local WSL/development machine behavior is irrelevant for production correctness. A feature that works on the host but fails in the container is **broken**.

## Checklist Before Declaring Done

- [ ] Change tested from inside the running container via `docker exec`
- [ ] Dockerfile includes all new system dependencies
- [ ] `pyproject.toml` / `uv.lock` includes all new Python packages
- [ ] `docker-compose.yml` includes all new services
- [ ] No hardcoded `127.0.0.1` or `localhost` for cross-container communication
