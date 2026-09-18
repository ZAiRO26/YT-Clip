"""
ClipForge AI — Master Product Smoke Test
Verifies all critical product features end-to-end.
"""
import json
import sys
import time
import urllib.request
import urllib.error

import sys
import io

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

API = "http://localhost:8000"
PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, condition, detail))
    print(f"  {status}  {name}" + (f"  ({detail})" if detail else ""))
    return condition


def api_get(path):
    try:
        with urllib.request.urlopen(f"{API}{path}", timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else {}
        except Exception:
            return e.code, {"raw": raw.decode("utf-8", errors="replace")}
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(path, data=None):
    body = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(f"{API}{path}", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body.decode("utf-8", errors="replace")}
    except Exception as e:
        return 0, {"error": str(e)}


print("=" * 60)
print("  ClipForge AI — Master Product Smoke Test")
print("=" * 60)
print()

# ─── 1. INFRASTRUCTURE CHECKS ───────────────────────────────
print("1. INFRASTRUCTURE")
print("-" * 40)

# Health endpoint
code, data = api_get("/health")
check("API /health returns 200", code == 200)
check("API reports status=ok", data.get("status") == "ok")
check("LLM gateway configured", "20128" in data.get("llm_gateway", ""))

# Ready endpoint
code, data = api_get("/ready")
check("API /ready returns 200", code == 200)

# LLM health
code, data = api_get("/health/llm")
check("LLM /health/llm returns 200", code == 200, data.get("status", "unknown"))

# Redis connectivity (via Celery broker ping)
try:
    import redis
    r = redis.Redis(host="127.0.0.1", port=6379, db=0)
    r.ping()
    check("Redis connectivity", True)
except Exception as e:
    check("Redis connectivity", False, str(e))

print()

# ─── 2. DATABASE & SCHEMA ───────────────────────────────────
print("2. DATABASE & SCHEMA")
print("-" * 40)

try:
    import psycopg2
    conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="clipforge", user="postgres", password="password")
    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    tables = [r[0] for r in cur.fetchall()]
    check("Clipforge DB accessible", True)

    expected_tables = ["projects", "clips", "jobs", "users", "campaign_briefs"]
    for t in expected_tables:
        check(f"Table '{t}' exists", t in tables)

    cur.execute("SELECT count(*) FROM projects")
    proj_count = cur.fetchone()[0]
    check("Projects table queryable", True, f"{proj_count} projects")
    conn.close()
except Exception as e:
    check("Database connection", False, str(e))

print()

# ─── 3. API ENDPOINTS ───────────────────────────────────────
print("3. API ENDPOINTS")
print("-" * 40)

# List projects
code, data = api_get("/api/projects")
check("GET /api/projects returns 200", code == 200)
if isinstance(data, list):
    check("Projects response is list", True, f"{len(data)} projects")
else:
    check("Projects response is list", False, str(type(data)))

# Settings
code, data = api_get("/api/settings")
check("GET /api/settings returns 200", code == 200)

# Campaign briefs
code, data = api_get("/api/campaign-briefs")
check("GET /api/campaign-briefs returns 200", code == 200)

# Voice personas
code, data = api_get("/api/voice-personas")
if code == 200:
    check("GET /api/voice-personas returns 200", True, f"{len(data)} voices")
else:
    check("GET /api/voice-personas", False, f"HTTP {code}")

print()

# ─── 4. CLIP OPERATIONS (if clips exist) ────────────────────
print("4. CLIP OPERATIONS")
print("-" * 40)

# Find a clip to test with
clip_id = None
project_id = None
try:
    conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="clipforge", user="postgres", password="password")
    cur = conn.cursor()
    cur.execute("SELECT id, project_id FROM clips LIMIT 1")
    row = cur.fetchone()
    if row:
        clip_id = str(row[0])
        project_id = str(row[1])
    conn.close()
except Exception:
    pass

if clip_id:
    check("Found test clip", True, f"clip={clip_id[:12]}...")

    # Voiceover context
    code, data = api_get(f"/api/clips/{clip_id}/voiceover-context")
    check("GET voiceover-context returns 200", code == 200)
    if code == 200:
        check("Has transcript_snippet", "transcript_snippet" in data)
        check("Has silence gaps", "gaps" in data)

    # Generate voiceover script (hook_intro)
    code, data = api_post(f"/api/clips/{clip_id}/generate-voiceover-script", {
        "style": "hook_intro",
        "voice_id": "af_bella"
    })
    check("POST generate-voiceover-script returns 200", code == 200, f"HTTP {code}")
    if code == 200:
        check("Script generated", bool(data.get("script")), data.get("script", "")[:50])
        check("Word count in budget", data.get("word_count", 0) >= 6)
        check("Start offset computed", "start_offset_sec" in data)
        check("Audio preview URL generated", bool(data.get("audio_preview_url")))

        # Test that the audio file is actually servable
        audio_url = data.get("audio_preview_url", "")
        if audio_url:
            try:
                with urllib.request.urlopen(f"{API}/{audio_url}", timeout=10) as r:
                    content_type = r.headers.get("Content-Type", "")
                    content_len = int(r.headers.get("Content-Length", 0))
                    check("Audio preview file servable", r.status == 200, f"{content_len} bytes, {content_type}")
            except Exception as e:
                check("Audio preview file servable", False, str(e))

    # Test project clips endpoint
    code, data = api_get(f"/api/projects/{project_id}/clips")
    check("GET project clips returns 200", code == 200)
    if code == 200 and isinstance(data, list):
        check("Clips returned for project", len(data) > 0, f"{len(data)} clips")
else:
    check("No clips in DB to test", True, "SKIPPED - fresh database")

print()

# ─── 5. KOKORO TTS ENGINE ───────────────────────────────────
print("5. KOKORO TTS ENGINE")
print("-" * 40)

try:
    from clipforge_core.services.tts_service import get_kokoro_engine, resolve_voice_id, VOICE_PERSONAS
    check("TTS service importable", True)
    check("Voice personas catalog", len(VOICE_PERSONAS) >= 7, f"{len(VOICE_PERSONAS)} voices")

    # Test voice ID resolution
    resolved = resolve_voice_id("af_bella")
    check("Voice ID resolve (af_bella)", resolved == "af_bella")
    resolved_legacy = resolve_voice_id("en-US-JennyNeural")
    check("Legacy voice alias resolve", resolved_legacy == "af_bella")

    # Test Kokoro engine initialization
    kokoro = get_kokoro_engine()
    check("Kokoro ONNX engine loads", kokoro is not None)

    if kokoro:
        samples, sr = kokoro.create(text="Hello world test", voice="af_bella", speed=1.0, lang="en-us")
        duration = round(len(samples) / float(sr), 2)
        check("Kokoro TTS synthesis works", duration > 0.3, f"{duration}s audio generated")
except Exception as e:
    check("Kokoro TTS Engine", False, str(e))

print()

# ─── 6. SCRIPT GENERATOR ────────────────────────────────────
print("6. SCRIPT GENERATOR")
print("-" * 40)

try:
    from clipforge_core.services.script_generator import enforce_word_count, check_groundedness, STYLE_WORD_BUDGETS
    check("Script generator importable", True)
    check("Style word budgets defined", len(STYLE_WORD_BUDGETS) == 4)

    # Test enforce_word_count
    text, count = enforce_word_count("This is a test hook for the video", "hook_intro")
    check("enforce_word_count works", count <= 9, f"{count} words")

    # Test groundedness
    result = check_groundedness("She was furious about the decision", "He said he liked the food")
    check("Groundedness flags ungrounded claims", result["has_unverified_claim"] is True)

    result2 = check_groundedness("He talked about the food", "He said he liked the food")
    check("Groundedness passes grounded script", result2["has_unverified_claim"] is False)
except Exception as e:
    check("Script Generator", False, str(e))

print()

# ─── 7. EFFECTS ENGINE ──────────────────────────────────────
print("7. EFFECTS ENGINE")
print("-" * 40)

try:
    from clipforge_core.services.effects_engine import EFFECT_CATALOG, build_effect_filter
    check("Effects engine importable", True)
    check("Effects catalog has entries", len(EFFECT_CATALOG) >= 6, f"{len(EFFECT_CATALOG)} effects")

    for effect_id in ["film_grain", "vignette", "zoom", "camera_shake", "rgb_split", "vhs_noise"]:
        filt = build_effect_filter(effect_id, 0.5)
        check(f"Effect '{effect_id}' builds filter", bool(filt))
except Exception as e:
    check("Effects Engine", False, str(e))

print()

# ─── 8. GAP DETECTOR ────────────────────────────────────────
print("8. GAP DETECTOR & VOICEOVER OFFSET")
print("-" * 40)

try:
    from clipforge_core.services.gap_detector import find_silence_gaps, compute_voiceover_start_offset
    check("Gap detector importable", True)

    segments = [
        {"start": 0.0, "end": 5.0, "text": "hello"},
        {"start": 10.0, "end": 15.0, "text": "world"},
    ]
    gaps = find_silence_gaps(segments, clip_start_sec=0.0, clip_end_sec=20.0, min_gap_sec=3.0)
    check("Silence gap detection works", len(gaps) > 0, f"{len(gaps)} gaps found")

    offset = compute_voiceover_start_offset(style="hook_intro", clip_duration_sec=30.0, script_word_count=8, gaps=[])
    check("Voiceover offset computed", offset >= 0, f"{offset}s offset")
except Exception as e:
    check("Gap Detector", False, str(e))

print()

# ─── 9. FACE TRACKER ────────────────────────────────────────
print("9. FACE TRACKER")
print("-" * 40)

try:
    from clipforge_core.services.face_tracker import track_faces
    check("Face tracker importable", True)
except Exception as e:
    check("Face tracker importable", False, str(e))

print()

# ─── 10. FRONTEND BUILD CHECK ───────────────────────────────
print("10. FRONTEND CONNECTIVITY")
print("-" * 40)

try:
    with urllib.request.urlopen("http://localhost:3000", timeout=10) as r:
        check("Next.js frontend reachable", r.status == 200)
except Exception as e:
    check("Next.js frontend reachable", False, str(e))

print()

# ─── SUMMARY ────────────────────────────────────────────────
print("=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total = len(results)
print(f"  TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}")
if failed == 0:
    print("  [SUCCESS] ALL CHECKS PASSED - PRODUCT IS WORKING AS INTENDED")
else:
    print(f"  [FAILURE] {failed} CHECK(S) FAILED - SEE ABOVE")
    print()
    print("  Failed checks:")
    for name, ok, detail in results:
        if not ok:
            print(f"    - {name}: {detail}")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
