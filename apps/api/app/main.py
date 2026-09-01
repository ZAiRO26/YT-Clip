"""
ClipForge AI — FastAPI Application Entry Point
"""

from pathlib import Path

from clipforge_core.config import settings
from clipforge_core.services.llm_client import llm_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.api.settings import router as settings_router

app = FastAPI(
    title="ClipForge AI",
    description="Automated video clipping pipeline powered by free/local LLM inference",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(settings_router)

# Serve media files (clip outputs) statically
media_dir = Path(settings.MEDIA_DIR)
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")


@app.get("/health")
async def health_check():
    """Health check endpoint. Returns service status and config summary."""
    return {
        "status": "ok",
        "service": "clipforge-api",
        "version": "0.1.0",
        "llm_gateway": settings.LLM_BASE_URL,
        "database": "supabase" if "supabase" in settings.DATABASE_URL else "local",
        "redis": settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL,
    }


@app.get("/health/llm")
async def llm_health_check():
    """Check LLM gateway connectivity. Returns provider status."""
    return await llm_client.health_check()
