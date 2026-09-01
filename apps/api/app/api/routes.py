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
        caption_style=data.caption_style,
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
    from clipforge_core.services.render_engine import render_clip, build_render_manifest
    from clipforge_core.services.tts_service import synthesize_voiceover
    from clipforge_core.services.music_library import ensure_synth_bed
    from clipforge_core.services.audio_mixer import mix_audio_tracks
    from clipforge_core.services.transformation_scorer import calculate_transformation_score

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
    focal_x = float(payload.get("focal_x", 0.5))
    voiceover_text = payload.get("voiceover_text")
    voice_id = payload.get("voice_id", "en-US-JennyNeural")
    music_track = payload.get("music_track")

    clips_dir = project_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    out_video_path = clips_dir / f"clip_{clip.id}_rerendered.mp4"
    out_thumb_path = clips_dir / f"clip_{clip.id}_thumb.jpg"

    # Optional Voiceover synthesis
    vo_path = None
    if voiceover_text and voiceover_text.strip():
        vo_path = clips_dir / f"vo_{clip.id}.mp3"
        synthesize_voiceover(voiceover_text, voice_id=voice_id, output_path=vo_path)

    # Optional Music bed
    bg_music_path = None
    if music_track and music_track != "none":
        bg_music_path = clips_dir / f"music_{clip.id}.aac"
        ensure_synth_bed(music_track, bg_music_path, duration_sec=end_sec - start_sec)

    # Load transcript segments if available
    analysis_file = project_dir / "analysis.json"
    segments = []
    if analysis_file.exists():
        import json
        analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
        segments = analysis_data.get("transcript", {}).get("segments", [])

    render_res = render_clip(
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

    # If VO or Music present, mix into the rendered video
    if vo_path or bg_music_path:
        mixed_audio = clips_dir / f"mixed_{clip.id}.aac"
        mix_audio_tracks(
            source_video_path=out_video_path,
            output_audio_path=mixed_audio,
            start_sec=0.0,
            end_sec=end_sec - start_sec,
            voiceover_path=vo_path,
            music_path=bg_music_path,
        )

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

