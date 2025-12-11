-- ============================================================================
-- AI Contact Center OS - Initial Database Schema
-- Migration: 001_initial_schema.sql
-- Created: 2025-10-31
-- Description: Initial schema for issue blocks, KB blocks, and approval logs
-- ============================================================================

-- ============================================================================
-- TABLES
-- ============================================================================

-- Issue Blocks Table (티켓 지식 = 경험)
-- 티켓에서 추출한 증상, 원인, 해결책 정보 저장
CREATE TABLE IF NOT EXISTS issue_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    block_type TEXT CHECK (block_type IN ('symptom', 'cause', 'resolution')),
    product TEXT,
    component TEXT,
    error_code TEXT,
    content TEXT NOT NULL,
    meta JSONB,
    embedding_id TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE issue_blocks IS '티켓에서 추출한 증상/원인/해결책 블록';
COMMENT ON COLUMN issue_blocks.block_type IS 'symptom(증상), cause(원인), resolution(해결책)';
COMMENT ON COLUMN issue_blocks.content IS '추출된 핵심 문장/요약 (최대 512~1024자)';
COMMENT ON COLUMN issue_blocks.meta IS '추가 메타데이터 (언어, 태그 등)';
COMMENT ON COLUMN issue_blocks.embedding_id IS 'Legacy 벡터 ID 참조';

-- KB Blocks Table (정책/절차 = 규범)
-- 표준 절차, 정책, 제약사항 저장
CREATE TABLE IF NOT EXISTS kb_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    article_id TEXT,
    intent TEXT,
    step TEXT,
    constraint TEXT,
    example TEXT,
    meta JSONB,
    embedding_id TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kb_blocks IS '표준 절차 및 정책 문서 블록';
COMMENT ON COLUMN kb_blocks.intent IS '의도/목적 설명';
COMMENT ON COLUMN kb_blocks.step IS '절차 단계';
COMMENT ON COLUMN kb_blocks.constraint IS '제약사항 및 주의점';
COMMENT ON COLUMN kb_blocks.example IS '예시';

-- Approval Logs Table (승인 이력)
-- AI 제안 및 상담원 승인 이력 저장
CREATE TABLE IF NOT EXISTS approval_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    draft_response TEXT,
    final_response TEXT,
    field_updates JSONB,
    approval_status TEXT CHECK (approval_status IN ('approved', 'modified', 'rejected')),
    agent_id TEXT,
    feedback_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE approval_logs IS 'AI 제안 및 상담원 승인 이력';
COMMENT ON COLUMN approval_logs.draft_response IS 'AI가 제안한 초안';
COMMENT ON COLUMN approval_logs.final_response IS '상담원이 최종 승인/수정한 응답';
COMMENT ON COLUMN approval_logs.field_updates IS '티켓 필드 업데이트 내역 (카테고리, 태그, 우선순위 등)';
COMMENT ON COLUMN approval_logs.approval_status IS 'approved(승인), modified(수정), rejected(거부)';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Issue Blocks Indexes
CREATE INDEX IF NOT EXISTS idx_issue_blocks_tenant_id ON issue_blocks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_issue_blocks_ticket_id ON issue_blocks(ticket_id);
CREATE INDEX IF NOT EXISTS idx_issue_blocks_block_type ON issue_blocks(block_type);
CREATE INDEX IF NOT EXISTS idx_issue_blocks_product ON issue_blocks(product);
CREATE INDEX IF NOT EXISTS idx_issue_blocks_component ON issue_blocks(component);
CREATE INDEX IF NOT EXISTS idx_issue_blocks_error_code ON issue_blocks(error_code);
CREATE INDEX IF NOT EXISTS idx_issue_blocks_created_at ON issue_blocks(created_at DESC);

-- KB Blocks Indexes
CREATE INDEX IF NOT EXISTS idx_kb_blocks_tenant_id ON kb_blocks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_kb_blocks_article_id ON kb_blocks(article_id);
CREATE INDEX IF NOT EXISTS idx_kb_blocks_created_at ON kb_blocks(created_at DESC);

-- Approval Logs Indexes
CREATE INDEX IF NOT EXISTS idx_approval_logs_tenant_id ON approval_logs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_approval_logs_ticket_id ON approval_logs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_approval_logs_status ON approval_logs(approval_status);
CREATE INDEX IF NOT EXISTS idx_approval_logs_created_at ON approval_logs(created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE issue_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_blocks ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policy for issue_blocks
-- 각 tenant는 자신의 데이터만 접근 가능
DROP POLICY IF EXISTS "Tenant isolation for issue_blocks" ON issue_blocks;
CREATE POLICY "Tenant isolation for issue_blocks" ON issue_blocks
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));

-- RLS Policy for kb_blocks
DROP POLICY IF EXISTS "Tenant isolation for kb_blocks" ON kb_blocks;
CREATE POLICY "Tenant isolation for kb_blocks" ON kb_blocks
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));

-- RLS Policy for approval_logs
DROP POLICY IF EXISTS "Tenant isolation for approval_logs" ON approval_logs;
CREATE POLICY "Tenant isolation for approval_logs" ON approval_logs
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));

-- ============================================================================
-- SAMPLE DATA (Optional - for development/testing)
-- ============================================================================

-- Set tenant context for sample data
-- In production, this would be set by the application
-- SET app.current_tenant_id = 'demo-tenant';

-- Sample issue_blocks
INSERT INTO issue_blocks (tenant_id, ticket_id, block_type, product, component, content, meta)
VALUES
    ('demo-tenant', 'TICKET-001', 'symptom', 'Product A', 'Login', '사용자가 로그인 시 "Invalid credentials" 에러 발생', '{"lang": "ko", "tags": ["auth", "error"]}'),
    ('demo-tenant', 'TICKET-001', 'cause', 'Product A', 'Login', 'JWT 토큰 만료 시간이 너무 짧게 설정됨 (5분)', '{"lang": "ko", "tags": ["jwt", "config"]}'),
    ('demo-tenant', 'TICKET-001', 'resolution', 'Product A', 'Login', 'JWT 만료 시간을 30분으로 연장하고 refresh token 구현', '{"lang": "ko", "tags": ["solution", "jwt"]}'),
    ('demo-tenant', 'TICKET-002', 'symptom', 'Product A', 'API', 'API 호출 시 504 Gateway Timeout 발생', '{"lang": "ko", "tags": ["api", "performance"]}'),
    ('demo-tenant', 'TICKET-002', 'cause', 'Product A', 'API', '데이터베이스 쿼리 최적화 부족으로 응답 시간 초과', '{"lang": "ko", "tags": ["database", "performance"]}'),
    ('demo-tenant', 'TICKET-002', 'resolution', 'Product A', 'API', '인덱스 추가 및 쿼리 최적화로 응답 시간 3초 → 300ms 단축', '{"lang": "ko", "tags": ["optimization"]}')
ON CONFLICT DO NOTHING;

-- Sample kb_blocks
INSERT INTO kb_blocks (tenant_id, article_id, intent, step, constraint, example, meta)
VALUES
    ('demo-tenant', 'KB-AUTH-001', '로그인 문제 해결', '1. JWT 설정 확인\n2. 토큰 만료 시간 검증\n3. Refresh token 구현 확인', 'JWT 만료 시간은 최소 15분 이상', 'JWT_EXPIRATION=30m', '{"category": "authentication", "lang": "ko"}'),
    ('demo-tenant', 'KB-AUTH-002', '비밀번호 재설정', '1. 이메일 인증\n2. 임시 비밀번호 발급\n3. 강제 변경 유도', '비밀번호는 8자 이상, 특수문자 포함', 'Temp123!@#', '{"category": "authentication", "lang": "ko"}'),
    ('demo-tenant', 'KB-PERF-001', 'API 성능 최적화', '1. 쿼리 분석\n2. 인덱스 추가\n3. 캐싱 적용\n4. 부하 테스트', '응답 시간 3초 이하 유지', 'CREATE INDEX idx_user_email ON users(email);', '{"category": "performance", "lang": "ko"}')
ON CONFLICT DO NOTHING;

-- Sample approval_logs
INSERT INTO approval_logs (tenant_id, ticket_id, draft_response, final_response, field_updates, approval_status, agent_id, feedback_notes)
VALUES
    ('demo-tenant', 'TICKET-001',
     'JWT 토큰 만료 시간을 확인하고 연장하는 것을 권장합니다. 현재 설정이 5분으로 너무 짧아 자주 재로그인이 필요합니다.',
     'JWT 토큰 만료 시간을 30분으로 연장하고, refresh token을 구현하여 사용자 경험을 개선하였습니다.',
     '{"category": "Technical Issue", "priority": "High", "tags": ["authentication", "jwt"]}',
     'approved', 'agent-001', '제안 내용이 정확하고 해결책이 명확함'),
    ('demo-tenant', 'TICKET-002',
     '데이터베이스 쿼리를 최적화하여 API 응답 시간을 개선할 수 있습니다.',
     '데이터베이스 인덱스를 추가하고 쿼리를 최적화하여 API 응답 시간을 3초에서 300ms로 단축하였습니다.',
     '{"category": "Performance", "priority": "High", "tags": ["database", "optimization"]}',
     'modified', 'agent-002', '구체적인 수치와 해결 방법 추가')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify table creation
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name IN ('issue_blocks', 'kb_blocks', 'approval_logs');

-- Verify RLS policies
-- SELECT tablename, policyname FROM pg_policies
-- WHERE tablename IN ('issue_blocks', 'kb_blocks', 'approval_logs');

-- Count records
-- SELECT
--     (SELECT COUNT(*) FROM issue_blocks) as issue_blocks_count,
--     (SELECT COUNT(*) FROM kb_blocks) as kb_blocks_count,
--     (SELECT COUNT(*) FROM approval_logs) as approval_logs_count;
