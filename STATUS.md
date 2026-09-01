# Project Status

## Current State
- **Branch:** `feature/clipforge-v2-foundation`
- **Phase 0 (Product Policy & Documentation):** ✅ Complete
- **Phase 1 (Foundation and Local Development):** ✅ 100% Complete
- **Phase 2 (Source Ingestion and Analysis):** ✅ 100% Complete
- **Next Milestone:** Phase 3 (Brief-Aware Candidate Selection & Transformation Scoring)

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
- Server-Sent Events (SSE) `/api/projects/{id}/events` & `/api/projects/{id}/audit-trail` ✅
- Test fixture set (3 synthetic MP4 files) & 15/15 passing tests ✅

## Phases
- **Phase 0 (Policy & Docs):** [x] Completed
- **Phase 1 (Foundation):** [x] Completed
- **Phase 2 (Ingestion & Analysis):** [x] Completed
- **Phase 3 (Brief-Aware Selection):** [ ] Next up
- **Phase 3 (Brief-Aware Selection):** [ ] Not started
- **Phase 4 (First Render):** [ ] Not started
- **Phase 5 (Editorial Transformation):** [ ] Not started
- **Phase 6 (Voiceover & Audio):** [ ] Not started
- **Phase 7 (Motion Effects):** [ ] Not started
- **Phase 8 (Clip Editor & Brand Kits):** [ ] Not started
- **Phase 9 (Testing & Reliability):** [ ] Not started
- **Phase 10 (Scale Readiness):** [ ] Not started
