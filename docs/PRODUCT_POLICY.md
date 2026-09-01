# ClipForge AI — Product Policy

> This document defines the non-negotiable product boundaries for ClipForge AI.
> Every feature, prompt, UI label, and export flow must comply with these rules.

---

## 1. Core Product Rule

ClipForge AI describes its outputs as **"transformation-supporting edits"**.

The product **must never** use any of the following language in UI, documentation,
marketing, prompts, or generated metadata:

- "Monetization-safe"
- "Copyright-free"
- "Strike-proof"
- "YPP guaranteed"
- "Fair use certified"
- "Safe to upload"
- "Compliant"

Effects, captions, and emojis alone are **not** sufficient proof of substantial
originality. The product must guide users toward meaningful editorial contribution.

---

## 2. Rights Declaration Requirement

Every project requires exactly one source-rights basis before processing begins:

| # | Declaration | Risk Level |
|---|---|---|
| 1 | I own this source content. | Lower workflow risk |
| 2 | I have written permission/licence from the rights holder. | Lower workflow risk |
| 3 | This source was provided in an authorized clipping/campaign program. | Lower workflow risk |
| 4 | I am creating commentary/criticism/review and will independently assess fair-use/fair-dealing risk. | Needs review |
| 5 | Other / not confirmed. | High — block export until acknowledged |

Supporting proof is optional but encouraged: permission URL, campaign name,
campaign brief attachment, rights-holder contact, or notes.

---

## 3. Source Risk Labels

ClipForge may help users assess workflow risk but **must not make legal conclusions**.

| Risk Label | Trigger | UX Behavior |
|---|---|---|
| Lower workflow risk | User owns content or attaches explicit authorization/campaign proof | Green informational label |
| Needs review | Creator/podcast URL without attached permission proof | Amber warning |
| High claim risk | Source labeled as movie/TV/anime/music/sports broadcast | Red warning + export checklist |
| Unknown | No declaration/proof | Block final export until user acknowledges risk |

**Wording for "Lower workflow risk" label:**
> "Authorization declared. YPP review still assesses originality."

---

## 4. Transformation Readiness Score

This is a **private workflow score** (0–100), not a legal score, and never a promise.

### Score Components

| Points | Component |
|---|---|
| 0–25 | Rights declaration completeness and proof attachment |
| 0–30 | Original editorial contribution (narration, analysis, reaction, framing) |
| 0–20 | Visual transformation (layout, callouts, B-roll, graphics beyond basic captions) |
| 0–15 | Clip uniqueness (unique hook/title, variation, non-duplicative segment) |
| 0–10 | Human review (user reviewed transcript, script, and visual preview) |

### UX Wording

> "This score is a production-readiness checklist, not legal advice or a
> monetization guarantee."

### Export Gate

No hard score threshold. Users can export after acknowledgements, but clips
scoring under 50 display a strong pre-export warning and a recommended-actions list.

---

## 5. Editorial Templates

Templates force a coherent editorial structure, not just visual effects:

1. **Explainer:** Original hook → source excerpt → explanatory narration/callouts → original takeaway.
2. **Commentary:** Creator's thesis → source evidence → pause/callout → creator conclusion.
3. **News/Context:** Original context card → source moment → "why it matters" voiceover → attribution.
4. **Reaction/PiP:** User-provided reaction camera → source excerpt in split layout → spoken reaction.
5. **Quote Breakdown:** Quote → claim label → annotation/definition → original summary.
6. **Campaign Promotion:** Brand disclosure/CTA → permitted source moment → original narration → campaign CTA.

Templates **must never** generate deceptive claims, fake endorsements, fabricated
facts, or imitation of named living voices.

---

## 6. Prohibited Product Behaviors

ClipForge AI **must never**:

- Auto-upload or auto-post to any social platform.
- Scrape, bypass DRM, download private/paywalled content, or bypass platform access controls.
- Claim that filters/effects alone satisfy YouTube reused-content policy.
- Generate or facilitate voice-cloning of a real person without verified rights and explicit consent.
- Offer legal advice, copyright clearance, or guaranteed YPP approval.
- Target movie, TV, anime, sports-broadcast, or music-video source libraries as a clipping workflow.
- Add payments, live clipping, or unconsented voice cloning.
- Process media synchronously in API request handlers.
- Generate deceptive claims, fake endorsements, fabricated facts, or medical/legal/financial advice.

---

## 7. Narration Constraints

- AI narration is always produced as an **editable draft script** and a preview before final render.
- Do not attribute unverified intent or statements to the source speaker.
- Do not manufacture facts absent from source/brief.
- Do not create testimonials, endorsements, or claims the brief/source does not support.
- Do not offer "sound like [public figure]" voice presets.
- User-provided original narration is always the highest-quality and lowest-policy-risk option.

---

## 8. Export Requirements

Before any clip export, the user must:

1. Have a rights declaration on file for the project.
2. Have reviewed the clip preview (video + captions + narration if applicable).
3. Acknowledge that ClipForge does not guarantee monetization, copyright clearance, or platform acceptance.

Clips with a Transformation Readiness Score below 50 show a strong warning with
specific recommended actions before export proceeds.

---

## 9. Audit Trail

ClipForge records the following events per project and per clip:

- `rights_declared` — timestamp and declaration type
- `candidate_selected` — which candidates were chosen and why
- `script_edited` — narration script review/edit events
- `clip_rendered` — render manifest and output metadata
- `clip_approved` — user approval timestamp
- `export_acknowledged` — user acknowledged pre-export warnings

This trail is for the user's internal compliance and organizational records.
It is **not** legal proof of any rights status.
