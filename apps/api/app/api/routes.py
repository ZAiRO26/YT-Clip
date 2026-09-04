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

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from fastapi.responses import FileResponse
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

    # Compute source risk label
    from clipforge_core.models import ProjectAuditEvent
    from clipforge_core.schemas import compute_source_risk

    risk_label = compute_source_risk(data.rights_basis, data.source_type, bool(data.rights_proof_url))

    # Create project
    project = Project(
        id=uuid.uuid4(),
        owner_id=uuid.UUID(owner_id),
        title=data.title or (f"Project {data.source_value[:30]}"),
        source_type=data.source_type,
        source_value=data.source_value,
        rights_basis=data.rights_basis,
        rights_proof_url=data.rights_proof_url,
        rights_notes=data.rights_notes,
        source_risk_label=risk_label,
        editorial_template=data.editorial_template,
        campaign_brief_id=data.campaign_brief_id,
        clip_count=data.clip_count,
        min_length_sec=data.min_length_sec,
        max_length_sec=data.max_length_sec,
        aspect_ratio=data.aspect_ratio,
        crop_mode=data.crop_mode,
        caption_style=data.caption_style,
        default_effects=data.default_effects,
        default_voice_id=data.default_voice_id,
        default_music_track=data.default_music_track,
        time_range_start=data.time_range_start,
        time_range_end=data.time_range_end,
        temporal_distribution=data.temporal_distribution,
        content_focus=data.content_focus,
        status="queued",
    )
    session.add(project)

    # Record Rights Declared Audit Event (context2-upgrade.md Section 2.2 & 7.1)
    audit_event = ProjectAuditEvent(
        id=uuid.uuid4(),
        project_id=project.id,
        event_type="rights_declared",
        payload={
            "rights_basis": data.rights_basis,
            "rights_proof_url": data.rights_proof_url,
            "source_risk_label": risk_label,
            "declared_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    session.add(audit_event)

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
                title=p.title,
                source_type=p.source_type,
                source_value=p.source_value,
                rights_basis=p.rights_basis or "owned",
                source_risk_label=p.source_risk_label or "lower_workflow_risk",
                editorial_template=p.editorial_template or "explainer",
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

    if data.review_status is not None:
        clip.review_status = data.review_status
    if data.start_sec is not None:
        clip.start_sec = data.start_sec
    if data.end_sec is not None:
        clip.end_sec = data.end_sec
    if data.reasoning is not None:
        clip.reasoning = data.reasoning

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


@router.get("/clips/{clip_id}/download")
async def download_clip(
    clip_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
):
    """Serve the clip file with Content-Disposition: attachment for automatic browser download."""
    clip_result = await session.execute(select(Clip).where(Clip.id == clip_id))
    clip = clip_result.scalar_one_or_none()
    if not clip or not clip.file_url:
        raise HTTPException(status_code=404, detail="Clip or video file not found")

    rel_url = clip.file_url.replace("\\", "/")
    if rel_url.startswith("media/"):
        rel_url = rel_url[len("media/") :]

    media_base = Path(settings.MEDIA_DIR).resolve()
    file_path = media_base / rel_url

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")

    filename = f"clip_{clip_id}.mp4"
    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.post("/projects/{project_id}/export", response_model=MessageResponse)
async def export_project_clips(
    project_id: uuid.UUID,
    data: ExportRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Export approved clips to a dedicated local subfolder under the export destination."""
    import json
    import re
    import shutil
    from pathlib import Path
    from sqlalchemy import text

    # Verify project exists
    proj_result = await session.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
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

    # Determine base export path (fallback to settings table if not provided)
    base_export_str = data.export_path.strip() if data.export_path else ""
    if not base_export_str:
        try:
            settings_res = await session.execute(text("SELECT value FROM settings WHERE key = 'export_path'"))
            row = settings_res.fetchone()
            if row and row[0]:
                base_export_str = row[0].strip('"').strip()
        except Exception:
            pass

    if not base_export_str:
        base_export_str = "C:\\ClipForgeExports"

    base_export_dir = Path(base_export_str)

    # Sanitize project title for a fresh dedicated folder
    raw_title = project.title or f"Project_{str(project_id)[:8]}"
    safe_folder_name = re.sub(r'[\\/*?:"<>|]', "", raw_title).strip().replace(" ", "_")[:60]
    if not safe_folder_name:
        safe_folder_name = f"Project_{str(project_id)[:8]}"

    target_export_dir = base_export_dir / safe_folder_name
    try:
        target_export_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create export directory '{target_export_dir}': {e}")

    exported_count = 0
    errors = []
    exported_manifest_items = []

    media_base = Path(settings.MEDIA_DIR).resolve()

    for idx, clip in enumerate(approved_clips):
        try:
            # Normalize backslashes and strip media prefix
            rel_url = clip.file_url.replace("\\", "/")
            if rel_url.startswith("media/"):
                rel_url = rel_url[len("media/") :]

            source_path = media_base / rel_url

            if source_path.exists():
                clip_title_raw = getattr(clip, "title", None) or f"clip_{idx + 1}"
                safe_clip_title = re.sub(r'[\\/*?:"<>|]', "", str(clip_title_raw)).strip().replace(" ", "_")[:50]
                clip_filename = f"{exported_count + 1:02d}_{safe_clip_title}.mp4"
                dest_path = target_export_dir / clip_filename
                shutil.copy2(source_path, dest_path)

                # Also copy thumbnail if it exists
                thumb_filename = None
                if clip.thumbnail_url:
                    thumb_rel = clip.thumbnail_url.replace("\\", "/")
                    if thumb_rel.startswith("media/"):
                        thumb_rel = thumb_rel[len("media/") :]
                    thumb_source = media_base / thumb_rel
                    if thumb_source.exists():
                        thumb_filename = f"{exported_count + 1:02d}_{safe_clip_title}_thumb.jpg"
                        thumb_dest = target_export_dir / thumb_filename
                        shutil.copy2(thumb_source, thumb_dest)

                duration_sec = round(clip.end_sec - clip.start_sec, 2) if (clip.end_sec is not None and clip.start_sec is not None) else None
                exported_manifest_items.append({
                    "clip_number": exported_count + 1,
                    "clip_id": str(clip.id),
                    "filename": clip_filename,
                    "thumbnail": thumb_filename,
                    "start_sec": clip.start_sec,
                    "end_sec": clip.end_sec,
                    "duration_sec": duration_sec,
                    "editorial_potential": clip.score,
                    "transformation_score": clip.transformation_score,
                    "reasoning": clip.reasoning,
                })

                exported_count += 1
            else:
                errors.append(f"Source file not found for clip {clip.id}: {source_path}")
        except Exception as e:
            errors.append(f"Failed to export clip {clip.id}: {e}")

    if exported_count == 0:
        raise HTTPException(status_code=500, detail=f"Failed to export any clips. Errors: {errors}")

    # Write export manifest JSON
    try:
        manifest_payload = {
            "project_id": str(project.id),
            "project_title": project.title,
            "source_type": project.source_type,
            "source_value": project.source_value,
            "rights_basis": project.rights_basis,
            "crop_mode": project.crop_mode,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "export_folder": str(target_export_dir),
            "total_clips_exported": exported_count,
            "clips": exported_manifest_items,
        }
        with open(target_export_dir / "export_manifest.json", "w", encoding="utf-8") as mf:
            json.dump(manifest_payload, mf, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write export manifest: {e}")

    msg = f"Successfully exported {exported_count} clips to {target_export_dir}"
    if errors:
        msg += f" (with {len(errors)} warnings)"

    return MessageResponse(
        message=msg,
        details={"export_folder": str(target_export_dir), "count": exported_count, "errors": errors}
    )


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
    if data.clip_count:
        project.clip_count = data.clip_count
    if data.min_length_sec:
        project.min_length_sec = data.min_length_sec
    if data.max_length_sec:
        project.max_length_sec = data.max_length_sec
    if data.aspect_ratio:
        project.aspect_ratio = data.aspect_ratio
    if data.caption_style:
        project.caption_style = data.caption_style
    if data.temporal_distribution:
        project.temporal_distribution = data.temporal_distribution
    if data.content_focus:
        project.content_focus = data.content_focus
    if data.time_range_start is not None:
        project.time_range_start = data.time_range_start
    if data.time_range_end is not None:
        project.time_range_end = data.time_range_end
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
        temporal_distribution=data.temporal_distribution,
        content_focus=data.content_focus,
    )

    return {
        "message": "Reclip pipeline started",
        "project_id": project_id,
        "task_id": task_id,
        "settings": data.model_dump(),
    }


# ============================================
# SSE & Audit Trail (context2-upgrade.md Section 3.2 & 7.1)
# ============================================
@router.get("/projects/{project_id}/events")
async def stream_project_events(
    project_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Server-Sent Events (SSE) stream for real-time project pipeline updates.
    """
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    async def event_generator():
        while True:
            result = await session.execute(
                select(Project)
                .options(selectinload(Project.jobs))
                .where(Project.id == uuid.UUID(project_id))
            )
            project = result.scalar_one_or_none()
            if not project:
                yield f"event: error\ndata: {json.dumps({'error': 'Project not found'})}\n\n"
                break

            payload = {
                "project_id": str(project.id),
                "status": project.status,
                "jobs": [
                    {
                        "id": str(j.id),
                        "stage": j.stage,
                        "status": j.status,
                        "error_message": j.error_message,
                    }
                    for j in project.jobs
                ],
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if project.status in ("done", "failed"):
                break

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/projects/{project_id}/audit-trail")
async def get_project_audit_trail(
    project_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Returns full immutable audit trail for rights, ingest, and editorial events.
    """
    from clipforge_core.models import ProjectAuditEvent

    result = await session.execute(
        select(ProjectAuditEvent)
        .where(ProjectAuditEvent.project_id == uuid.UUID(project_id))
        .order_by(ProjectAuditEvent.created_at.asc())
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]


# ============================================
# Phase 8: Audio Catalogs & Brand Kits
# ============================================
@router.get("/audio/voices")
async def list_voice_personas():
    """Returns available studio voice personas."""
    from clipforge_core.services.tts_service import VOICE_PERSONAS
    return VOICE_PERSONAS


@router.get("/audio/music")
async def list_music_tracks():
    """Returns available royalty-free background music tracks."""
    from clipforge_core.services.music_library import MUSIC_TRACKS
    return MUSIC_TRACKS


@router.get("/brand-kits")
async def list_brand_kits(session: AsyncSession = Depends(get_async_session)):
    """List all saved brand kits."""
    from clipforge_core.models import BrandKit
    result = await session.execute(select(BrandKit).order_by(BrandKit.created_at.desc()))
    return result.scalars().all()


@router.post("/brand-kits")
async def create_brand_kit(
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new brand kit."""
    from clipforge_core.models import BrandKit
    kit = BrandKit(
        id=uuid.uuid4(),
        name=payload.get("name", "Default Brand Kit"),
        primary_color=payload.get("primary_color", "#6366F1"),
        secondary_color=payload.get("secondary_color", "#10B981"),
        font_family=payload.get("font_family", "Montserrat"),
        logo_url=payload.get("logo_url"),
        watermark_position=payload.get("watermark_position", "top_right"),
        default_cta_text=payload.get("default_cta_text", "Subscribe for more"),
    )
    session.add(kit)
    await session.commit()
    await session.refresh(kit)
    return kit


@router.post("/clips/{clip_id}/rerender")
async def rerender_single_clip(
    clip_id: str,
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Re-render a single clip with custom trimming, caption style, voiceover, or effects
    without re-running upstream download and transcription.
    """
    from pathlib import Path

    from clipforge_core.services.audio_mixer import mix_audio_tracks
    from clipforge_core.services.effects_engine import apply_motion_effects
    from clipforge_core.services.media_probe import probe_media
    from clipforge_core.services.music_library import ensure_synth_bed
    from clipforge_core.services.render_engine import build_render_manifest, render_clip
    from clipforge_core.services.transformation_scorer import calculate_transformation_score
    from clipforge_core.services.tts_service import synthesize_voiceover

    result = await session.execute(select(Clip).where(Clip.id == uuid.UUID(clip_id)).options(selectinload(Clip.project)))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    project = clip.project
    project_dir = Path(settings.MEDIA_DIR) / str(project.id)
    source_video = project_dir / "source.mp4"
    if not source_video.exists():
        raise HTTPException(status_code=400, detail="Source video missing on disk")

    start_sec = float(payload.get("start_sec", clip.start_sec))
    end_sec = float(payload.get("end_sec", clip.end_sec))
    caption_style = payload.get("caption_style", "bold_karaoke")
    crop_mode = payload.get("crop_mode", "face_track")
    voiceover_text = payload.get("voiceover_text")
    voice_id = payload.get("voice_id", "en-US-JennyNeural")
    music_track = payload.get("music_track")
    raw_effects = payload.get("effects", [])

    # Load transcript segments and face tracking if available
    analysis_file = project_dir / "analysis.json"
    segments = []
    focal_x = 0.5

    if "focal_x" in payload and payload["focal_x"] is not None:
        focal_x = float(payload["focal_x"])
    elif crop_mode == "face_track" and analysis_file.exists():
        try:
            import json
            analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
            segments = analysis_data.get("transcript", {}).get("segments", [])
            focal_timeline = analysis_data.get("face_tracking", {}).get("timeline", [])
            clip_pts = [
                f["focal_x"] for f in focal_timeline
                if start_sec <= f.get("time_sec", 0.0) <= end_sec
            ]
            if clip_pts:
                focal_x = sum(clip_pts) / len(clip_pts)
            else:
                focal_x = float(analysis_data.get("face_tracking", {}).get("average_focal_x", 0.5))
        except Exception:
            focal_x = 0.5
    elif analysis_file.exists():
        try:
            import json
            analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
            segments = analysis_data.get("transcript", {}).get("segments", [])
        except Exception:
            segments = []

    # Filter effects to active and verified effects (All 6 verified: film_grain, vignette, zoom, camera_shake, rgb_split, vhs_noise)
    active_effects = []
    for eff in raw_effects:
        eff_id = eff.get("id") or eff.get("effect_id") or eff.get("type", "")
        if eff_id in [
            "film_grain", "grain",
            "vignette",
            "zoom", "punch_in_zoom",
            "camera_shake", "shake",
            "rgb_split", "rgb_glitch",
            "vhs_noise", "vhs_retro"
        ] and eff.get("enabled", True):
            active_effects.append({
                "id": eff_id,
                "type": eff_id,
                "intensity": float(eff.get("intensity", 0.5)),
                "enabled": True,
            })

    clips_dir = project_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    out_video_path = clips_dir / f"clip_{clip.id}_rerendered.mp4"
    out_thumb_path = clips_dir / f"clip_{clip.id}_thumb.jpg"

    # Optional Voiceover synthesis (Local Kokoro TTS)
    vo_path = None
    vo_asset_id = None
    actual_vo_duration = 0.0
    if voiceover_text and voiceover_text.strip():
        vo_asset_id = str(uuid.uuid4())
        vo_path = clips_dir / f"vo_{clip.id}.wav"
        synth_res = synthesize_voiceover(voiceover_text, voice_id=voice_id, output_path=vo_path)
        actual_vo_duration = float(synth_res.get("duration_sec", 0.0))

    # Optional Music bed
    bg_music_path = None
    if music_track and music_track != "none":
        bg_music_path = clips_dir / f"music_{clip.id}.aac"
        ensure_synth_bed(music_track, bg_music_path, duration_sec=end_sec - start_sec)

    render_clip(
        source_path=source_video,
        output_path=out_video_path,
        start_sec=start_sec,
        end_sec=end_sec,
        crop_mode=crop_mode,
        focal_x=focal_x,
        caption_style=caption_style,
        transcript_segments=segments,
        output_thumbnail_path=out_thumb_path,
    )

    # Apply motion effects post-render if requested
    if active_effects:
        apply_motion_effects(
            source_video_path=out_video_path,
            output_video_path=out_video_path,
            effects=active_effects,
            duration_sec=end_sec - start_sec,
        )

    # If VO or Music present, mix into the rendered video and remux atomically
    if vo_path or bg_music_path:
        mixed_audio = clips_dir / f"mixed_{clip.id}.aac"
        clip_duration = end_sec - start_sec
        buffer_sec = float(payload.get("outro_buffer_sec", 0.5))
        vo_style = payload.get("voiceover_style")

        # Two-pass placement computation using real synthesized duration
        if vo_style == "outro_cta":
            # Exact tail-anchoring using actual synthesized duration
            vo_offset = max(0.5, clip_duration - actual_vo_duration - buffer_sec)
        elif "voiceover_start_offset_sec" in payload and payload["voiceover_start_offset_sec"] is not None:
            requested_offset = float(payload["voiceover_start_offset_sec"])
            # Overflow guard: if requested offset + audio overflows clip duration, clamp back
            if vo_path and (requested_offset + actual_vo_duration > clip_duration):
                vo_offset = max(0.5, clip_duration - actual_vo_duration - buffer_sec)
            else:
                vo_offset = requested_offset
        else:
            vo_offset = float(payload.get("voiceover_delay_sec", 0.5))

        mix_audio_tracks(
            source_video_path=out_video_path,
            output_audio_path=mixed_audio,
            start_sec=0.0,
            end_sec=clip_duration,
            voiceover_path=vo_path,
            music_path=bg_music_path,
            voiceover_delay_sec=vo_offset,
            voiceover_start_offset_sec=vo_offset,
        )
        # Remux mixed audio into out_video_path atomically
        temp_muxed = clips_dir / f"clip_{clip.id}_muxed_temp.mp4"
        mux_cmd = [
            "ffmpeg", "-y",
            "-i", str(out_video_path),
            "-i", str(mixed_audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(temp_muxed),
        ]
        import subprocess
        subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        import os
        os.replace(temp_muxed, out_video_path)

    # Build and write updated manifest
    import json
    source_probe = probe_media(source_video)
    manifest = build_render_manifest(
        clip_id=str(clip.id),
        project_id=str(project.id),
        source_asset_id=str(uuid.uuid4()),
        source_path=str(source_video),
        source_probe=source_probe,
        start_sec=start_sec,
        end_sec=end_sec,
        crop_mode=crop_mode,
        focal_x=focal_x,
        caption_style=caption_style,
        editorial_template=project.editorial_template or "explainer",
        rights_basis=project.rights_basis or "owned",
        source_risk_label=project.source_risk_label or "lower_workflow_risk",
        transformation_score=clip.transformation_score or 75,
        transformation_breakdown=clip.transformation_breakdown or {},
        effect_layers=active_effects,
        audio_mode="mix" if (vo_path or bg_music_path) else "original_only",
        voiceover_asset_id=vo_asset_id,
    )
    if music_track and music_track != "none":
        manifest["music_track"] = music_track
    manifest_path = clips_dir / f"clip_{clip.id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Calculate updated transformation score
    t_data = calculate_transformation_score(
        clip_duration_sec=end_sec - start_sec,
        total_source_duration_sec=600.0,
        has_commentary=bool(vo_path),
        editorial_template=project.editorial_template or "explainer",
        callout_count=2,
        has_visual_reframing=True,
    )

    # Update Clip record
    rel_file = f"media/{project.id}/clips/{out_video_path.name}"
    rel_thumb = f"media/{project.id}/clips/{out_thumb_path.name}"
    clip.start_sec = start_sec
    clip.end_sec = end_sec
    clip.file_url = rel_file
    clip.thumbnail_url = rel_thumb
    clip.render_manifest = manifest
    clip.transformation_score = t_data["score"]
    clip.transformation_breakdown = t_data["breakdown"]

    await session.commit()
    await session.refresh(clip)

    return {
        "status": "success",
        "clip_id": str(clip.id),
        "file_url": rel_file,
        "thumbnail_url": rel_thumb,
        "transformation_score": clip.transformation_score,
    }


@router.post("/projects/{project_id}/retry-stage")
async def retry_project_stage(
    project_id: str,
    payload: dict,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Rerun a specific failed pipeline stage (download, transcribe, select, render) with idempotency.
    """
    stage = payload.get("stage", "select")
    result = await session.execute(select(Project).where(Project.id == uuid.UUID(project_id)).options(selectinload(Project.jobs)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = next((j for j in project.jobs if j.stage == stage), None)
    if job:
        job.status = "pending"
        job.error_message = None
        await session.commit()

    if stage in ("select", "llm"):
        from clipforge_core.workers.select import select_clips
        select_clips.delay(
            project_id=project_id,
            clip_count=project.clip_count or 5,
            min_length_sec=project.min_length_sec or 20,
            max_length_sec=project.max_length_sec or 60,
        )
    elif stage in ("render", "crop", "caption"):
        from clipforge_core.workers.render import render_project_clips
        render_project_clips.delay(project_id=project_id)
    elif stage in ("transcribe", "analysis"):
        from clipforge_core.workers.analysis import run_analysis
        source_path = f"{settings.MEDIA_DIR}/{project_id}/source.mp4"
        if not Path(source_path).exists() and project.source_value and Path(project.source_value).exists():
            source_path = project.source_value
        run_analysis.delay(project_id=project_id, source_path=source_path)

    return {"message": f"Stage '{stage}' re-enqueued for project {project_id}"}


@router.post("/projects/{project_id}/cleanup")
async def cleanup_project_artifacts(project_id: str):
    """
    Purge temporary artifacts and drafts while preserving final rendered outputs.
    """
    from clipforge_core.services.cleanup import cleanup_project_temp_files
    res = cleanup_project_temp_files(project_id=project_id, max_age_hours=0.0)
    return res


@router.post("/utils/browse-file")
async def browse_local_file(title: str = "Select Video File", initial_dir: str | None = None):
    """
    Open native Windows Explorer file dialog to pick a local video file.
    Returns the resolved absolute path on disk.
    """
    from clipforge_core.services.file_picker import pick_file_sync
    import asyncio
    result = await asyncio.to_thread(pick_file_sync, title=title, initial_dir=initial_dir)
    return result


@router.post("/utils/browse-folder")
async def browse_local_folder(title: str = "Select Destination Folder", initial_dir: str | None = None):
    """
    Open native Windows Explorer directory dialog to pick a local folder.
    Returns the resolved absolute path on disk.
    """
    from clipforge_core.services.file_picker import pick_folder_sync
    import asyncio
    result = await asyncio.to_thread(pick_folder_sync, title=title, initial_dir=initial_dir)
    return result


def _resolve_project_dir(proj_id: str) -> Path:
    candidates = [
        Path(settings.MEDIA_DIR) / proj_id,
        Path("media") / proj_id,
        Path(__file__).resolve().parents[4] / "media" / proj_id,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


@router.get("/clips/{clip_id}/voiceover-context")
async def get_clip_voiceover_context(
    clip_id: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get transcript context and silence gap intelligence for a clip,
    enabling UI to display source dialogue and conditionally enable the Explainer style.
    """
    result = await session.execute(
        select(Clip).where(Clip.id == uuid.UUID(clip_id)).options(selectinload(Clip.project))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    project = clip.project
    project_dir = _resolve_project_dir(str(project.id))
    transcript_file = project_dir / "transcript.json"
    analysis_file = project_dir / "analysis.json"

    all_segments = []
    if transcript_file.exists():
        try:
            t_data = json.loads(transcript_file.read_text(encoding="utf-8"))
            all_segments = t_data.get("segments", [])
        except Exception:
            pass
    if not all_segments and analysis_file.exists():
        try:
            a_data = json.loads(analysis_file.read_text(encoding="utf-8"))
            all_segments = a_data.get("transcript", {}).get("segments", [])
        except Exception:
            pass

    # Filter segments overlapping with clip
    clip_segments = []
    text_pieces = []
    for s in all_segments:
        s_start = float(s.get("start", 0.0))
        s_end = float(s.get("end", 0.0))
        if s_end > clip.start_sec and s_start < clip.end_sec:
            clip_segments.append(s)
            txt = s.get("text", "").strip()
            if txt:
                text_pieces.append(txt)

    transcript_snippet = " ".join(text_pieces)

    from clipforge_core.services.gap_detector import find_silence_gaps
    gaps = find_silence_gaps(
        transcript_segments=all_segments,
        clip_start_sec=clip.start_sec,
        clip_end_sec=clip.end_sec,
        min_gap_sec=3.0,
    )

    duration = round(clip.end_sec - clip.start_sec, 2)
    resolved_title = (clip.render_manifest or {}).get("title") or (clip.project.title if clip.project else "Untitled Clip")

    return {
        "clip_id": str(clip.id),
        "title": resolved_title,
        "start_sec": clip.start_sec,
        "end_sec": clip.end_sec,
        "duration_sec": duration,
        "transcript_snippet": transcript_snippet,
        "segments": clip_segments,
        "has_qualifying_gap": len(gaps) > 0,
        "gaps": gaps,
    }


@router.post("/clips/{clip_id}/generate-voiceover-script")
async def generate_clip_voiceover_script(
    clip_id: str,
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
):
    """
    Generate an AI voiceover script matching a style, enforcing Kokoro word counts,
    grounding against the transcript snippet, and computing start offset.
    """
    style = payload.get("style", "hook_intro")
    result = await session.execute(
        select(Clip).where(Clip.id == uuid.UUID(clip_id)).options(selectinload(Clip.project))
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    project = clip.project
    project_dir = _resolve_project_dir(str(project.id))
    transcript_file = project_dir / "transcript.json"
    analysis_file = project_dir / "analysis.json"

    all_segments = []
    if transcript_file.exists():
        try:
            t_data = json.loads(transcript_file.read_text(encoding="utf-8"))
            all_segments = t_data.get("segments", [])
        except Exception:
            pass
    if not all_segments and analysis_file.exists():
        try:
            a_data = json.loads(analysis_file.read_text(encoding="utf-8"))
            all_segments = a_data.get("transcript", {}).get("segments", [])
        except Exception:
            pass

    # Extract dialogue text in clip range
    text_pieces = []
    for s in all_segments:
        s_start = float(s.get("start", 0.0))
        s_end = float(s.get("end", 0.0))
        if s_end > clip.start_sec and s_start < clip.end_sec:
            txt = s.get("text", "").strip()
            if txt:
                text_pieces.append(txt)
    transcript_snippet = " ".join(text_pieces)

    duration = clip.end_sec - clip.start_sec
    clip_title = (clip.render_manifest or {}).get("title") or (clip.project.title if clip.project else "Highlight")

    preview_audio_file = project_dir / "clips" / f"vo_preview_{clip.id}.wav"
    from clipforge_core.services.script_generator import generate_voiceover_script
    script_data = await generate_voiceover_script(
        clip_title=clip_title,
        transcript_snippet=transcript_snippet,
        style=style,
        clip_duration_sec=duration,
        clip_start_sec=clip.start_sec,
        transcript_segments=all_segments,
        output_audio_path=preview_audio_file,
    )
    if preview_audio_file.exists():
        script_data["audio_preview_url"] = f"media/{project.id}/clips/{preview_audio_file.name}"

    return script_data




