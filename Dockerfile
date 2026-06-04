FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system packages required by Playwright Chromium on Debian slim.
# Using manual apt-get instead of `playwright install --with-deps` because the
# --with-deps path assumes Ubuntu package names (e.g. ttf-unifont) which do not
# exist on Debian bookworm.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libx11-xcb1 fonts-liberation \
    ffmpeg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create whisper model cache directory with open permissions so the app can
# download model weights on first run regardless of the runtime user ID.
RUN mkdir -p /data/whisper-models && chmod 777 /data/whisper-models

# Install dependencies first (separate layer for caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Install Playwright Chromium browser binary only — system deps installed above.
RUN uv run python -m rebrowser_playwright install chromium

# Copy source
COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "python", "-m", "assistant.main"]
