# Phase 8: Code Execution Sandbox (Optional)

**Goal:** The agent can execute short Python or shell snippets in an isolated Docker container and return the output.  
**Priority:** Lowest. Build this only after Phases 0–7 are verified working. Skip entirely if not needed.  
**Prerequisites:** Phase 7 complete.  
**Output:** "Calculate the compound interest on €5000 at 4% over 10 years" → agent runs Python, returns the result.

---

## Critique Review

**What could go wrong?**
- Code execution escaping the container: mitigated by running code in a separate `sandbox` container with no network access, no volume mounts, and resource limits (`mem_limit`, `cpus`)
- Infinite loops locking up the bot: enforce a hard timeout (5 seconds) on code execution
- Output too long: cap returned output at 2000 characters
- User injecting OS commands: only allow Python execution via `exec()`; shell execution is opt-in and disabled by default

**Design principle:** The sandbox is a separate Docker container that the bot triggers via a minimal HTTP REST wrapper. The bot container never executes arbitrary code directly.

**This is the highest-risk phase** from a security perspective. Do not implement unless you understand the isolation model.

---

## Architecture

```
bot container
    │
    │ HTTP POST /run { code: "...", lang: "python" }
    ▼
sandbox container (isolated)
    - no network (network_mode: none)
    - no volume mounts
    - mem_limit: 128m
    - cpus: 0.5
    - runs code in subprocess with timeout
    - returns stdout/stderr
```

The sandbox container exposes only an internal Docker network endpoint — not accessible from outside the VPS.

---

## Files to Create

```
src/assistant/
├── sandbox/
│   ├── __init__.py
│   ├── application/
│   │   └── execute_code.py
│   └── infrastructure/
│       └── sandbox_client.py
├── agent/
│   └── tools/
│       └── sandbox_tools.py
sandbox/
├── Dockerfile.sandbox      (minimal Python image with execution wrapper)
└── server.py               (FastAPI: POST /run → subprocess exec → return output)
```

---

## Implementation

### Sandbox Server (`sandbox/server.py`)

```python
"""Minimal code execution server. Runs in isolated Docker container."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import sys

app = FastAPI()

MAX_OUTPUT_CHARS = 2_000
EXEC_TIMEOUT_SECONDS = 5


class RunRequest(BaseModel):
    code: str
    lang: str = "python"  # only "python" supported in Phase 8


class RunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int


@app.post("/run", response_model=RunResponse)
async def run_code(req: RunRequest) -> RunResponse:
    if req.lang != "python":
        raise HTTPException(status_code=400, detail="Only 'python' is supported")

    try:
        result = subprocess.run(
            [sys.executable, "-c", req.code],
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return RunResponse(stdout="", stderr="Execution timed out (5s limit)", exit_code=1)

    return RunResponse(
        stdout=result.stdout[:MAX_OUTPUT_CHARS],
        stderr=result.stderr[:MAX_OUTPUT_CHARS],
        exit_code=result.returncode,
    )
```

### Sandbox Dockerfile (`sandbox/Dockerfile.sandbox`)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install fastapi uvicorn
COPY sandbox/server.py ./server.py
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8090"]
```

### Add to `docker-compose.yml`

```yaml
  sandbox:
    build:
      context: .
      dockerfile: sandbox/Dockerfile.sandbox
    restart: unless-stopped
    network_mode: none           # no network access from sandbox
    mem_limit: 128m
    cpus: 0.5
    # sandbox only reachable via internal network — not exposed externally
```

> **Note:** `network_mode: none` means the sandbox cannot reach the internet or the internal Docker network. The bot must communicate with it via a shared volume or sidecar pattern. An alternative: use a dedicated `sandbox_net` that only `bot` and `sandbox` share, with no external routing. Evaluate which approach your Docker version supports.

### Sandbox Client

```python
# sandbox/infrastructure/sandbox_client.py
import httpx
from assistant.shared.exceptions import InfrastructureError
import structlog

logger = structlog.get_logger()

SANDBOX_URL = "http://sandbox:8090"
SANDBOX_TIMEOUT_SECONDS = 10


class SandboxClient:
    async def execute(self, code: str) -> str:
        """Execute Python code in the isolated sandbox and return output."""
        try:
            async with httpx.AsyncClient(timeout=SANDBOX_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{SANDBOX_URL}/run",
                    json={"code": code, "lang": "python"},
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("sandbox_request_failed", error=str(e))
            raise InfrastructureError("Code execution sandbox unavailable") from e

        data = response.json()
        if data["exit_code"] != 0:
            return f"Error (exit {data['exit_code']}):\n{data['stderr']}"
        return data["stdout"] or "(no output)"
```

### Sandbox Tool

```python
# agent/tools/sandbox_tools.py
from pydantic_ai import Agent, RunContext
from assistant.sandbox.infrastructure.sandbox_client import SandboxClient
import structlog

logger = structlog.get_logger()
_sandbox = SandboxClient()


def register_sandbox_tools(agent: Agent) -> None:

    @agent.tool
    async def run_python(ctx: RunContext, code: str) -> str:
        """Execute a Python code snippet and return the output.

        Use for calculations, data processing, or anything that needs precise computation.
        The sandbox has no internet access and no file system access.

        Args:
            code: Valid Python code. Use print() to produce output.
        """
        logger.info("run_python_tool", code_preview=code[:100])
        return await _sandbox.execute(code)
```

---

## Security Checklist

Before enabling this phase in production:

- [ ] Sandbox container has `network_mode: none` or an isolated network with no external routing
- [ ] Sandbox container has `mem_limit: 128m` enforced in Compose
- [ ] Execution timeout is enforced at 5 seconds maximum
- [ ] Output is capped at 2000 characters
- [ ] Sandbox Dockerfile does not install any sensitive packages or copy secrets
- [ ] The sandbox service is not accessible from outside the VPS (no public port binding)
- [ ] Bot validates that `code` parameter is a non-empty string before calling (already done by Pydantic AI type checking)

---

## Verification

- [ ] Sandbox container starts and `curl http://sandbox:8090/run -d '{"code":"print(1+1)"}' -H 'Content-Type: application/json'` returns `{"stdout":"2\n","stderr":"","exit_code":0}` from inside the bot container
- [ ] "Calculate 2^32" → bot returns `4294967296`
- [ ] An infinite loop (`while True: pass`) times out after 5 seconds with a clear error message
- [ ] Code that tries to import `os` and read files fails or returns empty (no file system in sandbox)
- [ ] `uv run mypy src/` passes with zero errors

---

## Phase Review

Run this section after completing all implementation steps and before declaring the phase done.

### 1. Plan vs Implementation

For each file listed under **Files to Create**, confirm it exists and matches its stated purpose. Mark each as ✅ created / ⚠️ partial / ❌ missing. Note any deviations from the plan and why they were made.

### 2. Python Code Quality

Verify every new file against the `senior-engineer-python` checklist:

- [ ] All functions have complete type hints (parameters + return type)
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] No `except Exception: pass` — sandbox HTTP errors caught specifically and logged
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT — only WHY
- [ ] No `print()` in production paths — structlog used throughout
- [ ] No secrets in source code or logs
- [ ] All imports at top of file, grouped: stdlib → third-party → local → relative
- [ ] `uv run mypy src/` passes with zero errors

### 3. Architecture Compliance

Verify the layer dependency rules from `architecture/overview.md`:

- [ ] `sandbox/` is a **Supporting bounded context** — application use case + infrastructure HTTP client; no domain entities
- [ ] Bot container never executes arbitrary code directly — all execution goes through the sandbox HTTP API
- [ ] Sandbox container has `network_mode: none` — cannot make outbound requests
- [ ] Sandbox container has no volume mounts — no access to notes, SQLite, or secrets
- [ ] `mem_limit` and `cpus` resource limits set in Compose service definition
- [ ] Execution timeout (5 seconds) enforced in sandbox subprocess, not in the bot container
- [ ] Output cap (2000 characters) enforced in application layer before returning to agent

### 4. Developer Summary

Write a sequential plain-language explanation of what was built in this phase:

1. What existed before this phase (inputs / prerequisites)
2. Each component added, in the order it was built, and what role it plays
3. How the components connect to each other
4. What a developer would observe if the phase is working correctly
5. What this phase completes in the overall system
