# Project Progress

## Session 4 — v2 Upgrade Kickoff (2026-09-01)

### Completed
1. Read and analyzed full v2 product specification (`DOC/context2-upgrade.md`, 1139 lines).
2. Produced gap analysis comparing v1 codebase to v2 requirements.
3. Created implementation plan covering 10 phases with exact task breakdowns.
4. Received and locked in founder decisions on all open questions.
5. Initialized git repo, committed v1 baseline to `master`.
6. Created `feature/clipforge-v2-foundation` branch.
7. **Phase 0 complete:**
   - `docs/PRODUCT_POLICY.md` — Non-negotiable product boundaries (rights, transformation, export).
   - `docs/DECISIONS.md` — 10 Architecture Decision Records (stack, monorepo, migration, mode, TTS, orchestration, hardware, brand, UI, publishing).
   - `docs/RENDER_MANIFEST_SCHEMA.json` — Full JSON Schema for deterministic render manifests (source, output, crop, captions, audio, effects, editorial, metadata).
   - `TASKS.md` — Complete v2 master task list across all 10 phases.
8. **Phase 1, Task 1 (Initialize Monorepo) complete:**
   - Created monorepo structure: `apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `packages/python-core`, `infra`.
   - Created root `pnpm-workspace.yaml`, root `package.json`, and root `pyproject.toml` (uv workspace).
   - Migrated frontend into `apps/web` (`@clipforge/web`) and verified Next.js 16 build passing with zero errors.
   - Migrated shared Python models, database, services, and workers into `packages/python-core` (`clipforge-core`).
   - Created thin service shells in `apps/api` (`clipforge-api`) and `apps/worker` (`clipforge-worker`) referencing shared `clipforge-core`.
   - Verified Python imports and Celery task registration (all 9 tasks detected).
   - Created `infra/docker-compose.yml` with Postgres 16, Redis 7, and MinIO S3-compatible storage.
   - Kept original `frontend/` and `backend/` completely untouched for safe rollback.
9. **Phase 1 (Foundation and Local Development) — 100% COMPLETE:**
   - **Task 1.1 (Monorepo Layout):** Initialized `apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `packages/python-core`, and `infra`.
   - **Task 1.2 (Workspaces):** Configured `pnpm-workspace.yaml`, root `package.json`, and root `pyproject.toml` (uv workspace).
   - **Task 1.3 (Docker Compose):** Built multi-stage Dockerfiles (`apps/api/Dockerfile`, `apps/worker/Dockerfile`, `apps/web/Dockerfile`) and unified `infra/docker-compose.yml` with Postgres 16, Redis 7, MinIO, API, and Worker.
   - **Task 1.4 (Design Tokens):** Implemented dark-studio design tokens in `globals.css` per Section 6.3 (`--surface`, `--surface-raised`, `--primary-hover`, etc.).
   - **Task 1.5 (API & Observability):** Configured structured logging, request duration tracking middleware, `/health` and `/ready` probes with passing pytest test suite.
   - **Task 1.6 (Alembic):** Configured async Alembic migration runner (`alembic.ini`, `env.py`, initial revision `001_initial.py`) with verified static SQL generation.
   - **Task 1.7 (Worker Queues):** Configured 6 v2 named Celery queues (`ingest`, `analysis`, `llm`, `editorial`, `render`, `qa`) plus no-op verification task with passing unit tests.
   - **Task 1.8 (Tracking & Templates):** Created complete `.env.example` templates, `start-v2.bat`, and rewritten `DEPLOYMENT.md`.

10. **Phase 2 (Source Ingestion and Analysis) — 100% COMPLETE:**
    - **Rights & Policy Engine (Tasks 2.1 & 2.2):** Implemented mandatory rights declaration model (`owned`, `written_permission`, `authorized_campaign`, `commentary_review`, `other_unconfirmed`), automated workflow risk classification (`lower_workflow_risk`, `needs_review`, `unknown`), and immutable `ProjectAuditEvent` recording.
    - **Frontend Studio UI:** Built rights declaration picker, source risk badges, and 6 editorial template options (`explainer`, `commentary`, `news_context`, `reaction_pip`, `quote_breakdown`, `campaign_promo`) in `NewProjectPage`.
    - **Technical Probe & Ingestion (Tasks 2.3, 2.4, 2.5):** Built `media_probe.py` using `ffprobe` for frame-accurate metadata (duration, width, height, fps, codecs, bitrate, channels) and persisted into `SourceAsset` DB table. Enhanced `yt-dlp` adapter and local file ingestion.
    - **Analysis Workers (Tasks 2.6, 2.7, 2.8):**
      - Faster-Whisper with word-level timestamps and VAD voice activity detection.
      - PySceneDetect 0.7.1 scene cut boundary extractor.
      - MediaPipe face & speaker tracking with exponential coordinate smoothing and center-crop fallback.
      - Unified `run_analysis` worker emitting consolidated `analysis.json` and audit logs.
    - **Real-Time Streaming & Audit Trail (Task 2.9):** Added SSE endpoint `GET /api/projects/{id}/events` and audit trail endpoint `GET /api/projects/{id}/audit-trail`.
    - **Fixtures & QA Suite (Task 2.10):** Synthesized 3 test media fixtures and verified 15/15 unit tests passing.

11. **Phase 3 (Brief-Aware Candidate Selection) — 100% COMPLETE:**
    - **Transformation Score Engine (Task 3.3):** Built `transformation_scorer.py` computing 0–100 score across 5 pillars (`source_exclusivity`, `commentary_depth`, `visual_alteration`, `narrative_structure`, `editorial_callouts`) and risk bands (`high`, `moderate`, `low`).
    - **Candidate Ranking & Scene Snapping (Task 3.5):** Built `candidate_ranker.py` to snap candidate boundaries to nearest scene cuts, eliminate mid-sentence glitches, and deduplicate overlapping segments by composite rank.
    - **LLM Candidate Worker (Tasks 3.1, 3.2, 3.4):** Enhanced `select.py` worker on `llm` queue with structured prompt (transcript + scene boundaries + editorial template + campaign brief + rights basis), saving `selections.json` and populating DB `Clip` records with transformation score breakdowns.
    - **Studio UI Integration:** Added Transformation Score badges and virality pills to `ClipCard` in `apps/web`.
    - **Unit Tests (Task 3.6):** Created tests for transformation scorer, candidate ranker, and mocked LLM selection (21/21 passing).

12. **Phase 4 (First Professional Render & Manifest Generation) — 100% COMPLETE:**
    - **ASS Subtitle Renderer (Tasks 4.4 & 4.5):** Created `caption_renderer.py` supporting 4 presets (`bold_karaoke` with word-by-word `{\k}` highlight, `minimal`, `clean_subtitle`, `none`) with precise timestamp offset calculation.
    - **FFmpeg Render Engine (Tasks 4.1, 4.2, 4.3):** Built `render_engine.py` with 9:16 smart reframing, blurred-background layout for landscape source inputs, ASS subtitle burn-in, loudnorm audio mastering (-14.0 LUFS), and thumbnail generation.
    - **Deterministic Render Manifests (Task 4.6):** Built `build_render_manifest` emitting draft-07 JSON manifests conforming to `RENDER_MANIFEST_SCHEMA.json` and saved with every rendered clip.
    - **End-to-End Pipeline Orchestration (Task 4.7):** Linked Ingest -> Analysis -> Select -> Render in `pipeline.py` and Celery worker.
    - **Unit Tests:** Created tests for caption generator and deterministic render engine on synthetic fixtures (25/25 tests passing).

## Next Milestone: Phase 5 — Editorial Transformation Layer
- Add editorial-template configuration to project creation.
- Generate editable hook, narration draft, callout plan, closing takeaway per clip.
- Add factual-claim flagging; require manual script review before TTS render.
- Build hook card, lower-third, callout, attribution, CTA card renderer.
- Add optional reaction/PiP video layer with responsive layouts.
- Implement Transformation Readiness Score and action-oriented warning panel.
- Add pre-export acknowledgement dialog.
