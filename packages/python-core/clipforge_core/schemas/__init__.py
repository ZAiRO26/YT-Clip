"""
ClipForge AI — Pydantic Schemas

Request/response models for all API endpoints.
Per Backend Schema section 05 of context.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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
    source_type: str = Field(..., pattern="^(youtube_url|local_folder)$")
    source_value: str = Field(..., min_length=1)
    campaign_brief_id: UUID | None = None
    clip_count: int = Field(default=5, ge=1, le=50)
    min_length_sec: int = Field(default=20, ge=5, le=300)
    max_length_sec: int = Field(default=60, ge=10, le=600)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|1:1|16:9)$")
    caption_style: str = Field(default="bold_karaoke")
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
    source_type: str
    source_value: str
    campaign_brief_id: UUID | None = None
    clip_count: int
    min_length_sec: int
    max_length_sec: int
    aspect_ratio: str
    caption_style: str
    status: str
    created_at: datetime
    jobs: list[JobStatus] = []

    model_config = {"from_attributes": True}


class ProjectListItem(BaseModel):
    id: UUID
    source_type: str
    source_value: str
    clip_count: int
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
    reasoning: str | None = None
    file_url: str | None = None
    thumbnail_url: str | None = None
    review_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClipUpdate(BaseModel):
    review_status: str = Field(..., pattern="^(pending|approved|rejected)$")


class ThumbnailRequest(BaseModel):
    text: str | None = Field(None, description="Optional text to overlay on the thumbnail")
    style: str | None = Field("minimal", description="Visual style of the text overlay (bold, minimal, gradient)")


# ============================================
# Generic
# ============================================


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None


class ExportRequest(BaseModel):
    export_path: str = Field(..., description="Absolute path on the host machine to export clips to")


class ReclipRequest(BaseModel):
    clip_count: int = Field(default=5, ge=1, le=50)
    min_length_sec: int = Field(default=20, ge=5, le=300)
    max_length_sec: int = Field(default=60, ge=10, le=600)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|1:1|16:9)$")
    caption_style: str = Field(default="bold_karaoke")
    custom_prompt: str | None = Field(default=None, description="Optional custom prompt to guide clip selection")
    time_range_start: float | None = Field(default=None, description="Optional start time in seconds")
    time_range_end: float | None = Field(default=None, description="Optional end time in seconds")
