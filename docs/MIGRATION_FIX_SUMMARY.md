# 마이그레이션 충돌 수정 완료

## 문제 요약
`approval_logs` 테이블이 두 개의 마이그레이션 파일에서 서로 다른 구조로 정의되어 충돌 발생:
- **001_initial_schema.sql**: 티켓 승인 이력 (ticket_id, approval_status, agent_id)
- **002_tenant_and_proposals.sql**: Proposal 액션 로그 (proposal_id, action, agent_email)

## 해결 방법
002의 `approval_logs`를 `proposal_logs`로 이름 변경하여 충돌 해소

---

## 수정된 파일

### 1. backend/migrations/002_tenant_and_proposals.sql ✅
**변경 사항:**
- 테이블명: `approval_logs` → `proposal_logs`
- 인덱스명: `idx_approval_logs_*` → `idx_proposal_logs_*`
- 주석 추가: "Renamed from approval_logs to avoid conflict with 001"
- Rollback 스크립트 업데이트

**라인 91-117:**
```sql
CREATE TABLE IF NOT EXISTS proposal_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'refine')),
    agent_email TEXT,
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proposal_logs_proposal
ON proposal_logs(proposal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_proposal_logs_agent
ON proposal_logs(agent_email, created_at DESC);
```

---

### 2. backend/migrations/003_rls_policies.sql ✅
**변경 사항:**
- RLS 활성화: `ALTER TABLE proposal_logs ENABLE ROW LEVEL SECURITY;`
- 정책명: `proposal_logs_isolation`, `proposal_logs_service_role`
- 권한 부여: `GRANT ... ON proposal_logs TO authenticated;`
- Rollback 스크립트 업데이트

**라인 15:**
```sql
ALTER TABLE proposal_logs ENABLE ROW LEVEL SECURITY;
```

**라인 81-102:**
```sql
CREATE POLICY proposal_logs_isolation ON proposal_logs
    FOR ALL
    TO authenticated
    USING (
        proposal_id IN (
            SELECT id FROM proposals
            WHERE tenant_id = current_setting('app.current_tenant_id', true)
        )
    );

CREATE POLICY proposal_logs_service_role ON proposal_logs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

---

### 3. backend/repositories/proposal_repository.py ✅
**변경 사항:**
- `log_approval_action()`: `self.client.table("proposal_logs")`
- `get_approval_logs()`: `self.client.table("proposal_logs")`

**라인 316-318:**
```python
result = self.client.table("proposal_logs").insert(
    log_data
).execute()
```

**라인 344-346:**
```python
result = self.client.table("proposal_logs").select("*").eq(
    "proposal_id", proposal_id
).order("created_at", desc=False).execute()
```

---

## Supabase 적용 방법

### 옵션 1: Supabase Dashboard SQL Editor (권장)

1. **Supabase Dashboard 접속**
   - https://supabase.com/dashboard
   - 프로젝트 선택

2. **SQL Editor에서 실행**
   ```sql
   -- 002 마이그레이션 (수정된 버전)
   -- backend/migrations/002_tenant_and_proposals.sql 전체 내용 복사 후 실행

   -- 003 마이그레이션 (수정된 버전)
   -- backend/migrations/003_rls_policies.sql 전체 내용 복사 후 실행
   ```

3. **검증**
   ```sql
   -- 테이블 확인
   SELECT table_name
   FROM information_schema.tables
   WHERE table_name IN ('tenant_configs', 'proposals', 'proposal_logs');

   -- 예상 결과: 3개 테이블 모두 존재

   -- RLS 정책 확인
   SELECT polrelid::regclass, polname
   FROM pg_policy
   WHERE polrelid::regclass::text = 'proposal_logs';

   -- 예상 결과: 2개 정책 (proposal_logs_isolation, proposal_logs_service_role)
   ```

---

### 옵션 2: Supabase CLI

```bash
# Docker Desktop 실행 필요
docker info

# 마이그레이션 적용
supabase db push

# 또는 원격 DB에 직접 적용
supabase db remote commit
```

---

## 최종 데이터베이스 구조

### 001_initial_schema.sql 테이블 (기존 유지)
```
✅ issue_blocks - 티켓에서 추출한 증상/원인/해결책 블록
✅ kb_blocks - 표준 절차 및 정책 문서 블록
✅ approval_logs - AI 제안 및 상담원 승인 이력 (티켓 단위)
```

### 002_tenant_and_proposals.sql 테이블 (신규 추가)
```
✅ tenant_configs - 테넌트별 AI 설정
✅ proposals - AI 제안 버전 관리
✅ proposal_logs - Proposal 액션 감사 추적 ← 이름 변경
```

### 전체 테이블 목록 (6개)
```
1. issue_blocks (001)
2. kb_blocks (001)
3. approval_logs (001) - 티켓 승인 이력
4. tenant_configs (002)
5. proposals (002)
6. proposal_logs (002) - Proposal 액션 로그
```

---

## 검증 체크리스트

### Migration 002 ✓
- [ ] `tenant_configs` 테이블 생성됨
- [ ] `proposals` 테이블 생성됨
- [ ] `proposal_logs` 테이블 생성됨 (approval_logs 아님!)
- [ ] 인덱스 3개 생성됨 (tenant_configs_lookup, proposals_ticket/status/tenant)
- [ ] 샘플 데이터 2개 삽입됨 (demo-tenant, privacy-tenant)
- [ ] updated_at 트리거 생성됨

### Migration 003 ✓
- [ ] RLS 활성화 (tenant_configs, proposals, proposal_logs)
- [ ] set_current_tenant() 함수 생성됨
- [ ] get_current_tenant() 함수 생성됨
- [ ] tenant_configs 정책 2개 생성됨
- [ ] proposals 정책 2개 생성됨
- [ ] proposal_logs 정책 2개 생성됨
- [ ] 권한 부여 완료 (함수 실행, 테이블 CRUD)

### RLS 동작 테스트 ✓
```sql
-- 1. 테넌트 컨텍스트 설정
SELECT set_current_tenant('demo-tenant');

-- 2. 데이터 조회 (demo-tenant만 보여야 함)
SELECT tenant_id FROM tenant_configs;
SELECT tenant_id FROM proposals;

-- 3. 다른 테넌트로 변경
SELECT set_current_tenant('privacy-tenant');
SELECT tenant_id FROM tenant_configs;  -- privacy-tenant만 보여야 함
```

---

## 코드 영향 분석

### ✅ 영향 없음 (자동 처리)
- **backend/routes/assist.py** - Repository 메서드만 호출하므로 변경 불필요
- **backend/routes/admin.py** - Repository 메서드만 호출하므로 변경 불필요

### ✅ 수정 완료
- **backend/repositories/proposal_repository.py** - 테이블명 변경
  - `log_approval_action()`: proposal_logs 사용
  - `get_approval_logs()`: proposal_logs 사용

### ⚠️ 향후 주의사항
- 새로운 코드에서 `approval_logs` 참조 시:
  - 001의 approval_logs (티켓 승인 이력)
  - 002의 proposal_logs (Proposal 액션 로그)
  - 명확히 구분하여 사용

---

## 롤백 방법

문제 발생 시 롤백:

```sql
-- RLS 정책 삭제
DROP POLICY IF EXISTS proposal_logs_service_role ON proposal_logs;
DROP POLICY IF EXISTS proposal_logs_isolation ON proposal_logs;
DROP POLICY IF EXISTS proposals_service_role ON proposals;
DROP POLICY IF EXISTS proposals_isolation ON proposals;
DROP POLICY IF EXISTS tenant_configs_service_role ON tenant_configs;
DROP POLICY IF EXISTS tenant_configs_isolation ON tenant_configs;

-- RLS 비활성화
ALTER TABLE proposal_logs DISABLE ROW LEVEL SECURITY;
ALTER TABLE proposals DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_configs DISABLE ROW LEVEL SECURITY;

-- 테이블 삭제
DROP TABLE IF EXISTS proposal_logs CASCADE;
DROP TABLE IF EXISTS proposals CASCADE;
DROP TABLE IF EXISTS tenant_configs CASCADE;

-- 함수 삭제
DROP FUNCTION IF EXISTS get_current_tenant();
DROP FUNCTION IF EXISTS set_current_tenant(TEXT);
DROP FUNCTION IF EXISTS update_updated_at_column();

-- 트리거 삭제
DROP TRIGGER IF EXISTS tenant_configs_updated_at ON tenant_configs;
```

---

## 요약

✅ **문제**: approval_logs 테이블 중복 정의
✅ **해결**: 002의 approval_logs → proposal_logs 이름 변경
✅ **수정 파일**: 3개 (002.sql, 003.sql, proposal_repository.py)
✅ **적용 방법**: Supabase SQL Editor에서 002, 003 마이그레이션 실행
✅ **검증**: 6개 테이블 모두 존재, RLS 정책 동작 확인
