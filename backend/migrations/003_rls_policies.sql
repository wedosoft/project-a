-- ==========================================
-- Migration 003: Row-Level Security Policies
-- ==========================================
-- Purpose: Implement tenant isolation via RLS
-- Dependencies: 002_tenant_and_proposals.sql
-- Author: AI Assistant POC
-- Date: 2025-11-05

-- ==========================================
-- 1. Enable RLS on Tables
-- ==========================================

ALTER TABLE tenant_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposal_logs ENABLE ROW LEVEL SECURITY;

-- ==========================================
-- 2. Tenant Context Management
-- ==========================================

-- Function to set current tenant context
CREATE OR REPLACE FUNCTION set_current_tenant(tenant_id_param TEXT)
RETURNS VOID AS $$
BEGIN
    -- Set session variable for RLS policies
    PERFORM set_config('app.current_tenant_id', tenant_id_param, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION set_current_tenant IS 'Sets tenant context for RLS policies. Call this before querying tenant-scoped data.';

-- Function to get current tenant context
CREATE OR REPLACE FUNCTION get_current_tenant()
RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_current_tenant IS 'Returns the current tenant_id from session context';

-- ==========================================
-- 3. RLS Policies for tenant_configs
-- ==========================================

-- Policy: Users can only access their tenant's config
CREATE POLICY tenant_configs_isolation ON tenant_configs
    FOR ALL
    TO authenticated
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Policy: Service role can access all (for admin operations)
CREATE POLICY tenant_configs_service_role ON tenant_configs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON POLICY tenant_configs_isolation ON tenant_configs IS 'Isolates tenant configs by tenant_id';

-- ==========================================
-- 4. RLS Policies for proposals
-- ==========================================

-- Policy: Users can only access their tenant's proposals
CREATE POLICY proposals_isolation ON proposals
    FOR ALL
    TO authenticated
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- Policy: Service role can access all
CREATE POLICY proposals_service_role ON proposals
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON POLICY proposals_isolation ON proposals IS 'Isolates proposals by tenant_id';

-- ==========================================
-- 5. RLS Policies for proposal_logs
-- ==========================================

-- Policy: Users can access logs for their tenant's proposals only
CREATE POLICY proposal_logs_isolation ON proposal_logs
    FOR ALL
    TO authenticated
    USING (
        proposal_id IN (
            SELECT id FROM proposals
            WHERE tenant_id = current_setting('app.current_tenant_id', true)
        )
    );

-- Policy: Service role can access all
CREATE POLICY proposal_logs_service_role ON proposal_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

COMMENT ON POLICY proposal_logs_isolation ON proposal_logs IS 'Isolates proposal logs via proposal tenant_id';

-- ==========================================
-- 6. Grant Permissions
-- ==========================================

-- Grant execute on tenant context functions
GRANT EXECUTE ON FUNCTION set_current_tenant(TEXT) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION get_current_tenant() TO authenticated, service_role;

-- Grant table access to authenticated users
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_configs TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON proposals TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON proposal_logs TO authenticated;

-- Service role already has full access via policies

-- ==========================================
-- 7. Verification Queries (for testing)
-- ==========================================

-- To verify RLS is working, run these queries after setting tenant context:
--
-- SELECT set_current_tenant('demo-tenant');
-- SELECT * FROM tenant_configs;  -- Should only show demo-tenant
-- SELECT * FROM proposals;       -- Should only show demo-tenant proposals
--
-- SELECT set_current_tenant('privacy-tenant');
-- SELECT * FROM tenant_configs;  -- Should only show privacy-tenant
--

-- ==========================================
-- Rollback Script (commented out)
-- ==========================================

-- To rollback this migration, run:
--
-- DROP POLICY IF EXISTS proposal_logs_service_role ON proposal_logs;
-- DROP POLICY IF EXISTS proposal_logs_isolation ON proposal_logs;
-- DROP POLICY IF EXISTS proposals_service_role ON proposals;
-- DROP POLICY IF EXISTS proposals_isolation ON proposals;
-- DROP POLICY IF EXISTS tenant_configs_service_role ON tenant_configs;
-- DROP POLICY IF EXISTS tenant_configs_isolation ON tenant_configs;
--
-- ALTER TABLE proposal_logs DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE proposals DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE tenant_configs DISABLE ROW LEVEL SECURITY;
--
-- DROP FUNCTION IF EXISTS get_current_tenant();
-- DROP FUNCTION IF EXISTS set_current_tenant(TEXT);
