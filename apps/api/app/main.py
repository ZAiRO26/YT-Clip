"""
ClipForge AI — FastAPI Application Entry Point (v2)
Configures structured logging, CORS, static mounts, /health, and /ready endpoints.
"""
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict

import redis.asyncio as aioredis
from clipforge_core.config import settings
from clipforge_core.database import async_session_factory
from clipforge_core.services.llm_client import llm_client
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes import router as api_router
from app.api.settings import router as settings_router

# ============================================
# Structured Logging Configuration
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("clipforge.api")

app = FastAPI(
    title="ClipForge AI API",
    description="Rights-aware, transformation-supporting clipping studio API",
    version="0.2.0",
)

# ============================================
# Middleware: CORS & Request Timing
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response: Response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({process_time:.1f}ms)"
    )
    return response


# ============================================
# Routers & Static Mounts
# ============================================
app.include_router(api_router)
app.include_router(settings_router)

media_dir = Path(settings.MEDIA_DIR)
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")


# ============================================
# Health & Readiness Endpoints
# ============================================
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint. Returns service status and config summary."""
    return {
        "status": "ok",
        "service": "clipforge-api",
        "version": "0.2.0",
        "llm_gateway": settings.LLM_BASE_URL,
        "database": "supabase" if "supabase" in settings.DATABASE_URL else "postgres",
        "redis": settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL,
    }


@app.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe: validates database connectivity, Redis ping, and storage access.
    """
    checks = {
        "database": False,
        "redis": False,
        "storage": False,
    }

    # 1. Database Check
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.warning(f"Readiness check failed for database: {e}")

    # 2. Redis Check
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception as e:
        logger.warning(f"Readiness check failed for redis: {e}")

    # 3. Storage Check
    try:
        test_file = media_dir / ".ready_check"
        test_file.write_text("ok")
        test_file.unlink(missing_ok=True)
        checks["storage"] = True
    except Exception as e:
        logger.warning(f"Readiness check failed for storage: {e}")

    ready = all(checks.values())
    if not ready:
        raise HTTPException(
            status_code=503,
            detail={"ready": False, "checks": checks},
        )

    return {"ready": True, "checks": checks}


@app.get("/health/llm")
async def llm_health_check() -> Dict[str, Any]:
    """Check LLM gateway connectivity. Returns provider status."""
    return await llm_client.health_check()
