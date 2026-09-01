"""
ClipForge AI — Settings API Routes
"""

import httpx
from clipforge_core.config import settings
from clipforge_core.database import get_async_session
from clipforge_core.schemas.api_models import LLMSettingsSchema
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=LLMSettingsSchema)
async def get_llm_settings(db: AsyncSession = Depends(get_async_session)):
    """Get current LLM settings."""
    try:
        # Check if settings table exists
        result = await db.execute(
            text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'settings');")
        )
        has_table = result.scalar()

        if not has_table:
            # Fallback to config if table doesn't exist
            return LLMSettingsSchema(
                llm_base_url=settings.LLM_BASE_URL, llm_api_key=settings.LLM_API_KEY, llm_model=settings.LLM_MODEL
            )

        # Get settings from DB
        base_url_res = await db.execute(text("SELECT value FROM settings WHERE key = 'llm_base_url'"))
        base_url_row = base_url_res.fetchone()

        api_key_res = await db.execute(text("SELECT value FROM settings WHERE key = 'llm_api_key'"))
        api_key_row = api_key_res.fetchone()

        model_res = await db.execute(text("SELECT value FROM settings WHERE key = 'llm_model'"))
        model_row = model_res.fetchone()

        export_path_res = await db.execute(text("SELECT value FROM settings WHERE key = 'export_path'"))
        export_path_row = export_path_res.fetchone()

        return LLMSettingsSchema(
            llm_base_url=base_url_row[0].strip('"') if base_url_row else settings.LLM_BASE_URL,
            llm_api_key=api_key_row[0].strip('"') if api_key_row else settings.LLM_API_KEY,
            llm_model=model_row[0].strip('"') if model_row else settings.LLM_MODEL,
            export_path=export_path_row[0].strip('"') if export_path_row else None,
        )
    except Exception:
        # Fallback to config
        return LLMSettingsSchema(
            llm_base_url=settings.LLM_BASE_URL,
            llm_api_key=settings.LLM_API_KEY,
            llm_model=settings.LLM_MODEL,
            export_path=None,
        )


@router.put("", response_model=LLMSettingsSchema)
async def update_llm_settings(settings_data: LLMSettingsSchema, db: AsyncSession = Depends(get_async_session)):
    """Update LLM settings."""
    try:
        # Ensure table exists
        await db.execute(
            text("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        )

        # Upsert settings
        await db.execute(
            text(
                "INSERT INTO settings (key, value) VALUES ('llm_base_url', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {"val": f'"{settings_data.llm_base_url}"'},
        )
        await db.execute(
            text(
                "INSERT INTO settings (key, value) VALUES ('llm_api_key', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {"val": f'"{settings_data.llm_api_key}"'},
        )
        await db.execute(
            text(
                "INSERT INTO settings (key, value) VALUES ('llm_model', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            ),
            {"val": f'"{settings_data.llm_model}"'},
        )

        if settings_data.export_path is not None:
            await db.execute(
                text(
                    "INSERT INTO settings (key, value) VALUES ('export_path', :val) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
                ),
                {"val": f'"{settings_data.export_path}"'},
            )

        await db.commit()
        return settings_data
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/test-connection")
async def test_llm_connection(settings_data: LLMSettingsSchema):
    """Test connection to the LLM gateway."""
    url = f"{settings_data.llm_base_url.rstrip('/')}/models"
    headers = {}
    if settings_data.llm_api_key and settings_data.llm_api_key != "not-needed":
        headers["Authorization"] = f"Bearer {settings_data.llm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                models = [m.get("id") for m in data.get("data", [])]
                return {"status": "success", "message": "Connection successful", "models": models}
            else:
                return {"status": "error", "message": f"Connection failed with status {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}
