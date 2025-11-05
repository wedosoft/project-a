# Supabase Database Migration Verification

## 개요
이 문서는 로컬 마이그레이션 파일과 Supabase 데이터베이스 구조를 대조하기 위한 체크리스트입니다.

## Migration 002: Tenant Configs & Proposals

### 1. tenant_configs 테이블 ✓

**Supabase SQL Editor에서 실행하여 확인:**
```sql
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'tenant_configs'
ORDER BY ordinal_position;
```

**예상 결과:**
| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| id | uuid | NO | gen_random_uuid() |
| tenant_id | text | NO | - |
| platform | text | NO | - |
| embedding_enabled | boolean | YES | true |
| analysis_depth | text | YES | 'full' |
| llm_max_tokens | integer | YES | 1500 |
| created_at | timestamptz | YES | NOW() |
| updated_at | timestamptz | YES | NOW() |

**제약 조건 확인:**
```sql
-- Unique constraint on (tenant_id, platform)
SELECT conname, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'tenant_configs'::regclass;
```

**인덱스 확인:**
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'tenant_configs';
```

**체크 제약 확인:**
```sql
-- analysis_depth: 'full', 'summary', 'minimal'
-- llm_max_tokens: 500-8000 범위
```

### 2. proposals 테이블 ✓

**컬럼 확인:**
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'proposals'
ORDER BY ordinal_position;
```

**예상 컬럼 (17개):**
- id, tenant_id, ticket_id, proposal_version
- draft_response, field_updates (JSONB), reasoning, confidence, mode
- similar_cases (JSONB), kb_references (JSONB)
- status, approved_by, approved_at, rejection_reason
- analysis_time_ms, token_count, created_at

**인덱스 확인 (3개):**
```sql
-- idx_proposals_ticket ON (ticket_id, created_at DESC)
-- idx_proposals_status ON (tenant_id, status)
-- idx_proposals_tenant ON (tenant_id, created_at DESC)
```

**체크 제약:**
- proposal_version > 0
- confidence IN ('high', 'medium', 'low')
- mode IN ('synthesis', 'direct', 'fallback')
- status IN ('draft', 'approved', 'rejected', 'superseded')

### 3. approval_logs 테이블 ✓

**컬럼 확인:**
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'approval_logs'
ORDER BY ordinal_position;
```

**예상 컬럼 (5개):**
- id, proposal_id (FK), action, agent_email, feedback, created_at

**외래 키 확인:**
```sql
SELECT
    tc.constraint_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.table_name = 'approval_logs'
    AND tc.constraint_type = 'FOREIGN KEY';
```

**인덱스 확인 (2개):**
```sql
-- idx_approval_logs_proposal ON (proposal_id, created_at DESC)
-- idx_approval_logs_agent ON (agent_email, created_at DESC)
```

### 4. 트리거 확인 ✓

**updated_at 자동 업데이트 트리거:**
```sql
SELECT
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE event_object_table IN ('tenant_configs');
```

**예상 결과:**
- Trigger: `tenant_configs_updated_at`
- Event: BEFORE UPDATE
- Function: `update_updated_at_column()`

### 5. 샘플 데이터 확인

```sql
SELECT tenant_id, platform, embedding_enabled, analysis_depth, llm_max_tokens
FROM tenant_configs
WHERE tenant_id IN ('demo-tenant', 'privacy-tenant');
```

**예상 결과:**
- demo-tenant: embedding=true, depth=full, tokens=2000
- privacy-tenant: embedding=false, depth=summary, tokens=1500

---

## Migration 003: Row-Level Security

### 1. RLS 활성화 확인 ✓

```sql
SELECT
    tablename,
    rowsecurity
FROM pg_tables
WHERE tablename IN ('tenant_configs', 'proposals', 'approval_logs');
```

**예상 결과:** 모든 테이블 `rowsecurity = true`

### 2. RLS 함수 확인 ✓

**set_current_tenant() 함수:**
```sql
SELECT
    proname,
    prosrc,
    prosecdef
FROM pg_proc
WHERE proname = 'set_current_tenant';
```

**get_current_tenant() 함수:**
```sql
SELECT
    proname,
    prosrc
FROM pg_proc
WHERE proname = 'get_current_tenant';
```

### 3. RLS 정책 확인 ✓

**tenant_configs 정책 (2개):**
```sql
SELECT
    polname,
    polcmd,
    polroles::regrole[],
    qual,
    with_check
FROM pg_policy
WHERE polrelid = 'tenant_configs'::regclass;
```

**예상 정책:**
1. `tenant_configs_isolation` (authenticated role)
   - USING: `tenant_id = current_setting('app.current_tenant_id', true)`
2. `tenant_configs_service_role` (service_role)
   - USING: `true`, WITH CHECK: `true`

**proposals 정책 (2개):**
```sql
SELECT polname, polcmd, polroles::regrole[]
FROM pg_policy
WHERE polrelid = 'proposals'::regclass;
```

**예상 정책:**
1. `proposals_isolation` (authenticated)
2. `proposals_service_role` (service_role)

**approval_logs 정책 (2개):**
```sql
SELECT polname, polcmd, polroles::regrole[]
FROM pg_policy
WHERE polrelid = 'approval_logs'::regclass;
```

**예상 정책:**
1. `approval_logs_isolation` (authenticated) - proposal_id 기반 서브쿼리
2. `approval_logs_service_role` (service_role)

### 4. 권한 확인 ✓

```sql
-- 함수 실행 권한
SELECT
    routine_name,
    grantee,
    privilege_type
FROM information_schema.routine_privileges
WHERE routine_name IN ('set_current_tenant', 'get_current_tenant');
```

**예상 grantee:** authenticated, service_role

```sql
-- 테이블 권한
SELECT
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_name IN ('tenant_configs', 'proposals', 'approval_logs')
    AND grantee = 'authenticated';
```

**예상 권한:** SELECT, INSERT, UPDATE, DELETE

---

## RLS 동작 테스트

### 테스트 시나리오 1: demo-tenant 컨텍스트

```sql
-- 1. 테넌트 컨텍스트 설정
SELECT set_current_tenant('demo-tenant');

-- 2. tenant_configs 조회 (demo-tenant만 보여야 함)
SELECT tenant_id, platform FROM tenant_configs;

-- 3. proposals 조회 (demo-tenant만 보여야 함)
SELECT tenant_id, ticket_id FROM proposals;

-- 4. 현재 테넌트 확인
SELECT get_current_tenant();
```

### 테스트 시나리오 2: privacy-tenant 컨텍스트

```sql
-- 1. 컨텍스트 변경
SELECT set_current_tenant('privacy-tenant');

-- 2. tenant_configs 조회 (privacy-tenant만 보여야 함)
SELECT tenant_id, platform FROM tenant_configs;

-- 3. 다른 테넌트 데이터 접근 시도 (0 rows 반환되어야 함)
SELECT * FROM proposals WHERE tenant_id = 'demo-tenant';
```

### 테스트 시나리오 3: Service Role Bypass

```sql
-- Supabase Dashboard의 SQL Editor는 기본적으로 service_role 사용
-- 컨텍스트 설정 없이도 모든 데이터 조회 가능해야 함
SELECT tenant_id, COUNT(*)
FROM proposals
GROUP BY tenant_id;
```

---

## 불일치 발견 시 조치

### 테이블 구조 불일치
```sql
-- 로컬 마이그레이션 재실행
-- backend/migrations/002_tenant_and_proposals.sql 내용을 Supabase SQL Editor에 복사/실행
```

### RLS 정책 불일치
```sql
-- RLS 정책 삭제 후 재생성
DROP POLICY IF EXISTS tenant_configs_isolation ON tenant_configs;
DROP POLICY IF EXISTS tenant_configs_service_role ON tenant_configs;
-- ... (다른 정책들도 동일)

-- backend/migrations/003_rls_policies.sql 재실행
```

### 권한 불일치
```sql
-- 권한 재부여
GRANT EXECUTE ON FUNCTION set_current_tenant(TEXT) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION get_current_tenant() TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_configs TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON proposals TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON approval_logs TO authenticated;
```

---

## 체크리스트 요약

### Migration 002 ✓
- [ ] tenant_configs 테이블 구조
- [ ] proposals 테이블 구조
- [ ] approval_logs 테이블 구조
- [ ] 모든 인덱스 존재
- [ ] 모든 체크 제약 조건
- [ ] 외래 키 제약 (approval_logs → proposals)
- [ ] updated_at 트리거 동작
- [ ] 샘플 데이터 존재

### Migration 003 ✓
- [ ] RLS 활성화 (3개 테이블)
- [ ] set_current_tenant() 함수
- [ ] get_current_tenant() 함수
- [ ] tenant_configs RLS 정책 (2개)
- [ ] proposals RLS 정책 (2개)
- [ ] approval_logs RLS 정책 (2개)
- [ ] 함수 실행 권한
- [ ] 테이블 CRUD 권한
- [ ] RLS 동작 테스트 통과

---

## 참고 사항

### Supabase 특이사항
1. **Service Role vs Authenticated Role**
   - Supabase Dashboard SQL Editor: service_role 사용 (RLS bypass)
   - API 호출: authenticated role 사용 (RLS 적용)

2. **RLS 정책 우선순위**
   - service_role 정책이 항상 우선
   - authenticated 정책은 일반 사용자에게만 적용

3. **세션 변수**
   - `app.current_tenant_id`는 연결 단위로 관리
   - API 요청마다 `set_current_tenant()` 호출 필요
   - Repository 클래스의 `set_tenant_context()` 메서드가 담당

### 프로덕션 체크리스트
- [ ] 모든 마이그레이션 파일 Supabase에 적용 완료
- [ ] RLS 정책 동작 테스트 완료
- [ ] 샘플 데이터 삭제 또는 프로덕션 데이터로 교체
- [ ] 인덱스 성능 확인 (EXPLAIN ANALYZE)
- [ ] 백업 정책 설정
- [ ] 모니터링 설정
