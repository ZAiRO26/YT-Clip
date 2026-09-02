@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo       ClipForge AI v2 — 1-Click Studio Launcher
echo ===================================================
echo.

:: Ensure we are in the repository root
cd /d "%~dp0"

:: 1. Check & Start Docker Infrastructure
echo [1/5] Starting Docker Infrastructure (Postgres 16, Redis 7, MinIO S3)...
docker compose -f infra/docker-compose.yml up -d
if %errorlevel% neq 0 (
    echo [WARNING] Docker compose failed to start or is already running. Continuing...
)

:: 2. Run Database Migrations
echo [2/5] Running Alembic Database Migrations...
uv run alembic -c packages/python-core/alembic.ini upgrade head

:: 3. Check Kokoro TTS Offline Models
echo [3/5] Verifying Kokoro TTS Offline Models...
if not exist "models\kokoro\kokoro-v0_19.onnx" (
    echo Downloading Kokoro models with SHA-256 validation...
    uv run python scripts/download_kokoro_models.py
) else (
    echo Kokoro TTS model assets verified.
)

:: 4. Start FastAPI Backend & Celery Worker
echo [4/5] Launching Backend Services...
start "ClipForge AI — API (Port 8000)" cmd /k "set PYTHONPATH=apps/api;packages/python-core && uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload"

start "ClipForge AI — Celery Worker (7 Queues)" cmd /k "set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -Q default,ingest,analysis,llm,editorial,render,qa -P solo --loglevel=info"

:: 5. Start Next.js Frontend Web Studio
echo [5/5] Launching Next.js Web Studio (Port 3000)...
start "ClipForge AI — Web Studio (Port 3000)" cmd /k "pnpm --filter @clipforge/web dev"

echo.
echo ===================================================
echo        ClipForge AI v2 is Running Successfully!
echo ===================================================
echo.
echo  🌐 Web Studio:      http://localhost:3000
echo  ⚡ API & Docs:      http://localhost:8000/docs
echo  🗄️ PostgreSQL:      localhost:5433
echo  🔴 Redis:           localhost:6379
echo  🪣 MinIO S3 UI:     http://localhost:9001 (User: minioadmin / Pass: minioadmin)
echo.
echo  Press any key or close this window to exit launcher.
echo  (The services will remain running in their respective windows).
echo ===================================================
pause >nul
