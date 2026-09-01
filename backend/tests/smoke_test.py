"""
ClipForge AI — Smoke Test

Full-stack smoke test that:
1. Checks backend health
2. Creates a campaign brief via API
3. Creates a project via API (triggers pipeline)
4. Polls project status until done/failed
5. Lists generated clips
6. Reports pass/fail for each stage

Usage: uv run python tests/smoke_test.py
"""
import json
import sys
import time
import requests

API_BASE = "http://localhost:8000"


def check(name, condition, detail=""):
    status = "[PASS]" if condition else "[FAIL]"
    msg = f"  {status} {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    return condition


def main():
    print("=" * 60)
    print("  ClipForge AI -- Full-Stack Smoke Test")
    print("=" * 60)

    all_pass = True

    # 1. Health check
    print("\n--- Step 1: Health Check ---")
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        data = r.json()
        all_pass &= check("Backend reachable", r.status_code == 200)
        all_pass &= check("Service name", data.get("service") == "clipforge-api")
        all_pass &= check("Database", "supabase" in data.get("database", ""))
        all_pass &= check("Redis configured", "redis" in data.get("redis", ""))
    except Exception as e:
        check("Backend reachable", False, str(e))
        print("\nBackend not running. Start it first:")
        print("  cd backend && uv run uvicorn app.main:app --port 8000")
        sys.exit(1)

    # 2. Campaign brief
    print("\n--- Step 2: Campaign Brief ---")
    try:
        brief_data = {
            "name": "Smoke Test Brief",
            "brief_json": {
                "tone": "fun and engaging",
                "required_mentions": [],
                "banned_topics": [],
                "brand_rules": "Select the most interesting moments"
            }
        }
        r = requests.post(f"{API_BASE}/api/campaign-briefs", json=brief_data, timeout=10)
        brief = r.json()
        all_pass &= check("Brief created", r.status_code == 200, f"id={brief.get('id', '?')}")
        brief_id = brief.get("id")

        r = requests.get(f"{API_BASE}/api/campaign-briefs", timeout=10)
        briefs = r.json()
        all_pass &= check("Brief listed", any(b["id"] == brief_id for b in briefs))
    except Exception as e:
        all_pass &= check("Campaign brief", False, str(e))
        brief_id = None

    # 3. Create project
    print("\n--- Step 3: Create Project ---")
    try:
        project_data = {
            "source_type": "youtube_url",
            "source_value": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "clip_count": 1,
            "min_length_sec": 5,
            "max_length_sec": 19,
            "aspect_ratio": "9:16",
            "caption_style": "none",
        }
        if brief_id:
            project_data["campaign_brief_id"] = brief_id

        r = requests.post(f"{API_BASE}/api/projects", json=project_data, timeout=15)
        project = r.json()
        all_pass &= check("Project created", r.status_code == 200, f"id={project.get('id', '?')}")
        project_id = project.get("id")

        # Check jobs were created
        jobs = project.get("jobs", [])
        all_pass &= check("Pipeline jobs created", len(jobs) == 5, f"count={len(jobs)}")
        all_pass &= check("Status is queued", project.get("status") == "queued")
    except Exception as e:
        all_pass &= check("Project creation", False, str(e))
        project_id = None

    if not project_id:
        print("\n[FAIL] Cannot continue without project ID")
        sys.exit(1)

    # 4. Poll pipeline status
    print("\n--- Step 4: Pipeline Execution ---")
    print("  Polling every 5s (timeout: 10 minutes)...")

    start_time = time.time()
    timeout = 600  # 10 minutes
    last_status = ""

    while time.time() - start_time < timeout:
        try:
            r = requests.get(f"{API_BASE}/api/projects/{project_id}", timeout=10)
            proj = r.json()
            status = proj.get("status", "unknown")

            if status != last_status:
                elapsed = time.time() - start_time
                print(f"  [{elapsed:.0f}s] Status: {last_status} -> {status}")
                last_status = status

                # Print per-stage details
                for job in proj.get("jobs", []):
                    stage = job.get("stage", "?")
                    jstatus = job.get("status", "?")
                    err = job.get("error_message", "")
                    suffix = f" -- {err}" if err else ""
                    print(f"    {stage:12s} {jstatus}{suffix}")

            if status in ("done", "failed"):
                break

        except Exception as e:
            print(f"  [ERROR] Poll failed: {e}")

        time.sleep(5)

    elapsed = time.time() - start_time

    # Final status
    r = requests.get(f"{API_BASE}/api/projects/{project_id}", timeout=10)
    project = r.json()
    final_status = project.get("status", "unknown")

    print(f"\n  Final status: {final_status} (after {elapsed:.0f}s)")

    for job in project.get("jobs", []):
        stage = job.get("stage", "?")
        jstatus = job.get("status", "?")
        err = job.get("error_message", "")
        icon = "[PASS]" if jstatus == "success" else "[FAIL]" if jstatus == "failed" else "[----]"
        suffix = f" -- {err}" if err else ""
        print(f"  {icon} {stage:12s} {jstatus}{suffix}")
        if jstatus != "success" and stage in ("download", "transcribe", "crop"):
            all_pass = False

    # 5. Check clips
    print("\n--- Step 5: Generated Clips ---")
    try:
        r = requests.get(f"{API_BASE}/api/projects/{project_id}/clips", timeout=10)
        clips = r.json()
        all_pass &= check("Clips returned", len(clips) > 0, f"count={len(clips)}")

        for clip in clips:
            duration = clip.get("end_sec", 0) - clip.get("start_sec", 0)
            score = clip.get("score", 0)
            file_url = clip.get("file_url", "")
            review = clip.get("review_status", "?")
            print(f"    Clip: {clip.get('start_sec', 0):.1f}s-{clip.get('end_sec', 0):.1f}s "
                  f"({duration:.0f}s) score={score or '?'} review={review} "
                  f"file={'yes' if file_url else 'no'}")

        # Test clip review
        if clips:
            clip_id = clips[0]["id"]
            r = requests.patch(
                f"{API_BASE}/api/clips/{clip_id}",
                json={"review_status": "approved"},
                timeout=10,
            )
            updated = r.json()
            all_pass &= check("Clip approve", updated.get("review_status") == "approved")
    except Exception as e:
        all_pass &= check("Clips check", False, str(e))

    # 6. Project list
    print("\n--- Step 6: Project List ---")
    try:
        r = requests.get(f"{API_BASE}/api/projects", timeout=10)
        projects = r.json()
        all_pass &= check("Projects list", len(projects) > 0, f"count={len(projects)}")
        all_pass &= check("Our project listed", any(p["id"] == project_id for p in projects))
    except Exception as e:
        all_pass &= check("Projects list", False, str(e))

    # Summary
    print("\n" + "=" * 60)
    if all_pass:
        print("  SMOKE TEST PASSED -- All checks green")
    else:
        print("  SMOKE TEST PARTIAL -- Some checks failed (see above)")
    print("=" * 60)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
