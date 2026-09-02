# ClipForge AI — v2 Monorepo Deployment Guide

This guide covers local development, multi-container Docker Compose orchestration, and production deployment for ClipForge AI v2.

---

## 1. Monorepo Architecture Overview

```
Clip-Forge/
├── apps/
│   ├── web/                    # Next.js 16 + Tailwind + shadcn/ui
│   ├── api/                    # FastAPI HTTP server (/health, /ready, routes)
│   └── worker/                 # Celery worker process
├── packages/
│   ├── contracts/              # Shared TypeScript types & schemas
│   └── python-core/            # Shared Python models, services, pipeline, workers
├── infra/
│   ├── docker-compose.yml      # Postgres 16, Redis 7, MinIO, API, Worker
│   └── .env.example
├── docs/                       # PRODUCT_POLICY, DECISIONS, RENDER_MANIFEST_SCHEMA
└── start-v2.bat                # 1-click Windows startup script
```

---

## 2. Local Development (Fastest Workflow)

### Prerequisites
- **Node.js 20+** and **pnpm 11+**
- **Python 3.11+** and **uv 0.11+**
- **Docker** (for Postgres, Redis, MinIO)
- **FFmpeg** installed globally in system PATH

### Step 1: Clone & Setup Workspaces
```bash
# 1. Install Node dependencies across monorepo
pnpm install

# 2. Sync Python workspace dependencies
uv sync --all-packages

# 3. Create .env file
cp .env.example .env
```

### Step 2: Start Infrastructure
```bash
# Start Postgres, Redis, and MinIO
docker compose -f infra/docker-compose.yml up -d postgres redis minio
```

### Step 3: Run Database Migrations
```bash
uv run alembic -c packages/python-core/alembic.ini upgrade head
```

### Step 4: Start Services
Option A — 1-Click Script (Windows):
```cmd
start-v2.bat
```

Option B — Manual Terminal Windows:
```bash
# Terminal 1: FastAPI
set PYTHONPATH=apps/api;packages/python-core
uv run uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Celery Worker
set PYTHONPATH=apps/worker;packages/python-core
uv run celery -A clipforge_core.celery_app worker -Q default,ingest,analysis,llm,editorial,render,qa -P solo --loglevel=info

# Terminal 3: Next.js Frontend
pnpm dev
```

---

## 3. Full Multi-Container Docker Deployment

To run the entire stack (Database, Cache, Object Storage, API, Worker) inside Docker:

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

### Service Endpoints
| Service | URL | Purpose |
|---|---|---|
| Web UI | `http://localhost:3000` | Next.js dark studio dashboard |
| API | `http://localhost:8000` | FastAPI REST server |
| API Health | `http://localhost:8000/health` | Liveness check |
| API Ready | `http://localhost:8000/ready` | DB, Redis, and Storage readiness probe |
| MinIO Console | `http://localhost:9001` | S3 browser UI (user: `minioadmin`, pass: `minioadmin`) |
| MinIO S3 API | `http://localhost:9000` | S3 object storage |

---

## 4. Named Worker Queues

The Celery worker pool uses dedicated queues per pipeline stage:

| Queue | Handled Tasks |
|---|---|
| `ingest` | Video download, URL validation, ffprobe probing |
| `analysis` | faster-whisper transcription, scene cuts, face tracking |
| `llm` | Brief-aware candidate selection, script drafts |
| `editorial` | Caption preparation, hook cards, transformation scoring |
| `render` | FFmpeg cut/crop, 9:16 reframe, motion effects, audio mix |
| `qa` | Technical QC, aspect ratio, loudness validation |
| `default` | General background jobs & no-op health tasks |

---

## 5. Connecting LLM Gateway

ClipForge AI uses zero-cost local/proxy LLM inference via OpenAI-compatible endpoints:
1. Open the UI at `http://localhost:3000/settings`.
2. Enter your OmniRoute or FreeLLMAPI gateway URL (default: `http://localhost:8080/v1`).
3. Settings are persisted directly to the Postgres database.
