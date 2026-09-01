# ============================================
# ClipForge AI — API Service Dockerfile
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (FFmpeg for probes and media metadata)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy workspace configuration and packages
COPY pyproject.toml uv.lock pnpm-workspace.yaml* ./
COPY packages/python-core ./packages/python-core
COPY apps/api ./apps/api

# Sync dependencies using uv
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install --system -e ./packages/python-core -e ./apps/api

ENV PYTHONPATH="/app/apps/api:/app/packages/python-core"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "apps/api", "--host", "0.0.0.0", "--port", "8000"]
