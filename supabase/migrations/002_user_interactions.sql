-- ==============================================================================
-- Dr. Paper: Migration 002 - User Interactions & Cross-Device Reading State
-- Schema: dr_paper
-- Table: dr_paper.user_interactions
-- ==============================================================================

CREATE TABLE IF NOT EXISTS dr_paper.user_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'default',
    arxiv_id TEXT NOT NULL REFERENCES dr_paper.papers(arxiv_id) ON DELETE CASCADE,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    is_bookmarked BOOLEAN NOT NULL DEFAULT FALSE,
    is_starred BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, arxiv_id)
);

-- Enable Row Level Security (RLS)
ALTER TABLE dr_paper.user_interactions ENABLE ROW LEVEL SECURITY;

-- Allow public read access to interactions via anon key
DROP POLICY IF EXISTS "Allow public select on user_interactions" ON dr_paper.user_interactions;
CREATE POLICY "Allow public select on user_interactions"
    ON dr_paper.user_interactions FOR SELECT
    USING (true);

-- Allow public upsert/insert/update on user_interactions via anon key
DROP POLICY IF EXISTS "Allow public upsert on user_interactions" ON dr_paper.user_interactions;
CREATE POLICY "Allow public upsert on user_interactions"
    ON dr_paper.user_interactions FOR ALL
    USING (true)
    WITH CHECK (true);

-- Grant access on user_interactions table
GRANT ALL ON dr_paper.user_interactions TO anon, authenticated, service_role;
