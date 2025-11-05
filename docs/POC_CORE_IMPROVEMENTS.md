# POC Core Improvements - Final Touches

이 문서는 Codex 2차 피드백에서 제시된 이슈 중 **POC 구현 전 필수**로 보완할 핵심 사항만 정리합니다.

---

## 1. 검색 결과 분류 로직 (필수)

### 문제
- 현재: "검색 실패"로만 정의
- 개선: "무결과 (0건)" vs "실제 오류" 구분 필요

### 해결책

**Event Type 확장**:
```javascript
// 무결과 (정상 호출이지만 0건)
{
  type: "retriever_results",
  results: {
    similar_cases: [],
    kb_articles: []
  },
  result_count: 0,
  continue_with: "direct_analysis"  // 직접 분석으로 진행
}

// 실제 오류 (Qdrant 장애, timeout 등)
{
  type: "retriever_fallback",
  reason: "qdrant_error" | "timeout" | "connection_failed",
  fallback_to: "direct_analysis"
}
```

**Backend Logic** (`backend/agents/retriever.py`):
```python
async def retrieve_cases(state: AgentState) -> AgentState:
    """
    검색 수행 with 무결과 vs 오류 구분
    """
    try:
        results = await qdrant_search(...)

        if len(results) == 0:
            # 무결과 (정상)
            state["search_results"] = {
                "similar_cases": [],
                "kb_procedures": [],
                "result_count": 0,
                "status": "no_results"
            }
            # 직접 분석으로 자동 진행
            state["next_node"] = "propose_solution_direct"
        else:
            # 정상 결과
            state["search_results"] = {
                "similar_cases": results,
                "result_count": len(results),
                "status": "success"
            }
            state["next_node"] = "propose_solution"

        return state

    except QdrantException as e:
        # 실제 오류 - fallback
        logger.error(f"Qdrant error: {e}")
        state["search_results"] = {
            "status": "error",
            "error_type": "qdrant_error",
            "error_message": str(e)
        }
        state["next_node"] = "propose_solution_direct"
        return state

    except TimeoutError:
        # Timeout - fallback
        state["search_results"] = {
            "status": "error",
            "error_type": "timeout"
        }
        state["next_node"] = "propose_solution_direct"
        return state
```

---

## 2. RLS 정책 SQL (필수)

### 문제
- RLS만 언급, 실제 SQL 없음

### 해결책

**Migration File**: `backend/migrations/003_rls_policies.sql`

```sql
-- ==========================================
-- Row-Level Security Policies
-- ==========================================

-- 1. Enable RLS on all tenant-isolated tables
ALTER TABLE tenant_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_logs ENABLE ROW LEVEL SECURITY;

-- 2. Create security context setter function
CREATE OR REPLACE FUNCTION set_current_tenant(tenant_id_param TEXT)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', tenant_id_param, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Tenant isolation policy for tenant_configs
CREATE POLICY tenant_configs_isolation ON tenant_configs
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- 4. Tenant isolation policy for proposals
CREATE POLICY proposals_isolation ON proposals
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true));

-- 5. Approval logs - accessible via proposal's tenant
CREATE POLICY approval_logs_isolation ON approval_logs
    FOR ALL
    USING (
        proposal_id IN (
            SELECT id FROM proposals
            WHERE tenant_id = current_setting('app.current_tenant_id', true)
        )
    );

-- 6. Service role bypass (for admin operations)
CREATE POLICY service_role_bypass_tenant_configs ON tenant_configs
    FOR ALL
    TO service_role
    USING (true);

CREATE POLICY service_role_bypass_proposals ON proposals
    FOR ALL
    TO service_role
    USING (true);

CREATE POLICY service_role_bypass_approval_logs ON approval_logs
    FOR ALL
    TO service_role
    USING (true);

-- 7. Grant permissions
GRANT EXECUTE ON FUNCTION set_current_tenant(TEXT) TO authenticated, service_role;

COMMENT ON FUNCTION set_current_tenant IS 'Sets tenant context for RLS policies';
```

**Backend Integration** (`backend/repositories/base_repository.py`):

```python
from supabase import create_client

class BaseRepository:
    """Base repository with RLS support"""

    def __init__(self):
        self.client = create_client(...)

    async def set_tenant_context(self, tenant_id: str):
        """Set RLS tenant context for all queries in this session"""
        await self.client.rpc('set_current_tenant', {'tenant_id_param': tenant_id}).execute()

    async def with_tenant(self, tenant_id: str):
        """Context manager for tenant-scoped queries"""
        await self.set_tenant_context(tenant_id)
        return self
```

**Usage in Routes**:
```python
@router.post("/api/v1/assist/analyze")
async def analyze_ticket(
    request: AnalyzeRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    # Set RLS context
    await tenant_repo.with_tenant(tenant_id)

    # All subsequent queries are now tenant-scoped
    config = await tenant_repo.get_config(tenant_id, platform)
    # ...
```

---

## 3. Admin API 인증 (필수)

### 문제
- Admin API 인증 모델 없음

### 해결책 (간단한 API Key 방식)

**Environment Variables** (`.env`):
```bash
# Admin API Key (rotate periodically)
ADMIN_API_KEY=admin_secret_key_here_change_in_production
```

**Middleware** (`backend/middleware/admin_auth.py`):
```python
from fastapi import HTTPException, Header
from backend.config import get_settings

settings = get_settings()

def verify_admin_key(api_key: str = Header(..., alias="X-Admin-API-Key")):
    """
    Simple API Key validation for admin endpoints
    """
    if not api_key or api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing admin API key"
        )
    return True
```

**Admin Routes** (`backend/routes/admin.py`):
```python
from fastapi import APIRouter, Depends
from backend.middleware.admin_auth import verify_admin_key

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)]  # Apply to all routes
)

@router.post("/tenants")
async def create_tenant(tenant_data: TenantCreate):
    """Create new tenant (admin only)"""
    # Already protected by dependency
    ...

@router.put("/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, updates: TenantUpdate):
    """Update tenant config (admin only)"""
    ...

@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str):
    """Get tenant config (admin only)"""
    ...
```

**Frontend Usage**:
```javascript
// Admin dashboard
const adminHeaders = {
    'X-Admin-API-Key': process.env.ADMIN_API_KEY,
    'Content-Type': 'application/json'
};

fetch('/api/v1/admin/tenants', {
    method: 'POST',
    headers: adminHeaders,
    body: JSON.stringify(tenantData)
});
```

---

## POC 이후 개선 사항 (미루기)

다음 항목들은 **POC 이후** 개선:

1. ⏭️ Proposal 동시 편집 처리 (optimistic locking)
2. ⏭️ HMAC 시계 동기화 편차 처리 (±30초)
3. ⏭️ DB 저장 PII 암호화
4. ⏭️ CORS 헤더 상세화
5. ⏭️ PII 마스킹 다국가 패턴 (한국 주민번호 등)
6. ⏭️ updated_at 자동 트리거
7. ⏭️ Freshdesk API 재시도 상세 전략
8. ⏭️ Token counter 모델 교체 대응
9. ⏭️ SSE Nginx 설정 문서화
10. ⏭️ 요약 누적 정보 손실 방지

---

## 구현 시작 체크리스트

✅ **필수 보완 완료**:
- [x] 검색 무결과 vs 오류 구분 로직 정의
- [x] RLS 정책 SQL 작성
- [x] Admin API Key 인증 설계

🚀 **구현 준비 완료**:
- 플랜 검증 완료 (Codex 2회)
- 핵심 보완 사항 반영
- 파일 체크리스트 준비됨

**다음 단계**: 데이터베이스 마이그레이션부터 구현 시작!
