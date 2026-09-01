"""
ClipForge AI — Pipeline Orchestrator (v2)

Chains the v2 pipeline stages with granular status tracking:
  1. Ingest / Download (`download_source`)
  2. Unified Analysis (`run_analysis`: Whisper + SceneDetect + MediaPipe)
  3. LLM Candidate Selection (`select_clips`: brief-aware + transformation scoring + scene snapping)
  4. Professional Rendering (`render_project_clips`: 9:16 reframe, ASS captions, loudnorm, manifests)
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from clipforge_core.celery_app import celery_app
from clipforge_core.database import get_sync_session
from clipforge_core.models import Job, Project
from clipforge_core.workers.analysis import run_analysis
from clipforge_core.workers.download import download_source
from clipforge_core.workers.render import render_project_clips
from clipforge_core.workers.select import select_clips

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ["download", "transcribe", "select", "crop", "caption"]


def create_pipeline_jobs(project_id: str, session: Session | None = None) -> list[dict]:
    """Create job records for all pipeline stages."""
    close_session = False
    if session is None:
        session = get_sync_session()
        close_session = True

    try:
        jobs = []
        for stage in PIPELINE_STAGES:
            job = Job(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                stage=stage,
                status="pending",
                updated_at=datetime.now(timezone.utc),
            )
            session.add(job)
            jobs.append({"id": str(job.id), "stage": stage, "status": "pending"})

        session.commit()
        logger.info(f"Created {len(jobs)} pipeline jobs for project {project_id}")
        return jobs
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create pipeline jobs: {e}")
        raise
    finally:
        if close_session:
            session.close()


def _update_job(project_id: str, stage: str, status: str, error_message: str | None = None) -> None:
    """Update a specific job stage status."""
    session = get_sync_session()
    try:
        job = (
            session.query(Job)
            .filter(
                Job.project_id == uuid.UUID(project_id),
                Job.stage == stage,
            )
            .first()
        )
        if job:
            job.status = status
            job.error_message = error_message
            if status == "running":
                job.started_at = datetime.now(timezone.utc)
            if status in ("success", "failed"):
                job.completed_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update job {stage}: {e}")
        session.rollback()
    finally:
        session.close()


def _update_project(project_id: str, status: str) -> None:
    """Update project-level status."""
    session = get_sync_session()
    try:
        project = session.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
        if project:
            project.status = status
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update project status: {e}")
        session.rollback()
    finally:
        session.close()


@celery_app.task(
    name="app.services.pipeline.run_post_download",
    queue="default",
    bind=True,
    max_retries=0,
)
def run_post_download(
    self,
    download_result: dict,
    project_id: str,
    campaign_brief: dict,
    clip_count: int,
    min_length_sec: int,
    max_length_sec: int,
    aspect_ratio: str,
    caption_style: str,
    custom_prompt: str | None = None,
    time_range_start: float | None = None,
    time_range_end: float | None = None,
) -> dict:
    """
    Run analysis -> selection -> rendering sequentially after ingest.
    """
    source_path = download_result["source_path"]

    # ─── STAGE 2: UNIFIED ANALYSIS (transcribe, scene cuts, face track) ───
    logger.info(f"[Pipeline] Analysis starting for project {project_id}")
    _update_job(project_id, "transcribe", "running")
    _update_project(project_id, "transcribing")

    try:
        run_analysis(project_id=project_id, source_path=source_path)
        _update_job(project_id, "transcribe", "success")
        logger.info(f"[Pipeline] Analysis complete for {project_id}")
    except Exception as e:
        _update_job(project_id, "transcribe", "failed", str(e))
        _update_project(project_id, "failed")
        raise

    # ─── STAGE 3: BRIEF-AWARE SELECTION & TRANSFORMATION SCORING ───
    logger.info(f"[Pipeline] LLM Selection starting for project {project_id}")
    _update_job(project_id, "select", "running")
    _update_project(project_id, "selecting")

    try:
        select_clips(
            project_id=project_id,
            clip_count=clip_count,
            min_length_sec=min_length_sec,
            max_length_sec=max_length_sec,
            custom_prompt=custom_prompt,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        )
        _update_job(project_id, "select", "success")
        logger.info(f"[Pipeline] Candidate selection complete for {project_id}")
    except Exception as e:
        _update_job(project_id, "select", "failed", str(e))
        _update_project(project_id, "failed")
        raise

    # ─── STAGE 4 & 5: PROFESSIONAL RENDERING & MANIFEST GENERATION ───
    logger.info(f"[Pipeline] Rendering clips with manifests for {project_id}")
    _update_job(project_id, "crop", "running")
    _update_job(project_id, "caption", "running")
    _update_project(project_id, "encoding")

    try:
        render_res = render_project_clips(project_id=project_id)
        _update_job(project_id, "crop", "success")
        _update_job(project_id, "caption", "success")
        _update_project(project_id, "done")
        logger.info(f"[Pipeline] COMPLETE for {project_id}: {render_res.get('total_rendered', 0)} clips rendered with manifests")
        return {
            "project_id": project_id,
            "clips_produced": render_res.get("total_rendered", 0),
            "status": "done",
        }
    except Exception as e:
        _update_job(project_id, "crop", "failed", str(e))
        _update_job(project_id, "caption", "failed", str(e))
        _update_project(project_id, "failed")
        raise


def dispatch_pipeline(project_id: str, project: Project) -> str:
    """
    Dispatch the full v2 pipeline as a Celery chain.
    """
    from celery import chain as celery_chain

    brief_json = project.campaign_brief.brief_json if project.campaign_brief else {}

    pipeline = celery_chain(
        download_source.si(
            project_id=project_id,
            source_type=project.source_type,
            source_value=project.source_value,
        ),
        run_post_download.s(
            project_id=project_id,
            campaign_brief=brief_json,
            clip_count=project.clip_count,
            min_length_sec=project.min_length_sec,
            max_length_sec=project.max_length_sec,
            aspect_ratio=project.aspect_ratio,
            caption_style=project.caption_style,
        ),
    )

    result = pipeline.apply_async()
    logger.info(f"[Pipeline] Dispatched v2 chain for project {project_id} (task_id={result.id})")
    return str(result.id)


def dispatch_reclip(
    project_id: str,
    clip_count: int = 5,
    min_length_sec: int = 20,
    max_length_sec: int = 60,
    aspect_ratio: str = "9:16",
    caption_style: str = "bold_karaoke",
    custom_prompt: str | None = None,
    time_range_start: float | None = None,
    time_range_end: float | None = None,
) -> str:
    """
    Re-run select -> render pipeline.
    """
    from celery import chain as celery_chain

    reclip_chain = celery_chain(
        select_clips.si(
            project_id=project_id,
            clip_count=clip_count,
            min_length_sec=min_length_sec,
            max_length_sec=max_length_sec,
            custom_prompt=custom_prompt,
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        ),
        render_project_clips.si(project_id=project_id),
    )

    result = reclip_chain.apply_async()
    logger.info(f"[Pipeline] Dispatched reclip chain for project {project_id} (task_id={result.id})")
    return str(result.id)
