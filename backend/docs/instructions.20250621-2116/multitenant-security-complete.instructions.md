---
applyTo: "**"
---

# 🔐 멀티테넌트 보안 & 데이터 격리 지침서

_AI 참조 최적화 버전 - 완벽한 테넌트 분리 및 보안 전략_

## 🎯 멀티테넌트 보안 목표

**완벽한 테넌트 간 데이터 격리 및 보안 보장**

- **절대적 격리**: company_id 기반 100% 데이터 분리 (크로스 테넌트 액세스 차단)
- **자동 태깅**: 모든 데이터에 테넌트 식별자 자동 추가
- **계층적 보안**: API → 서비스 → 데이터베이스 → 벡터 DB 전 계층 보안
- **감사 추적**: 모든 테넌트 액세스 로깅 및 모니터링

---

## 🚀 **TL;DR - 핵심 멀티테넌트 보안 요약**

### 💡 **즉시 참조용 핵심 포인트**

**테넌트 식별 전략**:
```
도메인 추출: wedosoft.freshdesk.com → "wedosoft"
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

## 🏗️ **테넌트 식별 & 자동 태깅**

### 🔑 **company_id 추출 패턴**

```python
import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse

def extract_company_id(domain_or_url: str) -> Optional[str]:
    """
    다양한 플랫폼 도메인에서 company_id 추출
    
    Args:
        domain_or_url: 도메인 또는 URL
        
    Returns:
        company_id 또는 None
        
    Examples:
        extract_company_id("wedosoft.freshdesk.com") → "wedosoft"
        extract_company_id("https://acme.zendesk.com") → "acme"
        extract_company_id("company.service-now.com") → "company"
    """
    if not domain_or_url:
        return None
    
    # URL에서 도메인 추출
    if domain_or_url.startswith(('http://', 'https://')):
        parsed = urlparse(domain_or_url)
        domain = parsed.netloc
    else:
        domain = domain_or_url
    
    # 플랫폼별 패턴 매칭
    patterns = {
        'freshdesk': r'^([a-zA-Z0-9-]+)\.freshdesk\.com$',
        'zendesk': r'^([a-zA-Z0-9-]+)\.zendesk\.com$',
        'servicenow': r'^([a-zA-Z0-9-]+)\.service-now\.com$',
        'custom': r'^([a-zA-Z0-9-]+)\.'  # 일반적인 서브도메인 패턴
    }
    
    for platform, pattern in patterns.items():
        match = re.match(pattern, domain, re.IGNORECASE)
        if match:
            company_id = match.group(1).lower()
            
            # 유효성 검증
            if len(company_id) >= 2 and company_id.isalnum():
                return company_id
    
    return None

def validate_company_id(company_id: str) -> bool:
    """company_id 유효성 검증"""
    if not company_id:
        return False
    
    # 기본 규칙
    if not (2 <= len(company_id) <= 50):
        return False
    
    # 영숫자 및 하이픈만 허용
    if not re.match(r'^[a-zA-Z0-9-]+$', company_id):
        return False
    
    # 예약어 확인
    reserved_words = {'admin', 'api', 'www', 'mail', 'ftp', 'localhost', 'test'}
    if company_id.lower() in reserved_words:
        return False
    
    return True

class TenantContext:
    """테넌트 컨텍스트 관리 클래스"""
    
    def __init__(self, company_id: str, platform: str = None, user_id: str = None):
        if not validate_company_id(company_id):
            raise ValueError(f"Invalid company_id: {company_id}")
        
        self.company_id = company_id.lower()
        self.platform = platform
        self.user_id = user_id
        self.created_at = datetime.utcnow()
    
    def get_tenant_filter(self) -> Dict[str, Any]:
        """테넌트 필터 조건 생성"""
        filter_conditions = {'company_id': self.company_id}
        
        if self.platform:
            filter_conditions['platform'] = self.platform
        
        return filter_conditions
    
    def apply_tenant_tagging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """데이터에 테넌트 태그 자동 적용"""
        tagged_data = data.copy()
        
        # 필수 테넌트 필드 추가
        tagged_data.update({
            'company_id': self.company_id,
            'tenant_context': {
                'company_id': self.company_id,
                'platform': self.platform,
                'tagged_at': datetime.utcnow().isoformat(),
                'user_id': self.user_id
            }
        })
        
        # 플랫폼 정보 추가
        if self.platform and 'platform' not in tagged_data:
            tagged_data['platform'] = self.platform
        
        return tagged_data
```

---

## 🛡️ **API 레벨 보안 패턴**

### 🔒 **헤더 기반 테넌트 인증**

```python
from fastapi import HTTPException, Header, Depends
from typing import Optional

async def get_tenant_context(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
    authorization: Optional[str] = Header(None)
) -> TenantContext:
    """
    HTTP 헤더에서 테넌트 컨텍스트 추출 및 검증
    
    Required Headers:
        X-Company-ID: 테넌트 식별자 (필수)
        X-Platform: 플랫폼 식별자 (선택)
        Authorization: 인증 토큰 (필수)
    """
    
    # 1. 인증 토큰 검증
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )
    
    token = authorization.replace("Bearer ", "")
    user_info = await verify_jwt_token(token)
    
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
    # 2. company_id 검증
    if not x_company_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Company-ID header"
        )
    
    if not validate_company_id(x_company_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid company_id format: {x_company_id}"
        )
    
    # 3. 사용자-테넌트 권한 확인
    if not await verify_user_tenant_access(user_info['user_id'], x_company_id):
        raise HTTPException(
            status_code=403,
            detail=f"User does not have access to tenant: {x_company_id}"
        )
    
    # 4. 테넌트 컨텍스트 생성
    return TenantContext(
        company_id=x_company_id,
        platform=x_platform,
        user_id=user_info['user_id']
    )

# FastAPI 의존성으로 사용
async def require_tenant_context(
    tenant_context: TenantContext = Depends(get_tenant_context)
) -> TenantContext:
    """테넌트 컨텍스트 필수 의존성"""
    return tenant_context

# API 엔드포인트 예시
@app.post("/api/v1/tickets/ingest")
async def ingest_tickets(
    request: IngestRequest,
    tenant_context: TenantContext = Depends(require_tenant_context)
):
    """테넌트 격리가 적용된 티켓 수집 API"""
    
    # 요청 데이터에 테넌트 정보 자동 태깅
    tagged_request = tenant_context.apply_tenant_tagging(request.dict())
    
    # 테넌트별 격리된 처리
    result = await process_ingest_request(
        company_id=tenant_context.company_id,
        platform=tenant_context.platform,
        data=tagged_request
    )
    
    return result

@app.get("/api/v1/tickets/search")
async def search_tickets(
    query: str,
    limit: int = 10,
    tenant_context: TenantContext = Depends(require_tenant_context)
):
    """테넌트 격리가 적용된 티켓 검색 API"""
    
    # 테넌트별 필터링된 검색
    results = await search_similar_documents(
        company_id=tenant_context.company_id,
        platform=tenant_context.platform,
        query_text=query,
        limit=limit
    )
    
    return results
```

### 🔍 **API 액세스 로깅**

```python
import logging
from datetime import datetime
from typing import Dict, Any

class TenantAccessLogger:
    def __init__(self):
        self.logger = logging.getLogger("tenant_access")
        self.logger.setLevel(logging.INFO)
        
        # 파일 핸들러 설정
        handler = logging.FileHandler("logs/tenant_access.log")
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    async def log_api_access(
        self,
        tenant_context: TenantContext,
        endpoint: str,
        method: str,
        request_data: Dict[str, Any] = None,
        response_status: int = None,
        error: str = None
    ):
        """API 액세스 로깅"""
        
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'company_id': tenant_context.company_id,
            'platform': tenant_context.platform,
            'user_id': tenant_context.user_id,
            'endpoint': endpoint,
            'method': method,
            'response_status': response_status,
            'has_request_data': bool(request_data),
            'request_data_size': len(str(request_data)) if request_data else 0,
            'error': error
        }
        
        if error:
            self.logger.error(f"TENANT_ACCESS_ERROR: {orjson.dumps(log_entry).decode()}")
        else:
            self.logger.info(f"TENANT_ACCESS: {orjson.dumps(log_entry).decode()}")
        
        # 보안 이벤트 감지
        await self._detect_security_events(log_entry)
    
    async def _detect_security_events(self, log_entry: Dict[str, Any]):
        """보안 이벤트 감지 및 알림"""
        
        # 1. 무단 액세스 시도 감지
        if log_entry.get('response_status') == 403:
            await self._alert_unauthorized_access(log_entry)
        
        # 2. 대량 데이터 액세스 감지
        if log_entry.get('request_data_size', 0) > 1000000:  # 1MB 초과
            await self._alert_large_data_access(log_entry)
        
        # 3. 비정상적인 API 호출 패턴 감지
        # (구현 예: 시간당 요청 수 임계값 초과)
    
    async def _alert_unauthorized_access(self, log_entry: Dict[str, Any]):
        """무단 액세스 알림"""
        alert_message = f"""
        SECURITY ALERT: Unauthorized tenant access attempt
        
        Company ID: {log_entry['company_id']}
        User ID: {log_entry['user_id']}
        Endpoint: {log_entry['endpoint']}
        Timestamp: {log_entry['timestamp']}
        """
        
        # 알림 시스템으로 전송 (예: Slack, 이메일)
        await send_security_alert(alert_message)

# 전역 로거 인스턴스
tenant_logger = TenantAccessLogger()
```

---

## 🗄️ **데이터베이스 레벨 보안**

### 🔒 **Row-Level Security (RLS) 설정**

```sql
-- PostgreSQL Row-Level Security 설정

-- 1. 티켓 테이블 RLS 활성화
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;

-- 2. 테넌트별 액세스 정책 생성
CREATE POLICY tenant_isolation_policy ON tickets
    USING (company_id = current_setting('app.current_tenant')::text);

-- 3. 인덱스 최적화 (테넌트별 쿼리 성능 향상)
CREATE INDEX CONCURRENTLY idx_tickets_company_id ON tickets(company_id);
CREATE INDEX CONCURRENTLY idx_tickets_company_platform ON tickets(company_id, platform);
CREATE INDEX CONCURRENTLY idx_tickets_company_status ON tickets(company_id, status);

-- 4. 테넌트 컨텍스트 설정 함수
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id text)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant', tenant_id, true);
END;
$$ LANGUAGE plpgsql;

-- 5. 테넌트 검증 함수
CREATE OR REPLACE FUNCTION validate_tenant_access(tenant_id text, user_id text)
RETURNS boolean AS $$
BEGIN
    -- 사용자-테넌트 권한 확인 로직
    RETURN EXISTS (
        SELECT 1 FROM user_tenant_permissions 
        WHERE user_id = $2 AND company_id = $1 AND is_active = true
    );
END;
$$ LANGUAGE plpgsql;
```

### 🔐 **SQLAlchemy 테넌트 필터링**

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

class TenantSafeSession:
    """테넌트 안전 데이터베이스 세션"""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    @contextmanager
    def get_tenant_session(self, company_id: str):
        """테넌트 컨텍스트가 설정된 DB 세션"""
        session = self.SessionLocal()
        
        try:
            # 테넌트 컨텍스트 설정
            session.execute(
                text("SELECT set_tenant_context(:tenant_id)"),
                {"tenant_id": company_id}
            )
            
            yield session
            session.commit()
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

# 테넌트 안전 쿼리 헬퍼
class TenantSafeQueries:
    def __init__(self, db_session: TenantSafeSession):
        self.db = db_session
    
    async def get_tickets(
        self, 
        company_id: str, 
        platform: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """테넌트별 격리된 티켓 조회"""
        
        with self.db.get_tenant_session(company_id) as session:
            query = """
                SELECT * FROM tickets 
                WHERE company_id = :company_id
            """
            params = {"company_id": company_id}
            
            # 추가 필터링
            if platform:
                query += " AND platform = :platform"
                params["platform"] = platform
            
            if status:
                query += " AND status = :status"
                params["status"] = status
            
            query += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit
            
            result = session.execute(text(query), params)
            
            return [dict(row) for row in result.fetchall()]
    
    async def insert_ticket(
        self,
        company_id: str,
        ticket_data: Dict[str, Any]
    ) -> str:
        """테넌트별 격리된 티켓 삽입"""
        
        # company_id 자동 태깅 검증
        if ticket_data.get('company_id') != company_id:
            raise ValueError(f"Ticket company_id mismatch: {ticket_data.get('company_id')} != {company_id}")
        
        with self.db.get_tenant_session(company_id) as session:
            query = """
                INSERT INTO tickets (
                    company_id, platform, ticket_id, subject, description, 
                    status, priority, created_at, updated_at
                ) VALUES (
                    :company_id, :platform, :ticket_id, :subject, :description,
                    :status, :priority, :created_at, :updated_at
                ) RETURNING id
            """
            
            result = session.execute(text(query), ticket_data)
            inserted_id = result.fetchone()[0]
            
            return str(inserted_id)
    
    async def delete_tenant_data(self, company_id: str) -> Dict[str, int]:
        """테넌트 데이터 완전 삭제 (GDPR 준수)"""
        
        with self.db.get_tenant_session(company_id) as session:
            # 관련 모든 테이블에서 데이터 삭제
            tables = ['tickets', 'conversations', 'attachments', 'summaries']
            deletion_counts = {}
            
            for table in tables:
                query = f"DELETE FROM {table} WHERE company_id = :company_id"
                result = session.execute(text(query), {"company_id": company_id})
                deletion_counts[table] = result.rowcount
            
            return deletion_counts

# 전역 DB 인스턴스
tenant_db = TenantSafeSession(os.getenv("DATABASE_URL"))
tenant_queries = TenantSafeQueries(tenant_db)
```

---

## 🔍 **벡터 DB 테넌트 격리**

### 🎯 **Qdrant 필터링 보안**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

class SecureVectorDB:
    """보안이 강화된 벡터 데이터베이스 인터페이스"""
    
    def __init__(self):
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.collection_name = "documents"
    
    def _create_tenant_filter(
        self,
        company_id: str,
        platform: str = None,
        additional_filters: Dict[str, Any] = None
    ) -> Filter:
        """테넌트 격리 필터 생성"""
        
        # 필수 테넌트 필터
        conditions = [
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            )
        ]
        
        # 플랫폼 필터 (선택적)
        if platform:
            conditions.append(
                FieldCondition(
                    key="platform",
                    match=MatchValue(value=platform)
                )
            )
        
        # 추가 필터 적용
        if additional_filters:
            for field, value in additional_filters.items():
                if isinstance(value, list):
                    conditions.append(
                        FieldCondition(
                            key=field,
                            match=MatchAny(any=value)
                        )
                    )
                else:
                    conditions.append(
                        FieldCondition(
                            key=field,
                            match=MatchValue(value=value)
                        )
                    )
        
        return Filter(must=conditions)
    
    async def secure_search(
        self,
        company_id: str,
        query_vector: List[float],
        platform: str = None,
        limit: int = 10,
        additional_filters: Dict[str, Any] = None
    ) -> List[Dict]:
        """테넌트 격리가 보장된 벡터 검색"""
        
        # 테넌트 검증
        if not validate_company_id(company_id):
            raise ValueError(f"Invalid company_id: {company_id}")
        
        # 테넌트 필터 생성
        tenant_filter = self._create_tenant_filter(
            company_id=company_id,
            platform=platform,
            additional_filters=additional_filters
        )
        
        try:
            # 검색 실행
            search_result = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=tenant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            # 결과 후처리 및 보안 검증
            secure_results = []
            for point in search_result:
                # 이중 검증: 결과의 company_id 재확인
                result_company_id = point.payload.get('company_id')
                if result_company_id != company_id:
                    logger.error(f"Security violation: Found document with company_id {result_company_id} when searching for {company_id}")
                    continue
                
                # 민감한 정보 제거
                safe_payload = self._sanitize_payload(point.payload)
                
                secure_results.append({
                    'id': point.id,
                    'score': point.score,
                    'payload': safe_payload
                })
            
            # 액세스 로깅
            await tenant_logger.log_api_access(
                tenant_context=TenantContext(company_id, platform),
                endpoint="vector_search",
                method="POST",
                request_data={"query_vector_size": len(query_vector), "limit": limit},
                response_status=200
            )
            
            return secure_results
            
        except Exception as e:
            logger.error(f"Secure vector search failed for {company_id}: {e}")
            
            # 에러 로깅
            await tenant_logger.log_api_access(
                tenant_context=TenantContext(company_id, platform),
                endpoint="vector_search",
                method="POST",
                error=str(e),
                response_status=500
            )
            
            raise e
    
    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """페이로드에서 민감한 정보 제거"""
        
        # 민감한 필드 목록
        sensitive_fields = [
            'original_data.email',
            'original_data.phone',
            'original_data.address',
            'original_data.credit_card',
            'original_data.ssn'
        ]
        
        sanitized = payload.copy()
        
        # 중첩된 필드 처리
        for field in sensitive_fields:
            if '.' in field:
                keys = field.split('.')
                current = sanitized
                
                for key in keys[:-1]:
                    if key in current and isinstance(current[key], dict):
                        current = current[key]
                    else:
                        break
                else:
                    # 마지막 키 제거
                    final_key = keys[-1]
                    if final_key in current:
                        current[final_key] = "[REDACTED]"
            else:
                if field in sanitized:
                    sanitized[field] = "[REDACTED]"
        
        return sanitized
    
    async def secure_upsert(
        self,
        company_id: str,
        points: List[PointStruct]
    ) -> Dict[str, Any]:
        """테넌트 검증이 포함된 벡터 업서트"""
        
        # 모든 포인트의 테넌트 정보 검증
        for point in points:
            point_company_id = point.payload.get('company_id')
            
            if point_company_id != company_id:
                raise ValueError(f"Point company_id mismatch: {point_company_id} != {company_id}")
            
            # 필수 필드 확인
            required_fields = ['company_id', 'platform', 'data_type']
            for field in required_fields:
                if field not in point.payload:
                    raise ValueError(f"Missing required field '{field}' in point payload")
        
        try:
            result = await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )
            
            # 성공 로깅
            await tenant_logger.log_api_access(
                tenant_context=TenantContext(company_id),
                endpoint="vector_upsert",
                method="POST",
                request_data={"points_count": len(points)},
                response_status=200
            )
            
            return {
                'status': 'success',
                'points_count': len(points),
                'operation_id': result.operation_id if hasattr(result, 'operation_id') else None
            }
            
        except Exception as e:
            logger.error(f"Secure vector upsert failed for {company_id}: {e}")
            
            # 에러 로깅
            await tenant_logger.log_api_access(
                tenant_context=TenantContext(company_id),
                endpoint="vector_upsert",
                method="POST",
                error=str(e),
                response_status=500
            )
            
            raise e

# 전역 보안 벡터 DB 인스턴스
secure_vector_db = SecureVectorDB()
```

---

## 🚨 **보안 모니터링 & 알림**

### 📊 **테넌트 액세스 모니터링**

```python
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio

class TenantSecurityMonitor:
    """테넌트 보안 모니터링 시스템"""
    
    def __init__(self):
        self.access_patterns = defaultdict(lambda: {
            'requests': deque(maxlen=1000),  # 최근 1000개 요청
            'failed_attempts': deque(maxlen=100),  # 최근 100개 실패
            'data_access_volume': deque(maxlen=100)  # 데이터 액세스 볼륨
        })
    
    async def track_access(
        self,
        company_id: str,
        user_id: str,
        endpoint: str,
        success: bool,
        data_size: int = 0
    ):
        """액세스 패턴 추적"""
        
        timestamp = datetime.utcnow()
        access_key = f"{company_id}:{user_id}"
        
        # 요청 기록
        self.access_patterns[access_key]['requests'].append({
            'timestamp': timestamp,
            'endpoint': endpoint,
            'success': success,
            'data_size': data_size
        })
        
        # 실패 시 별도 추적
        if not success:
            self.access_patterns[access_key]['failed_attempts'].append({
                'timestamp': timestamp,
                'endpoint': endpoint
            })
        
        # 데이터 액세스 볼륨 추적
        if data_size > 0:
            self.access_patterns[access_key]['data_access_volume'].append({
                'timestamp': timestamp,
                'size': data_size
            })
        
        # 실시간 이상 징후 탐지
        await self._detect_anomalies(access_key)
    
    async def _detect_anomalies(self, access_key: str):
        """이상 징후 탐지"""
        
        pattern = self.access_patterns[access_key]
        now = datetime.utcnow()
        
        # 1. 과도한 실패 시도 감지
        recent_failures = [
            f for f in pattern['failed_attempts']
            if now - f['timestamp'] < timedelta(minutes=10)
        ]
        
        if len(recent_failures) >= 5:
            await self._alert_excessive_failures(access_key, recent_failures)
        
        # 2. 비정상적인 데이터 액세스 볼륨 감지
        recent_access = [
            a for a in pattern['data_access_volume']
            if now - a['timestamp'] < timedelta(hours=1)
        ]
        
        if recent_access:
            total_volume = sum(a['size'] for a in recent_access)
            if total_volume > 100 * 1024 * 1024:  # 100MB 초과
                await self._alert_large_data_access(access_key, total_volume)
        
        # 3. 비정상적인 요청 패턴 감지
        recent_requests = [
            r for r in pattern['requests']
            if now - r['timestamp'] < timedelta(minutes=5)
        ]
        
        if len(recent_requests) >= 100:  # 5분 내 100회 이상
            await self._alert_high_frequency_access(access_key, len(recent_requests))
    
    async def _alert_excessive_failures(self, access_key: str, failures: List[Dict]):
        """과도한 실패 알림"""
        company_id, user_id = access_key.split(':')
        
        alert = {
            'type': 'EXCESSIVE_FAILURES',
            'severity': 'HIGH',
            'company_id': company_id,
            'user_id': user_id,
            'failure_count': len(failures),
            'time_window': '10 minutes',
            'recent_endpoints': list(set(f['endpoint'] for f in failures[-5:]))
        }
        
        await self._send_security_alert(alert)
    
    async def _alert_large_data_access(self, access_key: str, total_volume: int):
        """대용량 데이터 액세스 알림"""
        company_id, user_id = access_key.split(':')
        
        alert = {
            'type': 'LARGE_DATA_ACCESS',
            'severity': 'MEDIUM',
            'company_id': company_id,
            'user_id': user_id,
            'data_volume_mb': total_volume / (1024 * 1024),
            'time_window': '1 hour'
        }
        
        await self._send_security_alert(alert)
    
    async def _alert_high_frequency_access(self, access_key: str, request_count: int):
        """고빈도 액세스 알림"""
        company_id, user_id = access_key.split(':')
        
        alert = {
            'type': 'HIGH_FREQUENCY_ACCESS',
            'severity': 'MEDIUM',
            'company_id': company_id,
            'user_id': user_id,
            'request_count': request_count,
            'time_window': '5 minutes'
        }
        
        await self._send_security_alert(alert)
    
    async def _send_security_alert(self, alert: Dict[str, Any]):
        """보안 알림 전송"""
        
        # 로그 기록
        logger.warning(f"SECURITY_ALERT: {orjson.dumps(alert).decode()}")
        
        # 외부 알림 시스템 연동 (예: Slack, 이메일)
        if alert['severity'] == 'HIGH':
            # 즉시 알림
            await send_immediate_alert(alert)
        else:
            # 배치 알림 (5분 간격)
            await queue_batch_alert(alert)
    
    def get_tenant_security_report(self, company_id: str) -> Dict[str, Any]:
        """테넌트별 보안 리포트 생성"""
        
        tenant_patterns = {
            k: v for k, v in self.access_patterns.items()
            if k.startswith(f"{company_id}:")
        }
        
        if not tenant_patterns:
            return {'company_id': company_id, 'status': 'no_data'}
        
        # 통계 계산
        total_requests = sum(len(p['requests']) for p in tenant_patterns.values())
        total_failures = sum(len(p['failed_attempts']) for p in tenant_patterns.values())
        total_users = len(tenant_patterns)
        
        # 최근 24시간 활동
        now = datetime.utcnow()
        recent_activity = 0
        
        for pattern in tenant_patterns.values():
            recent_activity += len([
                r for r in pattern['requests']
                if now - r['timestamp'] < timedelta(hours=24)
            ])
        
        return {
            'company_id': company_id,
            'total_users': total_users,
            'total_requests': total_requests,
            'total_failures': total_failures,
            'failure_rate': total_failures / max(total_requests, 1),
            'recent_24h_activity': recent_activity,
            'status': 'active' if recent_activity > 0 else 'inactive'
        }

# 전역 보안 모니터 인스턴스
security_monitor = TenantSecurityMonitor()
```

---

## 📚 **관련 참조 지침서**

- **data-collection-patterns.instructions.md** - 데이터 수집 시 테넌트 태깅
- **data-processing-llm.instructions.md** - LLM 처리 시 테넌트 격리
- **vector-storage-search.instructions.md** - 벡터 DB 테넌트 필터링
- **backend-implementation-patterns.instructions.md** - API 보안 패턴
- **quick-reference.instructions.md** - 핵심 보안 체크리스트

---

## 🔗 **크로스 참조**

이 지침서는 다음과 연계됩니다:
- **API 보안**: 모든 엔드포인트의 테넌트 인증/인가
- **데이터 처리**: 모든 데이터 파이프라인의 테넌트 격리
- **벡터 검색**: 벡터 DB의 테넌트별 필터링
- **모니터링**: 보안 이벤트 감지 및 알림

**세션 간 일관성**: 이 멀티테넌트 보안 패턴들은 AI 세션이 바뀌어도 반드시 동일하게 적용되어야 합니다.
