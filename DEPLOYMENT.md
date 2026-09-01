# ClipForge AI — Deployment Guide

This guide covers how to deploy the ClipForge pipeline on a home server or VPS for production use.

## 1. System Requirements
The ClipForge backend utilizes heavy multimedia tools. The host server must have:
- **FFmpeg**: Must be installed globally and accessible in the system PATH.
- **Python 3.11+**: We recommend using `uv` for dependency management.
- **GPU (Optional but highly recommended)**: `faster-whisper` and the `ClipsAI` cropper perform best with an NVIDIA GPU and CUDA toolkit installed.
- **Node.js 20+**: Required for the Next.js frontend.

## 2. Environment Variables

Create a `.env` file in the root directory based on `.env.example`. 

**Critical Variables:**
- `DATABASE_URL`: Your Postgres connection string (e.g., `postgresql+asyncpg://postgres:postgres@localhost:5432/clipforge`).
- `DATABASE_URL_SYNC`: The synchronous version for Celery (e.g., `postgresql://postgres:postgres@localhost:5432/clipforge`).
- `REDIS_URL`: Connection string for the Celery message broker (e.g., `redis://localhost:6379/0`).
- `NEXT_PUBLIC_API_URL`: The public URL where your backend is hosted (e.g., `http://your-server-ip:8000`).

## 3. Production Docker Compose

We recommend running your data layer (Postgres + Redis) in Docker, while running the Backend and Frontend directly on the host to easily access hardware acceleration (CUDA) and system binaries (FFmpeg).

Create a `docker-compose.yml` (or use the one in the repo):
```yaml
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: your_secure_password
      POSTGRES_DB: clipforge
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```
Run `docker compose up -d` to start the data layer.

## 4. Starting the Services

### Start the FastAPI Backend
In a `tmux` session or via `systemd`, navigate to the `backend/` directory and run:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Start the Celery Workers
The backend orchestration relies heavily on Celery. Start the workers with the correct queues:
```bash
uv run celery -A app.celery_app worker -Q default,download,transcribe,select,crop,caption -c 2 --loglevel=info --include=app.services.pipeline
```

### Start the Frontend
Navigate to the `frontend/` directory, build the app, and start it:
```bash
npm install
npm run build
npm run start -p 3000
```

## 5. Connecting the LLM Gateway
Once deployed, navigate to the **Settings** page in the ClipForge UI to configure your LLM Base URL.
If you are running **OmniRoute** or **FreeLLMAPI** on the same server, you can set the Base URL to `http://localhost:8080/v1` or the appropriate server IP. 
*Note: These settings are safely stored in the Postgres database.*
