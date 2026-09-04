@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo       ClipForge AI v2 — Studio Service Stopper
echo ===================================================
echo.

cd /d "%~dp0"

echo [1/3] Terminating services on Port 8000 (API) and Port 3000 (Web Studio)...
powershell -NoProfile -Command "8000, 3000 | ForEach-Object { $p = (Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }"

echo [2/3] Terminating Celery Workers and background runners...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*celery*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo [3/3] Checking Docker Infrastructure...
if "%1"=="--all" (
    echo Stopping Docker containers (Postgres, Redis, MinIO)...
    docker compose -f infra/docker-compose.yml stop
) else (
    echo (Docker containers kept running in background for fast re-launch. Pass '--all' to stop Docker as well).
)

echo.
echo ===================================================
echo       ClipForge AI services have been stopped.
echo       Run start.bat to launch a fresh session.
echo ===================================================
echo.
if "%~1"=="" timeout /t 3 >nul
