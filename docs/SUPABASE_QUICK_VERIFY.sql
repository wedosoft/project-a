-- ==========================================
-- Supabase 마이그레이션 검증 스크립트
-- ==========================================
-- 목적: 002, 003 마이그레이션이 올바르게 적용되었는지 빠르게 확인
-- 사용: Supabase SQL Editor에 복사하여 실행

-- ==========================================
-- 1. 테이블 존재 확인 (6개)
-- ==========================================

SELECT table_name,
       (SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = 'public' AND t.table_name = table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN (
    'issue_blocks',        -- 001
    'kb_blocks',           -- 001
    'approval_logs',       -- 001 (티켓 승인 이력)
    'tenant_configs',      -- 002
    'proposals',           -- 002
    'proposal_logs'        -- 002 (Proposal 액션 로그)
  )
ORDER BY table_name;

-- 예상 결과: 6개 테이블 모두 존재

-- ==========================================
-- 2. RLS 활성화 확인
-- ==========================================

SELECT
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables
WHERE tablename IN ('tenant_configs', 'proposals', 'proposal_logs')
ORDER BY tablename;

-- 예상 결과: 3개 테이블 모두 rls_enabled = true

-- ==========================================
-- 3. RLS 정책 개수 확인
-- ==========================================

SELECT
    polrelid::regclass as table_name,
    COUNT(*) as policy_count
FROM pg_policy
WHERE polrelid::regclass::text IN ('tenant_configs', 'proposals', 'proposal_logs')
GROUP BY polrelid
ORDER BY table_name;

-- 예상 결과:
-- tenant_configs: 2개 (isolation, service_role)
-- proposals: 2개
-- proposal_logs: 2개

-- ==========================================
-- 4. RLS 함수 존재 확인
-- ==========================================

SELECT
    proname as function_name,
    pg_get_functiondef(oid) LIKE '%app.current_tenant_id%' as uses_tenant_context
FROM pg_proc
WHERE proname IN ('set_current_tenant', 'get_current_tenant')
ORDER BY proname;

-- 예상 결과: 2개 함수 모두 존재

-- ==========================================
-- 5. 인덱스 확인
-- ==========================================

SELECT
    tablename,
    indexname
FROM pg_indexes
WHERE tablename IN ('tenant_configs', 'proposals', 'proposal_logs')
ORDER BY tablename, indexname;

-- 예상 결과:
-- tenant_configs: idx_tenant_configs_lookup + primary key
-- proposals: idx_proposals_ticket, idx_proposals_status, idx_proposals_tenant + primary key
-- proposal_logs: idx_proposal_logs_proposal, idx_proposal_logs_agent + primary key

-- ==========================================
-- 6. 샘플 데이터 확인
-- ==========================================

SELECT tenant_id, platform, embedding_enabled, analysis_depth, llm_max_tokens
FROM tenant_configs
WHERE tenant_id IN ('demo-tenant', 'privacy-tenant')
ORDER BY tenant_id;

-- 예상 결과:
-- demo-tenant: embedding=true, depth=full, tokens=2000
-- privacy-tenant: embedding=false, depth=summary, tokens=1500

-- ==========================================
-- 7. RLS 동작 테스트
-- ==========================================

-- 테스트 1: demo-tenant 컨텍스트
SELECT set_current_tenant('demo-tenant');
SELECT tenant_id FROM tenant_configs;  -- demo-tenant만 보여야 함

-- 테스트 2: privacy-tenant 컨텍스트
SELECT set_current_tenant('privacy-tenant');
SELECT tenant_id FROM tenant_configs;  -- privacy-tenant만 보여야 함

-- 테스트 3: 컨텍스트 확인
SELECT get_current_tenant();  -- 'privacy-tenant' 반환되어야 함

-- ==========================================
-- 8. 외래 키 확인
-- ==========================================

SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name = 'proposal_logs'
ORDER BY tc.table_name;

-- 예상 결과: proposal_logs.proposal_id → proposals.id

-- ==========================================
-- 9. 권한 확인
-- ==========================================

SELECT
    table_name,
    grantee,
    string_agg(privilege_type, ', ' ORDER BY privilege_type) as privileges
FROM information_schema.table_privileges
WHERE table_name IN ('tenant_configs', 'proposals', 'proposal_logs')
  AND grantee = 'authenticated'
GROUP BY table_name, grantee
ORDER BY table_name;

-- 예상 결과: SELECT, INSERT, UPDATE, DELETE 권한

-- ==========================================
-- 10. 종합 검증 요약
-- ==========================================

SELECT
    'Tables' as check_type,
    COUNT(*) as actual,
    6 as expected,
    CASE WHEN COUNT(*) = 6 THEN '✅ PASS' ELSE '❌ FAIL' END as status
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('issue_blocks', 'kb_blocks', 'approval_logs',
                     'tenant_configs', 'proposals', 'proposal_logs')

UNION ALL

SELECT
    'RLS Policies',
    COUNT(*),
    6,
    CASE WHEN COUNT(*) = 6 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM pg_policy
WHERE polrelid::regclass::text IN ('tenant_configs', 'proposals', 'proposal_logs')

UNION ALL

SELECT
    'RLS Functions',
    COUNT(*),
    2,
    CASE WHEN COUNT(*) = 2 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM pg_proc
WHERE proname IN ('set_current_tenant', 'get_current_tenant')

UNION ALL

SELECT
    'Sample Data',
    COUNT(*),
    2,
    CASE WHEN COUNT(*) = 2 THEN '✅ PASS' ELSE '❌ FAIL' END
FROM tenant_configs
WHERE tenant_id IN ('demo-tenant', 'privacy-tenant');

-- 예상 결과: 모든 항목 ✅ PASS
