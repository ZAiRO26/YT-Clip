#!/usr/bin/env bash
# ===================================================
#       ClipForge AI v2 — 1-Click Studio Launcher
# ===================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================================="
echo "       ClipForge AI v2 — 1-Click Studio Launcher"
echo "==================================================="
echo ""

# 1. Start Docker Infrastructure
echo "[1/5] Starting Docker Infrastructure (Postgres 16, Redis 7, MinIO S3)..."
docker compose -f infra/docker-compose.yml up -d postgres redis minio

# 2. Run Database Migrations
echo "[2/5] Running Alembic Database Migrations..."
uv run alembic -c packages/python-core/alembic.ini upgrade head

# 3. Check Kokoro TTS Offline Models
echo "[3/5] Verifying Kokoro TTS Offline Models..."
if [ ! -f "models/kokoro/kokoro-v0_19.onnx" ]; then
    echo "Downloading Kokoro models with SHA-256 validation..."
    uv run python scripts/download_kokoro_models.py
else
    echo "Kokoro TTS model assets verified."
fi

# 4. Start Backend Services
echo "[4/5] Launching Backend Services..."
export PYTHONPATH="apps/api:packages/python-core:$PYTHONPATH"
uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

export PYTHONPATH="apps/worker:packages/python-core:$PYTHONPATH"
uv run celery -A clipforge_core.celery_app worker -Q default,ingest,analysis,llm,editorial,render,qa -P solo --loglevel=info &
CELERY_PID=$!

# 5. Start Next.js Web Studio
echo "[5/5] Launching Next.js Web Studio (Port 3000)..."
pnpm --filter @clipforge/web dev &
WEB_PID=$!

echo ""
echo "==================================================="
echo "        ClipForge AI v2 is Running Successfully!"
echo "==================================================="
echo ""
echo "  🌐 Web Studio:      http://localhost:3000"
echo "  ⚡ API & Docs:      http://localhost:8000/docs"
echo "  🗄️ PostgreSQL:      localhost:5433"
echo "  🔴 Redis:           localhost:6379"
echo "  🪣 MinIO S3 UI:     http://localhost:9001 (minioadmin / minioadmin)"
echo ""
echo "  Press Ctrl+C to terminate all services."
echo "==================================================="

trap "kill $API_PID $CELERY_PID $WEB_PID 2>/dev/null || true; exit" INT TERM
wait
