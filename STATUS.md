# Project Status

## Current State
- The backend API is functional with PostgreSQL and Redis.
- The pipeline (`download` -> `transcribe` -> `select` -> `crop` -> `caption`) is fully operational.
- The Next.js frontend has been styled with modern, dark-mode aesthetics (Tailwind, Framer Motion).
- Live settings for LLM proxy (OmniRoute/FreeLLMAPI) are hooked up.
- Automated and manual clip export capabilities have been added.
- **LLM integration fixed** — `stream: false` prevents SSE streaming error.
- **Caption quality fixed** — full sentence segments instead of word-by-word, with Devanagari font support.
- **Re-clip feature added** — generate more clips from existing videos without re-downloading or re-transcribing.

## Phases
- **Phase 1 (Foundation):** [x] Completed
- **Phase 2 (Backend Orchestration):** [x] Completed
- **Phase 3 (AI Video Pipeline):** [x] Completed
- **Phase 4 (Frontend UI):** [x] Completed
- **Phase 5 (Polish):** [x] Completed
- **Phase 6 (Launch):** [x] Completed (Added Export capabilities and DEPLOYMENT.md)
- **Phase 7 (Post-Launch Fixes & Features):** [x] Completed

## Recent Changes (Session 3)
- Implemented automated thumbnail generation during the pipeline (crop step extracts thumbnail).
- Added `POST /api/clips/{id}/thumbnail` endpoint to regenerate a clip's thumbnail.
- Upgraded the UI dashboard to render actual clip thumbnails instead of generic icons.
- Added graceful fallbacks and warning banners to the frontend when the LLM connection fails.
- Hardened `yt-dlp` download configuration to gracefully manage tricky video formats.
- Added comprehensive "Delete Project" flow in UI + cascading deletion in DB and File System.
- Fixed `POST /api/projects/{id}/export` endpoint by resolving the file paths dynamically via `settings.MEDIA_DIR`.
- Ran full backend API smoke test and frontend build QA (100% stable).

## Celery Worker Command (must include --include flag)
`uv run celery -A app.celery_app worker -Q default,download,transcribe,select,crop,caption -c 2 -P solo --loglevel=info --include=app.services.pipeline`
