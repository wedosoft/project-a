-- ==========================================
-- Migration 002: Tenant Configs & Proposals
-- ==========================================
-- Purpose: Add tenant configuration and AI proposal tracking
-- Dependencies: 001_initial_schema.sql
-- Author: AI Assistant POC
-- Date: 2025-11-05

-- ==========================================
-- 1. Tenant Configurations Table
-- ==========================================

CREATE TABLE IF NOT EXISTS tenant_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'freshdesk', 'zendesk', 'intercom'

    -- AI Configuration
    embedding_enabled BOOLEAN DEFAULT true,
    analysis_depth TEXT DEFAULT 'full' CHECK (analysis_depth IN ('full', 'summary', 'minimal')),
    llm_max_tokens INTEGER DEFAULT 1500 CHECK (llm_max_tokens BETWEEN 500 AND 8000),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    UNIQUE(tenant_id, platform)
);

-- Index for fast tenant lookups
CREATE INDEX IF NOT EXISTS idx_tenant_configs_lookup
ON tenant_configs(tenant_id, platform);

-- Comments
COMMENT ON TABLE tenant_configs IS 'Tenant-specific AI assistant configuration';
COMMENT ON COLUMN tenant_configs.embedding_enabled IS 'Enable/disable embedding-based search (privacy control)';
COMMENT ON COLUMN tenant_configs.analysis_depth IS 'Analysis depth: full (complete), summary (key points), minimal (brief)';
COMMENT ON COLUMN tenant_configs.llm_max_tokens IS 'Maximum tokens for LLM responses';

-- ==========================================
-- 2. Proposals Table
-- ==========================================

CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    proposal_version INTEGER DEFAULT 1 CHECK (proposal_version > 0),

    -- Proposal Content
    draft_response TEXT NOT NULL,
    field_updates JSONB,
    reasoning TEXT,
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    mode TEXT CHECK (mode IN ('synthesis', 'direct', 'fallback')),

    -- References (search results)
    similar_cases JSONB,
    kb_references JSONB,

    -- Status Tracking
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected', 'superseded')),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Metadata
    analysis_time_ms INTEGER,
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_proposals_ticket
ON proposals(ticket_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_proposals_status
ON proposals(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_proposals_tenant
ON proposals(tenant_id, created_at DESC);

-- Comments
COMMENT ON TABLE proposals IS 'AI-generated ticket resolution proposals with version tracking';
COMMENT ON COLUMN proposals.mode IS 'Generation mode: synthesis (search-based), direct (no search), fallback (search failed)';
COMMENT ON COLUMN proposals.status IS 'Proposal lifecycle: draft → approved/rejected/superseded';
COMMENT ON COLUMN proposals.proposal_version IS 'Version number for refinement tracking';

-- ==========================================
-- 3. Proposal Logs Table (Renamed from approval_logs to avoid conflict with 001)
-- ==========================================

CREATE TABLE IF NOT EXISTS proposal_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,

    -- Action Details
    action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'refine')),
    agent_email TEXT,
    feedback TEXT,

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for audit trail queries
CREATE INDEX IF NOT EXISTS idx_proposal_logs_proposal
ON proposal_logs(proposal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_proposal_logs_agent
ON proposal_logs(agent_email, created_at DESC);

-- Comments
COMMENT ON TABLE proposal_logs IS 'Audit trail for all proposal actions';
COMMENT ON COLUMN proposal_logs.action IS 'Action taken: approve, reject, or refine';
COMMENT ON COLUMN proposal_logs.agent_email IS 'Email of the support agent who took the action';

-- ==========================================
-- 4. Sample Data
-- ==========================================

INSERT INTO tenant_configs (tenant_id, platform, embedding_enabled, analysis_depth, llm_max_tokens)
VALUES
    ('demo-tenant', 'freshdesk', true, 'full', 2000),
    ('privacy-tenant', 'freshdesk', false, 'summary', 1500)
ON CONFLICT (tenant_id, platform) DO NOTHING;

-- ==========================================
-- 5. Updated_at Triggers
-- ==========================================

-- Trigger for tenant_configs updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tenant_configs_updated_at
    BEFORE UPDATE ON tenant_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON FUNCTION update_updated_at_column IS 'Automatically updates updated_at timestamp on row modification';

-- ==========================================
-- Rollback Script (commented out)
-- ==========================================

-- To rollback this migration, run:
--
-- DROP TRIGGER IF EXISTS tenant_configs_updated_at ON tenant_configs;
-- DROP FUNCTION IF EXISTS update_updated_at_column();
-- DROP TABLE IF EXISTS proposal_logs CASCADE;
-- DROP TABLE IF EXISTS proposals CASCADE;
-- DROP TABLE IF EXISTS tenant_configs CASCADE;
