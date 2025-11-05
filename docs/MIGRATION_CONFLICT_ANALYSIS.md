# 마이그레이션 충돌 분석

## 🚨 중요: approval_logs 테이블 중복 문제

### 문제 상황
두 개의 마이그레이션 파일에서 `approval_logs` 테이블을 서로 다른 구조로 정의:

---

## 001_initial_schema.sql의 approval_logs

```sql
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
```

**용도:** AI 제안 및 상담원 승인 이력
**컬럼:** tenant_id, ticket_id, draft_response, final_response, field_updates, approval_status, agent_id, feedback_notes

---

## 002_tenant_and_proposals.sql의 approval_logs

```sql
CREATE TABLE IF NOT EXISTS approval_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'refine')),
    agent_email TEXT,
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**용도:** Proposal 액션 감사 추적 (POC 구현)
**컬럼:** proposal_id (FK), action, agent_email, feedback

---

## 현재 Supabase 상태 추정

실제 Supabase에는 **001_initial_schema.sql이 먼저 적용**되어 있을 것:

```
✅ issue_blocks (001)
✅ kb_blocks (001)
✅ approval_logs (001 버전 - 구버전)
❌ tenant_configs (002 - 미적용)
❌ proposals (002 - 미적용)
❌ approval_logs (002 버전 - 충돌로 미적용)
```

---

## 해결 방안

### 옵션 1: 002의 approval_logs → proposal_logs 이름 변경 (권장)

**장점:**
- 001의 기존 approval_logs 유지
- 명확한 의미 구분 (ticket 승인 vs proposal 액션)
- 하위 호환성 유지

**작업:**
1. 002_tenant_and_proposals.sql 수정
   - `approval_logs` → `proposal_logs`
2. 003_rls_policies.sql 수정
   - `approval_logs` → `proposal_logs`
3. Repository 코드 수정
   - `ProposalRepository.log_approval_action()` → 테이블명 변경
4. Route 코드 수정
   - `backend/routes/assist.py`, `admin.py` → 테이블명 변경

---

### 옵션 2: 001의 approval_logs → ticket_approvals 이름 변경

**단점:**
- 기존 Supabase 데이터베이스 구조 변경 필요
- 다른 코드에서 approval_logs 참조 시 모두 수정 필요
- 하위 호환성 깨짐

**비권장 이유:** 이미 Supabase에 적용된 001을 변경하는 것은 위험

---

### 옵션 3: 테이블 통합 (복잡함)

두 테이블의 용도가 다르므로 통합은 부적절:
- 001: 티켓 단위 승인 이력
- 002: Proposal 단위 액션 로그

---

## 권장 조치: 옵션 1 적용

### 1단계: 마이그레이션 파일 수정

**002_tenant_and_proposals.sql:**
```sql
-- Line 94 변경
CREATE TABLE IF NOT EXISTS proposal_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'refine')),
    agent_email TEXT,
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes 변경
CREATE INDEX IF NOT EXISTS idx_proposal_logs_proposal
ON proposal_logs(proposal_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_proposal_logs_agent
ON proposal_logs(agent_email, created_at DESC);

-- Comments 변경
COMMENT ON TABLE proposal_logs IS 'Audit trail for all proposal actions';
COMMENT ON COLUMN proposal_logs.action IS 'Action taken: approve, reject, or refine';
COMMENT ON COLUMN proposal_logs.agent_email IS 'Email of the support agent who took the action';
```

**003_rls_policies.sql:**
```sql
-- Line 85-102 변경
ALTER TABLE proposal_logs ENABLE ROW LEVEL SECURITY;

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

COMMENT ON POLICY proposal_logs_isolation ON proposal_logs IS 'Isolates proposal logs via proposal tenant_id';

GRANT SELECT, INSERT, UPDATE, DELETE ON proposal_logs TO authenticated;
```

### 2단계: Repository 코드 수정

**backend/repositories/proposal_repository.py:**
```python
# Line 90-100 수정
async def log_approval_action(
    self,
    proposal_id: str,
    action: str,
    agent_email: Optional[str] = None,
    feedback: Optional[str] = None
) -> Dict:
    """Log approval action to proposal_logs table"""

    log_data = {
        "proposal_id": proposal_id,
        "action": action,
        "agent_email": agent_email,
        "feedback": feedback
    }

    result = self.client.table("proposal_logs").insert(log_data).execute()
    return result.data[0] if result.data else None
```

### 3단계: Route 코드 검토

**backend/routes/assist.py:**
- Line 335-339: `log_approval_action()` 호출 (변경 불필요, repository 내부에서 처리)
- Line 358-363: `log_approval_action()` 호출 (변경 불필요)
- Line 439-444: `log_approval_action()` 호출 (변경 불필요)

**backend/routes/admin.py:**
- Line 294: `get_stats()` - proposal_logs 사용 여부 확인 필요

---

## 최종 테이블 구조

### 적용 후 Supabase 테이블 목록:

```
✅ issue_blocks (001)
✅ kb_blocks (001)
✅ approval_logs (001) - 티켓 승인 이력
✅ tenant_configs (002)
✅ proposals (002)
✅ proposal_logs (002) - Proposal 액션 로그 ← 이름 변경
```

---

## 마이그레이션 적용 순서

1. **로컬에서 파일 수정**
   - 002_tenant_and_proposals.sql
   - 003_rls_policies.sql
   - proposal_repository.py

2. **Supabase SQL Editor에서 실행**
   ```sql
   -- 002 마이그레이션 (수정된 버전)
   -- tenant_configs, proposals, proposal_logs 생성

   -- 003 마이그레이션 (수정된 버전)
   -- RLS 정책 적용
   ```

3. **검증**
   ```sql
   SELECT table_name
   FROM information_schema.tables
   WHERE table_name IN ('approval_logs', 'proposal_logs', 'tenant_configs', 'proposals');

   -- 예상 결과: 4개 테이블 모두 존재
   ```

---

## 요약

**문제:** `approval_logs` 테이블이 001과 002에서 중복 정의
**원인:** 서로 다른 용도의 테이블이지만 같은 이름 사용
**해결:** 002의 `approval_logs` → `proposal_logs`로 이름 변경
**영향:** 3개 파일 수정 필요 (002, 003, proposal_repository.py)
