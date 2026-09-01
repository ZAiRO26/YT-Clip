-- ============================================
-- ClipForge AI — Initial Schema Migration
-- Per Backend Schema section 05 of context.md
-- ============================================
-- Run against Supabase Postgres (or any Postgres 16+ instance)

-- Enable UUID extension (Supabase has this by default, but be safe)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- 1. USERS
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- 2. CAMPAIGN BRIEFS
-- ============================================
CREATE TABLE IF NOT EXISTS campaign_briefs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    brief_json  JSONB NOT NULL DEFAULT '{}'::jsonb,  -- tone, required mentions, banned topics, brand rules
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- 3. PROJECTS
-- ============================================
CREATE TABLE IF NOT EXISTS projects (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_type       TEXT NOT NULL CHECK (source_type IN ('youtube_url', 'local_folder')),
    source_value      TEXT NOT NULL,
    campaign_brief_id UUID REFERENCES campaign_briefs(id) ON DELETE SET NULL,
    clip_count        INT NOT NULL DEFAULT 5,
    min_length_sec    INT NOT NULL DEFAULT 20,
    max_length_sec    INT NOT NULL DEFAULT 60,
    aspect_ratio      TEXT NOT NULL DEFAULT '9:16' CHECK (aspect_ratio IN ('9:16', '1:1', '16:9')),
    caption_style     TEXT NOT NULL DEFAULT 'bold_karaoke',
    status            TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
                          'queued', 'downloading', 'transcribing', 'selecting',
                          'encoding', 'captioning', 'done', 'failed'
                      )),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- 4. CLIPS
-- ============================================
CREATE TABLE IF NOT EXISTS clips (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    start_sec       FLOAT NOT NULL,
    end_sec         FLOAT NOT NULL,
    score           FLOAT,                          -- LLM-assigned relevance score vs brief
    reasoning       TEXT,                           -- LLM reasoning for this clip selection
    file_url        TEXT,                           -- R2 storage path (null until encoding completes)
    thumbnail_url   TEXT,                           -- R2 path for thumbnail
    review_status   TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- 5. JOBS (Celery task tracking)
-- ============================================
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage           TEXT NOT NULL CHECK (stage IN ('download', 'transcribe', 'select', 'crop', 'caption')),
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'success', 'failed', 'retrying')),
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================
-- 6. INDEXES (per Backend Schema section 05)
-- ============================================
CREATE INDEX IF NOT EXISTS idx_projects_owner_created
    ON projects(owner_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_clips_project_review
    ON clips(project_id, review_status);

CREATE INDEX IF NOT EXISTS idx_jobs_project_stage
    ON jobs(project_id, stage);

CREATE INDEX IF NOT EXISTS idx_campaign_briefs_owner
    ON campaign_briefs(owner_id);

-- ============================================
-- 7. ROW-LEVEL SECURITY (per Backend Schema section 05)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_briefs ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE clips ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

-- Users: can only read/write their own row
CREATE POLICY users_own_row ON users
    FOR ALL USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Campaign briefs: owner_id = auth.uid()
CREATE POLICY campaign_briefs_owner ON campaign_briefs
    FOR ALL USING (owner_id = auth.uid())
    WITH CHECK (owner_id = auth.uid());

-- Projects: owner_id = auth.uid()
CREATE POLICY projects_owner ON projects
    FOR ALL USING (owner_id = auth.uid())
    WITH CHECK (owner_id = auth.uid());

-- Clips: must belong to a project owned by auth.uid()
CREATE POLICY clips_via_project ON clips
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = clips.project_id
              AND projects.owner_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = clips.project_id
              AND projects.owner_id = auth.uid()
        )
    );

-- Jobs: must belong to a project owned by auth.uid()
CREATE POLICY jobs_via_project ON jobs
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = jobs.project_id
              AND projects.owner_id = auth.uid()
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = jobs.project_id
              AND projects.owner_id = auth.uid()
        )
    );

-- ============================================
-- 8. SERVICE ROLE BYPASS
-- ============================================
-- The backend (FastAPI) connects as service_role which bypasses RLS.
-- This is intentional — the backend handles auth checks in application code.
-- RLS policies above protect direct client-side access via Supabase JS SDK.

-- ============================================
-- 9. UPDATED_AT TRIGGER for jobs table
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER jobs_updated_at
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
