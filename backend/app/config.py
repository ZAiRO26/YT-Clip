"""
ClipForge AI — Application Settings

All config loaded from environment variables via pydantic-settings.
See .env.example for the full list.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings. All values are loaded from environment variables."""

    # --- Application ---
    APP_ENV: str = "development"
    DEBUG: bool = True

    # --- Database (Supabase Postgres) ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clipforge"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/clipforge"

    # --- Redis (Celery broker + result backend) ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- LLM Gateway (OmniRoute / FreeLLMAPI) ---
    LLM_BASE_URL: str = "http://localhost:8080/v1"
    LLM_API_KEY: str = "not-needed"
    LLM_MODEL: str = "auto"

    # --- Cloudflare R2 (S3-compatible storage) ---
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "clipforge-media"

    # --- Supabase Auth ---
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"]

    # --- Whisper ---
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # --- Clip Defaults ---
    DEFAULT_CLIP_COUNT: int = 5
    DEFAULT_MIN_LENGTH_SEC: int = 20
    DEFAULT_MAX_LENGTH_SEC: int = 60
    DEFAULT_ASPECT_RATIO: str = "9:16"
    DEFAULT_CAPTION_STYLE: str = "bold_karaoke"

    # --- Paths ---
    MEDIA_DIR: str = "./media"
    TEMP_DIR: str = "./temp"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
