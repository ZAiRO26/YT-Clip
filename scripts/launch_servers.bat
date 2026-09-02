@echo off
cd /d "%~dp0\.."

echo Starting Docker infrastructure (Postgres, Redis, MinIO)...
docker compose -f infra/docker-compose.yml up -d postgres redis minio

echo Launching API on port 8000...
start "ClipForge API (Port 8000)" cmd /k "set PYTHONPATH=apps/api;packages/python-core && uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload"

echo Launching Celery Worker...
start "ClipForge Celery Worker" cmd /k "set PYTHONPATH=apps/worker;packages/python-core && uv run celery -A clipforge_core.celery_app worker -Q default,ingest,analysis,llm,editorial,render,qa -P solo --loglevel=info"

echo Launching Web Studio on port 3000...
start "ClipForge Web Studio (Port 3000)" cmd /k "pnpm --filter @clipforge/web dev"

echo All ClipForge AI servers launched in independent windows.
