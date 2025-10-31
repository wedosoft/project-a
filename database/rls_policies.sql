-- Enable Row Level Security on all tables
ALTER TABLE issue_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_logs ENABLE ROW LEVEL SECURITY;

-- issue_blocks policies
CREATE POLICY "issue_blocks_select_policy" ON issue_blocks
  FOR SELECT
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "issue_blocks_insert_policy" ON issue_blocks
  FOR INSERT
  TO authenticated
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "issue_blocks_update_policy" ON issue_blocks
  FOR UPDATE
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'))
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "issue_blocks_delete_policy" ON issue_blocks
  FOR DELETE
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "issue_blocks_service_role_policy" ON issue_blocks
  FOR ALL
  TO service_role
  USING (true);

-- kb_blocks policies
CREATE POLICY "kb_blocks_select_policy" ON kb_blocks
  FOR SELECT
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "kb_blocks_insert_policy" ON kb_blocks
  FOR INSERT
  TO authenticated
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "kb_blocks_update_policy" ON kb_blocks
  FOR UPDATE
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'))
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "kb_blocks_delete_policy" ON kb_blocks
  FOR DELETE
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "kb_blocks_service_role_policy" ON kb_blocks
  FOR ALL
  TO service_role
  USING (true);

-- approval_logs policies
CREATE POLICY "approval_logs_select_policy" ON approval_logs
  FOR SELECT
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "approval_logs_insert_policy" ON approval_logs
  FOR INSERT
  TO authenticated
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "approval_logs_update_policy" ON approval_logs
  FOR UPDATE
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'))
  WITH CHECK (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "approval_logs_delete_policy" ON approval_logs
  FOR DELETE
  TO authenticated
  USING (tenant_id = (auth.jwt() ->> 'tenant_id'));

CREATE POLICY "approval_logs_service_role_policy" ON approval_logs
  FOR ALL
  TO service_role
  USING (true);
