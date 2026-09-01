"""
ClipForge AI — API Routes

All endpoints from Backend Schema section 05:
- POST /api/projects          → create project + enqueue pipeline
- GET  /api/projects/:id      → read status + stage progress
- GET  /api/projects/:id/clips → list generated clips
- PATCH /api/clips/:id        → approve/reject a clip
- POST /api/campaign-briefs   → create reusable brief
- GET  /api/campaign-briefs   → list saved briefs

Note: Auth is simplified for v1 (single-user). Full Supabase Auth
integration will be added in Phase 4 with the frontend.
"""

import logging
import uuid
from datetime import datetime, timezone

from clipforge_core.config import settings
from clipforge_core.database import get_async_session
from clipforge_core.models import CampaignBrief, Clip, Job, Project, User
from clipforge_core.schemas import (
    CampaignBriefCreate,
    CampaignBriefResponse,
    ClipResponse,
    ClipUpdate,
    ExportRequest,
    MessageResponse,
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ReclipRequest,
    ThumbnailRequest,
)
from clipforge_core.services.pipeline import create_pipeline_jobs, dispatch_pipeline, dispatch_reclip
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

# Temporary: hardcoded user for v1 (single-user mode)
# Will be replaced with Supabase Auth in Phase 4
TEMP_USER_ID = "00000000-0000-0000-0000-000000000001"


async def _ensure_temp_user(session: AsyncSession) -> str:
    """Ensure the temporary user exists in the database."""
    user_id = uuid.UUID(TEMP_USER_ID)
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(id=user_id, email="dev@clipforge.local")
        session.add(user)
        await session.commit()

    return TEMP_USER_ID


# ============================================
# Campaign Briefs
# ============================================


@router.post("/campaign-briefs", response_model=CampaignBriefResponse)
async def create_campaign_brief(
    data: CampaignBriefCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """Create a reusable campaign brief."""
    owner_id = await _ensure_temp_user(session)

    brief = CampaignBrief(
        id=uuid.uuid4(),
        owner_id=uuid.UUID(owner_id),
        name=data.name,
        brief_json=data.brief_json,
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)

    return brief


@router.get("/campaign-briefs", response_model=list[CampaignBriefResponse])
async def list_campaign_briefs(
    session: AsyncSession = Depends(get_async_session),
):
    """List all saved campaign briefs."""
    owner_id = await _ensure_temp_user(session)

    result = await session.execute(
        select(CampaignBrief)
        .where(CampaignBrief.owner_id == uuid.UUID(owner_id))
        .order_by(CampaignBrief.created_at.desc())
    )
    return result.scalars().all()


# ============================================
# Projects
# ============================================


@router.post("/projects", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a project and enqueue the processing pipeline.

    This is the main entry point: user submits a source + settings,
    and the full pipeline (download → transcribe → select → crop → caption)
    is dispatched as background tasks.
    """
    owner_id = await _ensure_temp_user(session)

    # Validate campaign brief exists if provided
    if data.campaign_brief_id:
        result = await session.execute(
            select(CampaignBrief).where(
                CampaignBrief.id == data.campaign_brief_id,
                CampaignBrief.owner_id == uuid.UUID(owner_id),
            )
        )
        brief = result.scalar_one_or_none()
        if not brief:
            raise HTTPException(status_code=404, detail="Campaign brief not found")

    # Validate min/max length
    if data.min_length_sec >= data.max_length_sec:
        raise HTTPException(
            status_code=422,
            detail="min_length_sec must be less than max_length_sec",
        )

    # Create project
    project = Project(
        id=uuid.uuid4(),
        owner_id=uuid.UUID(owner_id),
        source_type=data.source_type,
        source_value=data.source_value,
        campaign_brief_id=data.campaign_brief_id,
        clip_count=data.clip_count,
        min_length_sec=data.min_length_sec,
        max_length_sec=data.max_length_sec,
        aspect_ratio=data.aspect_ratio,
        caption_style=data.caption_style,
        status="queued",
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)

    # Create pipeline job records (sync operation)
    project_id = str(project.id)
    create_pipeline_jobs(project_id)

    # Reload project with jobs using selectinload
    result = await session.execute(
        select(Project)
        .options(selectinload(Project.jobs), selectinload(Project.campaign_brief))
        .where(Project.id == project.id)
    )
    project = result.scalar_one()

    # Dispatch pipeline (Celery tasks)
    try:
        dispatch_pipeline(project_id, project)
    except Exception as e:
        logger.error(f"Failed to dispatch pipeline: {e}")
        # Don't fail the request — the project is created, pipeline can be retried
    return project


@router.delete("/projects/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a project, its jobs, clips, and associated media files."""
    import shutil
    from pathlib import Path

    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete from database (cascade deletes jobs and clips)
    await session.delete(project)
    await session.commit()

    # Delete media files from disk
    media_dir = Path(settings.MEDIA_DIR) / str(project_id)
    if media_dir.exists() and media_dir.is_dir():
        try:
            shutil.rmtree(media_dir)
        except Exception as e:
            logger.error(f"Failed to delete media directory {media_dir}: {e}")

    return MessageResponse(message="Project deleted successfully")


@router.post("/projects/{project_id}/retry", response_model=MessageResponse)
async def retry_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Retry a failed project pipeline."""
    result = await session.execute(
        select(Project)
        .options(selectinload(Project.jobs), selectinload(Project.campaign_brief))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status not in ["failed", "queued", "downloading"]:
        raise HTTPException(status_code=400, detail="Only failed or stuck projects can be retried")

    # Reset project status
    project.status = "queued"

    # Reset job statuses synchronously via helper or direct DB queries
    from clipforge_core.database import get_sync_session
    from clipforge_core.models import Job

    sync_session = get_sync_session()
    try:
        sync_session.query(Job).filter(Job.project_id == project_id).update(
            {"status": "pending", "error_message": None}
        )
        sync_session.commit()
    except Exception as e:
        sync_session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset jobs: {e}")
    finally:
        sync_session.close()

    await session.commit()

    # Re-dispatch
    try:
        dispatch_pipeline(str(project_id), project)
    except Exception as e:
        logger.error(f"Failed to re-dispatch pipeline: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart pipeline: {e}")

    return MessageResponse(message="Pipeline restarted successfully")


@router.get("/projects", response_model=list[ProjectListItem])
async def list_projects(
    session: AsyncSession = Depends(get_async_session),
):
    """List all projects for the current user."""
    owner_id = await _ensure_temp_user(session)

    result = await session.execute(
        select(Project)
        .options(selectinload(Project.clips))
        .where(Project.owner_id == uuid.UUID(owner_id))
        .order_by(Project.created_at.desc())
    )

    projects = result.scalars().all()
    items = []
    for p in projects:
        # Find the first clip with a thumbnail, if any
        preview_url = None
        for c in p.clips:
            if c.thumbnail_url:
                preview_url = c.thumbnail_url
                break

        items.append(
            ProjectListItem(
                id=p.id,
                source_type=p.source_type,
                source_value=p.source_value,
                clip_count=p.clip_count,
                status=p.status,
                created_at=p.created_at,
                preview_url=preview_url,
            )
        )

    return items


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Get project details with per-stage job progress."""
    result = await session.execute(select(Project).options(selectinload(Project.jobs)).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.get("/projects/{project_id}/clips", response_model=list[ClipResponse])
async def list_project_clips(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """List all generated clips for a project."""
    # Verify project exists
    proj_result = await session.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await session.execute(
        select(Clip).where(Clip.project_id == project_id).order_by(Clip.score.desc().nulls_last())
    )
    return result.scalars().all()


# ============================================
# Clips
# ============================================


@router.patch("/clips/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: uuid.UUID,
    data: ClipUpdate,
    session: AsyncSession = Depends(get_async_session),
):
    """Approve or reject a clip."""
    result = await session.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip.review_status = data.review_status
    await session.commit()
    await session.refresh(clip)

    if data.review_status == "approved" and clip.file_url:
        try:
            from clipforge_core.config import settings
            from sqlalchemy import text

            # Check if settings table exists
            table_check = await session.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'settings')")
            )
            if table_check.scalar():
                res = await session.execute(text("SELECT value FROM settings WHERE key = 'export_path'"))
                export_path = res.scalar()
                if export_path:
                    export_path = export_path.strip('"')
                    import shutil
                    from pathlib import Path

                    media_base = Path(settings.MEDIA_DIR).parent
                    source_path = media_base / clip.file_url
                    if source_path.exists():
                        target_dir = Path(export_path)
                        target_dir.mkdir(parents=True, exist_ok=True)
                        target_path = target_dir / f"clip_{clip.id}.mp4"
                        shutil.copy2(source_path, target_path)
                        logger.info(f"Automated export: copied {source_path.name} to {target_path}")
        except Exception as e:
            logger.error(f"Automated export failed for clip {clip_id}: {e}")

    return clip


@router.post("/clips/{clip_id}/thumbnail", response_model=ClipResponse)
async def regenerate_thumbnail(
    clip_id: uuid.UUID,
    data: ThumbnailRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Regenerate a thumbnail for a clip, optionally with text overlay."""
    result = await session.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if not clip.file_url:
        raise HTTPException(status_code=400, detail="Clip video file not generated yet")


    from clipforge_core.workers.thumbnail import generate_thumbnail

    video_path = clip.file_url

    # We will save it in the same directory
    output_path = video_path.rsplit(".", 1)[0] + "_custom_thumb.jpg"

    # For now, just generate a normal thumbnail. Later we can add Pillow text overlay if `data.text` is provided.
    duration = clip.end_sec - clip.start_sec if clip.end_sec and clip.start_sec else 10

    success = generate_thumbnail(video_path, output_path, duration)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    clip.thumbnail_url = output_path
    await session.commit()
    await session.refresh(clip)

    return clip


@router.post("/projects/{project_id}/export", response_model=MessageResponse)
async def export_project_clips(
    project_id: uuid.UUID,
    data: ExportRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Export approved clips to a local path."""
    import shutil
    from pathlib import Path

    # Verify project exists
    proj_result = await session.execute(select(Project).where(Project.id == project_id))
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get approved clips
    result = await session.execute(
        select(Clip)
        .where(Clip.project_id == project_id)
        .where(Clip.review_status == "approved")
        .where(Clip.file_url.is_not(None))
    )
    approved_clips = result.scalars().all()

    if not approved_clips:
        raise HTTPException(status_code=400, detail="No approved clips to export")

    export_dir = Path(data.export_path)
    try:
        export_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create export directory: {e}")

    exported_count = 0
    errors = []

    # file_url in DB looks like "media\<uuid>\clips\clip_000_final.mp4"
    # MEDIA_DIR is "./media"
    # Strip the leading "media/" or "media\" prefix so we get "<uuid>/clips/..."
    # Then join with MEDIA_DIR to get the real on-disk path.
    media_base = Path(settings.MEDIA_DIR).resolve()

    for clip in approved_clips:
        try:
            # Normalize backslashes
            rel_url = clip.file_url.replace("\\", "/")
            # Strip leading "media/" prefix if present
            if rel_url.startswith("media/"):
                rel_url = rel_url[len("media/") :]

            source_path = media_base / rel_url

            if source_path.exists():
                dest_path = export_dir / f"project_{project_id}_clip_{exported_count + 1}.mp4"
                shutil.copy2(source_path, dest_path)

                # Also copy thumbnail if it exists
                if clip.thumbnail_url:
                    thumb_rel = clip.thumbnail_url.replace("\\", "/")
                    if thumb_rel.startswith("media/"):
                        thumb_rel = thumb_rel[len("media/") :]
                    thumb_source = media_base / thumb_rel
                    if thumb_source.exists():
                        thumb_dest = export_dir / f"project_{project_id}_clip_{exported_count + 1}_thumb.jpg"
                        shutil.copy2(thumb_source, thumb_dest)

                exported_count += 1
            else:
                errors.append(f"Source file not found: {source_path}")
        except Exception as e:
            errors.append(f"Failed to export clip {clip.id}: {e}")

    if exported_count == 0:
        raise HTTPException(status_code=500, detail=f"Failed to export any clips. Errors: {errors}")

    msg = f"Successfully exported {exported_count} clips to {export_dir}"
    if errors:
        msg += f" (with {len(errors)} errors)"

    return MessageResponse(message=msg, detail="|".join(errors) if errors else None)


# ============================================
# Reclip — Generate more clips from existing project
# ============================================


@router.post("/projects/{project_id}/reclip")
async def reclip_project(
    project_id: str,
    data: ReclipRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Re-run AI Select → Crop → Caption on an already-processed project.
    Skips download and transcription entirely. New clips are appended.
    """
    from pathlib import Path

    from clipforge_core.config import settings as app_settings

    result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify transcript exists on disk
    transcript_path = Path(app_settings.MEDIA_DIR) / project_id / "transcript.json"
    if not transcript_path.exists():
        raise HTTPException(
            status_code=400, detail="No transcript found for this project. The video must be fully processed first."
        )

    # Create new job records for select/crop/caption stages
    for stage in ["select", "crop", "caption"]:
        job = Job(
            id=uuid.uuid4(),
            project_id=uuid.UUID(project_id),
            stage=stage,
            status="pending",
            updated_at=datetime.now(timezone.utc),
        )
        session.add(job)

    project.status = "selecting"
    await session.commit()

    # Dispatch the reclip task
    task_id = dispatch_reclip(
        project_id=project_id,
        clip_count=data.clip_count,
        min_length_sec=data.min_length_sec,
        max_length_sec=data.max_length_sec,
        aspect_ratio=data.aspect_ratio,
        caption_style=data.caption_style,
        custom_prompt=data.custom_prompt,
        time_range_start=data.time_range_start,
        time_range_end=data.time_range_end,
    )

    return {
        "message": "Reclip pipeline started",
        "project_id": project_id,
        "task_id": task_id,
        "settings": data.model_dump(),
    }
