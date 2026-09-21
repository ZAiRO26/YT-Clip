@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo       ClipForge AI v2 — 1-Click Studio Launcher
echo ===================================================
echo.

:: Ensure we are in the repository root and resolve clean path without trailing slash
set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%
cd /d "%ROOT%"

:: 1. Clean up stale/lingering processes on Port 8000, 3000, and old Celery workers
echo [1/7] Cleaning up lingering processes on Port 8000, 3000, and old Celery workers...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000, 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Stop-Process -Force -ErrorAction SilentlyContinue; Get-CimInstance Win32_Process -Filter 'CommandLine LIKE ''%%celery%%''' -ErrorAction SilentlyContinue | Invoke-CimMethod -MethodName Terminate; exit 0" >nul 2>&1

:: 2. Check Native PostgreSQL Service
echo [2/7] Checking PostgreSQL 16 (Native Windows Service on port 5432)...
sc.exe query postgresql-x64-16 | findstr RUNNING >nul 2>&1
if %errorlevel% neq 0 (
    echo Starting PostgreSQL service...
    net start postgresql-x64-16 >nul 2>&1
    if %errorlevel% neq 0 (
        echo [WARNING] Could not start PostgreSQL service automatically.
        echo Please ensure PostgreSQL is running or run: net start postgresql-x64-16 (as Administrator)
    ) else (
        echo PostgreSQL service started.
    )
) else (
    echo PostgreSQL 16 is running on port 5432.
)

:: 3. Check & Start Redis (Native Windows Install)
echo [3/7] Checking Redis (Native on port 6379)...
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 6379 -State Listen -ErrorAction SilentlyContinue; if ($conn) { Write-Host 'Redis is running on port 6379.' } else { Write-Host 'Starting Redis server...'; $dir = '%LOCALAPPDATA%\Microsoft\WinGet\Packages\taizod1024.redis-windows-fork_Microsoft.Winget.Source_8wekyb3d8bbwe\Redis-8.8.0-Windows-x64-msys2'; $exe = Join-Path $dir 'redis-server.exe'; if (-not (Test-Path $exe)) { $found = Get-ChildItem -Path ('{0}\Microsoft\WinGet\Packages' -f $env:LOCALAPPDATA) -Filter 'redis-server.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1; if ($found) { $exe = $found.FullName; $dir = $found.DirectoryName } }; if (Test-Path $exe) { Start-Process -FilePath $exe -WorkingDirectory $dir -ArgumentList '--port 6379' -WindowStyle Hidden; Start-Sleep -Seconds 2; Write-Host 'Redis started on port 6379.' } else { Write-Host '[WARNING] redis-server.exe not found. Please verify Redis is installed.' } }"

:: 4. Run Database Migrations
echo [4/7] Running Alembic Database Migrations...
uv run alembic -c packages/python-core/alembic.ini upgrade head

:: 5. Check Kokoro TTS Offline Models
echo [5/7] Verifying Kokoro TTS Offline Models...
if not exist "models\kokoro\kokoro-v0_19.onnx" (
    echo Downloading Kokoro models with SHA-256 validation...
    uv run python scripts/download_kokoro_models.py
) else (
    echo Kokoro TTS model assets verified.
)

:: 6. Check OmniRoute LLM Gateway
echo [6/7] Checking OmniRoute LLM Gateway (Port 20128)...
powershell -NoProfile -Command "$llm = Get-NetTCPConnection -LocalPort 20128 -State Listen -ErrorAction SilentlyContinue; if ($llm) { Write-Host 'OmniRoute LLM Gateway is online on port 20128.' } else { Write-Host '[INFO] OmniRoute on port 20128 not detected. Ensure LLM gateway is active for AI candidate selection.' }"

:: 7. Start FastAPI Backend & Celery Workers (Split IO & Compute for zero queue stalling)
echo [7/7] Launching Studio Backend, Celery Workers, and Web Studio...

start "ClipForge AI — API (Port 8000)" /D "%ROOT%" cmd /k "set PYTHONPATH=apps/api;packages/python-core && uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload --reload-dir apps/api --reload-dir packages/python-core"

start "ClipForge AI — Ingest & LLM Worker" /D "%ROOT%" cmd /k "set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n ingest_worker@%COMPUTERNAME% -Q ingest,llm,editorial,qa,default -P solo --loglevel=info"

start "ClipForge AI — Analysis Worker" /D "%ROOT%" cmd /k "set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n compute_worker@%COMPUTERNAME% -Q analysis -P solo --loglevel=info"

start "ClipForge AI — Render Worker" /D "%ROOT%" cmd /k "set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -n render_worker@%COMPUTERNAME% -Q render -P solo --loglevel=info"

start "ClipForge AI — Web Studio (Port 3000)" /D "%ROOT%" cmd /k "pnpm --filter @clipforge/web dev"

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
