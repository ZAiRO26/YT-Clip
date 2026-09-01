"""
ClipForge AI — Pipeline Orchestrator

Chains the 5 pipeline stages and creates job tracking records.
Each stage writes its own status to the jobs table so the frontend
can show granular progress (per requirement #6).

Pipeline: download -> orchestrate_remaining (transcribe -> select -> crop -> caption)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from clipforge_core.celery_app import celery_app
from clipforge_core.database import get_sync_session
from clipforge_core.models import Clip, Job, Project

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


def _save_clips_to_db(project_id: str, selections: list[dict]) -> None:
    """Save selected clip segments to the clips table."""
    session = get_sync_session()
    try:
        for sel in selections:
            clip = Clip(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                start_sec=sel["start_sec"],
                end_sec=sel["end_sec"],
                score=sel.get("score"),
                reasoning=sel.get("reasoning"),
                review_status="pending",
            )
            session.add(clip)
        session.commit()
        logger.info(f"Saved {len(selections)} clips to database for project {project_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to save clips: {e}")
    finally:
        session.close()


def _update_clips_with_files(project_id: str, final_clips: list[dict]) -> None:
    """Update clip records with file URLs after processing."""
    session = get_sync_session()
    try:
        db_clips = (
            session.query(Clip)
            .filter(
                Clip.project_id == uuid.UUID(project_id),
            )
            .order_by(Clip.start_sec)
            .all()
        )

        for db_clip, final in zip(db_clips, final_clips):
            db_clip.file_url = final.get("final_path", "")
            if final.get("thumbnail_url"):
                db_clip.thumbnail_url = final.get("thumbnail_url")
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update clip files: {e}")
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
    Run transcribe -> select -> crop -> caption sequentially after download.

    This is a statically-registered Celery task (not dynamic) so the worker
    can find it at startup.
    """
    source_path = download_result["source_path"]
    project_dir = str(Path(source_path).parent)

    # ─── STAGE 2: TRANSCRIBE ───
    logger.info(f"[Pipeline] Transcribe starting for {project_id}")
    _update_job(project_id, "transcribe", "running")
    _update_project(project_id, "transcribing")

    try:
        from clipforge_core.workers.transcribe import transcribe_audio

        transcript = transcribe_audio(source_path, project_dir)
        _update_job(project_id, "transcribe", "success")
        logger.info(f"[Pipeline] Transcribe done: {transcript['segment_count']} segments")
    except Exception as e:
        _update_job(project_id, "transcribe", "failed", str(e))
        _update_project(project_id, "failed")
        raise

    # ─── STAGE 3: SELECT ───
    logger.info(f"[Pipeline] Select starting for {project_id}")
    _update_job(project_id, "select", "running")
    _update_project(project_id, "selecting")

    transcript_path = str(Path(project_dir) / "transcript.json")
    selections = []

    try:
        from clipforge_core.workers.select import select_clips

        selections_result = asyncio.run(
            select_clips(
                transcript_path=transcript_path,
                campaign_brief=campaign_brief,
                clip_count=clip_count,
                min_length_sec=min_length_sec,
                max_length_sec=max_length_sec,
                custom_prompt=custom_prompt,
                time_range_start=time_range_start,
                time_range_end=time_range_end,
            )
        )
        selections = selections_result["clips"]
        _update_job(project_id, "select", "success")
        logger.info(f"[Pipeline] Selected {len(selections)} clips via LLM")
    except Exception as e:
        logger.warning(f"[Pipeline] LLM selection failed: {e}, using fallback")
        # Fallback: evenly-spaced segments
        total_dur = transcript["duration_sec"]
        clip_duration = min(max_length_sec, max(min_length_sec, total_dur / max(1, clip_count)))
        for i in range(min(clip_count, max(1, int(total_dur / clip_duration)))):
            start = i * (total_dur / max(1, clip_count))
            end = min(start + clip_duration, total_dur)
            if end - start >= min_length_sec:
                selections.append(
                    {
                        "start_sec": round(start, 3),
                        "end_sec": round(end, 3),
                        "score": 0.5,
                        "reasoning": "Fallback: evenly-spaced (LLM unavailable)",
                    }
                )
        _update_job(project_id, "select", "success", error_message="Used fallback selection (LLM unavailable)")

    if not selections:
        _update_job(project_id, "select", "failed", "No clips could be selected")
        _update_project(project_id, "failed")
        return {"error": "No clips selected", "project_id": project_id}

    # Save clips to database
    _save_clips_to_db(project_id, selections)

    # ─── STAGE 4: CROP ───
    logger.info(f"[Pipeline] Crop starting for {project_id}")
    _update_job(project_id, "crop", "running")
    _update_project(project_id, "encoding")

    from clipforge_core.workers.crop import crop_clip

    clips_dir = Path(project_dir) / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    cropped_clips = []
    for i, sel in enumerate(selections):
        output_path = str(clips_dir / f"clip_{i:03d}_cropped.mp4")
        try:
            result = crop_clip(
                source_path=source_path,
                output_path=output_path,
                start_sec=sel["start_sec"],
                end_sec=sel["end_sec"],
                aspect_ratio=aspect_ratio,
            )
            result["index"] = i
            result["score"] = sel["score"]
            result["reasoning"] = sel["reasoning"]
            cropped_clips.append(result)
        except Exception as e:
            logger.error(f"[Pipeline] Crop failed for clip {i}: {e}")

    if cropped_clips:
        _update_job(project_id, "crop", "success")
    else:
        _update_job(project_id, "crop", "failed", "All clips failed to crop")
        _update_project(project_id, "failed")
        return {"error": "All clips failed to crop", "project_id": project_id}

    # ─── STAGE 5: CAPTION ───
    logger.info(f"[Pipeline] Caption starting for {project_id}")
    _update_job(project_id, "caption", "running")
    _update_project(project_id, "captioning")

    from clipforge_core.workers.caption import caption_clip as add_caption

    final_clips = []
    for clip in cropped_clips:
        idx = clip["index"]
        final_path = str(clips_dir / f"clip_{idx:03d}_final.mp4")
        try:
            cap_result = add_caption(
                input_path=clip["output_path"],
                output_path=final_path,
                caption_style=caption_style,
            )
            clip["final_path"] = cap_result["output_path"]
            clip["caption_method"] = cap_result["method"]
            final_clips.append(clip)
        except Exception as e:
            logger.error(f"[Pipeline] Caption failed for clip {idx}: {e}")
            clip["final_path"] = clip["output_path"]
            clip["caption_method"] = "none"
            final_clips.append(clip)

    from clipforge_core.workers.thumbnail import generate_thumbnail

    for clip in final_clips:
        idx = clip["index"]
        # Determine duration for smart frame extraction
        duration = clip.get("end_sec", 0) - clip.get("start_sec", 0)

        # We generate the thumbnail from the cropped (or final) video
        thumb_path = str(clips_dir / f"clip_{idx:03d}_thumb.jpg")

        if generate_thumbnail(clip["final_path"], thumb_path, duration):
            clip["thumbnail_url"] = thumb_path
        else:
            clip["thumbnail_url"] = None

    # Update clip records with file URLs
    _update_clips_with_files(project_id, final_clips)

    _update_job(project_id, "caption", "success")
    _update_project(project_id, "done")

    logger.info(f"[Pipeline] COMPLETE for {project_id}: {len(final_clips)} clips produced")

    return {
        "project_id": project_id,
        "clips_produced": len(final_clips),
        "status": "done",
    }


def dispatch_pipeline(project_id: str, project: Project) -> str:
    """
    Dispatch the full pipeline as a Celery chain.

    download.si() | run_post_download.s()

    Returns the Celery chain task ID.
    """
    from celery import chain as celery_chain

    from clipforge_core.workers.download import download_source

    pid = str(project.id)

    # Load campaign brief if linked
    campaign_brief = {}
    if project.campaign_brief:
        campaign_brief = project.campaign_brief.brief_json or {}

    # Build chain: download -> run_post_download
    pipeline = celery_chain(
        download_source.si(
            project_id=pid,
            source_type=project.source_type,
            source_value=project.source_value,
        ),
        run_post_download.s(
            project_id=pid,
            campaign_brief=campaign_brief,
            clip_count=project.clip_count,
            min_length_sec=project.min_length_sec,
            max_length_sec=project.max_length_sec,
            aspect_ratio=project.aspect_ratio,
            caption_style=project.caption_style,
            custom_prompt=getattr(project, "custom_prompt", None),
            time_range_start=getattr(project, "time_range_start", None),
            time_range_end=getattr(project, "time_range_end", None),
        ),
    )

    result = pipeline.apply_async()
    logger.info(f"Pipeline dispatched for project {pid}, chain_id={result.id}")
    return result.id


@celery_app.task(
    name="app.services.pipeline.run_reclip",
    queue="default",
    bind=True,
    max_retries=0,
)
def run_reclip(
    self,
    project_id: str,
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
    Re-run Select → Crop → Caption on an already-transcribed project.
    Skips Download and Transcribe entirely.
    New clips are appended (not replacing existing ones).
    """
    from clipforge_core.config import settings as app_settings

    media_dir = Path(app_settings.MEDIA_DIR)
    project_dir = media_dir / project_id
    source_path = str(project_dir / "source.mp4")
    transcript_path = str(project_dir / "transcript.json")

    if not Path(transcript_path).exists():
        _update_project(project_id, "failed")
        return {"error": "No transcript found. Run the full pipeline first.", "project_id": project_id}

    # Load transcript
    transcript = json.loads(Path(transcript_path).read_text(encoding="utf-8"))

    # If time range specified, filter transcript segments
    if time_range_start is not None or time_range_end is not None:
        start = time_range_start or 0.0
        end = time_range_end or transcript.get("duration_sec", 999999)
        filtered_segments = [
            seg for seg in transcript.get("segments", []) if seg["end"] >= start and seg["start"] <= end
        ]
        transcript["segments"] = filtered_segments
        transcript["full_text"] = " ".join(seg["text"] for seg in filtered_segments)
        # Write filtered transcript temporarily
        filtered_path = str(project_dir / "transcript_reclip.json")
        Path(filtered_path).write_text(json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8")
        transcript_path = filtered_path

    # ─── STAGE: SELECT ───
    logger.info(f"[Reclip] Select starting for {project_id}")
    _update_job(project_id, "select", "running")
    _update_project(project_id, "selecting")

    campaign_brief = {}
    selections = []

    try:
        from clipforge_core.workers.select import select_clips

        selections_result = asyncio.run(
            select_clips(
                transcript_path=transcript_path,
                campaign_brief=campaign_brief,
                clip_count=clip_count,
                min_length_sec=min_length_sec,
                max_length_sec=max_length_sec,
                custom_prompt=custom_prompt,
            )
        )
        selections = selections_result["clips"]
        _update_job(project_id, "select", "success")
        logger.info(f"[Reclip] Selected {len(selections)} clips via LLM")
    except Exception as e:
        logger.warning(f"[Reclip] LLM selection failed: {e}, using fallback")
        total_dur = transcript.get("duration_sec", 0)
        if time_range_start is not None:
            total_dur = (time_range_end or total_dur) - (time_range_start or 0)
        offset = time_range_start or 0
        clip_duration = min(max_length_sec, max(min_length_sec, total_dur / max(1, clip_count)))
        for i in range(min(clip_count, max(1, int(total_dur / clip_duration)))):
            start = offset + i * (total_dur / max(1, clip_count))
            end = min(start + clip_duration, (time_range_end or transcript.get("duration_sec", 999999)))
            if end - start >= min_length_sec:
                selections.append(
                    {
                        "start_sec": round(start, 3),
                        "end_sec": round(end, 3),
                        "score": 0.5,
                        "reasoning": "Fallback: evenly-spaced (LLM unavailable)",
                    }
                )
        _update_job(project_id, "select", "success", error_message="Used fallback selection (LLM unavailable)")

    if not selections:
        _update_job(project_id, "select", "failed", "No clips could be selected")
        _update_project(project_id, "failed")
        return {"error": "No clips selected", "project_id": project_id}

    _save_clips_to_db(project_id, selections)

    # ─── STAGE: CROP ───
    logger.info(f"[Reclip] Crop starting for {project_id}")
    _update_job(project_id, "crop", "running")
    _update_project(project_id, "encoding")

    from clipforge_core.workers.crop import crop_clip

    clips_dir = Path(project_dir) / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Use a timestamp suffix to avoid overwriting existing clips
    import time

    batch_id = str(int(time.time()))

    cropped_clips = []
    for i, sel in enumerate(selections):
        output_path = str(clips_dir / f"clip_{batch_id}_{i:03d}_cropped.mp4")
        try:
            result = crop_clip(
                source_path=source_path,
                output_path=output_path,
                start_sec=sel["start_sec"],
                end_sec=sel["end_sec"],
                aspect_ratio=aspect_ratio,
            )
            result["index"] = i
            result["score"] = sel["score"]
            result["reasoning"] = sel["reasoning"]
            cropped_clips.append(result)
        except Exception as e:
            logger.error(f"[Reclip] Crop failed for clip {i}: {e}")

    if cropped_clips:
        _update_job(project_id, "crop", "success")
    else:
        _update_job(project_id, "crop", "failed", "All clips failed to crop")
        _update_project(project_id, "failed")
        return {"error": "All clips failed to crop", "project_id": project_id}

    # ─── STAGE: CAPTION ───
    logger.info(f"[Reclip] Caption starting for {project_id}")
    _update_job(project_id, "caption", "running")
    _update_project(project_id, "captioning")

    from clipforge_core.workers.caption import caption_clip as add_caption

    final_clips = []
    for clip in cropped_clips:
        idx = clip["index"]
        final_path = str(clips_dir / f"clip_{batch_id}_{idx:03d}_final.mp4")
        try:
            cap_result = add_caption(
                input_path=clip["output_path"],
                output_path=final_path,
                caption_style=caption_style,
            )
            clip["final_path"] = cap_result["output_path"]
            clip["caption_method"] = cap_result["method"]
            final_clips.append(clip)
        except Exception as e:
            logger.error(f"[Reclip] Caption failed for clip {idx}: {e}")
            clip["final_path"] = clip["output_path"]
            clip["caption_method"] = "none"
            final_clips.append(clip)

    from clipforge_core.workers.thumbnail import generate_thumbnail

    for clip in final_clips:
        idx = clip["index"]
        duration = clip.get("end_sec", 0) - clip.get("start_sec", 0)
        thumb_path = str(clips_dir / f"clip_{batch_id}_{idx:03d}_thumb.jpg")

        if generate_thumbnail(clip["final_path"], thumb_path, duration):
            clip["thumbnail_url"] = thumb_path
        else:
            clip["thumbnail_url"] = None

    _update_clips_with_files(project_id, final_clips)

    _update_job(project_id, "caption", "success")
    _update_project(project_id, "done")

    # Clean up temporary filtered transcript
    filtered_tmp = project_dir / "transcript_reclip.json"
    if filtered_tmp.exists():
        filtered_tmp.unlink(missing_ok=True)

    logger.info(f"[Reclip] COMPLETE for {project_id}: {len(final_clips)} new clips produced")

    return {
        "project_id": project_id,
        "clips_produced": len(final_clips),
        "status": "done",
    }


def dispatch_reclip(
    project_id: str,
    clip_count: int,
    min_length_sec: int,
    max_length_sec: int,
    aspect_ratio: str,
    caption_style: str,
    custom_prompt: str | None = None,
    time_range_start: float | None = None,
    time_range_end: float | None = None,
) -> str:
    """Dispatch a reclip task for an existing project."""
    result = run_reclip.apply_async(
        kwargs={
            "project_id": project_id,
            "clip_count": clip_count,
            "min_length_sec": min_length_sec,
            "max_length_sec": max_length_sec,
            "aspect_ratio": aspect_ratio,
            "caption_style": caption_style,
            "custom_prompt": custom_prompt,
            "time_range_start": time_range_start,
            "time_range_end": time_range_end,
        }
    )
    logger.info(f"Reclip dispatched for project {project_id}, task_id={result.id}")
    return result.id
