# ============================================
# ClipForge AI — Celery Worker Dockerfile
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (FFmpeg, ImageMagick, fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    imagemagick \
    fonts-noto \
    fonts-deva \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick security policy for video text rendering
RUN sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<!-- <policy domain="path" rights="none" pattern="@\*" -->/' /etc/ImageMagick-6/policy.xml || true

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy workspace configuration and packages
COPY pyproject.toml uv.lock ./
COPY packages/python-core ./packages/python-core
COPY apps/worker ./apps/worker

# Sync dependencies using uv
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install --system -e ./packages/python-core -e ./apps/worker

ENV PYTHONPATH="/app/apps/worker:/app/packages/python-core"

CMD ["celery", "-A", "app.celery_app", "worker", "-Q", "default,download,transcribe,select,crop,caption", "-c", "2", "-P", "solo", "--loglevel=info"]
