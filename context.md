# ClipForge AI — Build Documentation Pack
*Following the Vibe Coding Template Pack structure (PRD → TRD → App Flow → UI/UX Brief → Backend Schema → Implementation Plan)*

---

# 01. Product Requirements Document (PRD)

## 1. Overview
- **Product name:** ClipForge AI
- **One-liner:** A self-hosted, AI-powered tool that turns any YouTube video or local video folder into ready-to-post, caption-burned vertical clips, scored and selected against custom campaign guidelines — for free, using local/free LLM inference.
- **Author:** Ravi Saxena
- **Last updated:** 2026-08-31

## 2. Problem
Today, creators doing paid clipping work (e.g., Whop Content Rewards campaigns) manually watch long-form videos, find highlight moments, cut clips, reframe to vertical, and add captions — a slow, repetitive process. Existing commercial tools (OpusClip, Submagic, Riverside) charge per-clip/monthly fees and don't let users tailor clip selection to a specific brand campaign's exact content guidelines. There's no free, controllable, self-hosted alternative that does all of this end-to-end.

## 3. Target user
- **Primary:** Independent clippers/creators (starting with the builder himself) doing Whop/brand clipping campaigns, who need volume output matched to specific campaign briefs, with zero per-clip cost.
- **Secondary:** Small clipping agencies wanting to run this across multiple team members and multiple simultaneous campaigns.

## 4. Goals (v1)
- G1. Accept a YouTube URL **or** a local folder path as input.
- G2. Let the user specify: number of shorts to generate, min/max clip length, target aspect ratio, caption style.
- G3. Score and select highlight segments against a user-supplied **campaign brief** (text/JSON: tone, required mentions, banned topics, brand rules).
- G4. Auto-crop to vertical with speaker/face tracking, and burn in animated captions.
- G5. Run entirely on free/local LLM inference (OmniRoute/FreeLLMAPI, OpenAI-compatible).
- G6. Present a review gallery where the user approves/rejects/re-generates clips before export.

## 5. Non-goals (v1)
- We will NOT build automatic posting/scheduling to social platforms in v1 (manual download + post).
- We will NOT support live-stream/real-time clipping in v1.
- We will NOT build multi-tenant billing/payments in v1 (single-user or small-team use only).
- We will NOT support 3D/AI-generated animation content (separate product track, deferred).

## 6. Core user stories
- US1. As a clipper, I want to paste a YouTube link and get N vertical clips back, so that I don't have to manually cut and caption footage.
- US2. As a clipper, I want to upload a campaign brief once, so that every clip generated for that campaign matches the brand's tone and rules automatically.
- US3. As a clipper, I want to set exact clip count and length range before running a job, so that output matches what a specific Whop campaign requires.
- US4. As a clipper, I want to preview and reject bad clips before exporting, so that I only post clips likely to get approved.
- US5. As a clipper, I want to point the tool at my own local LLM/inference gateway, so that I never pay per-clip AI costs.

## 7. Success metrics
- M1. Time from "paste link" to "N reviewable clips ready" (target: under 10 minutes for a 30-minute source video).
- M2. % of auto-selected clips the user approves without manual re-cut (target: 60%+ by v1.1).
- M3. $0 recurring inference cost per job (target: 100% jobs routed through free LLM tiers).

## 8. Risks & assumptions
- Assumption: Free/local LLM tiers have sufficient reasoning quality for highlight-selection tasks.
- Risk: Free LLM rate limits throttle throughput during bulk runs (mitigation: OmniRoute/FreeLLMAPI auto-fallback across providers).
- Risk: Face-tracking/crop quality varies by source video type (mitigation: manual crop override in review step).
- Assumption: yt-dlp continues to reliably support YouTube downloads (external dependency risk).

---

# 02. Technical Requirements Document (TRD)

## 1. Stack
- **Frontend:** Next.js 15, React, TypeScript, Tailwind CSS, shadcn/ui
- **Backend/API:** FastAPI (Python 3.12)
- **Job queue:** Redis + Celery (separate queues per task type)
- **Database:** Postgres via Supabase
- **Auth:** Supabase Auth (email + Google)
- **Object storage:** Cloudflare R2 (S3-compatible)
- **Hosting:** Railway or Fly.io (Docker containers for API + each worker pool)
- **AI/LLM:** OmniRoute or FreeLLMAPI (local OpenAI-compatible gateway) — no paid API required
- **Payments:** None in v1 (deferred)

## 2. Architecture
**Pattern:** Queue-based worker pool (producer/consumer), not a monolith.

```
Next.js Frontend
      │
      ▼
FastAPI API (job creation, status polling, review actions)
      │
      ▼
Redis (Celery broker)
      │
   ┌──┴────────────┬───────────────┬──────────────┬───────────────┐
   ▼                ▼               ▼              ▼               ▼
Download Worker  Transcribe      Select Worker   Crop/Encode    Caption Worker
(yt-dlp)         Worker          (LLM via         Worker         (captacity)
                 (faster-        OmniRoute/       (ClipsAI +
                 whisper)        FreeLLMAPI)      ffmpeg)
      │                │               │               │               │
      └────────────────┴───────────────┴───────────────┴───────────────┘
                                   │
                                   ▼
                        Cloudflare R2 (source + output files)
                                   │
                                   ▼
                        Postgres (job/clip metadata, status)
```

Each worker type has its own Celery queue and independent concurrency setting (e.g., download=6 concurrent, transcribe=2, select=3 rate-limited to LLM provider limits, crop/encode=2 CPU-bound, caption=2).

## 3. Non-functional requirements
- Performance: a 20-minute source video → first reviewable clip in under 5 minutes; full batch (10 clips) under 15 minutes on CPU-only hardware.
- Uptime: best-effort (single-user/small-team tool, not SLA-bound in v1).
- Security: all campaign briefs and source files stored per-user with row-level security in Postgres; no public bucket access to R2.
- Accessibility: WCAG 2.1 AA on the review/dashboard UI.

## 4. Third-party services
| Service | Purpose | Pricing tier | Fallback |
|---|---|---|---|
| OmniRoute / FreeLLMAPI | LLM inference for clip selection | Free (self-hosted gateway) | Switch pooled provider automatically; manual model pin if needed |
| yt-dlp | YouTube video download | Free, open-source | None needed (actively maintained) |
| Cloudflare R2 | Video file storage | Free tier (10GB), then usage-based | Local disk storage fallback for single-machine use |
| Supabase | Auth + Postgres | Free tier | Self-hosted Postgres if scale requires |

## 5. Constraints
- Budget: $0–$20/month max for infra in v1 (Railway/Fly.io free-to-hobby tier + R2 free tier).
- Skills: comfortable with prompt-driven/AI-assisted build (Antigravity); minimal manual coding.
- Deadline: MVP (single campaign, single video, manual review) targeted within 2 weeks of active building.

## 6. Open questions
- Q1. GPU vs CPU for Whisper at scale — defer decision until job volume data exists (owner: Ravi, due: post-MVP).
- Q2. Whether to add auto-posting to social platforms in v1.1 (owner: Ravi, due: after MVP validation).

---

# 03. App Flow

## Screen inventory
| # | Screen | Auth? | Purpose |
|---|---|---|---|
| 1 | Landing/Login | No | Sign in via Supabase Auth |
| 2 | Dashboard | Yes | List of past projects/jobs, "New Project" CTA |
| 3 | New Project | Yes | Input source (YouTube URL or local folder path), campaign brief, clip settings |
| 4 | Job Status | Yes | Live progress per pipeline stage (download → transcribe → select → crop → caption) |
| 5 | Clip Review Gallery | Yes | Grid of generated clips with approve/reject/regenerate per clip |
| 6 | Campaign Briefs | Yes | Create/edit/save reusable campaign guideline templates |
| 7 | Settings | Yes | LLM gateway URL/key, storage config, default clip settings |

## States per screen
Every screen defines: empty, loading, success, error.
- **New Project**: error state must clearly surface invalid YouTube URLs and missing/invalid campaign briefs before job submission.
- **Job Status**: must show per-stage failure (e.g., "Download failed — video unavailable") distinctly from full-job failure.
- **Clip Review Gallery**: empty state = "No clips passed selection — try loosening campaign brief constraints."

## New Project — required input fields (this directly answers "how many shorts, size, etc.")
- Source type: [ YouTube URL ] or [ Local folder path ]
- Number of shorts to generate: numeric input (e.g., 5)
- Clip length range: min/max seconds (e.g., 20–60s)
- Aspect ratio: 9:16 / 1:1 / 16:9
- Caption style: preset dropdown (e.g., "Bold Karaoke", "Minimal", "None")
- Campaign brief: select saved brief OR paste new one
- LLM provider override (optional): default = OmniRoute/FreeLLMAPI auto

## Happy path
Login → Dashboard → New Project (fill settings) → Job Status (watch progress) → Clip Review Gallery (approve clips) → Download approved clips.

## Critical edge cases
- EC1. Invalid/private YouTube URL → inline error before job starts, no wasted queue slot.
- EC2. LLM provider rate-limited mid-job → job auto-retries via OmniRoute fallback; UI shows "Retrying with alternate provider," not a hard failure.
- EC3. Requested clip count exceeds available highlight segments in source video → UI returns fewer clips with a note, not an error.

---

# 04. UI/UX Brief

## Brand vibe
Three adjectives: **professional, efficient, dark-mode-native** (matching the reference tool screenshots you shared — dark background SaaS dashboard aesthetic).
Inspiration apps: OpusClip, Whop dashboard, Linear.

## Colour tokens
- primary: #6366F1 (indigo)
- secondary: #1E1E24
- accent: #F97316
- success: #22C55E
- warn: #F59E0B
- error: #EF4444
- bg: #0B0B0F
- text: #F5F5F7
- muted: #9CA3AF

## Type scale
- Font family: Inter
- h1: 32px / 700 · h2: 24px / 600 · body: 15px / 400 · small: 13px / 400

## Spacing & radius
- Spacing unit: 4px
- Radius: sm 6px · md 10px · lg 16px

## Components
- Library: shadcn/ui
- Required: Button, Input, Card, Dialog, Toast, ProgressBar (per pipeline stage), VideoThumbnailCard, EmptyState, Skeleton, ErrorBoundary

## Voice & tone
- Microcopy style: direct, minimal, technical — "Job queued." not "Yay, we're on it!"
- Error tone: precise and actionable — "Download failed: video is private or region-locked."

## Accessibility floor
- Contrast: 4.5:1 minimum for body text on dark backgrounds
- All interactive elements keyboard-reachable, visible focus rings
- Progress and status changes announced via ARIA live regions (important for long-running job status)

---

# 05. Backend Schema

## Entities

### users
- id uuid pk
- email text unique not null
- created_at timestamptz default now()

### campaign_briefs
- id uuid pk
- owner_id uuid fk -> users.id
- name text not null
- brief_json jsonb -- tone, required mentions, banned topics, brand rules
- created_at timestamptz default now()

### projects
- id uuid pk
- owner_id uuid fk -> users.id
- source_type text -- 'youtube_url' | 'local_folder'
- source_value text
- campaign_brief_id uuid fk -> campaign_briefs.id
- clip_count int not null
- min_length_sec int not null
- max_length_sec int not null
- aspect_ratio text -- '9:16' | '1:1' | '16:9'
- caption_style text
- status text -- 'queued' | 'downloading' | 'transcribing' | 'selecting' | 'encoding' | 'captioning' | 'done' | 'failed'
- created_at timestamptz default now()

### clips
- id uuid pk
- project_id uuid fk -> projects.id
- start_sec float
- end_sec float
- score float -- LLM-assigned relevance score vs brief
- file_url text -- R2 storage path
- review_status text -- 'pending' | 'approved' | 'rejected'
- created_at timestamptz default now()

### jobs (Celery task tracking)
- id uuid pk
- project_id uuid fk -> projects.id
- stage text -- 'download' | 'transcribe' | 'select' | 'crop' | 'caption'
- status text -- 'pending' | 'running' | 'success' | 'failed' | 'retrying'
- error_message text
- updated_at timestamptz

## Indexes
- projects(owner_id, created_at desc)
- clips(project_id, review_status)
- jobs(project_id, stage)

## Row-level security
- projects: read/write if owner_id = auth.uid()
- clips: read/write if EXISTS project WHERE project.id = clips.project_id AND owner_id = auth.uid()
- campaign_briefs: read/write if owner_id = auth.uid()

## API endpoints
- POST /api/projects → create project + enqueue pipeline
- GET /api/projects/:id → read status + stage progress
- GET /api/projects/:id/clips → list generated clips
- PATCH /api/clips/:id → approve/reject/regenerate a clip
- POST /api/campaign-briefs → create reusable brief
- GET /api/campaign-briefs → list saved briefs

## Storage
- Bucket: clipforge-media
- Path: {user_id}/{project_id}/source.mp4 and {user_id}/{project_id}/clips/{clip_id}.mp4
- Limit: no hard cap in v1 (self-hosted); monitor R2 usage against free tier

---

# 06. Implementation Plan

## Phase 1 — Project setup (Day 1–2)
- [ ] Initialise Next.js frontend + FastAPI backend repos
- [ ] Set up Supabase project (auth + Postgres, run schema migrations)
- [ ] Set up Redis + Celery locally
- [ ] Configure OmniRoute/FreeLLMAPI connection from FastAPI

## Phase 2 — Core pipeline, no UI (Day 3–6)
- [ ] Download worker: yt-dlp wrapper (URL) + local folder ingestion
- [ ] Transcribe worker: faster-whisper integration
- [ ] Select worker: LLM prompt template that takes transcript + campaign brief JSON, returns ranked segments
- [ ] Crop/encode worker: ClipsAI integration for vertical reframe
- [ ] Caption worker: captacity integration for burned-in captions
- [ ] End-to-end CLI test: one YouTube URL in, N captioned vertical clips out

## Phase 3 — API + job orchestration (Day 7–9)
- [ ] Build FastAPI endpoints (projects, clips, campaign-briefs)
- [ ] Wire Celery task chain per pipeline stage with status updates to Postgres
- [ ] Implement retry/fallback logic for LLM provider rate limits

## Phase 4 — Frontend (Day 10–14)
- [ ] Build Login/Dashboard screens
- [ ] Build New Project screen (source input, clip count/length/aspect/caption settings, brief selector)
- [ ] Build Job Status screen with live per-stage progress
- [ ] Build Clip Review Gallery (approve/reject/regenerate)
- [ ] Build Campaign Briefs CRUD screen

## Phase 5 — Polish & validation (Day 15–17)
- [ ] Run real end-to-end test against one live Whop campaign
- [ ] Tune LLM selection prompt based on real approval/rejection rates
- [ ] Add empty/loading/error states across all screens
- [ ] Accessibility pass

## Phase 6 — Launch (personal use) (Day 18)
- [ ] Deploy API + workers to Railway/Fly.io
- [ ] Deploy frontend
- [ ] Smoke test full pipeline in production
- [ ] Start using for real campaigns; track M1–M3 metrics from PRD
