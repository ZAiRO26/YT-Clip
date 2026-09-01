"""
ClipForge AI — SQLAlchemy ORM Models
Maps to the Postgres schema defined in migrations/001_initial_schema.sql
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    campaign_briefs = relationship("CampaignBrief", back_populates="owner", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class CampaignBrief(Base):
    __tablename__ = "campaign_briefs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    brief_json = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    owner = relationship("User", back_populates="campaign_briefs")
    projects = relationship("Project", back_populates="campaign_brief")

    __table_args__ = (
        Index("idx_campaign_briefs_owner", "owner_id"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(Text, nullable=False)
    source_value = Column(Text, nullable=False)
    campaign_brief_id = Column(UUID(as_uuid=True), ForeignKey("campaign_briefs.id", ondelete="SET NULL"), nullable=True)
    clip_count = Column(Integer, nullable=False, server_default=text("5"))
    min_length_sec = Column(Integer, nullable=False, server_default=text("20"))
    max_length_sec = Column(Integer, nullable=False, server_default=text("60"))
    aspect_ratio = Column(Text, nullable=False, server_default=text("'9:16'"))
    caption_style = Column(Text, nullable=False, server_default=text("'bold_karaoke'"))
    status = Column(Text, nullable=False, server_default=text("'queued'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    owner = relationship("User", back_populates="projects")
    campaign_brief = relationship("CampaignBrief", back_populates="projects")
    clips = relationship("Clip", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("source_type IN ('youtube_url', 'local_folder')", name="ck_projects_source_type"),
        CheckConstraint("aspect_ratio IN ('9:16', '1:1', '16:9')", name="ck_projects_aspect_ratio"),
        CheckConstraint(
            "status IN ('queued', 'downloading', 'transcribing', 'selecting', 'encoding', 'captioning', 'done', 'failed')",
            name="ck_projects_status",
        ),
        Index("idx_projects_owner_created", "owner_id", created_at.desc()),
    )


class Clip(Base):
    __tablename__ = "clips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    start_sec = Column(Float, nullable=False)
    end_sec = Column(Float, nullable=False)
    score = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    file_url = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    review_status = Column(Text, nullable=False, server_default=text("'pending'"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    project = relationship("Project", back_populates="clips")

    __table_args__ = (
        CheckConstraint("review_status IN ('pending', 'approved', 'rejected')", name="ck_clips_review_status"),
        Index("idx_clips_project_review", "project_id", "review_status"),
    )


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    stage = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationships
    project = relationship("Project", back_populates="jobs")

    __table_args__ = (
        CheckConstraint("stage IN ('download', 'transcribe', 'select', 'crop', 'caption')", name="ck_jobs_stage"),
        CheckConstraint("status IN ('pending', 'running', 'success', 'failed', 'retrying')", name="ck_jobs_status"),
        Index("idx_jobs_project_stage", "project_id", "stage"),
    )
