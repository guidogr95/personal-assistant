# ADR-007: Docker Compose for Deployment Portability

**Date:** 2025  
**Status:** Accepted

## Context

The stack has 6+ services (bot, memory, searxng, vikunja, vikunja_db, syncthing). It must run identically in two environments: local development on Windows via WSL2, and a Linux VPS in production. Development requires live code reloading without container rebuilds. Production requires automatic restarts on crash.

A critical performance constraint exists: Docker on Windows uses a Linux VM (WSL2). When Docker mounts a path from the Windows filesystem (`/mnt/c/...`) into a container, every file operation crosses the WSL2-to-Windows filesystem boundary, degrading I/O by 5–20x. This makes watching for file changes sluggish and application startup slow.

## Decision

Use **Docker Compose v2** with two files:

- `deploy/docker-compose.yml` — production definition (image builds, volumes, restart policies, env_file)
- `deploy/docker-compose.override.yml` — development overrides only (bind-mount `./src` for live reload, expose extra debug ports)

**WSL2 rule (mandatory, enforced by convention + documentation):**
The project must be cloned inside the WSL2 filesystem (`~/assistant/`), not in `/mnt/c/` or any Windows-side path. All Docker volume mounts originate from within WSL2. This rule is documented in:
- `README.md`
- `spec.md` (constraints table)
- `local_code/docs/telegram-assistant/implementation/phase-0-bootstrap.md`

Override pattern for dev:
```yaml
# docker-compose.override.yml
services:
  bot:
    volumes:
      - ./src:/app/src      # live reload without rebuild
    command: ["python", "-m", "watchfiles", "python src/assistant/main.py"]
    ports:
      - "5678:5678"         # debugpy remote attach
```

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| **Kubernetes (K3s)** | Overkill for a personal single-user stack; adds 300MB+ base overhead; operational complexity far exceeds the benefit |
| **Ansible playbooks** | Manages host-level config only; doesn't orchestrate service dependencies, networking, or volumes as cleanly as Compose for a multi-container app |
| **systemd units per service** | No service dependency graph; no internal DNS; no shared volumes without manual management; not portable across distros |
| **Single monolithic container** | All services in one container defeats isolation; complicates upgrades and restarts; can't update Vikunja without restarting the bot |

## Consequences

- All Docker commands use: `docker compose -f deploy/docker-compose.yml [-f deploy/docker-compose.override.yml] ...`
- Production: omit the override file
- Development: Docker Compose automatically merges `docker-compose.override.yml` when both files exist in the same directory; alternatively invoke both with `-f`
- The WSL2 rule **must be enforced** manually — there is no technical enforcement. Developers cloning to `/mnt/c/` will see slow I/O and are responsible for the mistake
- If migrating to a different VPS, `docker compose pull && docker compose up -d` is all that is needed after updating `.env`
