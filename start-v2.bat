@echo off
echo Starting ClipForge AI v2 (Monorepo)...

echo [1/4] Starting Docker services (Postgres, Redis, MinIO)...
docker compose -f infra/docker-compose.yml up -d

echo [2/4] Starting FastAPI Backend on port 8000...
start "ClipForge API (v2)" cmd /k "set PYTHONPATH=apps/api;packages/python-core && uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload"

echo [3/4] Starting Celery Worker...
start "ClipForge Worker (v2)" cmd /k "set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A app.celery_app worker -Q default,download,transcribe,select,crop,caption -c 2 -P solo --loglevel=info"

echo [4/4] Starting Next.js Web App on port 3000...
start "ClipForge Web (v2)" cmd /k "pnpm --filter @clipforge/web dev"

echo.
echo ===================================================
echo ClipForge AI v2 is starting!
echo.
echo Web UI:      http://localhost:3000
echo API:         http://localhost:8000
echo MinIO S3:    http://localhost:9000
echo MinIO UI:    http://localhost:9001
echo ===================================================
echo.
echo You can close this window at any time. The services are running in their own terminal windows.
pause
