# Pipeline Speed-Up — Implementation Plan

Status: **Phases 0–3 built, Phase 4 spiked (decision pending), 5–6 open** · Written 2026-10-10 · Branch: `qa-audit-fixes`

## 0. Results so far (measured 2026-10-10)

Baseline, full 98-min job on the old pipeline: **3h 06m** total — download 6 min, analysis 2h 46m (speech 65 min, scene cuts ~50 min, face tracking ~51 min), AI select 2 min, render 12 min (23 short clips).

10-minute slice of the same video (AV1 1080p, stacked-speaker tracking):

| Step | Full-resolution | With 540p proxy |
|---|---|---|
| Proxy creation | — | 46 s |
| Scene cuts | 297 s | 8 s |
| Face tracking | 313 s | 28 s |
| **Scene + face total** | **610 s** | **82 s (7.4× faster)** |
| Speech to text (unchanged) | 353 s | 353 s |

Projected for the 98-min video: analysis 2h 46m → about 1h 12m; whole job 3h 06m → about 1h 45m. The projection is extrapolated from the 10-minute slice, not yet run end to end on the full video.

Fidelity of proxy vs full resolution (3-minute slice): face position differs by more than 3% of frame width on 26 of 563 samples (mean difference 0.5%); scene cuts 40 vs 37, 35 of them within 0.25 s of a full-resolution cut. Close, not identical. Proxy is 540p rather than the planned 480p because 540p tracked noticeably closer. Output clips verified 1080×1920.

Phase 4 spike A (batched CPU Whisper), same 10-minute slice: **77 s vs 353 s (4.6× faster)**. Not adopted yet: it returns ~30-second segments (19 instead of 166), and clip boundaries, the selection prompt and subtitle translation all rely on short segments, so it needs a re-segmentation step first. Transcripts of this Hindi audio also vary a lot between runs of the `base` model (1,033 / 1,231 / 1,782 words across three runs), so word-timing drift could not be judged reliably. Spike B (GPU) not started — needs installs.

Not in the original plan but found on the way (selection quality): the AI was returning 2–13 s picks that the code padded forward to the minimum, so every clip was ~20 s and often missed the setup. Fixed with a stricter prompt, backward-biased expansion to natural pauses, and a refill pass. Same video re-run: 28 of 28 clips, 28–58 s, median 42 s.

## 1. Goal

Cut end-to-end processing time for a full-length video roughly in half **without changing output quality**.

Reference job: "Casual - Tea" stand-up special, 98 min, 1080p AV1, 28 clips, on this machine (8 logical cores, RX 5500M 4 GB, no NVIDIA GPU).

| Stage | Today | Target | Lever |
|---|---|---|---|
| Download | 6 min (measured) | ~8 min | H.264 file is larger |
| Speech → text | 65 min (measured) | 15–25 min | Whisper on GPU, or batched CPU |
| Scene cuts | ~47 min (measured) | 5–10 min | 480p analysis proxy |
| Face tracking | 45–60 min (estimate) | 15–25 min | 480p analysis proxy |
| Proxy creation | — | +5–8 min | new step |
| AI select | ~5 min (estimate) | same | — |
| Render 28 clips | 20–30 min (estimate) | same | quality kept |
| **Total** | **~3h10 – 3h30** | **~1h15 – 1h45** | |

Every "Target" number is an estimate. Phase 0 replaces the estimates in the "Today" column with measurements, and each later phase is accepted or rejected on measured time, not on this table.

## 2. Non-negotiables

1. **Output stays 1080×1920.** Final clips are always cut from the original 1080p source. The 480p proxy is read only to produce timestamps and face positions, then deleted.
2. **Final render keeps the current CPU encoder (`libx264`, CRF 22).** GPU encoding is opt-in "fast draft" only.
3. **Caption timing must not get worse.** Any new speech engine has to match the current word-level timing before it becomes default.
4. **Every new path has an automatic fallback** to today's behaviour. A GPU or proxy failure must never fail a project.
5. `transcript.json` and `analysis.json` keep their current shape, so select, render, captions and voiceover are untouched.

## 3. Non-goals

- No change to clip selection logic, caption styling, voiceover, or effects.
- No GPU face tracking (MediaPipe has no GPU path on Windows Python).
- No GPU scene detection (PySceneDetect is CPU only).
- No larger Whisper model. Same `base` model, just faster. Accuracy upgrades are a separate decision.

## 4. Why it is slow today (verified in code)

- The whole pipeline runs on CPU. `faster-whisper` only supports NVIDIA GPUs; this machine has AMD.
- The downloaded file was AV1, the most expensive format to decode on CPU. The RX 5500M cannot hardware-decode AV1.
- Scene detection (`scene_detector.py`) and face tracking (`face_tracker.py`) each decode all 147,248 frames at full 1080p. Face tracking already shrinks each frame to 480×270 before detection, so full-resolution decoding is pure waste there.
- The three analysis steps run strictly one after another inside `run_analysis` and are shown as one "Transcribe" card, so a 2.5-hour stage looks frozen.

## 5. Phases

Each task is sized for one working session. Do not start a phase until the previous one's check passes.

### Phase 0 — Measure first

| # | Task | Done when |
|---|---|---|
| 0.1 | Record per-step wall time (whisper, scenes, faces, select, render) into the `analysis_completed` / `render_completed` audit events and the worker log | Timings visible in `/api/projects/{id}/audit-trail` |
| 0.2 | Take the baseline from the current 98-min job (job timestamps + worker log) and write it into §1 | "Today" column has no estimates left |
| 0.3 | Pick a fixed 10-minute benchmark clip (first 10 min of the same video) for quick before/after runs | One command reproduces a timed run |

### Phase 1 — H.264 download (done, needs restart)

| # | Task | Done when |
|---|---|---|
| 1.1 | Prefer `avc1` video + `m4a` audio at ≤1080p, fall back to any codec | ✅ edited in `workers/download.py` |
| 1.2 | Restart ingest worker; download benchmark video | `ffprobe` shows `h264`, 1920×1080 |

Trade-off: file roughly twice as large (~800 MB vs ~360 MB for 98 min). Same resolution.

### Phase 2 — 480p analysis proxy

| # | Task | Done when |
|---|---|---|
| 2.1 | New `services/analysis_proxy.py`: one FFmpeg pass producing `analysis_proxy.mp4` — 480p height, **same frame rate and frame count as source**, no audio, `libx264 ultrafast`. Try hardware decode (`d3d11va`) first, fall back to CPU decode | Proxy frame count equals source frame count on the fixture |
| 2.2 | `run_analysis` creates the proxy after transcription inputs are ready and passes it to `detect_scenes` and `track_faces`. If proxy creation fails, use the source file as today | Analysis succeeds with FFmpeg proxy step forced to fail |
| 2.3 | Delete the proxy when analysis finishes; add it to the cleanup service's temp list | No `analysis_proxy.mp4` left after a successful run |
| 2.4 | Equivalence tests on the spoken fixture: scene cut times within ±0.2 s of full-resolution run; `focal_x` timeline within ±0.03; render output still 1080×1920 | Tests pass |
| 2.5 | Timed run on the 10-min benchmark | Scene + face time measured and recorded |

Why this is safe: scene detection outputs seconds, face tracking outputs a 0–1 horizontal position. Neither depends on resolution. PySceneDetect already auto-downscales internally and the face tracker already resizes to 480×270.

### Phase 3 — Visible sub-stages

| # | Task | Done when |
|---|---|---|
| 3.1 | Rebalance analysis progress ranges for the new step order and expose the current sub-step name alongside `progress_detail` | API returns sub-step for a running job |
| 3.2 | Project page: rename the card to "Analyze" and show a 4-line checklist under it — Speech, Analysis proxy, Scene cuts, Face tracking — each with done / running / pending | Visible in browser during a live run |
| 3.3 | Show elapsed time on the running stage | A long stage no longer looks frozen |

No database migration: uses the existing `jobs.progress_percent` and `jobs.progress_detail` columns.

### Phase 4 — Faster speech-to-text (spike, then decide)

This is the biggest win and the biggest risk, so it starts with a time-boxed experiment on the 10-min benchmark, not with a rewrite.

| # | Task | Done when |
|---|---|---|
| 4.1 | **Spike A — batched CPU:** `faster-whisper` `BatchedInferencePipeline`, same model, `word_timestamps=True`. No new dependency | Time + word-timing comparison recorded |
| 4.2 | **Spike B — GPU:** whisper.cpp built with Vulkan, run on the RX 5500M, token/word timestamps on | Time + word-timing comparison recorded |
| 4.3 | Compare both against today's output: speed, word-start drift (median and worst case), text differences, behaviour on Hindi/Hinglish audio with the existing Latin-script prompt | Written comparison in this doc |
| 4.4 | Put the winner behind a `WHISPER_ENGINE` setting with the current engine as automatic fallback; same `transcript.json` output | Full pipeline run passes on both settings |
| 4.5 | Regenerate captions on the benchmark and check karaoke sync by eye on three clips | You approve the look |

Acceptance gate for 4.4: median word-start drift ≤ 80 ms against current output and no visible karaoke desync. If neither spike passes, keep the current engine and stop — Phases 1–3 still deliver most of the saving.

### Phase 5 — Optional fast-draft GPU encode

| # | Task | Done when |
|---|---|---|
| 5.1 | `RENDER_ENCODER` setting: `x264` (default) or `amf`. `amf` uses `h264_amf` with a bitrate chosen to match current quality as closely as possible, and falls back to `x264` on any error | Both settings render the fixture |
| 5.2 | Studio: a "Fast preview render" toggle for re-renders only. Batch and export always use `x264` | Toggle works; exported files unchanged |

Low priority. Render is a small share of total time and quality is the constraint.

### Phase 6 — Lock it in

| # | Task | Done when |
|---|---|---|
| 6.1 | Full before/after run on the 98-min video, same settings | Real numbers replace §1 |
| 6.2 | Add ADR-013 to `docs/DECISIONS.md` (proxy analysis, speech engine choice, encoder policy); update `README.md` hardware notes | Docs match code |
| 6.3 | Full test suite + typecheck, commit, push | 118+ tests green |

## 6. Open questions and validation gates

| # | Question | How it gets answered |
|---|---|---|
| Q1 | Does whisper.cpp on Vulkan give word timings good enough for karaoke? Its word timing uses a different method from faster-whisper | Spike 4.2 / 4.3 |
| Q2 | How much does batched CPU inference actually gain with word timestamps on? Published claims are GPU-focused and unverified for CPU | Spike 4.1 |
| Q3 | Does whisper.cpp + Vulkan run correctly on the RX 5500M driver? | Spike 4.2 |
| Q4 | Does `d3d11va` hardware decode work reliably for the proxy pass, or is CPU decode simpler and fast enough? | Task 2.1 timing |
| Q5 | Can scene detection run in parallel with transcription (it does not need the transcript)? Possible extra saving | Revisit after Phase 2 numbers |

## 7. Needs from you

1. **Go-ahead** to start after the current 98-min job finishes.
2. **Phase 4, GPU spike only:** whisper.cpp with Vulkan has no official Windows GPU download. It needs either the Vulkan SDK + Visual Studio Build Tools installed so it can be built from source, or your explicit approval of a specific prebuilt binary. Nothing gets installed without you saying so. Spike A needs nothing.
3. **Eyes on captions** at task 4.5.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Proxy frame timing drifts from source (variable frame rate uploads) | Task 2.1 enforces equal frame count; mismatch → fall back to source |
| New speech engine changes transcript text and therefore clip selection | Engine is a setting; compare on benchmark before switching default |
| Extra disk use: larger H.264 source plus temporary proxy | Proxy deleted after analysis; note in README |
| GPU contention if another app uses the RX 5500M | Automatic CPU fallback |

## 9. Expected outcome by phase

| After phase | Estimated total for the 98-min job |
|---|---|
| Today | ~3h10 – 3h30 |
| 1 + 2 (low risk) | ~2h00 – 2h20 |
| + 4 (speech engine) | ~1h15 – 1h45 |

Sources consulted for Phase 4 feasibility: [whisper.cpp Windows Vulkan build notes](https://github.com/DomoticX/whisper.cpp-windows-vulkan), [whisper.cpp on AMD GPUs with Vulkan](https://www.maroonmed.com/subtitle-edit-and-whisper-cpp-stt-on-amd-and-other-non-nvidia-gpus-with-vulkan/), [faster-whisper batched processing docs](https://tessl.io/registry/tessl/pypi-faster-whisper/files/docs/batched-processing.md).
