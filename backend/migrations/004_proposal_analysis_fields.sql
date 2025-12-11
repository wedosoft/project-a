-- 004_proposal_analysis_fields.sql
-- Adds analysis metadata fields to proposals for status polling/UI.

ALTER TABLE proposals
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS intent TEXT,
    ADD COLUMN IF NOT EXISTS sentiment TEXT,
    ADD COLUMN IF NOT EXISTS field_reasons JSONB;
