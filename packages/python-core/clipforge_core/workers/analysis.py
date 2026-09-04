"""
ClipForge AI — Unified Analysis Worker (v2)

Pipeline stage 2 (Analysis Queue):
- faster-whisper transcription with word-level timestamps
- PySceneDetect scene cut boundaries
- MediaPipe face & speaker tracking with center-crop fallback
- Outputs complete analysis.json to project directory
- Updates jobs and emits audit events
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from clipforge_core.celery_app import celery_app
from clipforge_core.config import settings
from clipforge_core.database import get_sync_session
from clipforge_core.models import Job, Project, ProjectAuditEvent
from clipforge_core.services.face_tracker import track_faces
from clipforge_core.services.scene_detector import detect_scenes
from clipforge_core.workers.transcribe import transcribe_audio

logger = logging.getLogger(__name__)


from clipforge_core.services.progress import update_job_progress


def _update_project_status(project_id: str, status: str) -> None:
    """Update project status."""
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
    name="clipforge_core.workers.analysis.run_analysis",
    queue="analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def run_analysis(self, project_id: str, source_path: str) -> Dict[str, Any]:
    """
    Unified analysis pipeline stage:
      1. Whisper transcription
      2. Scene boundary detection
      3. Face/subject tracking
    """
    logger.info(f"[Analysis] Starting unified analysis for project {project_id}")
    update_job_progress(project_id, stage="analysis", status="running", percent=5.0, detail="Loading Whisper transcription model...", force_write=True)
    _update_project_status(project_id, "transcribing")

    project_dir = Path(settings.MEDIA_DIR) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    video_file = Path(source_path)

    if not video_file.exists():
        error_msg = f"Source video not found for analysis: {source_path}"
        update_job_progress(project_id, stage="analysis", status="failed", error_message=error_msg, force_write=True)
        _update_project_status(project_id, "failed")
        raise FileNotFoundError(error_msg)

    try:
        # Step 1: Faster-Whisper Transcription (or load existing cached transcript)
        transcript_file = project_dir / "transcript.json"
        if transcript_file.exists():
            logger.info(f"[Analysis] Found existing transcript.json for project {project_id}, reusing cached transcript")
            transcript = json.loads(transcript_file.read_text(encoding="utf-8"))
            update_job_progress(project_id, stage="analysis", percent=60.0, detail=f"Reused cached transcript ({len(transcript.get('segments', []))} segments).", force_write=True)
        else:
            logger.info(f"[Analysis] Transcribing audio for project {project_id}")
            transcript = transcribe_audio(str(video_file), str(project_dir), project_id=project_id)

        # Step 2: Scene Detection with graceful fallback
        update_job_progress(project_id, stage="analysis", percent=62.0, detail="Detecting scene cuts & visual boundaries...", force_write=True)
        try:
            logger.info(f"[Analysis] Detecting scenes for project {project_id}")
            scenes = detect_scenes(video_file)
            update_job_progress(project_id, stage="analysis", percent=75.0, detail=f"Detected {len(scenes)} visual scene cuts.", force_write=True)
        except Exception as e:
            logger.warning(f"[Analysis] Scene detection warning: {e}. Defaulting to continuous scene.")
            scenes = [{
                "scene_id": 1,
                "start_sec": 0.0,
                "end_sec": transcript.get("duration_sec", 60.0),
                "duration_sec": transcript.get("duration_sec", 60.0),
                "start_frame": 0,
                "end_frame": int(transcript.get("duration_sec", 60.0) * 30),
            }]
            update_job_progress(project_id, stage="analysis", percent=75.0, detail="Scene detection fallback applied (single scene).", force_write=True)

        # Step 3: Face & Subject Tracking with active speaker detection
        update_job_progress(project_id, stage="analysis", percent=77.0, detail="Analyzing face & active speaker tracking...", force_write=True)

        def on_face_progress(face_pct: float, detail_msg: str):
            # Maps face tracking 0-100% into 77% - 94% of analysis stage
            overall_pct = 77.0 + (face_pct / 100.0) * 17.0
            update_job_progress(
                project_id,
                stage="analysis",
                percent=round(overall_pct, 1),
                detail=detail_msg,
            )

        try:
            logger.info(f"[Analysis] Tracking face coordinates for project {project_id}")
            face_data = track_faces(video_file, transcript=transcript, progress_callback=on_face_progress)
            update_job_progress(project_id, stage="analysis", percent=95.0, detail="Face tracking complete. Consolidating timeline...", force_write=True)
        except Exception as e:
            logger.warning(f"[Analysis] Face tracking warning: {e}. Defaulting to center-crop.")
            face_data = {
                "timeline": [],
                "average_focal_x": 0.5,
                "std_dev_focal_x": 0.0,
                "total_samples": 0,
                "faces_detected_samples": 0,
                "detection_rate": 0.0,
                "fallback_used": True,
            }
            update_job_progress(project_id, stage="analysis", percent=95.0, detail="Face tracking fallback applied (center-crop).", force_write=True)

        analysis_result = {
            "project_id": project_id,
            "transcript": transcript,
            "scenes": scenes,
            "face_tracking": face_data,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save consolidated analysis.json
        analysis_path = project_dir / "analysis.json"
        analysis_path.write_text(json.dumps(analysis_result, indent=2, ensure_ascii=False), encoding="utf-8")

        # Save audit event in DB
        session = get_sync_session()
        try:
            audit = ProjectAuditEvent(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                event_type="analysis_completed",
                payload={
                    "segment_count": len(transcript.get("segments", [])),
                    "scene_count": len(scenes),
                    "face_fallback_used": face_data.get("fallback_used", False),
                    "speaker_tracking_used": face_data.get("speaker_tracking_used", False),
                    "language": transcript.get("language", "unknown"),
                    "duration_sec": transcript.get("duration_sec", 0.0),
                },
            )
            session.add(audit)
            session.commit()
        except Exception as e:
            logger.warning(f"Failed to record analysis audit event: {e}")
            session.rollback()
        finally:
            session.close()

        update_job_progress(project_id, stage="analysis", status="success", percent=100.0, detail="Analysis complete.", force_write=True)
        logger.info(f"[Analysis] Complete for project {project_id}: {len(transcript.get('segments', []))} transcript segments, {len(scenes)} scenes")
        return analysis_result

    except Exception as e:
        error_msg = f"Analysis error: {e}"
        logger.error(f"[Analysis] Error for project {project_id}: {error_msg}")
        if self.request.retries < self.max_retries:
            update_job_progress(project_id, stage="analysis", status="retrying", error_message=error_msg, force_write=True)
            raise self.retry(exc=e)
        else:
            update_job_progress(project_id, stage="analysis", status="failed", error_message=error_msg, force_write=True)
            _update_project_status(project_id, "failed")
            raise
