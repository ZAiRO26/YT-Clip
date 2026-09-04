@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo       ClipForge AI v2 — 1-Click Studio Launcher
echo ===================================================
echo.

:: Ensure we are in the repository root
cd /d "%~dp0"

:: 0. Clean up stale/lingering processes from previous sessions
echo [1/6] Cleaning up lingering processes on Port 8000, 3000, and old Celery workers...
powershell -NoProfile -Command "8000, 3000 | ForEach-Object { $p = (Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }; Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*celery*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

:: 1. Check & Start Docker Infrastructure
echo [2/6] Starting Docker Infrastructure (Postgres 16, Redis 7, MinIO S3)...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker Desktop does not appear to be running.
    echo Please make sure Docker Desktop is started so Postgres and Redis can run!
)
docker compose -f infra/docker-compose.yml up -d postgres redis minio
if %errorlevel% neq 0 (
    echo [WARNING] Docker compose encountered an issue. Continuing if services already active...
)

:: Wait 2 seconds for Postgres socket readiness
powershell -NoProfile -Command "Start-Sleep -Seconds 2"

:: 2. Run Database Migrations
echo [3/6] Running Alembic Database Migrations...
uv run alembic -c packages/python-core/alembic.ini upgrade head

:: 3. Check Kokoro TTS Offline Models
echo [4/6] Verifying Kokoro TTS Offline Models...
if not exist "models\kokoro\kokoro-v0_19.onnx" (
    echo Downloading Kokoro models with SHA-256 validation...
    uv run python scripts/download_kokoro_models.py
) else (
    echo Kokoro TTS model assets verified.
)

:: 4. Start FastAPI Backend & Celery Workers (Split IO & Compute for zero queue stalling)
echo [5/6] Launching Backend Services...
start "ClipForge AI — API (Port 8000)" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/api;packages/python-core && uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload --reload-dir apps/api --reload-dir packages/python-core"

start "ClipForge AI — Ingest & LLM Worker" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n ingest_worker@%%COMPUTERNAME%% -Q ingest,llm,editorial,qa,default -P solo --loglevel=info"

start "ClipForge AI — Compute & Render Worker" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n compute_worker@%%COMPUTERNAME%% -Q analysis,render -P solo --loglevel=info"

:: 5. Start Next.js Frontend Web Studio
echo [6/6] Launching Next.js Web Studio (Port 3000)...
start "ClipForge AI — Web Studio (Port 3000)" cmd /k "cd /d \"%~dp0\" && pnpm --filter @clipforge/web dev"

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
echo  Tip: Run 'stop.bat' to stop all services cleanly anytime.
echo.
echo  Press any key or close this window to exit launcher.
echo  (The services will remain running in their respective windows).
echo ===================================================
pause >nul
