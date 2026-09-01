# Project Status

## Current State
- **Branch:** `feature/clipforge-v2-foundation`
- **Phase 0 (Product Policy & Documentation):** ✅ Complete
- **Phase 1 (Foundation and Local Development):** ✅ 100% Complete
- **Phase 2 (Source Ingestion and Analysis):** ✅ 100% Complete
- **Phase 3 (Brief-Aware Candidate Selection):** ✅ 100% Complete
- **Phase 4 (First Professional Render):** ✅ 100% Complete
- **Phase 5 (Editorial Transformation Layer):** ✅ 100% Complete
- **Next Milestone:** Phase 6 (Voiceover and Audio Studio)

## v1 Baseline
- `master` branch contains the QA-verified v1 codebase (commit `f342cbe`).
- v1 pipeline (download → transcribe → select → crop → caption) is fully operational.
- Original `frontend/` and `backend/` directories remain intact for immediate rollback.

## v2 Upgrade Status
- Product specification: `DOC/context2-upgrade.md` (source of truth)
- Product policy: `docs/PRODUCT_POLICY.md` ✅
- Architecture decisions: `docs/DECISIONS.md` (ADR-001 through ADR-010 updated with AMD Ryzen 7 + 32GB RAM profile) ✅
- Render manifest schema: `docs/RENDER_MANIFEST_SCHEMA.json` ✅
- Master task list: `TASKS.md` ✅
- Monorepo structure (`apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `packages/python-core`, `infra`) ✅
- Mandatory Rights Declaration & Risk Label System (Section 2.2, 2.3) ✅
- Source Ingestion (yt-dlp + local file) & ffprobe extraction (`SourceAsset` DB table) ✅
- Faster-Whisper word-level transcription worker ✅
- PySceneDetect scene boundary detection worker ✅
- MediaPipe subject/face tracking service with center-crop fallback ✅
- Transformation Score Engine (0–100) across 5 pillars (Section 2.4) ✅
- Brief-Aware Candidate Selection with LLM Gateway & retry logic ✅
- Candidate ranking, scene snapping, and deduplication logic ✅
- Professional Render Engine (9:16 reframe, blurred background, loudnorm -14 LUFS) ✅
- ASS Subtitle Generator with 4 presets (Bold Karaoke, Minimal, Clean Subtitle, None) ✅
- Deterministic Render Manifest generation conforming to schema ✅
- Editorial Overlay Generator (Hook Cards, Lower Thirds, CTA End Cards) ✅
- Factual Claim & Sensitivity Detector ✅
- Pre-Export Rights Acknowledgement Modal & Transformation Warning Panel ✅
- Server-Sent Events (SSE) `/api/projects/{id}/events` & `/api/projects/{id}/audit-trail` ✅
- Test fixture set (3 synthetic MP4 files) & 30/30 passing tests ✅

## Phases
- **Phase 0 (Policy & Docs):** [x] Completed
- **Phase 1 (Foundation):** [x] Completed
- **Phase 2 (Ingestion & Analysis):** [x] Completed
- **Phase 3 (Brief-Aware Selection):** [x] Completed
- **Phase 4 (First Render):** [x] Completed
- **Phase 5 (Editorial Transformation):** [x] Completed
- **Phase 6 (Voiceover & Audio):** [ ] Next up
- **Phase 7 (Motion Effects):** [ ] Not started
- **Phase 8 (Clip Editor & Brand Kits):** [ ] Not started
- **Phase 9 (Testing & Reliability):** [ ] Not started
- **Phase 10 (Scale Readiness):** [ ] Not started
