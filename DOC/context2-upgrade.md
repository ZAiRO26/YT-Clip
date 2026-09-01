# ClipForge AI — Product Specification v2
## Transformative, Rights-Aware AI Clipping Pipeline

**Owner:** Ravi Saxena  
**Version:** 2.0  
**Status:** Build specification for Google Antigravity  
**Last updated:** 2026-09-01  

> **Purpose:** This document upgrades ClipForge AI from a basic auto-clipping pipeline into a professional, rights-aware, review-first production system. It helps creators produce materially transformed clips through original commentary, narration, structured editing, dynamic graphics, captions, and visual treatments.
>
> **Important policy boundary:** No software can guarantee YouTube Partner Program acceptance, prevent copyright claims, or make unlicensed footage legal. ClipForge must never promise “monetization without issues.” It must help users make better, more original, better-documented decisions; final rights clearance, publishing, and platform-policy compliance remain the user’s responsibility.

---

# 1. Product Requirements Document

## 1.1 Overview

**Product name:** ClipForge AI  
**One-liner:** A local-first, AI-assisted video clipping studio that turns authorized long-form source video into reviewable, vertical social clips with campaign-aware segment selection, original narrative overlays, captions, voiceover, audio mixing, and reusable motion-effect presets.

## 1.2 Problem

Clippers and small creator teams can quickly cut content, but getting clips accepted by campaign owners and potentially eligible for monetization requires more than a raw crop plus captions. Users need a workflow that:

- Uses content they are allowed to use.
- Converts campaign briefs into practical edit constraints.
- Adds meaningful original contribution: contextual narration, analysis, an editorial framing, visual structure, and original motion design.
- Produces consistently formatted Shorts/Reels/TikToks without requiring a professional editor for every output.
- Preserves a human review and publishing decision before content goes live.

Commercial clipping tools are optimized for generic virality and batch automation. ClipForge differentiates by combining configurable production controls with a **Transformation & Rights Checklist** per project and per clip.

## 1.3 Target users

**Primary user — Solo clipper:** Uses creator-authorized footage or campaign-provided assets, needs 3–20 polished vertical clips from a source video, and posts manually to Shorts/Reels/TikTok.

**Secondary user — Creator/podcast team:** Owns the source footage and needs a repeatable, brand-consistent clipping workflow for their own channel.

**Tertiary user — Small clipping agency:** Manages multiple campaigns/clients, needs reusable brand presets, approval trails, and team-ready output packages.

## 1.4 Product goals

- **G1 — Flexible ingestion:** Accept a YouTube URL, local media file, or local folder of source video files.
- **G2 — Production controls:** Before a job starts, users choose clip count, length range, platform, aspect ratio, quality, caption preset, brand preset, effects, and audio/voiceover mode.
- **G3 — Brief-aware discovery:** Rank candidate clips against a campaign brief and return machine-readable reasons, exclusions, and a relevance score.
- **G4 — Transformative editing:** Provide original narration, structured editorial templates, captions, callouts, B-roll/visual layers, motion effects, and optional creator reaction/picture-in-picture tracks.
- **G5 — Rights-aware workflow:** Require the user to state their source-rights basis and surface high-risk source warnings; record this in project metadata.
- **G6 — Review before export:** Put all outputs through a review gallery with editability, compliance checks, and manual approval before download/export.
- **G7 — Local/free inference:** Support OpenAI-compatible LLMs through existing OmniRoute and FreeLLMAPI configuration, plus local TTS where possible.
- **G8 — Reliable output:** Render 1080×1920 MP4/H.264/AAC outputs suitable for standard vertical video platforms.

## 1.5 Non-goals (v1)

- ClipForge will not auto-upload or auto-post to YouTube, TikTok, Instagram, or Whop.
- ClipForge will not scrape, bypass DRM, download private/paywalled content, or bypass platform access controls.
- ClipForge will not claim that filters/effects alone satisfy YouTube reused-content policy.
- ClipForge will not generate or facilitate imitation/voice-cloning of a real person without verified rights and explicit consent.
- ClipForge will not offer legal advice, copyright clearance, or guaranteed YPP approval.
- ClipForge will not target movie, TV, anime, sports-broadcast, music-video, or other high-claim-risk source libraries as a clipping workflow.

## 1.6 User stories

- **US1:** As a creator, I want to paste an authorized YouTube URL or upload a source video so that I can process it without manual file preparation.
- **US2:** As a campaign clipper, I want to save a campaign brief and use it in a project so clip suggestions follow brand tone, required talking points, forbidden topics, and duration rules.
- **US3:** As a creator, I want to choose exactly how many clips, their duration, platform format, caption style, and quality so the outputs match my publishing plan.
- **US4:** As a creator, I want to generate an original hook, contextual voiceover, and on-screen commentary for each suggested clip so I can create an editorially transformed output rather than a raw repost.
- **US5:** As a creator, I want control over original audio and voiceover levels so I can use original-only, narration-only, or mixed audio.
- **US6:** As a creator, I want optional motion graphics and visual effects per project and per clip so I can achieve a recognizable, customized editing style.
- **US7:** As a creator, I want a clip-level checklist warning me when my output lacks commentary or has high rights/reuse risk so I can make an informed review decision before exporting.
- **US8:** As a creator, I want the tool to preserve an audit trail of my source, claimed rights basis, brief, edits, and export history so I can organize campaign proof and internal compliance records.

## 1.7 Success metrics

- **Activation:** User produces and approves at least one clip in their first project.
- **Pipeline reliability:** 95% of valid jobs complete without a worker crash or manual database repair.
- **Review quality:** At least 60% of automatically selected candidates are approved or lightly edited by the user after prompt tuning.
- **Transformation adoption:** At least 75% of exported clips include at least one meaningful editorial contribution: user-supplied commentary, generated explanatory narration reviewed by the user, reaction track, original framing, or substantive visual storytelling.
- **Time-to-output:** 10 candidate clips from a 30-minute source video complete within 20 minutes in a baseline CPU environment; faster with optional GPU workers.
- **Cost:** LLM-based selection and draft-copy generation use configured free/local inference by default.

## 1.8 Risks and mitigations

| Risk | Why it matters | Product mitigation |
|---|---|---|
| Reused-content/YPP rejection | Permission is not automatically equivalent to YPP eligibility | Transformation checklist, editorial templates, warning labels, manual review; no promise of monetization |
| Copyright claims/strikes | Rights-holders can claim/block/takedown reused footage | Rights-basis declaration, source-risk labels, no “safe to use” claim, export warnings, audit log |
| Mass-produced content classification | Repetitive templated output can be ineligible even if AI-generated | Require per-clip editorial input/review; variation prompts; quality gate; disable unattended bulk export by default |
| AI narration is inaccurate | A narration can misrepresent a speaker or event | Generate as draft only; user must review/edit/approve script before render |
| LLM failure/rate limiting | Free providers can be inconsistent | OpenAI-compatible adapter, provider fallback, retry limits, clear errors |
| Audio clipping/mixing quality | Bad levels harm watchability | Loudness normalization, ducking, waveform preview, audio presets |
| GPU/CPU performance | Video rendering is resource-heavy | Queue architecture, worker isolation, CPU baseline, optional GPU scaling |

---

# 2. Monetization and Rights Product Policy

## 2.1 Core product rule

ClipForge must describe outputs as **“transformation-supporting edits”**, not “monetization-safe,” “copyright-free,” “strike-proof,” or “YPP guaranteed.” Effects, captions, and emojis alone are not sufficient proof of substantial originality.

## 2.2 Rights declaration at project creation

The project wizard must require exactly one source-rights basis before a job can start:

1. **I own this source content.**
2. **I have written permission/licence from the rights holder.**
3. **This source was provided in an authorized clipping/campaign program.**
4. **I am creating commentary/criticism/review and will independently assess fair-use/fair-dealing risk.**
5. **Other / not confirmed** — show high-risk warning; permit local draft generation only, but show a blocking warning before export.

Store supporting proof optionally: permission URL, campaign name, campaign brief attachment, rights-holder contact, or notes.

## 2.3 Source risk labels

ClipForge may help users assess workflow risk but must not make legal conclusions.

| Risk label | Trigger | UX behavior |
|---|---|---|
| Lower workflow risk | User owns content or attaches explicit authorization/campaign proof | Green informational label: “Authorization declared. YPP review still assesses originality.” |
| Needs review | Creator/podcast URL without attached permission proof | Amber warning: “Permission and YPP eligibility are separate. Add original editorial value.” |
| High claim risk | User labels source as movie/TV/anime/music/sports broadcast or enters such category | Red warning and export checklist; discourage use |
| Unknown | No declaration/proof | Block final export until user acknowledges risk and completes checklist |

## 2.4 Transformation Readiness Score

This is a private workflow score, not a legal score and never a promise. It helps the creator see what is missing.

**Score components, 0–100:**

- 0–25: Rights declaration completeness and proof attachment.
- 0–30: Original editorial contribution — approved narration, analysis text, user reaction track, or original contextual framing.
- 0–20: Visual transformation — meaningful layout/callouts/B-roll/graphics beyond a basic caption preset.
- 0–15: Clip uniqueness — unique hook/title, variation from other selected clips, non-duplicative source segment.
- 0–10: Human review — user reviewed transcript, script, and visual preview.

**UX wording:** “This score is a production-readiness checklist, not legal advice or a monetization guarantee.”

**Export gate:** No hard score threshold. The user can export after acknowledgements, but clips under 50 show a strong pre-export warning and a recommended-actions list.

## 2.5 Editorial templates (not just effects)

Provide templates that force a coherent editorial structure:

1. **Explainer:** Original 2–4 second hook → source excerpt → explanatory narration/callouts → original takeaway.
2. **Commentary:** Creator's own thesis → source evidence → pause/callout → creator conclusion.
3. **News/context:** Original context card → source moment → “why it matters” voiceover → attribution/end card.
4. **Reaction/PiP:** User-provided reaction-camera file → source excerpt in responsive split layout → original spoken reaction overlay.
5. **Quote breakdown:** Quote → claim label → annotation/definition → original summary.
6. **Campaign promotion:** Brand disclosure/required CTA → permitted source moment → original narration explaining product/value → campaign CTA.

Templates must never generate deceptive claims, fake endorsements, fabricated facts, or imitation of named living voices.

---

# 3. Technical Requirements Document (TRD)

## 3.1 Final recommended stack

| Layer | Decision | Rationale |
|---|---|---|
| Web app | Next.js 15/16, React, TypeScript, App Router | Fast product UI, strong type safety, compatible with your existing workflow |
| UI | Tailwind CSS + shadcn/ui + Radix primitives | High-quality accessible components without vendor lock-in |
| Video editor | Custom review/timeline layer plus optional OpenCut integration | OpenCut can be an optional manual editor; it is not the render-orchestration core |
| API | FastAPI, Python 3.12+ | Best ecosystem fit for video/ML processing, workers, and local inference |
| Background jobs | Celery + Redis for MVP; task routing by queue | Worker isolation, retries, scheduled tasks, scale-out capacity |
| Workflow orchestration | Celery chains/chords in MVP; evaluate Temporal only after multi-tenant scale | Avoid premature orchestration complexity while retaining durable task boundaries |
| Database | Supabase Postgres + SQLAlchemy/Alembic | Auth, relational metadata, row-level security, proven developer ergonomics |
| Realtime updates | Supabase Realtime or Server-Sent Events from FastAPI | Live job progress without aggressive browser polling |
| Object storage | Local filesystem adapter for dev; Cloudflare R2/S3 adapter for hosted mode | Local-first cheap MVP, scalable object storage later |
| Video engine | FFmpeg/ffprobe | Industry-standard decode, cut, compositing, audio mix, encode |
| Transcript engine | faster-whisper + WhisperX option for word-level alignment | Fast local transcription; accurate timestamps for captions |
| Face/person tracking | MediaPipe + OpenCV; optional ClipsAI components where compatible | Auto-reframe and tracked overlays without relying on a paid service |
| Scene detection | PySceneDetect | Better clip boundaries and cut-aware reframing |
| LLM gateway | OpenAI-compatible adapter for OmniRoute/FreeLLMAPI | Existing free/local setup; provider-agnostic model routing |
| TTS default | Kokoro local TTS, Apache-2.0 compatible where applicable | Lightweight local narration; avoid non-commercial voice cloning in product default |
| Voice cloning | Not enabled in v1 | Consent, impersonation, and licence risk; revisit with a verified-consent flow |
| Rendering | FFmpeg filtergraphs with deterministic render manifests | Reproducible, debuggable outputs instead of browser-only rendering |
| Observability | Structured JSON logs + Sentry (optional) + job event table | Debug long-running media failures |
| Testing | Pytest, Playwright, Vitest, fixture media set | Prevent regression in pipeline and UI |
| Deployment | Docker Compose local; Railway/Fly/Render plus managed Redis/R2 for hosted | Simple progression from personal use to SaaS |

## 3.2 Architecture principles

1. **Local-first, cloud-capable:** a developer can run the full stack on one machine; hosted workers are optional.
2. **Asynchronous by design:** a browser request never renders/transcodes video synchronously.
3. **Deterministic render manifests:** every generated clip stores source timestamps, effects configuration, captions, audio config, assets, and renderer version.
4. **Provider-agnostic AI:** LLM and TTS services are adapters behind interfaces, never wired directly into UI code.
5. **Human-in-the-loop by default:** selected clips, narration scripts, and final renders are reviewable before export.
6. **Rights-aware metadata:** authorization declarations and campaign constraints move through the entire job lifecycle.
7. **No hidden automation:** show exactly what is being generated, what source it uses, and what transformation elements were applied.

## 3.3 Pipeline topology

```text
Frontend Project Wizard
        |
        v
FastAPI: validates input + rights declaration + settings
        |
        v
Postgres: Project + ProcessingRun + RenderManifest (draft)
        |
        v
Redis / Celery Orchestrator
        |
        +--> ingest queue: yt-dlp / local-file validator / ffprobe
        +--> analysis queue: audio extraction, faster-whisper, scenes, faces, silence, speech segments
        +--> intelligence queue: LLM candidate ranking + brief matching + narration draft generation
        +--> editorial queue: hook/callout plan + caption timings + transformation readiness analysis
        +--> render queue: FFmpeg crop/composite/effects/audio mix/captions
        +--> QA queue: technical validation, duration/aspect/loudness checks, output manifest
        |
        v
Review Gallery: user edits/approves/re-renders selected clips
        |
        v
Export Package: MP4 + caption text + metadata + source attribution/rights notes
```

## 3.4 Worker queues

| Queue | Work | Concurrency default | Notes |
|---|---|---:|---|
| ingest | Validate/upload/download source, ffprobe | 2 | I/O and disk bound |
| analysis | Transcription, scene detection, face tracking | 1 CPU / 1 GPU optional | Resource intensive |
| llm | Candidate ranking, script drafts, metadata | 2 with rate limiter | Must respect gateway/provider availability |
| editorial | Caption prep, motion-plan generation | 2 | CPU-light |
| render | FFmpeg composites, effects, encode | 1–2 | CPU/GPU resource heavy |
| qa | Probe outputs, loudness, compliance checklist | 3 | Fast validation |

## 3.5 LLM API contract

The backend has one `LLMProvider` interface. It reads only environment variables:

```dotenv
LLM_BASE_URL=http://localhost:PORT/v1
LLM_API_KEY=your_local_gateway_key
LLM_MODEL=auto
LLM_TIMEOUT_SECONDS=90
LLM_MAX_RETRIES=2
```

All model responses requiring program control must use JSON-schema structured output. Validate with Pydantic. If parsing fails, retry once with a repair prompt; then create an actionable task failure.

**Clip-selection response schema:**

```json
{
  "candidates": [
    {
      "start_sec": 123.4,
      "end_sec": 164.8,
      "score": 0.0,
      "brief_match_reasons": ["..."],
      "exclusions_checked": ["..."],
      "suggested_hook": "...",
      "suggested_editorial_angle": "...",
      "requires_human_fact_check": true
    }
  ]
}
```

## 3.6 TTS and narration requirements

- Default engine: local Kokoro TTS adapter, configured as an optional service.
- Do not use source speaker audio to imitate/clone their voice.
- Do not offer “sound like [public figure]” presets.
- User can provide their own original narration audio file, which is the highest-quality and lowest-policy-risk option.
- AI narration is always produced as an editable script and a draft audio preview before final render.
- Apply loudness normalization to narration and final mix.

## 3.7 Audio mix requirements

Project configuration includes:

```json
{
  "mode": "mix",
  "original_volume": 35,
  "voiceover_volume": 100,
  "background_music_volume": 0,
  "duck_original_under_voiceover": true,
  "normalize_loudness": true,
  "target_lufs": -14
}
```

Modes:

- `original_only`
- `voiceover_only`
- `mix`
- `mute_original_keep_ambient` (deferred; v1 should treat as `voiceover_only` unless source-separation is explicitly added)

Use FFmpeg `volume`, `sidechaincompress` or equivalent ducking, `amix`, and `loudnorm` stages. Provide a short preview before a full render.

## 3.8 Render quality requirements

- Default output: 1080×1920, 30fps, H.264 video + AAC audio, MP4 container.
- Presets: Draft (fast/720×1280), Standard (1080×1920), High (1080×1920 higher bitrate).
- Ensure even pixel dimensions and platform-safe text zones.
- Burn captions into output for consistent platform display.
- Keep source/caption/script files separately so a user can render alternate versions later.

## 3.9 Security and privacy

- Never expose OmniRoute/FreeLLMAPI keys to the frontend browser.
- Store per-user source assets in scoped storage prefixes; use signed URLs for preview/download.
- Delete unfinished local temp files after configurable retention.
- Do not retain raw source media by default after project expiration in hosted mode; make retention user-configurable.
- Project and campaign brief records must use owner-only Supabase RLS policies.

---

# 4. Feature Specification

## 4.1 New Project wizard

### Step 1 — Source and rights

| Field | Type | Required | Notes |
|---|---|---:|---|
| Source type | Radio | Yes | YouTube URL / upload file / local folder (desktop/local mode) |
| Source URL/file | Input | Yes | Validate publicly accessible URL or supported media file |
| Source title | Text | Auto/editable | Pulled from metadata or file name |
| Rights basis | Radio | Yes | Required declaration; see section 2.2 |
| Supporting evidence | URL/file/notes | Optional | Campaign terms, permission screenshot, rights note |
| Source category | Select | Yes | Owned content / podcast / creator interview / course / campaign source / other |

### Step 2 — Clip output

| Field | Type | Default |
|---|---|---|
| Number of clips | Number, 1–50 | 5 |
| Clip min length | Number seconds | 20 |
| Clip max length | Number seconds | 60 |
| Platform preset | Select | YouTube Shorts (9:16) |
| Aspect ratio | Select | 9:16 |
| Resolution/quality | Select | Standard 1080×1920 |
| Safe text zone | Toggle | On |
| Candidate multiplier | Number, 1–5× | 2× (suggest more candidates than final desired count) |

### Step 3 — Campaign brief and editorial plan

| Field | Type | Required | Notes |
|---|---|---:|---|
| Saved brief | Select | No | Select a reusable brief |
| Campaign/brand brief | Rich text/JSON | Yes | Tone, topics, CTA, banned claims/topics, language, target viewer |
| Editorial template | Select | Yes | Explainer, commentary, news/context, reaction/PiP, quote breakdown, campaign promotion |
| Clip selection priority | Multi-select | Yes | Brief match / education / emotional hook / controversy only if allowed / quotable moment / product relevance |
| Required disclosures | Text | Optional | e.g., #ad where required; user must confirm obligations |

### Step 4 — Captions and graphics

| Field | Type | Default |
|---|---|---|
| Captions | Toggle | On |
| Caption preset | Select | Bold Karaoke |
| Caption position | Select | Lower safe zone |
| Caption language | Auto-detect/select | Auto |
| Hook card | Toggle | On for editorial templates |
| Callout labels | Toggle | On |
| Source attribution line | Toggle | On |
| CTA card | Toggle | Optional |
| Branding kit | Select | None |

### Step 5 — Narration and audio

| Field | Type | Default |
|---|---|---|
| Add voiceover | Toggle | On for commentary/explainer templates |
| Voiceover source | Select | AI local voice / upload my narration / none |
| Narration script | Generated then editable | Required if voiceover on |
| Voice preset | Select | Neutral, warm, energetic (no named-person imitation) |
| Audio mode | Select | Mix |
| Original audio volume | Slider 0–100 | 35 |
| Voiceover volume | Slider 0–100 | 100 |
| Duck original beneath narration | Toggle | On |
| Normalize final audio | Toggle | On |

### Step 6 — Effects and motion

Effects are enhancement layers. Interface copy must say: **“Effects improve visual storytelling; use narration, commentary, or original editorial structure for substantive transformation.”**

- Global effects apply to every generated clip.
- Clip-level overrides are available in review.
- Use a maximum of 1–3 visual effect groups by default to avoid low-quality, distracting output.

### Step 7 — Review and run

- Show a settings summary.
- Show rights-basis acknowledgment.
- Explain the tool produces drafts, not guaranteed monetization or copyright clearance.
- “Generate candidate clips” starts pipeline.

## 4.2 Effects catalog and implementation priority

### V1: Build first (high value, deterministic, low complexity)

| Category | Effect | User controls | Implementation |
|---|---|---|---|
| Basic/cinematic | Punch-in zoom | Intensity, frequency, target | FFmpeg `zoompan` / crop keyframes |
| Basic/cinematic | Camera shake | Intensity, duration | FFmpeg crop translation keyframes |
| Basic/cinematic | Film grain/vignette | Intensity | FFmpeg `noise`, vignette |
| Basic/cinematic | Speed ramp | Start/end speed, curve preset | FFmpeg `setpts`, `atempo` with audio handling |
| Glitch | RGB split/chromatic offset | Intensity, duration | FFmpeg color-channel offset/filtergraph |
| Glitch | VHS/noise/scanline | Intensity, opacity | FFmpeg noise + scanline overlay asset |
| Style | Background blur | Blur strength, layout | FFmpeg blurred duplicate background for vertical composition |
| Style | Pixelate/mosaic | Block size, timing | FFmpeg `scale` down/up nearest-neighbor |
| Celebrate | Bubble/snow/light leaks | Asset, opacity, position | Licensed/custom transparent overlay video assets via FFmpeg |
| Motion graphics | Floating subscribe button | Copy, style, route, frequency | Generate SVG/PNG asset + deterministic FFmpeg overlay expressions |
| Motion graphics | DVD corner bounce | Asset, speed, scale, opacity | Python computes bounce/keyframes; FFmpeg overlay expressions/keyframe asset |
| Motion graphics | CTA lower-third | Text, brand color, timing | FFmpeg drawtext/ASS/SVG overlay |

### V1.1: Build next (good value, more sophistication)

| Category | Effect | Implementation |
|---|---|---|
| AI tracking | Face-attached label/sticker | MediaPipe face landmarks + render coordinate tracks |
| AI tracking | Person-following callout | MediaPipe pose/person tracking + coordinate track |
| AI tracking | Auto punch-in on active speaker | Face/diarization activity signals + crop keyframes |
| Style | Comic/edge style | OpenCV edge preprocess + FFmpeg blend |
| Distort | Mirror/fisheye/wave | FFmpeg filters / OpenCV where needed |
| Beats | Audio-reactive pulse | Precompute beat/onset timings; animate overlay/scale |

### V2: Defer until validated

- Full segmentation/body effects.
- Real-time AR effects.
- Third-party marketplace of effect packs.
- Generative video effects that change factual content.

## 4.3 DVD-bounce artifact specification

**Goal:** add an optional, controllable animated artifact that bounces across the frame like a classic DVD screensaver.

**Parameters:**

```json
{
  "enabled": true,
  "asset": "dvd_logo_default",
  "scale_percent": 12,
  "opacity_percent": 80,
  "speed_px_per_sec": 180,
  "start_position": "random",
  "corner_collision_flash": true,
  "active_windows": [{"start_sec": 2, "end_sec": 12}],
  "avoid_caption_zone": true,
  "avoid_face_zone": true
}
```

**Rules:**

- Use an original or properly licensed logo asset, never another platform's trademark by default.
- Default to a generic “ClipForge” / user-uploaded asset, not the DVD trademarked mark.
- Avoid caption zone and tracked face zone when enabled.
- Randomize start direction per clip, but store seed in render manifest so re-renders remain reproducible.
- Treat as a decorative layer, not a policy-compliance feature.

## 4.4 Subscribe-button artifact specification

**Goal:** add a user-branded CTA animation without interfering with captions or content comprehension.

- User-provided/custom CTA text only; default: “Follow for more” rather than “Subscribe,” to support cross-platform output.
- Position modes: bounce, corner float, lower-third, timed center pop.
- Frequency cap: default one appearance per clip; maximum two.
- User can upload their own icon/brand mark.
- Must use safe zones and avoid tracked face/caption regions.

## 4.5 Narration workflow

1. The LLM proposes a **draft narration script** based only on the chosen source segment, user campaign brief, and editorial template.
2. It identifies factual claims and adds a `requires_human_fact_check` boolean.
3. User reviews and edits script in the Review Gallery before final audio render.
4. Local TTS generates a preview voiceover.
5. User selects audio mode and levels; UI plays a 10–15 second preview.
6. Renderer creates final mix with ducking/normalization.

**Narration prompt constraints:**

- Do not attribute unverified intent or statements to the source speaker.
- Do not manufacture facts absent from source/brief.
- Avoid medical, legal, financial advice unless user supplies approved wording.
- Do not create testimonials, endorsements, or claims that the brief/source does not support.
- Generate a unique hook and explanatory bridge; do not repeat generic filler.

## 4.6 Review Gallery

Every clip card contains:

- Video preview.
- Source time range and transcript excerpt.
- Clip relevance score and brief-match reasons.
- Transformation Readiness Score breakdown.
- Rights declaration summary and source risk badge.
- Editable title, hook, narration script, captions, CTA text.
- Audio mode/volume sliders.
- Effects chips with on/off controls and parameter drawer.
- Crop editor / subject focus override.
- Approve, Reject, Duplicate Variant, Re-render Draft, Export.

**Required warnings:**

- “This clip has captions/effects but no original commentary or narrative layer.”
- “This project has no recorded rights declaration/proof.”
- “Source category has elevated Content ID/takedown risk.”
- “Generated narration contains factual claims requiring review.”

---

# 5. App Flow

## 5.1 Screen inventory

| # | Screen | Auth required | Purpose |
|---|---|---:|---|
| 1 | Landing / Login | No | Explain local-first product and authenticate user |
| 2 | Dashboard | Yes | Recent projects, campaign briefs, new project CTA |
| 3 | New Project Wizard | Yes | Source, rights declaration, clip, campaign, editorial, voiceover, effects settings |
| 4 | Source Analysis | Yes | Transcript, scenes, candidates, source metadata after analysis |
| 5 | Processing Status | Yes | Granular background-job status and retry/error states |
| 6 | Candidate Selection | Yes | Compare/choose LLM suggestions before rendering all clips |
| 7 | Review Gallery | Yes | Edit, preview, approve/reject, re-render each final clip |
| 8 | Clip Editor | Yes | Detailed single-clip controls: crop, captions, voiceover, audio mix, effects, assets |
| 9 | Export Center | Yes | Download approved MP4s, scripts, SRT, manifest, project audit summary |
| 10 | Campaign Brief Library | Yes | Manage reusable campaign/brand briefs |
| 11 | Brand Kits | Yes | Brand colors, fonts, logos, CTA assets, overlay presets |
| 12 | Settings | Yes | LLM gateway/TTS configuration, storage/retention, default render settings |

## 5.2 Core user journey

1. Dashboard → **New Project**.
2. User adds a source and completes rights declaration.
3. User chooses 5 clips, 20–60 seconds, 9:16, standard quality.
4. User selects campaign brief + “Commentary” or “Explainer” editorial template.
5. User enables captions, hook card, original narration, and desired motion effects.
6. System validates and starts ingest/analysis.
7. System presents more candidates than requested (e.g., 10 suggestions for a request of 5).
8. User chooses the best 5 candidates and reviews generated hooks/scripts.
9. System renders drafts.
10. User adjusts each clip in Review Gallery, approves selected outputs.
11. User exports approved clips plus metadata package and manually posts them.

## 5.3 Critical edge cases

- **Private/blocked URL:** Explain that ClipForge cannot access unavailable/DRM-protected video; ask user to upload source media they are authorized to use.
- **No strong candidates:** Show transcript and enable manual in/out range selection rather than creating poor clips.
- **Free provider exhausted:** Mark intelligence task “Waiting for alternate provider”; allow retry with user-selected gateway model.
- **TTS fails:** Preserve the editable script, allow narration upload, and let user render original-only audio.
- **Face tracking fails:** Fall back to center or user-set crop; never fail full job solely due to tracking.
- **Render failure:** Preserve all source analysis, selected candidates, scripts, and effect configuration; retry only failed render stage.

---

# 6. UI/UX Brief

## 6.1 Product character

**Three adjectives:** professional, editorial, controlled.  
The product should feel like a serious creator-production desk, not a “one-click viral content machine.”

## 6.2 Design direction

- Dark studio interface: near-black canvas, elevated panels, high-contrast previews.
- Indigo as system/action color; orange as attention/accent; green/amber/red only for status/risk clarity.
- Prioritize clear timeline controls, before/after views, render status, and decision-making.
- Avoid gamified “viral score” language. Use “Brief Match,” “Editorial Readiness,” and “Review Required.”

## 6.3 Tokens

```css
:root {
  --bg: #0B0B0F;
  --surface: #15151C;
  --surface-raised: #1E1E27;
  --border: #2B2B36;
  --text: #F5F5F7;
  --muted: #9CA3AF;
  --primary: #6366F1;
  --primary-hover: #818CF8;
  --accent: #F97316;
  --success: #22C55E;
  --warning: #F59E0B;
  --danger: #EF4444;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
}
```

## 6.4 Key components

- `ProjectWizard` with explicit steps and saved draft support.
- `RightsDeclarationCard` with informational tooltips and non-legal-disclaimer text.
- `ProcessingPipeline` showing each worker stage and retry status.
- `CandidateCard` with transcript, timestamps, brief-match reasons, and selection checkbox.
- `ReadinessScoreCard` with action recommendations, never a “safe/unsafe” binary.
- `ClipPreviewCard` with video controls, caption toggle, visual-layer inspector.
- `AudioMixer` with original/voiceover sliders, mute/solo, waveform preview.
- `EffectsPanel` with presets, parameter controls, performance note, and safe-zone preview.
- `ExportChecklistDialog` with rights and originality acknowledgments.

## 6.5 Accessibility

- WCAG 2.1 AA contrast minimum.
- Keyboard navigation for timeline, clip selection, sliders, dialogs.
- Captions available in preview by default.
- Do not use color as the only risk/status signal; pair with icons/text.
- All processing-status updates announce through ARIA live regions.

---

# 7. Backend Schema and API Contract

## 7.1 Core entities

### users

```text
id uuid pk
auth_user_id uuid unique not null
email text unique not null
full_name text nullable
created_at timestamptz default now()
updated_at timestamptz default now()
```

### campaign_briefs

```text
id uuid pk
owner_id uuid fk -> users.id
name text not null
brief_text text not null
rules_json jsonb not null default '{}'
language text default 'en'
created_at timestamptz default now()
updated_at timestamptz default now()
```

### brand_kits

```text
id uuid pk
owner_id uuid fk -> users.id
name text not null
primary_color text nullable
secondary_color text nullable
font_family text nullable
logo_asset_id uuid nullable
cta_defaults jsonb default '{}'
caption_defaults jsonb default '{}'
created_at timestamptz default now()
updated_at timestamptz default now()
```

### projects

```text
id uuid pk
owner_id uuid fk -> users.id
name text not null
source_type text not null -- youtube_url | upload | local_folder
source_value text not null
source_title text nullable
source_category text not null
rights_basis text not null -- owned | written_permission | authorized_campaign | commentary_review | other_unconfirmed
rights_evidence_json jsonb default '{}'
rights_acknowledged_at timestamptz nullable
campaign_brief_id uuid nullable fk -> campaign_briefs.id
brand_kit_id uuid nullable fk -> brand_kits.id
editorial_template text not null
clip_count_requested int not null
candidate_multiplier int not null default 2
min_length_seconds int not null
max_length_seconds int not null
aspect_ratio text not null default '9:16'
render_preset text not null default 'standard'
caption_config jsonb not null default '{}'
audio_config jsonb not null default '{}'
effects_config jsonb not null default '{}'
status text not null default 'draft'
created_at timestamptz default now()
updated_at timestamptz default now()
```

### source_assets

```text
id uuid pk
project_id uuid fk -> projects.id
owner_id uuid fk -> users.id
asset_type text not null -- source_video | uploaded_narration | logo | overlay | reaction_camera
storage_key text not null
mime_type text nullable
size_bytes bigint nullable
duration_seconds numeric nullable
metadata_json jsonb default '{}'
created_at timestamptz default now()
```

### processing_runs

```text
id uuid pk
project_id uuid fk -> projects.id
status text not null -- queued | running | waiting | succeeded | failed | cancelled
pipeline_version text not null
input_snapshot jsonb not null
started_at timestamptz nullable
completed_at timestamptz nullable
error_summary text nullable
created_at timestamptz default now()
```

### jobs

```text
id uuid pk
processing_run_id uuid fk -> processing_runs.id
project_id uuid fk -> projects.id
stage text not null -- ingest | analyze | select | editorial | render | qa
queue_name text not null
external_task_id text nullable
status text not null -- pending | running | retrying | succeeded | failed | skipped
progress_percent int default 0
attempt_count int default 0
error_message text nullable
payload_json jsonb default '{}'
started_at timestamptz nullable
completed_at timestamptz nullable
created_at timestamptz default now()
```

### transcripts

```text
id uuid pk
project_id uuid fk -> projects.id
source_asset_id uuid fk -> source_assets.id
language text nullable
full_text text not null
segments_json jsonb not null -- timestamps, word-level alignment, speaker where available
created_at timestamptz default now()
```

### clip_candidates

```text
id uuid pk
project_id uuid fk -> projects.id
processing_run_id uuid fk -> processing_runs.id
start_seconds numeric not null
end_seconds numeric not null
selection_score numeric nullable
brief_match_reasons jsonb default '[]'
exclusions_checked jsonb default '[]'
transcript_excerpt text nullable
suggested_hook text nullable
suggested_editorial_angle text nullable
requires_human_fact_check boolean default false
selection_status text not null default 'pending' -- pending | selected | rejected
created_at timestamptz default now()
```

### clips

```text
id uuid pk
project_id uuid fk -> projects.id
candidate_id uuid nullable fk -> clip_candidates.id
sequence_number int not null
start_seconds numeric not null
end_seconds numeric not null
status text not null default 'draft' -- draft | rendering | ready_for_review | approved | rejected | exported | failed
title text nullable
hook_text text nullable
editorial_template text not null
narration_script text nullable
narration_status text default 'none' -- none | draft | reviewed | rendered
requires_human_fact_check boolean default false
caption_config jsonb not null default '{}'
audio_config jsonb not null default '{}'
effects_config jsonb not null default '{}'
crop_config jsonb not null default '{}'
transformation_score int nullable
transformation_breakdown jsonb default '{}'
reviewed_at timestamptz nullable
approved_at timestamptz nullable
created_at timestamptz default now()
updated_at timestamptz default now()
```

### clip_renders

```text
id uuid pk
clip_id uuid fk -> clips.id
render_type text not null -- preview | draft | final
status text not null
storage_key text nullable
thumbnail_key text nullable
render_manifest jsonb not null
technical_qc_json jsonb default '{}'
duration_seconds numeric nullable
width int nullable
height int nullable
created_at timestamptz default now()
```

### project_audit_events

```text
id uuid pk
project_id uuid fk -> projects.id
clip_id uuid nullable fk -> clips.id
actor_user_id uuid nullable fk -> users.id
event_type text not null -- rights_declared | candidate_selected | script_edited | clip_rendered | clip_approved | export_acknowledged
metadata_json jsonb default '{}'
created_at timestamptz default now()
```

## 7.2 Indexes

```text
projects(owner_id, updated_at desc)
processing_runs(project_id, created_at desc)
jobs(processing_run_id, stage, status)
clip_candidates(project_id, selection_status, selection_score desc)
clips(project_id, status, sequence_number)
clip_renders(clip_id, render_type, created_at desc)
project_audit_events(project_id, created_at desc)
```

## 7.3 Row-level security

All user-owned tables enforce `owner_id = auth.uid()` directly or indirectly through their project. A user can only read/write project descendants where they own the project. Service-role credentials are restricted to background workers and never sent to client browsers.

## 7.4 API endpoints

### Project and source

```text
POST   /v1/projects
GET    /v1/projects
GET    /v1/projects/{project_id}
PATCH  /v1/projects/{project_id}
DELETE /v1/projects/{project_id}
POST   /v1/projects/{project_id}/source/upload-url
POST   /v1/projects/{project_id}/analyze
```

### Campaign and brands

```text
GET    /v1/campaign-briefs
POST   /v1/campaign-briefs
PATCH  /v1/campaign-briefs/{brief_id}
DELETE /v1/campaign-briefs/{brief_id}
GET    /v1/brand-kits
POST   /v1/brand-kits
PATCH  /v1/brand-kits/{brand_kit_id}
```

### Candidate and clip workflow

```text
GET    /v1/projects/{project_id}/candidates
PATCH  /v1/candidates/{candidate_id}              -- select/reject/edit timestamps
POST   /v1/projects/{project_id}/render-selected
GET    /v1/projects/{project_id}/clips
GET    /v1/clips/{clip_id}
PATCH  /v1/clips/{clip_id}                        -- scripts, effect/audio/crop config
POST   /v1/clips/{clip_id}/preview
POST   /v1/clips/{clip_id}/render
POST   /v1/clips/{clip_id}/approve
POST   /v1/clips/{clip_id}/reject
```

### Export and jobs

```text
GET    /v1/projects/{project_id}/jobs
GET    /v1/projects/{project_id}/events           -- SSE status stream
POST   /v1/clips/{clip_id}/export-acknowledgement
POST   /v1/projects/{project_id}/export-package
GET    /v1/renders/{render_id}/download-url
```

---

# 8. Implementation Plan

## Phase 0 — Spec and safety baseline (Day 0–1)

**Milestone:** Product scope and non-negotiable policy boundaries are present in repository documentation.

- [ ] Add this document as `/context.md` (or link it from a concise `context.md`).
- [ ] Create `/docs/PRODUCT_POLICY.md` with the no-guarantee, no-rights-clearance, and no-unconsented-cloning requirements.
- [ ] Create `/docs/DECISIONS.md` recording stack choices and deferred decisions.
- [ ] Add `/docs/RENDER_MANIFEST_SCHEMA.json`.

## Phase 1 — Foundation and local development (Day 1–3)

**Milestone:** Frontend, API, Redis, Postgres, worker process, and local storage run from one command.

- [ ] Initialize monorepo: `apps/web`, `apps/api`, `apps/worker`, `packages/contracts`, `infra`.
- [ ] Choose package tooling: pnpm for Node workspace; uv for Python workspace/dependency lock.
- [ ] Add Docker Compose for Postgres 16, Redis 7, MinIO (S3-compatible local storage), FastAPI, worker.
- [ ] Configure Next.js + Tailwind + shadcn/ui and UI tokens.
- [ ] Configure FastAPI settings, structured logging, `/health`, `/ready` endpoints.
- [ ] Configure Supabase-compatible Postgres schema migrations with Alembic.
- [ ] Add Redis/Celery app with named queues and a no-op test job.
- [ ] Add `.env.example`, `.gitignore`, `STATUS.md`, `PROGRESS.md`, and `TASKS.md`.

## Phase 2 — Ingestion and source analysis (Day 4–7)

**Milestone:** Authorized source URL/upload becomes a stored, analyzed source with transcript, scenes, and metadata.

- [ ] Implement project/source creation with mandatory rights declaration.
- [ ] Build yt-dlp ingestion adapter with URL validation and clear unavailable/private/DRM failures.
- [ ] Build local-file upload pipeline using presigned storage upload URLs.
- [ ] Use ffprobe to extract duration, tracks, dimensions, fps, and codec information.
- [ ] Implement faster-whisper transcript worker with segment/word timestamps.
- [ ] Add PySceneDetect scene-boundary worker.
- [ ] Add MediaPipe subject/face track analysis with center-crop fallback.
- [ ] Persist worker/job events and stream status over SSE.
- [ ] Create a fixture set of three authorized/open test media files for repeatable development tests.

## Phase 3 — Brief-aware candidate selection (Day 8–10)

**Milestone:** Project brief and source transcript produce ranked, reviewable candidate moments in structured JSON.

- [ ] Implement `LLMProvider` OpenAI-compatible adapter using OmniRoute/FreeLLMAPI environment config.
- [ ] Implement Pydantic schema validation and bounded retry strategy for LLM output.
- [ ] Create a segment-window generator using transcript, scenes, speech/silence cues, and requested min/max duration.
- [ ] Build selection prompt that evaluates each segment against campaign rules and returns score/reasons/exclusions/suggested editorial angle.
- [ ] Return 2× candidate multiplier rather than instantly rendering requested clip count.
- [ ] Create Candidate Selection UI with transcript, timestamps, reasons, and manual in/out selection.
- [ ] Add “No strong candidates” state with manual clipping option.

## Phase 4 — First professional render (Day 11–14)

**Milestone:** Selected source ranges become clean, vertical, captioned MP4 draft clips.

- [ ] Implement FFmpeg cut/render service using exact source timestamps.
- [ ] Implement 9:16 smart reframe using MediaPipe-derived crop keyframes, with center-crop fallback.
- [ ] Implement blurred-background vertical layout for horizontal source footage.
- [ ] Add caption generation and burn-in from word-level transcript timings.
- [ ] Add caption presets: Bold Karaoke, Minimal, Clean Subtitle, None.
- [ ] Add render manifest creation and output technical QA: dimensions, duration, codec, audio presence.
- [ ] Build Review Gallery preview card and approve/reject flow.

## Phase 5 — Editorial transformation layer (Day 15–19)

**Milestone:** User can add reviewed original narrative structure, hooks, callouts, attribution, and CTA layers.

- [ ] Add editorial-template configuration to project creation.
- [ ] Generate editable hook, narration draft, callout plan, and closing takeaway per selected clip.
- [ ] Add factual-claim flagging in LLM output; require manual script review before TTS render.
- [ ] Build hook card, lower-third, contextual callout, attribution line, and CTA card renderer.
- [ ] Add optional user-uploaded reaction/PiP video layer with responsive layouts.
- [ ] Implement Transformation Readiness Score and action-oriented warning panel.
- [ ] Add pre-export acknowledgement dialog documenting that no monetization/copyright outcome is guaranteed.

## Phase 6 — Voiceover and audio studio (Day 20–23)

**Milestone:** A creator can use local TTS or uploaded narration, mix it with source audio, preview it, and render it reliably.

- [ ] Implement TTS adapter interface and local Kokoro TTS integration.
- [ ] Add narration script editor, script approval status, and local audio preview generation.
- [ ] Add uploaded narration file support.
- [ ] Implement audio-mode settings: original only / voiceover only / mix.
- [ ] Implement original + narration sliders, source-audio ducking, and final loudness normalization.
- [ ] Add short audio preview endpoint and waveform/level UI.
- [ ] Add audio technical QA to render output.

## Phase 7 — Motion effects v1 (Day 24–28)

**Milestone:** Users can apply controlled, deterministic, render-manifest-backed graphics/effects safely.

- [ ] Add effects configuration schema and Effects Panel UI.
- [ ] Implement zoom, shake, film grain, vignette, RGB split, VHS/noise, blur background, mosaic.
- [ ] Implement reusable transparent overlay asset handling (bubbles, snow, light leaks).
- [ ] Implement generic user-branded floating CTA animation.
- [ ] Implement generic bouncing-logo artifact (not trademarked DVD artwork by default), safe-zone/face avoidance where available.
- [ ] Enforce effect limits and preview a low-resolution draft before full standard render.
- [ ] Persist random seeds/keyframes in render manifests for deterministic re-renders.

## Phase 8 — Clip editor and project assets (Day 29–33)

**Milestone:** Per-clip overrides and reusable brand kits make results look intentional, not templated.

- [ ] Build single Clip Editor: crop focus, captions, script, voiceover, audio, effects, overlay timing.
- [ ] Add duplicate variant / A-B version functionality.
- [ ] Build Brand Kit CRUD: logos, colors, CTA default, caption defaults.
- [ ] Add per-clip override vs project-default inheritance model.
- [ ] Add source attribution/rights note in export package.

## Phase 9 — Reliability, testing, and release (Day 34–38)

**Milestone:** Stable personal-use release with auditability and recovery from common failures.

- [ ] Add idempotency keys for project analysis and render jobs.
- [ ] Add retries with exponential backoff, worker timeouts, and stage-level rerun controls.
- [ ] Add test suite: unit tests for configs/prompt schemas; integration tests for fixture pipeline; Playwright happy-path UI test.
- [ ] Add observability dashboard/logging and error tracking.
- [ ] Add asset-retention cleanup job.
- [ ] Test exports in YouTube Shorts, Instagram Reels, and TikTok uploader interfaces manually.
- [ ] Publish a user-facing “Rights and Originality Checklist” inside the product.

## Phase 10 — Scale readiness (post-validation)

- [ ] Add hosted R2 object storage adapter.
- [ ] Split worker pools by resource tier; enable autoscaling based on queue depth.
- [ ] Add GPU worker profile for faster-whisper/face analysis where workload justifies it.
- [ ] Add team/workspace model and project collaboration permissions.
- [ ] Add billing only after real product validation and with a clear commercial-use policy.
- [ ] Evaluate Temporal only if Celery job recovery/long-running workflows become a real operational bottleneck.

---

# 9. Antigravity Implementation Instructions

## 9.1 Operating rule

Before each change, read this document and `STATUS.md`. Implement **one checklist task only**. Do not begin a later phase until its previous milestone has been tested and accepted.

## 9.2 Required agent response format per task

1. **Task:** Restate the one implementation-plan checkbox being executed.
2. **Spec references:** List exact sections in this document being followed.
3. **Plan:** Name files to create/change and the test approach.
4. **Implementation:** Make the smallest coherent change.
5. **Verification:** Give the founder exact commands/clicks and expected output.
6. **Documentation:** Update `STATUS.md`, `PROGRESS.md`, and check off the completed task in `TASKS.md` only after tests pass.
7. **Stop:** Wait for founder approval before taking the next task.

## 9.3 Prohibited agent behavior

- Do not promise monetization, copyright safety, strike prevention, fair use, or YPP acceptance.
- Do not add automatic social publishing, payments, or unconsented voice cloning.
- Do not switch away from the selected stack without explicit founder approval.
- Do not write frontend-only fake progress; all pipeline status must come from stored backend job events.
- Do not make UI-only placeholders for a pipeline stage claimed as complete.
- Do not process media synchronously in FastAPI request handlers.

## 9.4 First build prompt

```text
Read /context.md, /STATUS.md, /PROGRESS.md, and /TASKS.md fully. We are building ClipForge AI according to the product spec.

Execute only Phase 1, first unchecked task: initialize the monorepo using apps/web, apps/api, apps/worker, packages/contracts, and infra. Use pnpm for Node and uv for Python. Do not build product UI or media-processing logic yet.

Before editing, restate the task, cite the relevant spec sections, list files you will create, and describe verification. After implementation, run the available checks, update STATUS.md/PROGRESS.md/TASKS.md, provide exact commands I can run, then stop and wait for approval.
```

---

# 10. Founder Decisions Needed Before Phase 2

1. **Initial product mode:** local-only desktop/dev application first, or web app with cloud deployment from day one? Recommended: local-first with Docker Compose, then hosted after pipeline validation.
2. **Operating system:** confirm whether primary dev machine is Windows, macOS, or Linux. FFmpeg, Docker, local TTS, and local file paths need OS-specific setup instructions.
3. **Hardware:** confirm RAM, CPU, and GPU model/VRAM. This determines whether local faster-whisper and TTS are comfortable or whether a GPU worker is needed.
4. **Authorized test footage:** provide 2–3 videos you own or have explicit permission to process. Do not use movie/TV/anime footage as the core test dataset.
5. **Brand name:** keep “ClipForge AI” as working title or choose final product name before building branding assets.

---

# Appendix A — Campaign Brief JSON Example

```json
{
  "campaign_name": "Example Creator Clips",
  "goal": "Drive viewers to understand and discuss practical AI product-building lessons.",
  "target_audience": "English-speaking founders and builders, age 18+",
  "tone": ["clear", "curious", "practical"],
  "required_topics": ["AI product building"],
  "preferred_moments": ["specific tactics", "counterintuitive insight", "concrete example"],
  "banned_topics": ["unverified income claims", "medical advice", "hate or harassment"],
  "required_cta": "Follow for practical AI-building lessons.",
  "disclosures": [],
  "clip_duration_min_seconds": 20,
  "clip_duration_max_seconds": 60,
  "source_attribution": "Source: @creatorhandle",
  "language": "en"
}
```

# Appendix B — Effects Configuration Example

```json
{
  "preset_name": "Editorial Energy",
  "safe_zones": true,
  "effects": [
    {
      "type": "punch_in_zoom",
      "enabled": true,
      "intensity": 0.25,
      "trigger": "emphasis_words"
    },
    {
      "type": "rgb_split",
      "enabled": true,
      "intensity": 0.15,
      "active_windows": [{"start_sec": 0.0, "end_sec": 0.35}]
    },
    {
      "type": "floating_cta",
      "enabled": true,
      "text": "Follow for more",
      "animation": "corner_float",
      "start_sec": 18.0,
      "end_sec": 21.0
    }
  ]
}
```

# Appendix C — Audio Configuration Example

```json
{
  "voiceover_enabled": true,
  "voiceover_source": "local_tts",
  "voice_preset": "warm",
  "mode": "mix",
  "original_volume": 35,
  "voiceover_volume": 100,
  "duck_original_under_voiceover": true,
  "normalize_loudness": true,
  "target_lufs": -14
}
```