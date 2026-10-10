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
from clipforge_core.services.candidate_ranker import (
    clamp_to_boundary,
    deduplicate_and_rank_candidates,
    expand_to_natural_bit,
    preferred_length,
)
from clipforge_core.services.llm_client import LLMClientError, llm_client
from clipforge_core.services.temporal_binner import compute_temporal_bins, format_bin_directives, validate_bin_membership
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


# Content focus prompt directives
_CONTENT_FOCUS_DIRECTIVES = {
    "balanced": (
        "Select a balanced mix of clips: include both performer/contestant acts "
        "(setups, performances, punchlines) AND host/judge reactions (commentary, "
        "banter, roasts). Aim for roughly equal representation."
    ),
    "contestant_primary": (
        "PRIORITIZE contestant/performer moments: their setups, acts, performances, "
        "jokes, and audience reactions to their work. In acts/windows where no active "
        "contestant performance is occurring (e.g., initial host/panel introductions, "
        "or final host wrap-up and award announcements), select the best highlight "
        "moment for that act. Every assigned act must have a clip selected."
    ),
    "judges_primary": (
        "PRIORITIZE judge/host/panel moments: their commentary, roasts, banter, "
        "reactions, and discussions. Include contestant content only when the "
        "performance itself is the setup for a judge reaction. At least 70% of "
        "clips should feature judges/hosts as the primary subject."
    ),
}


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
    temporal_bins_directive: str = "",
    content_focus: str = "balanced",
) -> str:
    """Build structured LLM prompt with optional temporal and content focus directives."""
    segments = transcript.get("segments", [])
    formatted_segments = []
    for seg in segments:
        s = seg.get("start", 0.0)
        e = seg.get("end", 0.0)
        t = seg.get("text", "").strip()
        formatted_segments.append(f"[{s:.1f}s - {e:.1f}s] {t}")

    transcript_text = "\n".join(formatted_segments)
    total_duration = transcript.get("duration_sec", 0.0)

    # Build optional sections
    focus_directive = _CONTENT_FOCUS_DIRECTIVES.get(content_focus, _CONTENT_FOCUS_DIRECTIVES["balanced"])
    temporal_section = f"\n{temporal_bins_directive}\n" if temporal_bins_directive else ""

    preferred_length_sec = round(preferred_length(min_length_sec, max_length_sec))

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

## CONTENT FOCUS
{focus_directive}
{temporal_section}
## USER GUIDANCE
{custom_prompt if custom_prompt else "Identify the most engaging standalone moments matching the campaign brief and editorial template."}

## TASK
Select exactly {clip_count} highlight candidates. You MUST return exactly {clip_count} clips — no fewer.

CLIP LENGTH — HARD RULE:
- Every clip MUST run between {min_length_sec} and {max_length_sec} seconds (end_sec - start_sec). A clip shorter than {min_length_sec}s is INVALID and will be thrown away.
- A clip is a RANGE covering many transcript lines, never a single line. One transcript line is only a few seconds.
- Each clip must be a complete, self-contained bit: start_sec = the first line of the setup/context, end_sec = the end of the payoff (punchline, answer, reaction or laugh). Never start on the punchline.
- Preferred length is {preferred_length_sec}–{max_length_sec}s: include the full setup, the build-up and the reaction after the payoff. At least half of the clips must be longer than {preferred_length_sec}s. Use {min_length_sec}–{preferred_length_sec}s only for a genuinely short one-liner that is complete on its own.
- start_sec must be the start time of a transcript line and end_sec the end time of a later transcript line.
- Fill in duration_sec = end_sec - start_sec and check it is within range before answering.

OTHER RULES:
- Clips should not overlap.
- Hook Type must be one of: "question", "bold_statement", "surprising_stat", "story_loop", "controversial_thesis".
- Keep reasoning brief (1 short sentence) and suggested_callouts concise.
- Output JSON directly without any conversational preamble or thinking text.

## REQUIRED JSON FORMAT
Return a JSON object:
{{
  "clips": [
    {{
      "start_sec": 12.5,
      "end_sec": 48.0,
      "duration_sec": 35.5,
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


from clipforge_core.services.progress import update_job_progress


def _run_llm_selection(prompt: str, temperature: float) -> List[Dict[str, Any]]:
    """One blocking LLM selection call; returns the raw clip list."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        response = loop.run_until_complete(
            llm_client.complete_json(
                prompt=prompt,
                system=SELECTION_SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=16384,
            )
        )
    finally:
        loop.close()
    return response.get("clips", []) if isinstance(response, dict) else response


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
    temporal_distribution: str = "even_spread",
    content_focus: str = "balanced",
) -> Dict[str, Any]:
    """
    Candidate selection task running on the 'llm' queue.
    """
    logger.info(f"[LLM Select] Starting candidate selection for project {project_id}")
    session_check = get_sync_session()
    try:
        proj_check = session_check.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
        if not proj_check:
            logger.warning(f"[LLM Select] Project {project_id} not found in database. Aborting orphaned select task.")
            return {"error": "Project not found"}
    finally:
        session_check.close()

    update_job_progress(project_id, stage="select", status="running", percent=10.0, detail="Parsing transcript & brief...")
    _update_project_status(project_id, "selecting")

    project_dir = Path(settings.MEDIA_DIR) / project_id
    transcript_path = project_dir / "transcript.json"
    analysis_path = project_dir / "analysis.json"

    if not transcript_path.exists() and not analysis_path.exists():
        error_msg = f"Transcript missing for project {project_id}"
        update_job_progress(project_id, stage="select", status="failed", error_message=error_msg, force_write=True)
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
        if time_range_start is None and project.time_range_start is not None:
            time_range_start = project.time_range_start
        if time_range_end is None and project.time_range_end is not None:
            time_range_end = project.time_range_end
        if temporal_distribution == "even_spread" and getattr(project, "temporal_distribution", None):
            temporal_distribution = project.temporal_distribution
        if content_focus == "balanced" and getattr(project, "content_focus", None):
            content_focus = project.content_focus
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

    # Compute temporal bins for even spread
    temporal_bins_directive = ""
    temporal_bins = []
    total_source_dur_for_bins = transcript.get("duration_sec", 60.0)
    if temporal_distribution == "even_spread" and clip_count > 1:
        effective_start = time_range_start or 0.0
        effective_end = time_range_end or total_source_dur_for_bins
        temporal_bins = compute_temporal_bins(
            total_duration_sec=total_source_dur_for_bins,
            clip_count=clip_count,
            time_range_start=effective_start,
            time_range_end=effective_end,
        )
        temporal_bins_directive = format_bin_directives(temporal_bins)

    # Determine if we need to batch the LLM calls for large transcripts
    segments = transcript.get("segments", [])
    total_duration = transcript.get("duration_sec", 60.0)

    # Strategy: if requesting >3 clips, split the transcript into time-based chunks
    # and send each chunk as a separate LLM request for a proportional number of clips
    MAX_CLIPS_PER_BATCH = 5  # Sweet spot for most LLMs to reliably return
    need_batching = clip_count > MAX_CLIPS_PER_BATCH and len(segments) > 100

    if need_batching:
        num_batches = (clip_count + MAX_CLIPS_PER_BATCH - 1) // MAX_CLIPS_PER_BATCH
        effective_start = time_range_start or 0.0
        effective_end = time_range_end or total_duration
        chunk_duration = (effective_end - effective_start) / num_batches

        all_raw_clips: List[Dict[str, Any]] = []
        clips_remaining = clip_count

        for batch_idx in range(num_batches):
            batch_start = effective_start + batch_idx * chunk_duration
            batch_end = effective_start + (batch_idx + 1) * chunk_duration
            batch_clips_count = min(MAX_CLIPS_PER_BATCH, clips_remaining)
            clips_remaining -= batch_clips_count

            if batch_clips_count <= 0:
                break

            # Filter segments for this time chunk
            batch_segments = [
                s for s in segments
                if s.get("start", 0.0) >= batch_start and s.get("end", 0.0) <= batch_end
            ]
            if not batch_segments:
                continue

            batch_transcript = {**transcript, "segments": batch_segments}

            update_job_progress(
                project_id, stage="select",
                percent=30.0 + (50.0 * batch_idx / num_batches),
                detail=f"LLM batch {batch_idx + 1}/{num_batches} ({batch_clips_count} clips from {batch_start:.0f}s–{batch_end:.0f}s)..."
            )

            batch_prompt = _build_selection_prompt(
                transcript=batch_transcript,
                scenes=[s for s in scenes if batch_start <= s.get("start_sec", s.get("time", 0.0)) <= batch_end][:10],
                campaign_brief=campaign_brief,
                editorial_template=editorial_template,
                rights_basis=rights_basis,
                clip_count=batch_clips_count,
                min_length_sec=min_length_sec,
                max_length_sec=max_length_sec,
                custom_prompt=custom_prompt,
                temporal_bins_directive="",
                content_focus=content_focus,
            )

            batch_raw = []
            for attempt in range(1, 3):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    batch_response = loop.run_until_complete(
                        llm_client.complete_json(
                            prompt=batch_prompt,
                            system=SELECTION_SYSTEM_PROMPT,
                            temperature=0.25,
                            max_tokens=16384,
                        )
                    )
                    batch_raw = (
                        batch_response.get("clips", []) if isinstance(batch_response, dict) else batch_response
                    )
                    if batch_raw:
                        break
                except Exception as e:
                    logger.warning(f"[LLM Select] Batch {batch_idx + 1} attempt {attempt} failed: {e}")
                finally:
                    loop.close()

            logger.info(f"[LLM Select] Batch {batch_idx + 1}/{num_batches}: got {len(batch_raw)} clips")
            all_raw_clips.extend(batch_raw)

        raw_clips = all_raw_clips
        logger.info(f"[LLM Select] Batched selection complete: {len(raw_clips)} total clips from {num_batches} batches")

    else:
        # Single-shot for small clip counts
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
            temporal_bins_directive=temporal_bins_directive,
            content_focus=content_focus,
        )

        update_job_progress(project_id, stage="select", percent=30.0, detail="Awaiting LLM extraction (this takes a moment)...")

        raw_clips = []
        max_llm_attempts = 3

        for attempt in range(1, max_llm_attempts + 1):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                current_prompt = prompt
                if attempt > 1:
                    current_prompt = prompt + f"\n\n⚠️ CRITICAL: Your previous response contained only {len(raw_clips)} clips. You MUST return exactly {clip_count} clips. This is attempt {attempt}/{max_llm_attempts}."

                response_json = loop.run_until_complete(
                    llm_client.complete_json(
                        prompt=current_prompt,
                        system=SELECTION_SYSTEM_PROMPT,
                        temperature=0.2 + (attempt - 1) * 0.1,
                        max_tokens=16384,
                    )
                )
            finally:
                loop.close()

            raw_clips = (
                response_json.get("clips", []) if isinstance(response_json, dict) else response_json
            )

            if len(raw_clips) >= clip_count:
                logger.info(f"[LLM Select] Got {len(raw_clips)} clips on attempt {attempt}")
                break
            else:
                logger.warning(
                    f"[LLM Select] Attempt {attempt}/{max_llm_attempts}: LLM returned {len(raw_clips)} clips "
                    f"but {clip_count} were requested. {'Retrying...' if attempt < max_llm_attempts else 'Proceeding.'}"
                )

    # === Fallback: if LLM still returned fewer clips, generate evenly-spaced fillers ===
    if len(raw_clips) < clip_count:
        shortfall = clip_count - len(raw_clips)
        logger.warning(f"[LLM Select] LLM underdelivered by {shortfall} clips. Generating transcript-based fillers.")

        # Find time ranges NOT already covered by LLM clips
        covered_ranges = [(float(c.get("start_sec", 0)), float(c.get("end_sec", 0))) for c in raw_clips]
        effective_start = time_range_start or 0.0
        effective_end = time_range_end or total_duration
        available_duration = effective_end - effective_start

        for filler_idx in range(shortfall):
            # Evenly space filler clips across the timeline
            target_time = effective_start + (available_duration * (filler_idx + 0.5) / shortfall)

            # Find the nearest segment to this target time
            nearest_seg = min(segments, key=lambda s: abs(s.get("start", 0.0) - target_time), default=None)
            if not nearest_seg:
                continue

            filler_start = float(nearest_seg.get("start", target_time))

            # Check if this overlaps with existing clips
            overlaps = any(
                filler_start >= cs and filler_start <= ce
                for cs, ce in covered_ranges
            )
            if overlaps:
                # Shift forward to avoid overlap
                filler_start = max(ce for cs, ce in covered_ranges if filler_start >= cs and filler_start <= ce) + 2.0

            filler_end = filler_start + ((min_length_sec + max_length_sec) / 2.0)
            filler_end = min(filler_end, effective_end)

            if filler_end - filler_start < min_length_sec:
                continue

            # Grab text around this time for a title
            nearby_text = " ".join(
                s.get("text", "").strip()
                for s in segments
                if filler_start <= s.get("start", 0.0) <= filler_start + 10
            )[:60]

            raw_clips.append({
                "start_sec": round(filler_start, 1),
                "end_sec": round(filler_end, 1),
                "title": f"Highlight @ {int(filler_start)}s" + (f" — {nearby_text}..." if nearby_text else ""),
                "hook_type": "bold_statement",
                "hook_text": nearby_text[:80] if nearby_text else "Check this out!",
                "editorial_potential": 0.65,
                "reasoning": "Auto-generated filler to meet requested clip count.",
                "suggested_callouts": [],
            })
            covered_ranges.append((filler_start, filler_end))

        logger.info(f"[LLM Select] After fillers: {len(raw_clips)} total clips")

    update_job_progress(project_id, stage="select", percent=80.0, detail="Ranking candidates & deduplicating...")

    try:
        total_source_dur = transcript.get("duration_sec", 60.0)

        # Compute transformation score and enrich candidates
        transcript_segments = transcript.get("segments", [])

        clamp_stats = {"none": 0, "sentence_boundary": 0, "scene_boundary": 0, "raw_fallback": 0}

        def enrich(raw: Dict[str, Any]) -> Dict[str, Any]:
            start_s = float(raw.get("start_sec", 0.0))
            end_s = float(raw.get("end_sec", start_s + min_length_sec))

            # Widen payoff-only picks into a full bit before enforcing the hard limits
            start_s, end_s = expand_to_natural_bit(
                start_s, end_s, min_length_sec, max_length_sec, transcript_segments
            )

            # Boundary-aware duration enforcement
            start_s, end_s, clamp_method = clamp_to_boundary(
                start_sec=start_s,
                end_sec=end_s,
                max_length_sec=max_length_sec,
                min_length_sec=min_length_sec,
                transcript_segments=transcript_segments,
                scenes=scenes,
            )
            clamp_stats[clamp_method] = clamp_stats.get(clamp_method, 0) + 1

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
                "raw_start_sec": round(float(raw.get("start_sec", 0.0)), 2),
                "raw_end_sec": round(float(raw.get("end_sec", 0.0)), 2),
                "raw_duration_sec": round(float(raw.get("end_sec", 0.0)) - float(raw.get("start_sec", 0.0)), 2),
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
                "clamp_method": clamp_method,
            }
            return cand

        enriched_candidates = [enrich(raw) for raw in raw_clips]

        logger.info(f"[LLM Select] Clamp stats: {clamp_stats}")

        # Bin-membership validation for even_spread mode
        if temporal_bins and temporal_distribution == "even_spread":
            enriched_candidates, bin_violations = validate_bin_membership(
                enriched_candidates, temporal_bins
            )
            if bin_violations:
                logger.warning(
                    f"[LLM Select] {len(bin_violations)} candidates discarded "
                    f"due to bin-membership violations"
                )

        # Snap to scene cut boundaries and deduplicate
        final_clips = deduplicate_and_rank_candidates(enriched_candidates, scenes=scenes, max_length_sec=max_length_sec)

        # Refill: overlap removal can leave fewer clips than requested. Ask for one more
        # pick from each of the largest stretches that have no clip yet (also evens out the spread).
        range_start = time_range_start or 0.0
        range_end = time_range_end or total_source_dur
        for _refill_round in range(2):
            shortfall = clip_count - len(final_clips)
            if shortfall <= 0:
                break
            gaps = []
            cursor = range_start
            for c_start, c_end in sorted((c["start_sec"], c["end_sec"]) for c in final_clips):
                if c_start - cursor >= max_length_sec * 2:
                    gaps.append((c_start - cursor, cursor, c_start))
                cursor = max(cursor, c_end)
            if range_end - cursor >= max_length_sec * 2:
                gaps.append((range_end - cursor, cursor, range_end))
            gaps.sort(reverse=True)

            extra_raw: List[Dict[str, Any]] = []
            for _gap_len, gap_start, gap_end in gaps[: min(shortfall, 6)]:
                gap_segments = [
                    s for s in transcript_segments
                    if s.get("start", 0.0) >= gap_start and s.get("end", 0.0) <= gap_end
                ]
                if len(gap_segments) < 5:
                    continue
                update_job_progress(
                    project_id, stage="select", percent=85.0,
                    detail=f"Filling gap {gap_start:.0f}s–{gap_end:.0f}s ({shortfall} clips short)...",
                )
                try:
                    extra_raw.extend(_run_llm_selection(
                        _build_selection_prompt(
                            transcript={**transcript, "segments": gap_segments},
                            scenes=[],
                            campaign_brief=campaign_brief,
                            editorial_template=editorial_template,
                            rights_basis=rights_basis,
                            clip_count=1,
                            min_length_sec=min_length_sec,
                            max_length_sec=max_length_sec,
                            custom_prompt=custom_prompt,
                            content_focus=content_focus,
                        ),
                        temperature=0.3,
                    )[:1])
                except Exception as e:
                    logger.warning(f"[LLM Select] Refill call failed for gap {gap_start:.0f}s–{gap_end:.0f}s: {e}")
            if not extra_raw:
                break
            final_clips = deduplicate_and_rank_candidates(
                final_clips + [enrich(r) for r in extra_raw], scenes=scenes, max_length_sec=max_length_sec
            )

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
            existing_clips = db_session.query(Clip).filter(Clip.project_id == pid).all()
            
            for c in final_clips:
                matched = False
                for ex in existing_clips:
                    if abs(float(ex.start_sec) - c["start_sec"]) < 0.2 and abs(float(ex.end_sec) - c["end_sec"]) < 0.2:
                        matched = True
                        c["clip_id"] = str(ex.id)
                        break
                        
                if not matched:
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
                    db_session.flush()
                    c["clip_id"] = str(clip_record.id)
                    existing_clips.append(clip_record)

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

        update_job_progress(project_id, stage="select", status="success", percent=100.0, detail="Selection complete.", force_write=True)
        logger.info(f"[LLM Select] Selected {len(final_clips)} clips for project {project_id}")
        return selections_payload

    except LLMClientError as e:
        error_msg = f"LLM Gateway error: {e.message}"
        logger.error(f"[LLM Select] {error_msg}")
        update_job_progress(project_id, stage="select", status="failed", error_message=error_msg, force_write=True)
        _update_project_status(project_id, "failed")
        raise

    except Exception as e:
        error_msg = f"Candidate selection error: {e}"
        logger.error(f"[LLM Select] {error_msg}")
        if self.request.retries < self.max_retries:
            update_job_progress(project_id, stage="select", status="retrying", error_message=error_msg, force_write=True)
            raise self.retry(exc=e)
        else:
            update_job_progress(project_id, stage="select", status="failed", error_message=error_msg, force_write=True)
            _update_project_status(project_id, "failed")
            raise

