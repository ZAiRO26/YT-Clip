"""
ClipForge AI — Pydantic Schemas (v2)
Includes mandatory rights basis, source risk labels, editorial templates, and render manifests.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================
# Rights & Risk Types (context2-upgrade.md Section 2.2 & 2.3)
# ============================================
RightsBasisType = Literal[
    "owned",
    "written_permission",
    "authorized_campaign",
    "commentary_review",
    "other_unconfirmed",
]

SourceRiskLabelType = Literal[
    "lower_workflow_risk",
    "needs_review",
    "high_claim_risk",
    "unknown",
]

EditorialTemplateType = Literal[
    "explainer",
    "commentary",
    "news_context",
    "reaction_pip",
    "quote_breakdown",
    "campaign_promotion",
]


def compute_source_risk(rights_basis: str, source_type: str = "youtube_url", has_proof: bool = False) -> SourceRiskLabelType:
    """
    Computes workflow risk level per context2-upgrade.md Section 2.3:
      - owned / written_permission / authorized_campaign -> lower_workflow_risk
      - commentary_review -> needs_review
      - other_unconfirmed -> unknown / high_claim_risk
    """
    if rights_basis in ("owned", "written_permission", "authorized_campaign"):
        return "lower_workflow_risk"
    elif rights_basis == "commentary_review":
        return "needs_review"
    elif rights_basis == "other_unconfirmed":
        return "unknown"
    return "unknown"


# ============================================
# Campaign Briefs
# ============================================
class CampaignBriefCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brief_json: dict = Field(
        default_factory=lambda: {
            "tone": "",
            "required_mentions": [],
            "banned_topics": [],
            "brand_rules": "",
        }
    )


class CampaignBriefResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    brief_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================
# Projects
# ============================================
class ProjectCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    source_type: str = Field(..., pattern="^(youtube_url|local_folder|upload)$")
    source_value: str = Field(..., min_length=1)

    # Mandatory Rights Declaration (Section 2.2)
    rights_basis: RightsBasisType = Field(
        ...,
        description="Mandatory declaration of source rights basis.",
    )
    rights_proof_url: str | None = Field(
        default=None,
        description="Optional proof URL (permission link, license doc, campaign page)",
    )
    rights_notes: str | None = Field(
        default=None,
        description="Optional rights context or license notes",
    )

    # Editorial & Style Configuration
    editorial_template: EditorialTemplateType = Field(
        default="explainer",
        description="Editorial transformation template",
    )
    campaign_brief_id: UUID | None = None
    clip_count: int = Field(default=5, ge=1, le=50)
    min_length_sec: int = Field(default=20, ge=5, le=300)
    max_length_sec: int = Field(default=60, ge=10, le=600)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|1:1|16:9)$")
    crop_mode: str = Field(default="face_track", description="Framing mode: face_track, blur_background, center")
    caption_style: str = Field(default="bold_karaoke", description="Caption typography preset")
    default_effects: list[dict[str, Any]] = Field(default_factory=list, description="Default motion effect layers")
    default_voice_id: str = Field(default="af_bella", description="Default Kokoro voice persona")
    default_music_track: str = Field(default="none", description="Default ambient background music bed")
    custom_prompt: str | None = Field(default=None, description="Optional custom prompt to guide clip selection")
    time_range_start: float | None = Field(default=None, description="Optional start time in seconds")
    time_range_end: float | None = Field(default=None, description="Optional end time in seconds")


class JobStatus(BaseModel):
    id: UUID
    stage: str
    status: str
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str | None = None
    source_type: str
    source_value: str
    rights_basis: str
    rights_proof_url: str | None = None
    rights_notes: str | None = None
    source_risk_label: str
    editorial_template: str
    campaign_brief_id: UUID | None = None
    clip_count: int
    min_length_sec: int
    max_length_sec: int
    aspect_ratio: str
    crop_mode: str = "face_track"
    caption_style: str = "bold_karaoke"
    default_effects: list[dict[str, Any]] = Field(default_factory=list)
    default_voice_id: str = "af_bella"
    default_music_track: str = "none"
    status: str
    created_at: datetime
    jobs: list[JobStatus] = []

    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    id: UUID
    title: str | None = None
    source_type: str
    source_value: str
    rights_basis: str = "owned"
    source_risk_label: str = "lower_workflow_risk"
    editorial_template: str = "explainer"
    clip_count: int = 5
    status: str
    created_at: datetime
    preview_url: str | None = None

    model_config = {"from_attributes": True}


# ============================================
# Clips
# ============================================
class ClipResponse(BaseModel):
    id: UUID
    project_id: UUID
    start_sec: float
    end_sec: float
    score: float | None = None
    transformation_score: int | None = None
    transformation_breakdown: dict | None = None
    reasoning: str | None = None
    file_url: str | None = None
    thumbnail_url: str | None = None
    render_manifest: dict | None = None
    review_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipUpdate(BaseModel):
    review_status: str | None = Field(default=None, pattern="^(pending|approved|rejected)$")
    start_sec: float | None = None
    end_sec: float | None = None
    reasoning: str | None = None


class ReclipRequest(BaseModel):
    clip_count: int = Field(default=5, ge=1, le=20)
    min_length_sec: int = Field(default=20, ge=5, le=300)
    max_length_sec: int = Field(default=60, ge=10, le=600)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|1:1|16:9)$")
    caption_style: str = Field(default="bold_karaoke")
    custom_prompt: str | None = Field(default=None, description="Guidance for new clips")
    time_range_start: float | None = Field(default=None, description="Start time in seconds")
    time_range_end: float | None = Field(default=None, description="End time in seconds")


class ThumbnailRequest(BaseModel):
    text: str | None = Field(default=None, description="Optional custom title or text to burn onto thumbnail")


class ExportRequest(BaseModel):
    export_path: str = Field(..., min_length=1, description="Absolute folder path to save approved clips into")
    acknowledged_risks: bool = Field(
        default=False,
        description="Mandatory user acknowledgment that ClipForge outputs are editorial edits and not a copyright clearance guarantee.",
    )


class MessageResponse(BaseModel):
    message: str
    details: dict[str, Any] | None = None


# ============================================
# Candidate Selection & Transformation (context2-upgrade.md Section 2.4 & 3.3)
# ============================================
HookType = Literal[
    "question",
    "bold_statement",
    "surprising_stat",
    "story_loop",
    "controversial_thesis",
]


class CandidateClipSchema(BaseModel):
    start_sec: float
    end_sec: float
    title: str
    hook_type: HookType = "bold_statement"
    hook_text: str
    key_takeaway: str
    editorial_potential: float = Field(default=0.7, ge=0.0, le=1.0)
    virality_score: float = Field(default=0.7, ge=0.0, le=1.0)
    transformation_score: int = Field(default=75, ge=0, le=100)
    transformation_breakdown: dict[str, int] = Field(default_factory=dict)
    reasoning: str
    suggested_callouts: list[str] = Field(default_factory=list)


class CandidateSelectionResponse(BaseModel):
    project_id: UUID
    clips: list[CandidateClipSchema]
    total_found: int


# ============================================
# Brand Kits & Clip Re-render (context2-upgrade.md Section 5.4 & Phase 8)
# ============================================
class BrandKitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    primary_color: str = Field(default="#6366F1", pattern="^#[0-9a-fA-F]{6}$")
    secondary_color: str = Field(default="#10B981", pattern="^#[0-9a-fA-F]{6}$")
    font_family: str = Field(default="Montserrat", max_length=50)
    logo_url: str | None = None
    watermark_position: Literal["top_right", "top_left", "bottom_right", "bottom_left"] = "top_right"
    default_cta_text: str = Field(default="Subscribe for more", max_length=100)


class BrandKitResponse(BaseModel):
    id: UUID
    name: str
    primary_color: str
    secondary_color: str
    font_family: str
    logo_url: str | None
    watermark_position: str
    default_cta_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipRerenderRequest(BaseModel):
    start_sec: float = Field(..., ge=0.0)
    end_sec: float = Field(..., ge=1.0)
    caption_style: str = Field(default="bold_karaoke", pattern="^(bold_karaoke|minimal|clean_subtitle|none)$")
    crop_mode: str = Field(default="face_track", pattern="^(face_track|blur_background|center)$")
    focal_x: float = Field(default=0.5, ge=0.0, le=1.0)
    voiceover_text: str | None = None
    voice_id: str | None = None
    music_track: str | None = None
    effects: list[dict[str, Any]] = Field(default_factory=list)


