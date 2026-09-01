@echo off
echo Starting ClipForge AI...

echo [1/4] Starting Docker services (Supabase, Redis)...
docker compose up -d

echo [2/4] Starting FastAPI Backend on port 8000...
start "ClipForge API" cmd /k "cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [3/4] Starting Celery Worker...
start "ClipForge Worker" cmd /k "cd backend && uv run celery -A app.celery_app worker -Q default,download,transcribe,select,crop,caption -c 2 -P solo --loglevel=info --include=app.services.pipeline"

echo [4/4] Starting Next.js Frontend on port 3000...
start "ClipForge UI" cmd /k "cd frontend && npm run dev"

echo.
echo ===================================================
echo ClipForge AI is starting!
echo.
echo UI will be available at:  http://localhost:3000
echo API will be available at: http://localhost:8000
echo ===================================================
echo.
echo You can close this window at any time. The services are running in their own terminal windows.
pause
