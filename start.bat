@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo       ClipForge AI v2 — 1-Click Studio Launcher
echo ===================================================
echo.

:: Ensure we are in the repository root
cd /d "%~dp0"

:: 0. Clean up stale/lingering processes from previous sessions
echo [1/7] Cleaning up lingering processes on Port 8000, 3000, and old Celery workers...
powershell -NoProfile -Command "8000, 3000 | ForEach-Object { $p = (Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }; Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*celery*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

:: 1. Check Native PostgreSQL Service
echo [2/7] Checking PostgreSQL 16 (Native Windows Service on port 5432)...
sc query postgresql-x64-16 | findstr RUNNING >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting PostgreSQL service...
    net start postgresql-x64-16 >nul 2>&1
    if %errorlevel% neq 0 (
        echo [WARNING] Could not start PostgreSQL service. Please start it manually.
        echo Run: net start postgresql-x64-16 (as Administrator)
    ) else (
        echo PostgreSQL service started.
    )
) else (
    echo PostgreSQL 16 is already running on port 5432.
)

:: 2. Check & Start Redis (Native Windows Install)
echo [3/7] Checking Redis (Native on port 6379)...
powershell -NoProfile -Command "$r = Get-NetTCPConnection -LocalPort 6379 -State Listen -ErrorAction SilentlyContinue; if ($r) { Write-Host 'Redis already running on port 6379.' } else { Write-Host 'Starting Redis...'; $dir = '%LOCALAPPDATA%\Microsoft\WinGet\Packages\taizod1024.redis-windows-fork_Microsoft.Winget.Source_8wekyb3d8bbwe\Redis-8.8.0-Windows-x64-msys2'; Start-Process -FilePath (Join-Path $dir 'redis-server.exe') -WorkingDirectory $dir -ArgumentList '--port 6379' -WindowStyle Hidden; Start-Sleep -Seconds 2; Write-Host 'Redis started on port 6379.' }"

:: Wait 1 second for socket readiness
powershell -NoProfile -Command "Start-Sleep -Seconds 1"

:: 3. Run Database Migrations
echo [4/7] Running Alembic Database Migrations...
uv run alembic -c packages/python-core/alembic.ini upgrade head

:: 4. Check Kokoro TTS Offline Models
echo [5/7] Verifying Kokoro TTS Offline Models...
if not exist "models\kokoro\kokoro-v0_19.onnx" (
    echo Downloading Kokoro models with SHA-256 validation...
    uv run python scripts/download_kokoro_models.py
) else (
    echo Kokoro TTS model assets verified.
)

:: 5. Start FastAPI Backend & Celery Workers (Split IO & Compute for zero queue stalling)
echo [6/7] Launching Backend Services...
start "ClipForge AI — API (Port 8000)" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/api;packages/python-core && uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload --reload-dir apps/api --reload-dir packages/python-core"

start "ClipForge AI — Ingest & LLM Worker" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n ingest_worker@%%COMPUTERNAME%% -Q ingest,llm,editorial,qa,default -P solo --loglevel=info"

start "ClipForge AI — Analysis Worker" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n compute_worker@%%COMPUTERNAME%% -Q analysis -P solo --loglevel=info"

start "ClipForge AI — Render Worker" cmd /k "cd /d \"%~dp0\" && set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n render_worker@%%COMPUTERNAME%% -Q render -P solo --loglevel=info"

:: 6. Start Next.js Frontend Web Studio
echo [7/7] Launching Next.js Web Studio (Port 3000)...
start "ClipForge AI — Web Studio (Port 3000)" cmd /k "cd /d \"%~dp0\" && pnpm --filter @clipforge/web dev"

echo.
echo ===================================================
echo        ClipForge AI v2 is Running Successfully!
echo ===================================================
echo.
echo  Web Studio:      http://localhost:3000
echo  API ^& Docs:      http://localhost:8000/docs
echo  PostgreSQL:      localhost:5432 (Native Windows Service)
echo  Redis:           localhost:6379 (Native)
echo.
echo  Tip: Run 'stop.bat' to stop all services cleanly anytime.
echo.
echo  Press any key or close this window to exit launcher.
echo  (The services will remain running in their respective windows).
echo ===================================================
pause >nul
