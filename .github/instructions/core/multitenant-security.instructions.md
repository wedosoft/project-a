````instructions
# 🔐 멀티테넌트 보안 핵심 패턴

_AI 참조 최적화 버전 - 핵심 보안 패턴만 집중 정리_

## 🎯 멀티테넌트 보안 목표

**완벽한 테넌트 간 데이터 격리 및 보안 보장**

- **절대적 격리**: company_id 기반 100% 데이터 분리
- **자동 태깅**: 모든 데이터에 테넌트 식별자 자동 추가
- **계층적 보안**: API → 서비스 → 데이터베이스 → 벡터 DB 전 계층 보안
- **감사 추적**: 모든 테넌트 액세스 로깅 및 모니터링

---

## 🚨 **중요 업데이트 (2025-06-22)**

### 📋 **표준 4개 헤더 기반 API 일관성 확보**

**모든 FastAPI 라우터에서 표준 헤더만 사용**:
```python
# ✅ 표준 헤더 (의존성으로 주입)
async def endpoint(
    headers: StandardHeaders = Depends(get_standard_headers)
):
    # headers.company_id, headers.platform, headers.domain, headers.api_key
    pass

# ❌ 레거시 환경변수/쿼리 파라미터 사용 금지
# FRESHDESK_DOMAIN, FRESHDESK_API_KEY 등 완전 제거
```

**헤더 우선순위**:
1. **X-Company-ID** (필수)
2. **X-Platform** (필수: freshdesk, zendesk 등)
3. **X-Domain** (필수: API 엔드포인트)
4. **X-API-Key** (필수: 인증 키)

### 🗄️ **멀티테넌트 데이터베이스 정책 확정**

**개발환경 (SQLite) - 회사별 데이터베이스 파일 분리**:
```
data/
├── company1_freshdesk_data.db     # 물리적 격리
├── acme_freshdesk_data.db         # 완전 독립
└── demo_zendesk_data.db           # 플랫폼별 분리
```

**운영환경 (PostgreSQL) - 테넌트별 스키마**:
```sql
-- 스키마 기반 격리
CREATE SCHEMA tenant_company1_freshdesk;
CREATE SCHEMA tenant_acme_freshdesk;

-- Row-level Security 적용
ALTER TABLE tenant_company1_freshdesk.tickets ENABLE ROW LEVEL SECURITY;
```

**데이터베이스 생성 함수 업데이트**:
```python
def get_database(company_id: str, platform: str = "freshdesk"):
    """멀티테넌트 데이터베이스 인스턴스 반환"""
    if os.getenv("DATABASE_URL"):
        # PostgreSQL: 스키마 기반 격리
        return PostgreSQLDatabase(
            schema_name=f"tenant_{company_id}_{platform}"
        )
    else:
        # SQLite: 파일 기반 격리
        db_path = f"data/{company_id}_{platform}_data.db"
        return SQLiteDatabase(db_path)
```

### 🔧 **Fetcher 함수 리팩토링 완료**

**fetch_tickets/fetch_kb_articles 파라미터 표준화**:
```python
# ✅ 수정 후: company_id 파라미터 제거
async def fetch_tickets(
    domain: Optional[str] = None,
    api_key: Optional[str] = None,
    max_tickets: int = 10000
) -> List[Dict[str, Any]]:

# ✅ 내부에서 company_id 추출
company_id = extract_company_id_from_domain(domain)
```

**ingest 프로세서 호출부 수정**:
```python
# ✅ 수정 후: company_id 파라미터 제거
tickets = await fetch_tickets(
    domain=domain, 
    api_key=api_key,
    max_tickets=max_tickets
)
```

---

## 🚀 **TL;DR - 핵심 멀티테넌트 보안 요약**

### 💡 **즉시 참조용 핵심 포인트**

**테넌트 식별 전략**:
```
도메인 추출: your_company.freshdesk.com → "your_company"
X-Company-ID 헤더 → API 전체에 필수 적용
모든 DB 쿼리 → company_id WHERE 조건 필수
```

**데이터 격리 원칙**:
- **API 레벨**: X-Company-ID 헤더 검증 필수
- **서비스 레벨**: 모든 함수에 company_id 매개변수 필수
- **DB 레벨**: Row-level Security (RLS) 적용
- **벡터 DB**: 필터링 기반 격리 (company_id + platform)

**절대 금지 사항**:
- company_id 없는 데이터 처리 절대 금지
- 전체 테이블 스캔 (SELECT * FROM table) 금지
- 테넌트 간 데이터 공유 금지
- 하드코딩된 company_id 금지

### 🚨 **멀티테넌트 보안 주의사항**

- ⚠️ company_id 누락 시 즉시 에러 → 데이터 무결성 보장
- ⚠️ SQL 인젝션 방지 → 파라미터화 쿼리 필수
- ⚠️ 테넌트 권한 검증 → 모든 요청에 대한 인증/인가 확인

---

## 🔑 **1. company_id 자동 추출 및 검증**

### 🏗️ **테넌트 식별 핵심 패턴**

```python
import re
from typing import Optional
from urllib.parse import urlparse

def extract_company_id(domain_or_url: str) -> Optional[str]:
    """도메인에서 company_id 자동 추출"""
    try:
        # URL인 경우 도메인 추출
        if domain_or_url.startswith(('http://', 'https://')):
            parsed = urlparse(domain_or_url)
            domain = parsed.hostname
        else:
            domain = domain_or_url
        
        # company_id 추출: subdomain.freshdesk.com → subdomain
        if '.freshdesk.com' in domain:
            return domain.split('.freshdesk.com')[0]
        
        # 기타 패턴 처리
        parts = domain.split('.')
        if len(parts) >= 2:
            return parts[0]
            
        return None
        
    except Exception:
        return None

def validate_company_id(company_id: str) -> bool:
    """company_id 유효성 검증"""
    if not company_id or len(company_id) < 2:
        return False
    
    # 알파벳, 숫자, 하이픈만 허용
    return re.match(r'^[a-zA-Z0-9-]+$', company_id) is not None

# 사용 예시
company_id = extract_company_id("your_company.freshdesk.com")  # "your_company"
if not validate_company_id(company_id):
    raise ValueError(f"Invalid company_id: {company_id}")
```

### 🎯 **테넌트 컨텍스트 클래스**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class TenantContext:
    company_id: str
    platform: str = "freshdesk"
    user_id: Optional[str] = None
    permissions: list = None
    
    def __post_init__(self):
        if not validate_company_id(self.company_id):
            raise ValueError(f"Invalid company_id: {self.company_id}")
        
        if self.permissions is None:
            self.permissions = []
    
    def has_permission(self, permission: str) -> bool:
        """권한 확인"""
        return permission in self.permissions or "admin" in self.permissions
    
    def get_db_filter(self) -> dict:
        """데이터베이스 필터링용 조건"""
        return {
            "company_id": self.company_id,
            "platform": self.platform
        }
```

---

## 🛡️ **2. API 레벨 보안**

### 🔒 **FastAPI 의존성 기반 테넌트 인증**

```python
from fastapi import HTTPException, Header, Depends
from typing import Optional

async def get_tenant_context(
    x_company_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
) -> TenantContext:
    """테넌트 컨텍스트 추출 및 검증"""
    
    # company_id 필수 확인
    if not x_company_id:
        raise HTTPException(
            status_code=400,
            detail="X-Company-ID header is required"
        )
    
    # company_id 유효성 검증
    if not validate_company_id(x_company_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid company_id format: {x_company_id}"
        )
    
    # 테넌트 컨텍스트 생성
    return TenantContext(
        company_id=x_company_id,
        platform="freshdesk"  # FDK는 항상 freshdesk
    )

# FastAPI 의존성으로 사용
async def require_tenant_context(
    tenant_context: TenantContext = Depends(get_tenant_context)
) -> TenantContext:
    """테넌트 컨텍스트 필수 의존성"""
    return tenant_context

# API 엔드포인트 예시
from fastapi import FastAPI

app = FastAPI()

@app.post("/api/v1/tickets/ingest")
async def ingest_tickets(
    request: dict,
    tenant_context: TenantContext = Depends(require_tenant_context)
):
    """티켓 수집 API - 테넌트 격리 적용"""
    
    # 자동으로 company_id가 검증된 상태
    result = await process_tickets(
        tickets=request.get("tickets", []),
        company_id=tenant_context.company_id,
        platform=tenant_context.platform
    )
    
    return {"status": "success", "processed": len(result)}

@app.get("/api/v1/tickets/search")
async def search_tickets(
    query: str,
    tenant_context: TenantContext = Depends(require_tenant_context)
):
    """티켓 검색 API - 테넌트 격리 적용"""
    
    # 테넌트별 필터링이 자동 적용됨
    results = await search_similar_tickets(
        query=query,
        company_id=tenant_context.company_id,
        limit=10
    )
    
    return {"results": results, "company_id": tenant_context.company_id}
```

---

## 🗄️ **3. 데이터베이스 레벨 보안**

### 🔒 **PostgreSQL Row-Level Security 설정**

```sql
-- 1. 티켓 테이블 RLS 활성화
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;

-- 2. 테넌트별 액세스 정책 생성
CREATE POLICY tenant_isolation_policy ON tickets
    FOR ALL TO app_user 
    USING (company_id = current_setting('app.current_company_id'));

-- 3. 테넌트별 인덱스 최적화
CREATE INDEX CONCURRENTLY idx_tickets_company_id ON tickets(company_id);
CREATE INDEX CONCURRENTLY idx_tickets_company_platform ON tickets(company_id, platform);

-- 4. 테넌트 컨텍스트 설정 함수
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id text)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_company_id', tenant_id, true);
END;
$$ LANGUAGE plpgsql;
```

### 🔧 **Python DB 쿼리 보안 패턴**

```python
import asyncpg
from typing import List, Dict, Any

class SecureDBManager:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    async def execute_tenant_query(
        self,
        company_id: str,
        query: str,
        params: tuple = ()
    ) -> List[Dict[str, Any]]:
        """테넌트 격리가 적용된 안전한 쿼리 실행"""
        
        async with asyncpg.connect(self.connection_string) as conn:
            # 테넌트 컨텍스트 설정
            await conn.execute("SELECT set_tenant_context($1)", company_id)
            
            # 파라미터화된 쿼리 실행 (SQL 인젝션 방지)
            results = await conn.fetch(query, *params)
            
            # 결과를 딕셔너리 리스트로 변환
            return [dict(record) for record in results]
    
    async def get_tenant_tickets(
        self,
        company_id: str,
        status: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """테넌트별 티켓 조회 (안전한 패턴)"""
        
        # company_id는 RLS로 자동 필터링됨
        query = """
            SELECT id, subject, description, status, created_at
            FROM tickets
            WHERE ($2::text IS NULL OR status = $2)
            ORDER BY created_at DESC
            LIMIT $3
        """
        
        return await self.execute_tenant_query(
            company_id=company_id,
            query=query,
            params=(company_id, status, limit)
        )

# 전역 DB 관리자
db_manager = SecureDBManager(os.getenv("DATABASE_URL"))

# 사용 예시
async def get_tickets_safely(company_id: str, status: str = None):
    """안전한 티켓 조회"""
    
    # company_id 검증
    if not validate_company_id(company_id):
        raise ValueError(f"Invalid company_id: {company_id}")
    
    # RLS가 적용된 안전한 쿼리
    tickets = await db_manager.get_tenant_tickets(
        company_id=company_id,
        status=status
    )
    
    return tickets
```

---

## 🔍 **4. 벡터 DB 보안**

### 🎯 **Qdrant 테넌트 필터링**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

class SecureVectorManager:
    def __init__(self, qdrant_url: str, api_key: str):
        self.client = QdrantClient(url=qdrant_url, api_key=api_key)
        self.collection_name = "documents"
    
    def create_tenant_filter(
        self,
        company_id: str,
        platform: str = "freshdesk"
    ) -> Filter:
        """테넌트별 필터 생성"""
        return Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=company_id)
                ),
                FieldCondition(
                    key="platform", 
                    match=MatchValue(value=platform)
                )
            ]
        )
    
    async def search_similar_documents(
        self,
        company_id: str,
        query_vector: List[float],
        limit: int = 10,
        platform: str = "freshdesk"
    ) -> List[Dict]:
        """테넌트 격리된 벡터 검색"""
        
        # company_id 검증
        if not validate_company_id(company_id):
            raise ValueError(f"Invalid company_id: {company_id}")
        
        # 테넌트별 필터 적용
        tenant_filter = self.create_tenant_filter(company_id, platform)
        
        # 안전한 벡터 검색 (테넌트 격리 보장)
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=tenant_filter,  # 필수 필터
            limit=limit
        )
        
        # 결과에 company_id 확인 (이중 검증)
        validated_results = []
        for result in results:
            if result.payload.get("company_id") == company_id:
                validated_results.append(result.payload)
        
        return validated_results

# 전역 벡터 관리자
vector_manager = SecureVectorManager(
    qdrant_url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# 사용 예시
async def search_tickets_safely(
    company_id: str,
    query_text: str,
    limit: int = 5
):
    """안전한 유사 티켓 검색"""
    
    # query_text를 벡터로 변환
    query_vector = await generate_embedding(query_text)
    
    # 테넌트 격리된 검색
    similar_tickets = await vector_manager.search_similar_documents(
        company_id=company_id,
        query_vector=query_vector,
        limit=limit
    )
    
    return similar_tickets
```

---

## 📊 **5. 보안 모니터링 및 로깅**

### 🔍 **테넌트 액세스 로깅**

```python
import logging
from datetime import datetime
from typing import Dict, Any

class TenantAccessLogger:
    def __init__(self):
        self.logger = logging.getLogger("tenant_access")
        self.logger.setLevel(logging.INFO)
        
        # 구조화된 로그 포맷
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_api_access(
        self,
        company_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        user_id: str = None
    ):
        """API 액세스 로깅"""
        log_data = {
            "event": "api_access",
            "company_id": company_id,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"API_ACCESS: {log_data}")
    
    def log_data_access(
        self,
        company_id: str,
        operation: str,
        table_name: str,
        record_count: int,
        user_id: str = None
    ):
        """데이터 액세스 로깅"""
        log_data = {
            "event": "data_access",
            "company_id": company_id,
            "operation": operation,  # SELECT, INSERT, UPDATE, DELETE
            "table_name": table_name,
            "record_count": record_count,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"DATA_ACCESS: {log_data}")
    
    def log_security_violation(
        self,
        company_id: str,
        violation_type: str,
        details: str,
        user_id: str = None
    ):
        """보안 위반 로깅"""
        log_data = {
            "event": "security_violation",
            "company_id": company_id,
            "violation_type": violation_type,
            "details": details,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.error(f"SECURITY_VIOLATION: {log_data}")

# 전역 로거 인스턴스
tenant_logger = TenantAccessLogger()

# 보안 검증 데코레이터
def log_tenant_access(operation: str, table_name: str = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            company_id = kwargs.get('company_id', 'unknown')
            
            try:
                result = await func(*args, **kwargs)
                
                # 성공 로그
                tenant_logger.log_data_access(
                    company_id=company_id,
                    operation=operation,
                    table_name=table_name or func.__name__,
                    record_count=len(result) if isinstance(result, list) else 1
                )
                
                return result
                
            except Exception as e:
                # 에러 로그
                tenant_logger.log_security_violation(
                    company_id=company_id,
                    violation_type="operation_failed",
                    details=f"{operation} failed: {str(e)}"
                )
                raise
                
        return wrapper
    return decorator
```

---

## 🎯 **멀티테넌트 보안 체크리스트**

### ✅ **API 레벨 보안**
- [ ] X-Company-ID 헤더 필수 검증
- [ ] company_id 형식 유효성 검사
- [ ] 모든 엔드포인트에 테넌트 컨텍스트 적용
- [ ] 에러 메시지에서 테넌트 정보 누출 방지

### ✅ **데이터베이스 보안**
- [ ] Row-Level Security (RLS) 활성화
- [ ] 모든 쿼리에 company_id 필터 적용
- [ ] 파라미터화된 쿼리 사용 (SQL 인젝션 방지)
- [ ] 테넌트별 인덱스 최적화

### ✅ **벡터 DB 보안**
- [ ] 모든 벡터 검색에 테넌트 필터 적용
- [ ] 결과에서 company_id 이중 검증
- [ ] 단일 컬렉션 내 테넌트 격리 확인

### ✅ **모니터링 및 감사**
- [ ] 모든 API 액세스 로깅
- [ ] 데이터 액세스 패턴 추적
- [ ] 보안 위반 알림 설정
- [ ] 정기적 보안 검증

---

## 📚 **관련 참조 지침서**

- **[시스템 아키텍처](system-architecture.instructions.md)** - 전체 보안 아키텍처 설계
- **[데이터 워크플로우](../data/data-workflow.instructions.md)** - 데이터 처리 시 보안 적용
- **[벡터 저장 검색](../data/vector-storage-search.instructions.md)** - 벡터 DB 보안
- **[에러 처리](../development/error-handling-debugging.instructions.md)** - 보안 로깅

---

*📝 이 지침서는 멀티테넌트 보안의 핵심 패턴만 정리했습니다. 더 상세한 구현은 legacy/multitenant-security-complete.instructions.md를 참조하세요.*

**🔗 Next Steps**: 단계별로 보안 패턴을 적용하여 테넌트 격리를 강화하세요.

---

## 🧪 **데이터 파이프라인 테스트 가이드라인 (2025-06-22 추가)**

### 📊 **ingest 엔드포인트 테스트 프로세스**

**1. 서버 실행 및 확인**:
```bash
cd backend && source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 서버 상태 확인
curl http://localhost:8000/health
```

**2. 표준 헤더로 ingest 테스트**:
```bash
# ✅ 올바른 테스트 방법
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: your_company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: your_company.freshdesk.com" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "max_tickets": 100,
    "max_articles": 50,
    "include_kb": true
  }'
```

**3. 데이터베이스 파일 확인**:
```bash
# SQLite 파일 생성 확인
ls -la backend/core/data/
# → your_company_freshdesk_data.db 파일 존재 확인

# 데이터 확인
sqlite3 backend/core/data/your_company_freshdesk_data.db
.tables
SELECT COUNT(*) FROM integrated_objects;
```

### 🔍 **일반적인 문제 해결**

**문제**: `fetch_tickets() got an unexpected keyword argument 'company_id'`
**해결**: processor.py에서 company_id 파라미터 제거 완료

**문제**: SQL 데이터베이스가 생성되지 않음
**해결**: get_database() 함수에 company_id, platform 파라미터 추가 완료

**문제**: 환경변수 우선순위 충돌
**해결**: 
- 헤더 우선, 환경변수는 fallback으로만 사용
- FRESHDESK_* 레거시 환경변수 완전 제거

### 📈 **성공 기준**

**✅ 데이터 수집 성공 지표**:
- SQLite 파일 자동 생성: `{company_id}_{platform}_data.db`
- 100건 티켓 데이터 정상 수집
- 50건 KB 문서 정상 수집
- 첨부파일 메타데이터 포함
- 대화 내역 포함

**✅ 멀티테넌트 격리 확인**:
- 회사별 데이터베이스 파일 분리
- company_id 태깅 100% 적용
- 헤더 검증 정상 동작

---

## 📝 **구현 체크리스트 (최종)**

### ✅ **완료된 작업**
- [x] 표준 4개 헤더 API 일관성 확보
- [x] 레거시 환경변수/파라미터 완전 제거
- [x] fetch_tickets/fetch_kb_articles 파라미터 표준화
- [x] 멀티테넌트 데이터베이스 정책 구현
- [x] get_database() 함수 company_id 지원
- [x] processor.py ingest 파이프라인 수정
- [x] 서버 실행 오류 수정

### 🔄 **진행 중인 작업**
- [ ] ingest 엔드포인트 100건 테스트 데이터 수집 검증
- [ ] 전체 파이프라인 통합 테스트
- [ ] 벡터 검색 성능 검증

### 📋 **다음 단계**
- [ ] 프론트엔드 연동 테스트
- [ ] 운영환경 PostgreSQL 전환 준비
- [ ] AWS Secrets Manager 통합
- [ ] 백업 및 복구 정책 수립
````
