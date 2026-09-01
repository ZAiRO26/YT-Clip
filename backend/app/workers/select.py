"""
ClipForge AI — Select Worker

Pipeline stage 3: Use LLM to select highlight segments from transcript.

Per TRD section 2 and user requirements:
- LLM prompt takes full transcript (with timestamps) AND campaign brief JSON
- Returns structured JSON: [{start_sec, end_sec, score, reasoning}]
- Never free-text output that requires fragile parsing
- Routes through OmniRoute/FreeLLMAPI (zero-cost inference)
- Surfaces rate limits clearly per requirement #6

Output: {MEDIA_DIR}/{project_id}/selections.json

Celery queue: select (concurrency=3 in production, rate-limited to LLM provider limits)
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.celery_app import celery_app
from app.config import settings
from app.database import get_sync_session
from app.models import Job, Project
from app.services.llm_client import LLMClientError, llm_client

logger = logging.getLogger(__name__)

# System prompt for clip selection
SELECTION_SYSTEM_PROMPT = """You are a professional video editor AI assistant specializing in creating viral short-form clips from long-form video content.

Your task is to analyze a video transcript and select the best segments for short-form vertical clips (YouTube Shorts, TikTok, Instagram Reels).

You MUST evaluate each potential segment against the provided campaign brief to ensure alignment with brand guidelines, tone, required mentions, and banned topics.

SCORING CRITERIA (0.0 to 1.0):
- 0.9-1.0: Perfect match — high-energy moment, matches campaign tone exactly, includes required mentions
- 0.7-0.8: Strong match — engaging content, good campaign alignment
- 0.5-0.6: Acceptable — decent content, partial campaign alignment
- 0.3-0.4: Weak — content is okay but poor campaign alignment
- 0.0-0.2: Reject — off-topic, contains banned topics, or boring

SELECTION RULES:
1. Each clip must be a self-contained moment that makes sense without context
2. Prefer segments with clear speech, emotional peaks, humor, or surprising statements
3. Avoid segments that are mid-sentence or cut off abruptly
4. Ensure clips start and end at natural speech boundaries
5. Never select segments containing banned topics from the campaign brief
6. Prefer segments that include required mentions from the campaign brief
7. Clips should not overlap with each other

You MUST respond with valid JSON only. No markdown, no code fences, no explanation."""


def _build_selection_prompt(
    transcript: dict,
    campaign_brief: dict,
    clip_count: int,
    min_length_sec: int,
    max_length_sec: int,
    custom_prompt: str | None = None,
) -> str:
    """Build the LLM prompt for clip selection."""
    # Format transcript segments with timestamps for the LLM
    formatted_segments = []
    for seg in transcript.get("segments", []):
        start = seg["start"]
        end = seg["end"]
        text = seg["text"]
        formatted_segments.append(f"[{start:.1f}s - {end:.1f}s] {text}")

    transcript_text = "\n".join(formatted_segments)
    total_duration = transcript.get("duration_sec", 0)

    prompt = f"""## SOURCE VIDEO TRANSCRIPT
Total duration: {total_duration:.1f} seconds
Language: {transcript.get('language', 'unknown')}

{transcript_text}

## CAMPAIGN BRIEF
{json.dumps(campaign_brief, indent=2)}

## SPECIFIC INSTRUCTIONS FROM USER
{custom_prompt if custom_prompt else "No specific instructions. Select the best general highlights based on the campaign brief."}

## TASK
Select exactly {clip_count} highlight segments from the transcript above.

CONSTRAINTS:
- Each clip must be between {min_length_sec} and {max_length_sec} seconds long
- Clips must not overlap
- Score each clip 0.0-1.0 against the campaign brief
- If fewer than {clip_count} quality segments exist, return as many as you can find (minimum score 0.3)

## REQUIRED OUTPUT FORMAT
Return a JSON object with this exact structure:
{{
    "clips": [
        {{
            "start_sec": <float>,
            "end_sec": <float>,
            "score": <float between 0.0 and 1.0>,
            "reasoning": "<one sentence explaining why this segment was selected and how it matches the campaign brief>"
        }}
    ],
    "total_found": <int>,
    "notes": "<optional: any notes about the selection, e.g. if fewer clips than requested>"
}}"""

    return prompt


def _update_job_status(
    project_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the select job status in the database."""
    session = get_sync_session()
    try:
        job = session.query(Job).filter(
            Job.project_id == uuid.UUID(project_id),
            Job.stage == "select",
        ).first()

        if job:
            job.status = status
            job.error_message = error_message
            if status == "running":
                job.started_at = datetime.now(timezone.utc)
            if status in ("success", "failed"):
                job.completed_at = datetime.now(timezone.utc)
            session.commit()
        else:
            logger.warning(f"No select job found for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        session.rollback()
    finally:
        session.close()


def _update_project_status(project_id: str, status: str) -> None:
    """Update the project-level status."""
    session = get_sync_session()
    try:
        project = session.query(Project).filter(
            Project.id == uuid.UUID(project_id),
        ).first()
        if project:
            project.status = status
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update project status: {e}")
        session.rollback()
    finally:
        session.close()


def _validate_selections(
    selections: dict,
    min_length_sec: int,
    max_length_sec: int,
    total_duration: float,
) -> list[dict]:
    """
    Validate and clean up LLM selection output.

    Ensures:
    - All required fields are present
    - start_sec < end_sec
    - Clip duration is within bounds
    - Clips don't exceed source duration
    - Scores are 0.0-1.0
    - Clips are sorted by score descending
    """
    clips = selections.get("clips", [])
    valid_clips = []

    for clip in clips:
        try:
            start = float(clip.get("start_sec", 0))
            end = float(clip.get("end_sec", 0))
            score = float(clip.get("score", 0))
            reasoning = str(clip.get("reasoning", "No reasoning provided"))

            # Validate bounds
            if start >= end:
                logger.warning(f"Skipping clip: start ({start}) >= end ({end})")
                continue

            duration = end - start
            if duration < min_length_sec or duration > max_length_sec:
                logger.warning(
                    f"Skipping clip: duration {duration:.1f}s outside "
                    f"[{min_length_sec}, {max_length_sec}]"
                )
                continue

            if end > total_duration + 1:  # 1s tolerance
                logger.warning(f"Skipping clip: end ({end}) exceeds duration ({total_duration})")
                continue

            # Clamp score
            score = max(0.0, min(1.0, score))

            valid_clips.append({
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "score": round(score, 3),
                "reasoning": reasoning,
            })

        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid clip entry: {e}")
            continue

    # Sort by score descending
    valid_clips.sort(key=lambda c: c["score"], reverse=True)

    return valid_clips


async def select_clips(
    transcript_path: str,
    campaign_brief: dict,
    clip_count: int,
    min_length_sec: int,
    max_length_sec: int,
    custom_prompt: str | None = None,
    time_range_start: float | None = None,
    time_range_end: float | None = None,
) -> dict:
    """
    Use LLM to select highlight segments from transcript.

    Args:
        transcript_path: Path to transcript.json
        campaign_brief: Campaign brief dict (tone, required mentions, etc.)
        clip_count: Number of clips to select
        min_length_sec: Minimum clip duration
        max_length_sec: Maximum clip duration

    Returns:
        dict with validated clips and metadata
    """
    # Load transcript
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = json.loads(transcript_file.read_text(encoding="utf-8"))
    
    if time_range_start is not None or time_range_end is not None:
        start = time_range_start or 0.0
        end = time_range_end or transcript.get("duration_sec", 999999)
        transcript["segments"] = [
            seg for seg in transcript.get("segments", [])
            if seg["end"] >= start and seg["start"] <= end
        ]
        
    total_duration = transcript.get("duration_sec", 0)

    # Build prompt
    prompt = _build_selection_prompt(
        transcript=transcript,
        campaign_brief=campaign_brief,
        clip_count=clip_count,
        min_length_sec=min_length_sec,
        max_length_sec=max_length_sec,
        custom_prompt=custom_prompt,
    )

    logger.info(
        f"Requesting {clip_count} clips "
        f"({min_length_sec}-{max_length_sec}s) from {total_duration:.1f}s source"
    )

    # Call LLM for structured JSON response
    raw_response = await llm_client.complete_json(
        prompt=prompt,
        system=SELECTION_SYSTEM_PROMPT,
        temperature=0.1,
        max_tokens=4096,
    )

    # Validate and clean up selections
    valid_clips = _validate_selections(
        selections=raw_response,
        min_length_sec=min_length_sec,
        max_length_sec=max_length_sec,
        total_duration=total_duration,
    )

    # Trim to requested count
    if len(valid_clips) > clip_count:
        valid_clips = valid_clips[:clip_count]

    result = {
        "clips": valid_clips,
        "total_found": len(valid_clips),
        "requested": clip_count,
        "source_duration_sec": total_duration,
        "llm_notes": raw_response.get("notes", ""),
    }

    # Save selections to disk
    output_path = transcript_file.parent / "selections.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(f"Selected {len(valid_clips)}/{clip_count} clips")

    return result


@celery_app.task(
    name="app.workers.select.select_highlights",
    queue="select",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def select_highlights(
    self,
    project_id: str,
    transcript_path: str,
    campaign_brief: dict,
    clip_count: int,
    min_length_sec: int,
    max_length_sec: int,
) -> dict:
    """
    Select highlight clips from transcript using LLM.

    This is a sync Celery task that wraps the async LLM call.

    Updates jobs table with granular status:
        pending -> running -> success/failed/retrying
    """
    import asyncio

    logger.info(f"[Select] Starting for project {project_id}")

    _update_job_status(project_id, "running")
    _update_project_status(project_id, "selecting")

    try:
        # Run the async function in a new event loop
        result = asyncio.run(select_clips(
            transcript_path=transcript_path,
            campaign_brief=campaign_brief,
            clip_count=clip_count,
            min_length_sec=min_length_sec,
            max_length_sec=max_length_sec,
        ))

        result["project_id"] = project_id

        _update_job_status(project_id, "success")
        logger.info(
            f"[Select] Complete for project {project_id}: "
            f"{result['total_found']}/{result['requested']} clips selected"
        )

        return result

    except LLMClientError as e:
        error_msg = str(e.message)
        logger.error(f"[Select] LLM error for project {project_id}: {error_msg}")

        if e.provider_info:
            error_msg += f" (Provider: {e.provider_info})"

        if e.retryable and self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise

    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(f"[Select] Failed for project {project_id}: {error_msg}")
        _update_job_status(project_id, "failed", error_message=error_msg)
        _update_project_status(project_id, "failed")
        raise

    except Exception as e:
        error_msg = f"Selection error: {e}"
        logger.error(f"[Select] Error for project {project_id}: {error_msg}")

        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
