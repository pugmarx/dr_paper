-- ==============================================================================
-- Dr. Paper: Supabase PostgreSQL Schema Migration (Dedicated Schema: dr_paper)
-- Supports Human-in-the-Loop Editorial Moderation & Weekly Curation
-- ==============================================================================

-- 1. Create dedicated schema
create schema if not exists dr_paper;

-- Grant usage on the schema to standard Supabase roles
grant usage on schema dr_paper to anon, authenticated, service_role;

-- 2. Papers table inside dr_paper schema
create table if not exists dr_paper.papers (
    id uuid primary key default gen_random_uuid(),
    arxiv_id text unique not null,
    title text not null,
    authors text[] not null default '{}',
    summary text not null,
    structured_analysis jsonb not null default '{}',
    topic text not null default 'General',
    score numeric(4,2) default 0.0,
    pdf_url text,
    hf_url text,
    status text not null default 'draft', -- 'draft', 'published', 'rejected'
    is_featured boolean not null default false,
    editorial_notes text,
    curated_source text not null default 'arxiv', -- 'arxiv', 'huggingface', 'lastweekinai', 'manual'
    published_edition text, -- e.g. '2026-W36'
    published_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- 3. Pipeline Runs / Observability table inside dr_paper schema
create table if not exists dr_paper.runs (
    id uuid primary key default gen_random_uuid(),
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    status text not null default 'running', -- 'running', 'success', 'failed'
    papers_fetched integer default 0,
    papers_added integer default 0,
    papers_skipped integer default 0,
    duration_ms integer default 0,
    llm_calls integer default 0,
    error_message text,
    metadata jsonb default '{}'
);

-- 4. Create Indexes for query performance
create index if not exists idx_dr_paper_papers_status on dr_paper.papers (status);
create index if not exists idx_dr_paper_papers_published_at on dr_paper.papers (published_at desc);
create index if not exists idx_dr_paper_papers_score on dr_paper.papers (score desc);
create index if not exists idx_dr_paper_papers_arxiv_id on dr_paper.papers (arxiv_id);
create index if not exists idx_dr_paper_runs_started_at on dr_paper.runs (started_at desc);

-- 5. Row Level Security (RLS)
alter table dr_paper.papers enable row level security;
alter table dr_paper.runs enable row level security;

-- Drop existing policies if re-running
drop policy if exists "Public read published papers" on dr_paper.papers;
drop policy if exists "Public read papers" on dr_paper.papers;
drop policy if exists "Public read runs" on dr_paper.runs;
drop policy if exists "Service role manage papers" on dr_paper.papers;
drop policy if exists "Service role manage runs" on dr_paper.runs;

-- PUBLIC READ POLICY: Public website can ONLY read papers that are approved & published!
create policy "Public read published papers" on dr_paper.papers
    for select using (status = 'published');

create policy "Public read runs" on dr_paper.runs
    for select using (true);

-- SERVICE ROLE POLICIES: Full management for ingestion and review CLI
create policy "Service role manage papers" on dr_paper.papers
    for all using (auth.role() = 'service_role');

create policy "Service role manage runs" on dr_paper.runs
    for all using (auth.role() = 'service_role');

-- 6. User Interactions & Reading State table
create table if not exists dr_paper.user_interactions (
    id uuid primary key default gen_random_uuid(),
    user_id text not null default 'default',
    arxiv_id text not null references dr_paper.papers(arxiv_id) on delete cascade,
    is_read boolean not null default false,
    is_bookmarked boolean not null default false,
    is_starred boolean not null default false,
    read_at timestamptz,
    updated_at timestamptz default now(),
    unique (user_id, arxiv_id)
);

create index if not exists idx_dr_paper_interactions_user on dr_paper.user_interactions (user_id);
create index if not exists idx_dr_paper_interactions_arxiv on dr_paper.user_interactions (arxiv_id);

alter table dr_paper.user_interactions enable row level security;

drop policy if exists "Allow public select on user_interactions" on dr_paper.user_interactions;
create policy "Allow public select on user_interactions"
    on dr_paper.user_interactions for select using (true);

drop policy if exists "Allow public upsert on user_interactions" on dr_paper.user_interactions;
create policy "Allow public upsert on user_interactions"
    on dr_paper.user_interactions for all using (true) with check (true);

-- 7. Role Grants
grant select on dr_paper.papers to anon, authenticated, service_role;
grant select on dr_paper.runs to anon, authenticated, service_role;
grant all on dr_paper.user_interactions to anon, authenticated, service_role;
grant all on dr_paper.papers to service_role;
grant all on dr_paper.runs to service_role;

