# ClipForge AI — Master Task List

## Phase 0 — Product Policy and Documentation
- [x] Create `docs/PRODUCT_POLICY.md`.
- [x] Create `docs/DECISIONS.md`.
- [x] Create `docs/RENDER_MANIFEST_SCHEMA.json`.
- [x] Update `TASKS.md` with full v2 task list.

## Phase 1 — Foundation and Local Development
- [x] Initialize monorepo: `apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `packages/python-core`, `infra`.
- [x] Configure pnpm workspace and uv Python workspace.
- [x] Add Docker Compose: Postgres 16, Redis 7, MinIO, API, worker.
- [x] Configure Next.js + Tailwind + shadcn/ui (stable) + v2 design tokens.
- [x] Configure FastAPI, structured logging, `/health`, `/ready`.
- [x] Configure Alembic migrations.
- [x] Configure Celery named queues (ingest, analysis, llm, editorial, render, qa) and no-op worker test.
- [x] Add environment templates and repository tracking files.

## Phase 2 — Source Ingestion and Analysis
- [ ] Implement project creation with mandatory rights declaration (Section 2.2).
- [ ] Build source-risk label system (Section 2.3).
- [ ] Build yt-dlp ingestion adapter with URL validation and error states.
- [ ] Build local-file upload pipeline.
- [ ] Use ffprobe for source metadata extraction.
- [ ] Implement faster-whisper transcript worker with word-level timestamps.
- [ ] Add PySceneDetect scene-boundary worker.
- [ ] Add MediaPipe subject/face track analysis with center-crop fallback.
- [ ] Persist job events and stream status over SSE.
- [ ] Create fixture set of 3 authorized/open test media files.

## Phase 3 — Brief-Aware Candidate Selection
- [ ] Implement `LLMProvider` OpenAI-compatible adapter with Pydantic validation and retry.
- [ ] Create segment-window generator using transcript + scenes + speech/silence.
- [ ] Build selection prompt (score, reasons, exclusions, editorial angle).
- [ ] Return 2× candidate multiplier.
- [ ] Create Candidate Selection UI with transcript and manual in/out override.
- [ ] Add "No strong candidates" state with manual clipping option.

## Phase 4 — First Professional Render
- [ ] Implement FFmpeg cut/render service with deterministic render manifests.
- [ ] Implement 9:16 smart reframe using MediaPipe crop keyframes.
- [ ] Implement blurred-background vertical layout.
- [ ] Add caption generation and burn-in from word-level timings.
- [ ] Add caption presets: Bold Karaoke, Minimal, Clean Subtitle, None.
- [ ] Add render manifest creation and output QA.
- [ ] Build Review Gallery preview card and approve/reject flow.

## Phase 5 — Editorial Transformation Layer
- [ ] Add editorial-template configuration to project creation.
- [ ] Generate editable hook, narration draft, callout plan, closing takeaway per clip.
- [ ] Add factual-claim flagging; require manual script review before TTS render.
- [ ] Build hook card, lower-third, callout, attribution, CTA card renderer.
- [ ] Add optional reaction/PiP video layer with responsive layouts.
- [ ] Implement Transformation Readiness Score and action-oriented warning panel.
- [ ] Add pre-export acknowledgement dialog.

## Phase 6 — Voiceover and Audio Studio
- [ ] Implement TTS adapter interface and local Kokoro TTS integration.
- [ ] Add narration script editor, approval status, and local audio preview.
- [ ] Add uploaded narration file support.
- [ ] Implement audio modes: original only / voiceover only / mix.
- [ ] Implement original + narration sliders, ducking, loudness normalization.
- [ ] Add short audio preview endpoint and waveform/level UI.
- [ ] Add audio technical QA to render output.

## Phase 7 — Motion Effects v1
- [ ] Add effects configuration schema and Effects Panel UI.
- [ ] Implement zoom, shake, film grain, vignette, RGB split, VHS/noise, blur background, mosaic.
- [ ] Implement reusable transparent overlay asset handling.
- [ ] Implement generic user-branded floating CTA animation.
- [ ] Implement generic bouncing-logo artifact with safe-zone/face avoidance.
- [ ] Enforce effect limits and preview low-res draft before full render.
- [ ] Persist random seeds/keyframes in render manifests for deterministic re-renders.

## Phase 8 — Clip Editor and Brand Kits
- [ ] Build single Clip Editor: crop, captions, script, voiceover, audio, effects, overlay timing.
- [ ] Add duplicate variant / A-B version functionality.
- [ ] Build Brand Kit CRUD: logos, colors, CTA defaults, caption defaults.
- [ ] Add per-clip override vs project-default inheritance model.
- [ ] Add source attribution/rights note in export package.

## Phase 9 — Testing, Reliability, and Release
- [ ] Add idempotency keys for project analysis and render jobs.
- [ ] Add retries with exponential backoff, worker timeouts, stage-level rerun.
- [ ] Add test suite: unit (config/prompt schemas), integration (fixture pipeline), Playwright UI.
- [ ] Add observability dashboard/logging and error tracking.
- [ ] Add asset-retention cleanup job.
- [ ] Test exports in YouTube Shorts, Instagram Reels, TikTok uploaders manually.
- [ ] Publish in-product "Rights and Originality Checklist."

## Phase 10 — Scale Readiness
- [ ] Add hosted R2/S3 object storage adapter.
- [ ] Split worker pools by resource tier; enable autoscaling.
- [ ] Add GPU worker profile for faster-whisper/face analysis.
- [ ] Add team/workspace model and collaboration permissions.
- [ ] Add billing (post-validation only, with commercial-use policy).
- [ ] Evaluate Temporal only if Celery becomes an operational bottleneck.
