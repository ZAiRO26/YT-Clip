"""
ClipForge AI — Brief-Aware Candidate Selection Worker (v2)

Pipeline stage 3 (LLM Queue):
- Uses OpenAI-compatible LLM Gateway (OmniRoute/FreeLLMAPI)
- Integrates transcript, scene boundaries, editorial template, rights basis, and campaign brief
- Computes 0–100 Transformation Score and breakdown per Section 2.4
- Snaps candidates to scene cut boundaries and deduplicates overlapping excerpts
- Persists selections.json and populates Clip database records with transformation scores
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from clipforge_core.celery_app import celery_app
from clipforge_core.config import settings
from clipforge_core.database import get_sync_session
from clipforge_core.models import Clip, Job, Project, ProjectAuditEvent
from clipforge_core.services.candidate_ranker import deduplicate_and_rank_candidates
from clipforge_core.services.llm_client import LLMClientError, llm_client
from clipforge_core.services.transformation_scorer import calculate_transformation_score

logger = logging.getLogger(__name__)

SELECTION_SYSTEM_PROMPT = """You are an expert video editor and transformation strategist for short-form social video (YouTube Shorts, TikTok, Instagram Reels).

Your task is to analyze a source video transcript, scene boundaries, and project brief to identify the highest-potential, transformation-ready clipping candidates.

EDITORIAL PRINCIPLES:
1. Self-contained Narrative: Each clip must have a strong hook, clear body point/evidence, and a satisfying conclusion or punchline.
2. High Transformation Potential: Favor moments where original commentary, callouts, and explanatory context add significant value.
3. Natural Speech Boundaries: Start and end at natural pause points.
4. Brief Alignment: Strictly adhere to the tone, required mentions, and banned topics in the campaign brief.

You MUST respond with valid JSON matching the requested schema exactly. No markdown fences, no conversational text."""


def _build_selection_prompt(
    transcript: dict,
    scenes: list,
    campaign_brief: dict,
    editorial_template: str,
    rights_basis: str,
    clip_count: int,
    min_length_sec: int,
    max_length_sec: int,
    custom_prompt: str | None = None,
) -> str:
    """Build structured LLM prompt."""
    segments = transcript.get("segments", [])
    formatted_segments = []
    for seg in segments:
        s = seg.get("start", 0.0)
        e = seg.get("end", 0.0)
        t = seg.get("text", "").strip()
        formatted_segments.append(f"[{s:.1f}s - {e:.1f}s] {t}")

    transcript_text = "\n".join(formatted_segments)
    total_duration = transcript.get("duration_sec", 0.0)

    prompt = f"""## SOURCE VIDEO INFORMATION
- Total Duration: {total_duration:.1f}s
- Language: {transcript.get('language', 'unknown')}
- Rights Basis: {rights_basis}
- Editorial Template: {editorial_template}

## TRANSCRIPT WITH TIMESTAMPS
{transcript_text}

## SCENE CUT BOUNDARIES (First 20)
{json.dumps(scenes[:20], indent=2)}

## CAMPAIGN BRIEF
{json.dumps(campaign_brief, indent=2)}

## USER GUIDANCE
{custom_prompt if custom_prompt else "Identify the most engaging standalone moments matching the campaign brief and editorial template."}

## TASK
Select up to {clip_count} highlight candidates.
- Each clip duration MUST be between {min_length_sec} and {max_length_sec} seconds.
- Clips should not overlap.
- Hook Type must be one of: "question", "bold_statement", "surprising_stat", "story_loop", "controversial_thesis".

## REQUIRED JSON FORMAT
Return a JSON object:
{{
  "clips": [
    {{
      "start_sec": 12.5,
      "end_sec": 48.0,
      "title": "Short punchy title",
      "hook_type": "question",
      "hook_text": "Did you know that...",
      "editorial_potential": 0.85,
      "reasoning": "Why this moment was selected",
      "suggested_callouts": ["Term 1", "Statistic 2"]
    }}
  ]
}}"""
    return prompt


def _update_job_status(
    project_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update select job status in DB."""
    session = get_sync_session()
    try:
        job = (
            session.query(Job)
            .filter(
                Job.project_id == uuid.UUID(project_id),
                Job.stage.in_(["select", "llm"]),
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
        logger.error(f"Failed to update job status: {e}")
        session.rollback()
    finally:
        session.close()


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
    name="clipforge_core.workers.select.select_clips",
    queue="llm",
    bind=True,
    max_retries=3,
    default_retry_delay=15,
)
def select_clips(
    self,
    project_id: str,
    clip_count: int = 5,
    min_length_sec: int = 20,
    max_length_sec: int = 60,
    custom_prompt: str | None = None,
    time_range_start: float | None = None,
    time_range_end: float | None = None,
) -> Dict[str, Any]:
    """
    Candidate selection task running on the 'llm' queue.
    """
    logger.info(f"[LLM Select] Starting candidate selection for project {project_id}")
    _update_job_status(project_id, "running")
    _update_project_status(project_id, "selecting")

    project_dir = Path(settings.MEDIA_DIR) / project_id
    transcript_path = project_dir / "transcript.json"
    analysis_path = project_dir / "analysis.json"

    if not transcript_path.exists() and not analysis_path.exists():
        error_msg = f"Transcript missing for project {project_id}"
        _update_job_status(project_id, "failed", error_message=error_msg)
        _update_project_status(project_id, "failed")
        raise FileNotFoundError(error_msg)

    # Load transcript & scenes
    if analysis_path.exists():
        analysis_data = json.loads(analysis_path.read_text(encoding="utf-8"))
        transcript = analysis_data.get("transcript", {})
        scenes = analysis_data.get("scenes", [])
    else:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
        scenes = []

    # Fetch Project & Brief from DB
    session = get_sync_session()
    try:
        project = session.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        editorial_template = project.editorial_template or "explainer"
        rights_basis = project.rights_basis or "owned"
        campaign_brief = project.campaign_brief.brief_json if project.campaign_brief else {}
    finally:
        session.close()

    # Filter transcript by time range if requested
    if time_range_start is not None or time_range_end is not None:
        t_start = time_range_start or 0.0
        t_end = time_range_end or float("inf")
        filtered_segs = [
            s for s in transcript.get("segments", [])
            if s.get("start", 0.0) >= t_start and s.get("end", 0.0) <= t_end
        ]
        transcript["segments"] = filtered_segs

    # Build prompt
    prompt = _build_selection_prompt(
        transcript=transcript,
        scenes=scenes,
        campaign_brief=campaign_brief,
        editorial_template=editorial_template,
        rights_basis=rights_basis,
        clip_count=clip_count,
        min_length_sec=min_length_sec,
        max_length_sec=max_length_sec,
        custom_prompt=custom_prompt,
    )

    try:
        # Run async LLM completion in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response_json = loop.run_until_complete(
                llm_client.complete_json(
                    prompt=prompt,
                    system=SELECTION_SYSTEM_PROMPT,
                    temperature=0.2,
                )
            )
        finally:
            loop.close()

        raw_clips: List[Dict[str, Any]] = (
            response_json.get("clips", []) if isinstance(response_json, dict) else response_json
        )

        total_source_dur = transcript.get("duration_sec", 60.0)

        # Compute transformation score and enrich candidates
        enriched_candidates = []
        for raw in raw_clips:
            start_s = float(raw.get("start_sec", 0.0))
            end_s = float(raw.get("end_sec", start_s + min_length_sec))
            duration = end_s - start_s

            t_score_data = calculate_transformation_score(
                clip_duration_sec=duration,
                total_source_duration_sec=total_source_dur,
                has_commentary=True,
                editorial_template=editorial_template,
                callout_count=len(raw.get("suggested_callouts", [])),
                has_hook=bool(raw.get("hook_text")),
                has_takeaway=bool(raw.get("key_takeaway")),
            )

            editorial_pot = round(
                float(raw.get("editorial_potential", raw.get("virality_score", raw.get("score", 0.75)))), 2
            )
            cand = {
                "start_sec": round(start_s, 2),
                "end_sec": round(end_s, 2),
                "title": raw.get("title", f"Clip @ {int(start_s)}s"),
                "hook_type": raw.get("hook_type", "bold_statement"),
                "hook_text": raw.get("hook_text", ""),
                "key_takeaway": raw.get("key_takeaway", ""),
                "editorial_potential": editorial_pot,
                "virality_score": editorial_pot,  # Backward compatibility
                "transformation_score": t_score_data["score"],
                "transformation_breakdown": t_score_data["breakdown"],
                "transformation_band": t_score_data["band"],
                "reasoning": raw.get("reasoning", "Strong highlight candidate matching editorial template"),
                "suggested_callouts": raw.get("suggested_callouts", []),
            }
            enriched_candidates.append(cand)

        # Snap to scene cut boundaries and deduplicate
        final_clips = deduplicate_and_rank_candidates(enriched_candidates, scenes=scenes)

        # Limit to requested clip count
        final_clips = final_clips[:clip_count]

        # Save selections.json to disk
        selections_path = project_dir / "selections.json"
        selections_payload = {
            "project_id": project_id,
            "clips": final_clips,
            "total_selected": len(final_clips),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        selections_path.write_text(json.dumps(selections_payload, indent=2, ensure_ascii=False), encoding="utf-8")

        # Persist Clip records in DB
        db_session = get_sync_session()
        try:
            pid = uuid.UUID(project_id)
            for c in final_clips:
                clip_record = Clip(
                    id=uuid.uuid4(),
                    project_id=pid,
                    start_sec=c["start_sec"],
                    end_sec=c["end_sec"],
                    score=c.get("editorial_potential", c.get("virality_score", 0.75)),
                    transformation_score=c["transformation_score"],
                    transformation_breakdown=c["transformation_breakdown"],
                    reasoning=f"[{c['hook_type']}] {c['title']} — {c['reasoning']}",
                    review_status="pending",
                )
                db_session.add(clip_record)

            # Record audit event
            audit = ProjectAuditEvent(
                id=uuid.uuid4(),
                project_id=pid,
                event_type="candidates_selected",
                payload={
                    "candidate_count": len(final_clips),
                    "avg_transformation_score": round(
                        sum(c["transformation_score"] for c in final_clips) / len(final_clips), 1
                    ) if final_clips else 0,
                },
            )
            db_session.add(audit)
            db_session.commit()
        except Exception as e:
            logger.error(f"Failed to record clips in DB: {e}")
            db_session.rollback()
        finally:
            db_session.close()

        _update_job_status(project_id, "success")
        logger.info(f"[LLM Select] Selected {len(final_clips)} clips for project {project_id}")
        return selections_payload

    except LLMClientError as e:
        error_msg = f"LLM Gateway error: {e.message}"
        logger.error(f"[LLM Select] {error_msg}")
        _update_job_status(project_id, "failed", error_message=error_msg)
        _update_project_status(project_id, "failed")
        raise

    except Exception as e:
        error_msg = f"Candidate selection error: {e}"
        logger.error(f"[LLM Select] {error_msg}")
        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
