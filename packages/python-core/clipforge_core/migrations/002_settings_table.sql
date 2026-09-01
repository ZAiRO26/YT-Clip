-- Migration: Add Settings Table
-- Created: 2026-09-01 00:43:40

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RLS Policies
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;

-- For now, all authenticated users can read/write settings (this is a single-user self-hosted app)
CREATE POLICY "Enable all for authenticated users on settings" 
    ON settings FOR ALL 
    TO authenticated 
    USING (true) 
    WITH CHECK (true);

-- Also allow anon for local testing
CREATE POLICY "Enable all for anon on settings" 
    ON settings FOR ALL 
    TO anon 
    USING (true) 
    WITH CHECK (true);
