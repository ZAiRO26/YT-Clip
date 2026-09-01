# ClipForge AI — Architecture Decisions Record

> This document records stack choices, deferred decisions, and founder directives.
> Each entry is immutable once recorded. New decisions are appended, not edited.

---

## ADR-001: Stack Selection

**Date:** 2026-09-01
**Status:** Accepted
**Spec ref:** context2-upgrade.md Section 3.1

| Layer | Decision | Rationale |
|---|---|---|
| Web app | Next.js 15/16 + TypeScript + App Router | Fast product UI, strong type safety |
| UI | Tailwind CSS + shadcn/ui (stable) + Radix primitives | High-quality accessible components |
| API | FastAPI + Python 3.12+ | Best ecosystem for video/ML/workers |
| Background jobs | Celery + Redis | Worker isolation, retries, named queues |
| Database | Supabase Postgres + SQLAlchemy + Alembic | Relational metadata, RLS, proven ergonomics |
| Object storage | Local filesystem (dev); R2/S3 adapter (hosted, post-validation) | Local-first cheap MVP |
| Video engine | FFmpeg / ffprobe | Industry-standard codec toolchain |
| Transcript | faster-whisper + optional WhisperX | Fast local transcription |
| Face/person tracking | MediaPipe + OpenCV | Auto-reframe without paid services |
| Scene detection | PySceneDetect | Cut-aware clip boundaries |
| LLM gateway | OpenAI-compatible adapter (OmniRoute / FreeLLMAPI) | Provider-agnostic, free/local |
| TTS | Kokoro local TTS (Apache-2.0) | Lightweight local narration |
| Rendering | FFmpeg filtergraphs + deterministic render manifests | Reproducible, debuggable outputs |
| Package mgmt (Node) | pnpm workspaces | Efficient monorepo management |
| Package mgmt (Python) | uv | Fast, lockfile-based dependency resolution |

---

## ADR-002: Monorepo Structure

**Date:** 2026-09-01
**Status:** Accepted
**Spec ref:** context2-upgrade.md Section 8 Phase 1

### Structure

```
apps/web/          — Next.js frontend
apps/api/          — FastAPI HTTP server
apps/worker/       — Celery worker process
packages/contracts/       — Shared TypeScript types
packages/python-core/     — Shared Python business logic (clipforge_core/)
infra/             — Docker Compose, env templates, scripts
docs/              — Product policy, decisions, schemas
```

### Founder directive

Shared Python logic (config, database, models, services, pipeline) lives in
`packages/python-core/clipforge_core/` and is imported by both `apps/api` and
`apps/worker`. No duplication of business logic between API and worker packages.

---

## ADR-003: Migration Strategy

**Date:** 2026-09-01
**Status:** Accepted

- Work on branch `feature/clipforge-v2-foundation`.
- `master` remains a runnable, QA-verified v1 rollback point.
- Incremental migration: create v2 structure first, copy existing code, update
  imports, verify, then remove duplicates.
- Do not delete old `frontend/` or `backend/` folders in the first migration task.

---

## ADR-004: Product Mode

**Date:** 2026-09-01
**Status:** Accepted

Build local-first as a browser-based web application using Docker Compose.
Not a native desktop application. Cloud deployment comes after end-to-end
local pipeline validation.

---

## ADR-005: Voice Cloning

**Date:** 2026-09-01
**Status:** Deferred indefinitely
**Spec ref:** context2-upgrade.md Section 3.6

Voice cloning is not enabled in v1/v2. Requires a verified-consent flow before
consideration. The product will not offer "sound like [person]" presets.

---

## ADR-006: Workflow Orchestration

**Date:** 2026-09-01
**Status:** Accepted — Celery for MVP
**Spec ref:** context2-upgrade.md Section 3.1

Use Celery chains/chords for MVP workflow orchestration. Evaluate Temporal only
after multi-tenant scale becomes a real operational bottleneck.

---

## ADR-007: Hardware Requirements & Optimization Profile

**Date:** 2026-09-01
**Status:** Accepted — Configured for AMD Ryzen 7 + 32GB RAM + AMD GPU

### Hardware Profile
- **Device:** MSI Alpha 15 A3DD (Windows 11 64-bit)
- **CPU:** AMD Ryzen 7 3750H (4 cores / 8 threads @ 2.30 GHz)
- **RAM:** 32.0 GB (High memory headroom for parallel worker queues)
- **GPU:** AMD Radeon (6 GB VRAM, multiple GPUs)
- **Storage:** Local NVMe SSD

### Architecture Decisions for this Profile
1. **Transcription (`faster-whisper`):** Run on CPU using `int8` quantization and 4 compute threads. CTranslate2 CPU engine is highly optimized for AMD Ryzen AVX2 instruction sets.
2. **Face/Subject Tracking (`MediaPipe`):** Run on CPU using OpenCV / MediaPipe Lite/Full models.
3. **Local TTS (`Kokoro`):** Run on CPU via ONNX Runtime / Torch CPU.
4. **Storage Retention:** Implement automatic local cleanup for raw downloads and temporary cut files after project render.

---

## ADR-008: Brand Name

**Date:** 2026-09-01
**Status:** Accepted

Keep "ClipForge AI" as the working product name.
Do not invest in final branding assets until Phase 4 rendering milestone.

---

## ADR-009: UI Component Library

**Date:** 2026-09-01
**Status:** Accepted

Use current stable shadcn/ui CLI/release, not canary/v2.

---

## ADR-010: Auto-Publishing

**Date:** 2026-09-01
**Status:** Rejected
**Spec ref:** context2-upgrade.md Section 1.5

ClipForge will not auto-upload or auto-post to YouTube, TikTok, Instagram,
or any other platform. All publishing is manual and user-initiated.
