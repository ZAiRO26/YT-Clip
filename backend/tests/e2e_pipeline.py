"""
ClipForge AI — End-to-End Pipeline CLI

Run the full pipeline from the command line:
    YouTube URL in -> N captioned vertical clips out

Usage:
    uv run python -m tests.e2e_pipeline \
        --url "https://www.youtube.com/watch?v=VIDEO_ID" \
        --clips 3 \
        --min-length 15 \
        --max-length 60 \
        --aspect-ratio "9:16" \
        --caption-style "bold_karaoke" \
        --brief '{"tone": "energetic", "required_mentions": [], "banned_topics": []}'

    Or with a local file:
    uv run python -m tests.e2e_pipeline \
        --local "D:/path/to/video.mp4" \
        --clips 3

This runs each pipeline stage sequentially (no Celery, no database)
to prove the core pipeline works end-to-end before building any UI.
"""
import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_step(step: int, total: int, text: str) -> None:
    print(f"\n--- Step {step}/{total}: {text} ---")


def main():
    parser = argparse.ArgumentParser(
        description="ClipForge AI — End-to-End Pipeline CLI Test"
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--url", "-u", help="YouTube URL to process")
    source_group.add_argument("--local", "-l", help="Local video file/folder path")

    parser.add_argument("--clips", "-n", type=int, default=3, help="Number of clips to generate (default: 3)")
    parser.add_argument("--min-length", type=int, default=15, help="Minimum clip length in seconds (default: 15)")
    parser.add_argument("--max-length", type=int, default=60, help="Maximum clip length in seconds (default: 60)")
    parser.add_argument("--aspect-ratio", type=str, default="9:16", choices=["9:16", "1:1", "16:9"], help="Target aspect ratio (default: 9:16)")
    parser.add_argument("--caption-style", type=str, default="bold_karaoke", choices=["bold_karaoke", "minimal", "subtitle", "none"], help="Caption style (default: bold_karaoke)")
    parser.add_argument("--brief", type=str, default=None, help="Campaign brief JSON string")
    parser.add_argument("--skip-captions", action="store_true", help="Skip caption stage (faster for testing)")
    parser.add_argument("--skip-clipsai", action="store_true", help="Skip ClipsAI, use center-crop only")

    args = parser.parse_args()

    # Default campaign brief
    if args.brief:
        campaign_brief = json.loads(args.brief)
    else:
        campaign_brief = {
            "tone": "engaging and energetic",
            "required_mentions": [],
            "banned_topics": [],
            "brand_rules": "Select the most interesting, attention-grabbing moments. Prefer segments with clear speech and emotional peaks.",
        }

    # Generate a project ID
    project_id = str(uuid.uuid4())

    print_header("ClipForge AI — End-to-End Pipeline Test")
    print(f"Project ID:     {project_id}")
    print(f"Source:         {args.url or args.local}")
    print(f"Clips:          {args.clips}")
    print(f"Length:         {args.min_length}-{args.max_length}s")
    print(f"Aspect ratio:   {args.aspect_ratio}")
    print(f"Caption style:  {args.caption_style}")
    print(f"Media dir:      {settings.MEDIA_DIR}")

    total_steps = 5 if not args.skip_captions else 4
    overall_start = time.time()

    # ========================================
    # STEP 1: DOWNLOAD
    # ========================================
    print_step(1, total_steps, "DOWNLOAD")
    step_start = time.time()

    from app.workers.download import _download_youtube, _get_project_dir, _ingest_local_folder

    project_dir = _get_project_dir(project_id)
    source_path = str(project_dir / "source.mp4")

    if args.url:
        source_type = "youtube_url"
        metadata = _download_youtube(args.url, project_dir / "source.mp4")
        print(f"Title:      {metadata.get('title')}")
        print(f"Duration:   {metadata.get('duration_sec')}s")
        print(f"Resolution: {metadata.get('resolution')}")
    else:
        source_type = "local_folder"
        metadata = _ingest_local_folder(args.local, project_dir)
        print(f"File:       {metadata.get('title')}")
        print(f"Size:       {metadata.get('file_size_mb')} MB")

    # Verify source exists
    if not Path(source_path).exists():
        # Check for alternative file
        candidates = list(project_dir.glob("source.*"))
        if candidates:
            actual = candidates[0]
            if actual.name != "source.mp4":
                actual.rename(source_path)
        else:
            print("[FAIL] No source file found after download")
            sys.exit(1)

    elapsed = time.time() - step_start
    size_mb = Path(source_path).stat().st_size / (1024 * 1024)
    print(f"\n[OK] Downloaded: {size_mb:.2f} MB in {elapsed:.1f}s")

    # ========================================
    # STEP 2: TRANSCRIBE
    # ========================================
    print_step(2, total_steps, "TRANSCRIBE")
    step_start = time.time()

    from app.workers.transcribe import transcribe_audio

    transcript = transcribe_audio(source_path, str(project_dir))

    elapsed = time.time() - step_start
    print(f"Language:   {transcript['language']}")
    print(f"Duration:   {transcript['duration_sec']:.1f}s")
    print(f"Segments:   {transcript['segment_count']}")
    print(f"Text:       {transcript['full_text'][:200]}...")
    print(f"\n[OK] Transcribed in {elapsed:.1f}s")

    # ========================================
    # STEP 3: SELECT (LLM)
    # ========================================
    print_step(3, total_steps, "SELECT (LLM)")
    step_start = time.time()

    transcript_path = str(project_dir / "transcript.json")

    try:
        from app.workers.select import select_clips

        selections_result = asyncio.run(select_clips(
            transcript_path=transcript_path,
            campaign_brief=campaign_brief,
            clip_count=args.clips,
            min_length_sec=args.min_length,
            max_length_sec=args.max_length,
        ))

        elapsed = time.time() - step_start
        selections = selections_result["clips"]

        print(f"Found:      {len(selections)}/{args.clips} clips")
        for i, sel in enumerate(selections):
            print(
                f"  Clip {i+1}: {sel['start_sec']:.1f}s - {sel['end_sec']:.1f}s "
                f"(score={sel['score']:.2f}) {sel['reasoning'][:80]}"
            )
        print(f"\n[OK] Selected in {elapsed:.1f}s")

    except Exception as e:
        print(f"\n[WARN] LLM selection failed: {e}")
        print("Falling back to evenly-spaced segments...")

        # Fallback: create evenly-spaced clips from the transcript
        total_dur = transcript["duration_sec"]
        clip_duration = min(args.max_length, max(args.min_length, total_dur / args.clips))
        selections = []
        for i in range(min(args.clips, int(total_dur / clip_duration))):
            start = i * (total_dur / args.clips)
            end = min(start + clip_duration, total_dur)
            selections.append({
                "start_sec": round(start, 3),
                "end_sec": round(end, 3),
                "score": 0.5,
                "reasoning": "Fallback: evenly-spaced segment (LLM unavailable)",
            })

        # Save fallback selections
        selections_result = {"clips": selections, "total_found": len(selections)}
        sel_path = project_dir / "selections.json"
        sel_path.write_text(json.dumps(selections_result, indent=2), encoding="utf-8")

        elapsed = time.time() - step_start
        print(f"[OK] Fallback selection: {len(selections)} clips in {elapsed:.1f}s")

    if not selections:
        print("[FAIL] No clips selected. Source video may be too short.")
        sys.exit(1)

    # ========================================
    # STEP 4: CROP
    # ========================================
    print_step(4, total_steps, "CROP")
    step_start = time.time()

    from app.workers.crop import crop_clip

    clips_dir = project_dir / "clips"
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
                aspect_ratio=args.aspect_ratio,
                use_clipsai=not args.skip_clipsai,
            )
            result["index"] = i
            result["score"] = sel["score"]
            result["reasoning"] = sel["reasoning"]
            cropped_clips.append(result)
            print(f"  Clip {i+1}: {result['method']} | {result['duration_sec']:.1f}s | {result['file_size_mb']} MB")
        except Exception as e:
            print(f"  Clip {i+1}: [FAIL] {e}")

    elapsed = time.time() - step_start
    print(f"\n[OK] Cropped {len(cropped_clips)}/{len(selections)} clips in {elapsed:.1f}s")

    if not cropped_clips:
        print("[FAIL] No clips cropped successfully")
        sys.exit(1)

    # ========================================
    # STEP 5: CAPTION
    # ========================================
    if not args.skip_captions:
        print_step(5, total_steps, "CAPTION")
        step_start = time.time()

        from app.workers.caption import caption_clip as add_caption

        final_clips = []
        caption_style = args.caption_style

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
                print(f"  Clip {idx+1}: {cap_result['method']} | {cap_result.get('file_size_mb', '?')} MB")
            except Exception as e:
                print(f"  Clip {idx+1}: [FAIL] {e}")
                # Keep the cropped version as fallback
                clip["final_path"] = clip["output_path"]
                clip["caption_method"] = "none"
                final_clips.append(clip)

        elapsed = time.time() - step_start
        print(f"\n[OK] Captioned {len(final_clips)} clips in {elapsed:.1f}s")
    else:
        final_clips = cropped_clips
        for clip in final_clips:
            clip["final_path"] = clip["output_path"]
            clip["caption_method"] = "skipped"
        print("\n--- Captions skipped ---")

    # ========================================
    # SUMMARY
    # ========================================
    total_elapsed = time.time() - overall_start

    print_header("PIPELINE COMPLETE")
    print(f"Total time:     {total_elapsed:.1f}s")
    print(f"Output dir:     {clips_dir}")
    print(f"Clips produced: {len(final_clips)}")
    print()

    for clip in final_clips:
        final = clip.get("final_path", clip.get("output_path", "?"))
        print(
            f"  [{clip.get('index', '?')+1}] {Path(final).name} | "
            f"score={clip.get('score', 0):.2f} | "
            f"{clip.get('duration_sec', 0):.1f}s | "
            f"crop={clip.get('method', '?')} | "
            f"caption={clip.get('caption_method', '?')}"
        )

    print(f"\nOutput files:")
    for f in sorted(clips_dir.glob("*_final.mp4")):
        print(f"  {f}")
    if not list(clips_dir.glob("*_final.mp4")):
        for f in sorted(clips_dir.glob("*_cropped.mp4")):
            print(f"  {f}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
