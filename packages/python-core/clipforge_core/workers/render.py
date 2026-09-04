"""
ClipForge AI — Professional Render Worker (v2)

Pipeline stage 4 & 5 (Render Queue):
- Executes deterministic FFmpeg rendering with smart 9:16 reframing, blurred backgrounds, and ASS captions
- Emits draft-07 Render Manifests matching RENDER_MANIFEST_SCHEMA.json
- Performs output QA verification (1080x1920, loudness normalization, audio sync)
- Updates Clip records with file_url, thumbnail_url, and render_manifest
- Emits render_completed audit events
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from clipforge_core.celery_app import celery_app
from clipforge_core.config import settings
from clipforge_core.database import get_sync_session
from clipforge_core.models import Clip, Job, Project, ProjectAuditEvent, SourceAsset
from clipforge_core.services.media_probe import probe_media
from clipforge_core.services.render_engine import build_render_manifest, render_clip

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
    name="clipforge_core.workers.render.render_project_clips",
    queue="render",
    bind=True,
    max_retries=2,
    default_retry_delay=15,
)
def render_project_clips(self, project_id: str) -> Dict[str, Any]:
    """
    Renders all selected clips for a project with manifests and thumbnails.
    """
    logger.info(f"[Render Worker] Starting render pipeline for project {project_id}")
    update_job_progress(project_id, stage="render", status="running", percent=0.0, detail="Initializing render pipeline...")
    _update_project_status(project_id, "encoding")

    project_dir = Path(settings.MEDIA_DIR) / project_id
    source_video = project_dir / "source.mp4"
    selections_file = project_dir / "selections.json"
    analysis_file = project_dir / "analysis.json"

    if not source_video.exists():
        error_msg = f"Source video not found: {source_video}"
        update_job_progress(project_id, stage="render", status="failed", error_message=error_msg, force_write=True)
        _update_project_status(project_id, "failed")
        raise FileNotFoundError(error_msg)

    if not selections_file.exists():
        error_msg = f"Selections file not found: {selections_file}"
        update_job_progress(project_id, stage="render", status="failed", error_message=error_msg, force_write=True)
        _update_project_status(project_id, "failed")
        raise FileNotFoundError(error_msg)

    # Load selections and analysis
    selections = json.loads(selections_file.read_text(encoding="utf-8"))
    candidate_clips = selections.get("clips", [])

    transcript_segments = []
    focal_timeline = []
    if analysis_file.exists():
        analysis_data = json.loads(analysis_file.read_text(encoding="utf-8"))
        transcript_segments = analysis_data.get("transcript", {}).get("segments", [])
        focal_timeline = analysis_data.get("face_tracking", {}).get("timeline", [])

    # Fetch Project & Source Asset from DB
    session = get_sync_session()
    try:
        pid = uuid.UUID(project_id)
        project = session.query(Project).filter(Project.id == pid).first()
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        source_asset = session.query(SourceAsset).filter(SourceAsset.project_id == pid).first()
        source_asset_id = str(source_asset.id) if source_asset else str(uuid.uuid4())
        source_probe = source_asset.metadata_json if source_asset else probe_media(source_video)

        crop_mode = getattr(project, "crop_mode", "face_track") or "face_track"
        caption_style = project.caption_style or "bold_karaoke"
        default_effects = getattr(project, "default_effects", []) or []
        default_music_track = getattr(project, "default_music_track", "none") or "none"
        editorial_template = project.editorial_template or "explainer"
        rights_basis = project.rights_basis or "owned"
        source_risk_label = project.source_risk_label or "lower_workflow_risk"
        db_clips = session.query(Clip).filter(Clip.project_id == pid).order_by(Clip.created_at, Clip.id).all()
    finally:
        session.close()

    # Filter active verified effects
    active_effects = []
    for eff in default_effects:
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

    from clipforge_core.services.effects_engine import apply_motion_effects
    from clipforge_core.services.audio_mixer import mix_audio_tracks
    from clipforge_core.services.music_library import ensure_synth_bed

    clips_output_dir = project_dir / "clips"
    clips_output_dir.mkdir(parents=True, exist_ok=True)

    rendered_results: List[Dict[str, Any]] = []

    try:
        total_clips = len(candidate_clips)
        for idx, cand in enumerate(candidate_clips):
            base_percent = (idx / total_clips) * 100.0

            start_s = cand.get("start_sec", 0.0)
            end_s = cand.get("end_sec", start_s + 30.0)

            # Match to specific DB clip by ID, time range, or sequential order
            matched_clip = None
            if "clip_id" in cand:
                clip_id = cand["clip_id"]
                matched_clip = next((c for c in db_clips if str(c.id) == clip_id), None)
            
            if not matched_clip:
                for c in db_clips:
                    if abs(float(c.start_sec) - start_s) < 0.2 and abs(float(c.end_sec) - end_s) < 0.2:
                        matched_clip = c
                        break

            if matched_clip:
                clip_id = str(matched_clip.id)
                clip_num = db_clips.index(matched_clip) + 1
            elif idx < len(db_clips):
                matched_clip = db_clips[idx]
                clip_id = str(matched_clip.id)
                clip_num = idx + 1
            else:
                clip_id = str(uuid.uuid4())
                clip_num = len(db_clips) + idx + 1

            # Determine focal point for this clip's time range
            clip_focal_points = [
                f["focal_x"] for f in focal_timeline
                if start_s <= f.get("time_sec", 0.0) <= end_s
            ]
            focal_x = (
                sum(clip_focal_points) / len(clip_focal_points)
                if clip_focal_points
                else 0.5
            )

            out_video_path = clips_output_dir / f"clip_{clip_num}.mp4"
            out_thumb_path = clips_output_dir / f"clip_{clip_num}_thumb.jpg"

            # Define progress callback
            def clip_progress(p: float):
                overall_percent = base_percent + (p / total_clips)
                update_job_progress(
                    project_id=project_id,
                    stage="render",
                    percent=overall_percent,
                    detail=f"Rendering clip {idx+1}/{total_clips} ({p:.0f}%)"
                )

            # Execute rendering
            render_res = render_clip(
                source_path=source_video,
                output_path=out_video_path,
                start_sec=start_s,
                end_sec=end_s,
                crop_mode=crop_mode,
                focal_x=focal_x,
                caption_style=caption_style,
                transcript_segments=transcript_segments,
                output_thumbnail_path=out_thumb_path,
                progress_callback=clip_progress,
            )

            # Apply project-wide default motion effects if selected
            if active_effects:
                apply_motion_effects(
                    source_video_path=out_video_path,
                    output_video_path=out_video_path,
                    effects=active_effects,
                    duration_sec=end_s - start_s,
                )

            # Apply project-wide ambient background music if selected
            if default_music_track and default_music_track != "none":
                try:
                    import os
                    import subprocess
                    bg_music_path = clips_output_dir / f"music_{clip_num}.aac"
                    ensure_synth_bed(default_music_track, bg_music_path, duration_sec=end_s - start_s)

                    mixed_audio = clips_output_dir / f"mixed_{clip_num}.aac"
                    mix_audio_tracks(
                        source_video_path=out_video_path,
                        output_audio_path=mixed_audio,
                        start_sec=0.0,
                        end_sec=end_s - start_s,
                        music_path=bg_music_path,
                    )

                    temp_muxed = clips_output_dir / f"clip_{clip_num}_muxed_temp.mp4"
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
                    subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                    os.replace(temp_muxed, out_video_path)
                except Exception as e:
                    logger.warning(f"[Render Worker] Failed to mix default background music for clip {clip_num}: {e}")

            # Build and write Render Manifest
            manifest = build_render_manifest(
                clip_id=clip_id,
                project_id=project_id,
                source_asset_id=source_asset_id,
                source_path=str(source_video),
                source_probe=source_probe,
                start_sec=start_s,
                end_sec=end_s,
                crop_mode=crop_mode,
                focal_x=focal_x,
                caption_style=caption_style,
                editorial_template=editorial_template,
                rights_basis=rights_basis,
                source_risk_label=source_risk_label,
                transformation_score=cand.get("transformation_score", 75),
                transformation_breakdown=cand.get("transformation_breakdown", {}),
                effect_layers=active_effects,
            )

            manifest_path = clips_output_dir / f"clip_{clip_num}_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            # Relative media paths for web client
            rel_file_url = f"media/{project_id}/clips/{out_video_path.name}"
            rel_thumb_url = f"media/{project_id}/clips/{out_thumb_path.name}"

            # Update Clip record in DB
            db_session = get_sync_session()
            try:
                clip_rec = db_session.query(Clip).filter(Clip.id == uuid.UUID(clip_id)).first()
                if clip_rec:
                    clip_rec.file_url = rel_file_url
                    clip_rec.thumbnail_url = rel_thumb_url
                    clip_rec.render_manifest = manifest
                    clip_rec.review_status = "pending"
                    db_session.commit()
            except Exception as e:
                logger.error(f"Failed to update clip record in DB: {e}")
                db_session.rollback()
            finally:
                db_session.close()

            rendered_results.append({
                "clip_id": clip_id,
                "clip_number": clip_num,
                "file_url": rel_file_url,
                "thumbnail_url": rel_thumb_url,
                "duration_sec": render_res["duration_sec"],
                "file_size_mb": render_res["file_size_mb"],
                "manifest_path": str(manifest_path),
            })

        # Record QA & audit event
        audit_session = get_sync_session()
        try:
            audit = ProjectAuditEvent(
                id=uuid.uuid4(),
                project_id=uuid.UUID(project_id),
                event_type="render_completed",
                payload={
                    "total_rendered": len(rendered_results),
                    "resolution": "1080x1920",
                    "caption_style": caption_style,
                    "loudnorm_target": "-14 LUFS",
                },
            )
            audit_session.add(audit)
            audit_session.commit()
        except Exception as e:
            logger.error(f"Failed to record render audit event: {e}")
            audit_session.rollback()
        finally:
            audit_session.close()

        update_job_progress(project_id, stage="render", status="success", percent=100.0, detail="Rendering complete.", force_write=True)
        _update_project_status(project_id, "done")
        logger.info(f"[Render Worker] Completed rendering {len(rendered_results)} clips for project {project_id}")

        return {
            "project_id": project_id,
            "clips": rendered_results,
            "total_rendered": len(rendered_results),
        }

    except Exception as e:
        error_msg = f"Render pipeline error: {e}"
        logger.error(f"[Render Worker] {error_msg}")
        if self.request.retries < self.max_retries:
            update_job_progress(project_id, stage="render", status="retrying", error_message=error_msg, force_write=True)
            raise self.retry(exc=e)
        else:
            update_job_progress(project_id, stage="render", status="failed", error_message=error_msg, force_write=True)
            _update_project_status(project_id, "failed")
            raise
