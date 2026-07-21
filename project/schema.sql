-- Ship Delivery Intelligence schema (safe, idempotent)
-- main.py also applies the same non-destructive migrations on startup.
CREATE TABLE IF NOT EXISTS public.projects (
    dedupe_key TEXT PRIMARY KEY,
    identity_key TEXT,
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    company TEXT,
    announcement_no TEXT,
    contract_no TEXT,
    project_no TEXT,
    region TEXT,
    order_value TEXT,
    currency TEXT,
    registered_at TEXT,
    contract_date TEXT,
    delivery_date TEXT,
    shipyard TEXT,
    stage TEXT NOT NULL DEFAULT 'LEAD',
    source_type TEXT,
    source_service TEXT,
    source_operation TEXT,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    verification_confidence INTEGER NOT NULL DEFAULT 0,
    verification_checked_at TIMESTAMPTZ,
    sales_category TEXT NOT NULL DEFAULT 'REFERENCE',
    sales_score INTEGER NOT NULL DEFAULT 0,
    classification_version INTEGER NOT NULL DEFAULT 0,
    matched_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    keyword_text TEXT,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner TEXT,
    next_action_date TEXT,
    next_action TEXT,
    notes TEXT,
    favorite BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS identity_key TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'LEAD';
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS verification_confidence INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS verification_checked_at TIMESTAMPTZ;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS sales_category TEXT NOT NULL DEFAULT 'REFERENCE';
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS sales_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS classification_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS owner TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS next_action_date TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS next_action TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS favorite BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS public.collector_run_logs (
    id TEXT PRIMARY KEY,
    collector_name TEXT NOT NULL,
    status TEXT NOT NULL,
    collected_count INTEGER NOT NULL DEFAULT 0,
    response_ms NUMERIC NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_identity ON public.projects(identity_key);
CREATE INDEX IF NOT EXISTS idx_projects_stage ON public.projects(stage);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON public.projects(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_next_action ON public.projects(next_action_date);
CREATE INDEX IF NOT EXISTS idx_projects_announcement ON public.projects(announcement_no);
CREATE INDEX IF NOT EXISTS idx_projects_sales_focus ON public.projects(sales_category, sales_score DESC);
