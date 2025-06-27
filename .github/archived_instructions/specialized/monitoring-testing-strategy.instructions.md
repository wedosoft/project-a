````instructions
---
applyTo: "**"
---

# 📊 모니터링 & 테스트 전략 지침서

_AI 참조 최적화 버전 - 모니터링, 메트릭, 테스트 전략 가이드_

## 📋 **TL;DR - 모니터링 & 테스트 핵심 요약**

### 📊 **핵심 모니터링 메트릭**
- **성능**: LLM 응답시간, 벡터 검색시간, API 응답시간, 캐시 적중률
- **비즈니스**: 처리된 티켓 수, 사용자 만족도, 플랫폼별 사용량, 에러율
- **알림 임계값**: API 응답 5초+, 에러율 5%+, 캐시 적중률 60%-

### 🧪 **핵심 테스트 전략**
- **단위 테스트**: 플랫폼 어댑터, 데이터 모델, 캐싱, 멀티테넌트
- **통합 테스트**: API 엔드포인트, DB 연동, LLM 체인, 멀티플랫폼
- **성능 테스트**: 100 RPS 부하, 캐시 70%+, LLM 3초-, 메모리 최적화

---

## 📊 **모니터링, 메트릭 & 알림 (AI 구현 필수 체크리스트)**

### ✅ **모니터링 필수 구현 체크리스트**

**성능 메트릭 (Prometheus)**:

- [x] **LLM 요청 시간**: `llm_request_duration_seconds` (히스토그램)
- [x] **벡터 검색 시간**: `vector_search_duration_seconds` (히스토그램)
- [x] **캐시 적중률**: `cache_hit_rate_percent` (게이지)
- [x] **API 응답 시간**: `api_response_duration_seconds` (히스토그램)

**비즈니스 메트릭**:

- [x] **처리된 티켓 수**: `tickets_processed_total` (카운터)
- [x] **사용자 만족도**: `user_satisfaction_score` (게이지)
- [x] **플랫폼별 사용량**: `platform_usage_by_type` (카운터)
- [x] **에러율**: `error_rate_percent` (게이지)

### 📈 **핵심 메트릭 수집 패턴**

**LLM 성능 메트릭**:

```python
from prometheus_client import Histogram, Counter, Gauge
import time

# 메트릭 정의
llm_request_duration = Histogram(
    "llm_request_duration_seconds",
    "LLM 요청 처리 시간",
    ["company_id", "model_name", "request_type"]
)

llm_token_usage = Histogram(
    "llm_token_usage_total",
    "LLM 토큰 사용량",
    ["company_id", "model_name", "token_type"]
)

# 메트릭 수집 데코레이터
def track_llm_performance(request_type: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            company_id = current_company_id.get()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                llm_request_duration.labels(
                    company_id=company_id,
                    model_name="gpt-4",
                    request_type=request_type
                ).observe(duration)
                return result
            except Exception as e:
                # 에러 메트릭 수집
                llm_error_counter.labels(
                    company_id=company_id,
                    error_type=type(e).__name__
                ).inc()
                raise
        return wrapper
    return decorator
```

**캐시 성능 모니터링**:

```python
cache_hit_counter = Counter("cache_hits_total", "캐시 적중 횟수", ["cache_type", "company_id"])
cache_miss_counter = Counter("cache_misses_total", "캐시 실패 횟수", ["cache_type", "company_id"])

async def monitor_cache_performance(cache_key: str, cache_type: str):
    """캐시 성능 모니터링"""
    company_id = current_company_id.get()

    cached_value = await redis_client.get(cache_key)
    if cached_value:
        cache_hit_counter.labels(cache_type=cache_type, company_id=company_id).inc()
        return orjson.loads(cached_value)
    else:
        cache_miss_counter.labels(cache_type=cache_type, company_id=company_id).inc()
        return None
```

### 🚨 **알림 & 임계값 관리**

**핵심 알림 임계값**:

```python
ALERT_THRESHOLDS = {
    "api_response_time": 5.0,  # 5초 이상 시 알림
    "error_rate": 0.05,        # 5% 이상 에러율 시 알림
    "cache_hit_rate": 0.6,     # 60% 미만 캐시 적중률 시 알림
    "llm_request_time": 10.0,  # 10초 이상 LLM 응답 시 알림
}

async def check_performance_alerts():
    """성능 임계값 모니터링 및 알림"""
    current_metrics = await collect_current_metrics()

    for metric_name, threshold in ALERT_THRESHOLDS.items():
        current_value = current_metrics.get(metric_name)
        if current_value and should_alert(metric_name, current_value, threshold):
            await send_alert(metric_name, current_value, threshold)
```

**Grafana 대시보드 구성**:

```yaml
# grafana-dashboard.yaml
dashboard:
  title: "RAG System Performance"
  panels:
    - title: "LLM Response Time"
      type: "graph"
      query: "llm_request_duration_seconds"
      alert:
        threshold: 5.0
        condition: "avg() > 5"

    - title: "Cache Hit Rate"
      type: "stat"
      query: "rate(cache_hits_total) / (rate(cache_hits_total) + rate(cache_misses_total))"
      alert:
        threshold: 0.6
        condition: "avg() < 0.6"
```

### 📊 **구조화된 로깅 패턴**

**JSON 로깅 구조**:

```python
import structlog
import orjson

# 구조화된 로거 설정
logger = structlog.get_logger()

async def log_api_request(request: Request, response_time: float, status_code: int):
    """API 요청 구조화 로깅"""
    company_id = current_company_id.get()

    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "company_id": company_id,
        "request_id": str(uuid4()),
        "method": request.method,
        "url": str(request.url),
        "response_time": response_time,
        "status_code": status_code,
        "user_agent": request.headers.get("user-agent"),
        "platform_type": request.headers.get("X-Platform-Type")
    }

    logger.info("api_request", **log_data)
```

### ⚠️ **모니터링 주의사항**

- 🚨 **민감정보 제외**: 로그에 API 키, 개인정보 절대 기록 금지
- 🚨 **성능 영향 최소화**: 메트릭 수집이 응답시간에 영향 주지 않도록
- 🚨 **테넌트별 분리**: 모든 메트릭에 company_id 라벨 필수 포함
- 🚨 **알림 피로도**: 중요한 알림만 설정, 스팸 알림 방지

---

## 🧪 **테스트 전략 & 품질 보증 (AI 구현 필수 체크리스트)**

### ✅ **테스트 전략 필수 구현 체크리스트**

**단위 테스트 (Unit Tests)**:

- [x] **플랫폼 어댑터**: 각 플랫폼별 어댑터 로직 검증
- [x] **데이터 모델**: Pydantic 모델 검증 및 직렬화 테스트
- [x] **캐싱 로직**: Redis 캐시 히트/미스 시나리오
- [x] **멀티테넌트**: company_id 격리 로직 검증

**통합 테스트 (Integration Tests)**:

- [x] **API 엔드포인트**: 실제 플랫폼 연동 테스트
- [x] **데이터베이스**: PostgreSQL + Qdrant 연동 검증
- [x] **LLM 체인**: langchain 체인 전체 플로우 테스트
- [x] **멀티플랫폼**: Freshdesk ↔ 백엔드 전체 연동

**성능 테스트 (Performance Tests)**:

- [x] **부하 테스트**: 100 RPS 동시 요청 처리 능력
- [x] **캐시 성능**: Redis 캐시 적중률 70% 이상 검증
- [x] **LLM 응답시간**: 평균 3초 이하 목표 달성 검증
- [x] **메모리 사용량**: 메모리 누수 및 최적화 검증

### 🧪 **핵심 테스트 패턴**

**멀티테넌트 격리 테스트**:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_tenant_isolation():
    """테넌트 간 데이터 격리 테스트"""

    # 테넌트 1 데이터 생성
    async with AsyncClient() as client:
        response1 = await client.post(
            "/api/query",
            headers={"X-Company-ID": "company1"},
            json={"query": "test query", "ticket_id": "123"}
        )

    # 테넌트 2에서 테넌트 1 데이터 접근 시도
    async with AsyncClient() as client:
        response2 = await client.post(
            "/api/query",
            headers={"X-Company-ID": "company2"},
            json={"query": "test query", "ticket_id": "123"}
        )

    # 테넌트 2는 테넌트 1의 데이터에 접근할 수 없어야 함
    assert response2.status_code == 404 or response2.json()["results"] == []
```

**플랫폼 어댑터 테스트**:

```python
@pytest.mark.asyncio
async def test_platform_adapter_factory():
    """플랫폼 어댑터 팩토리 테스트"""

    # Freshdesk 어댑터 생성 테스트
    freshdesk_adapter = await create_platform_adapter("freshdesk", "company1")
    assert isinstance(freshdesk_adapter, FreshdeskAdapter)

    with pytest.raises(NotImplementedError):

    # 지원하지 않는 플랫폼 테스트
    with pytest.raises(UnsupportedPlatformError):
        await create_platform_adapter("unsupported", "company3")
```

**LLM 체인 성능 테스트**:

```python
@pytest.mark.asyncio
async def test_llm_chain_performance():
    """LLM 체인 성능 및 캐싱 테스트"""

    query = "How to resolve login issues?"
    context = "User cannot login to the application"

    # 첫 번째 요청 (캐시 미스)
    start_time = time.time()
    response1 = await generate_ai_response("company1", query, context)
    first_duration = time.time() - start_time

    # 두 번째 요청 (캐시 히트)
    start_time = time.time()
    response2 = await generate_ai_response("company1", query, context)
    second_duration = time.time() - start_time

    # 캐시로 인한 성능 향상 검증
    assert response1 == response2  # 동일한 응답
    assert second_duration < first_duration * 0.1  # 90% 이상 빨라짐
```

### 📊 **테스트 데이터 관리**

**테스트 픽스처 패턴**:

```python
@pytest.fixture
async def test_company_data():
    """테스트용 회사 데이터 픽스처"""
    company_id = "test_company"

    # 테스트 데이터 생성
    test_tickets = [
        {
            "id": "ticket_1",
            "company_id": company_id,
            "subject": "Login Issue",
            "description": "User cannot login"
        },
        {
            "id": "ticket_2",
            "company_id": company_id,
            "subject": "Password Reset",
            "description": "User wants to reset password"
        }
    ]

    # 데이터 삽입
    await insert_test_data(company_id, test_tickets)

    yield company_id, test_tickets

    # 테스트 후 정리
    await cleanup_test_data(company_id)

@pytest.fixture
async def redis_test_client():
    """테스트용 Redis 클라이언트"""
    import aioredis

    # 테스트용 Redis DB (DB 15 사용)
    redis = aioredis.from_url("redis://localhost:6379/15")
    yield redis

    # 테스트 후 모든 키 삭제
    await redis.flushdb()
    await redis.close()
```

### 🚨 **테스트 환경 격리**

**환경별 설정 분리**:

```python
# tests/conftest.py
import os
import pytest
from backend.core.config import get_settings

@pytest.fixture(scope="session")
def test_settings():
    """테스트 환경 설정"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test_db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"
    os.environ["QDRANT_URL"] = "http://localhost:6333"

    return get_settings()

@pytest.fixture(autouse=True)
async def setup_test_db(test_settings):
    """각 테스트마다 DB 초기화"""
    # 테스트 DB 초기화
    await init_test_database()
    yield
    # 테스트 후 정리
    await cleanup_test_database()
```

### ⚠️ **테스트 주의사항**

- 🚨 **실제 데이터 사용 금지**: 프로덕션 데이터는 절대 테스트에 사용 금지
- 🚨 **테스트 격리**: 각 테스트는 독립적으로 실행 가능해야 함
- 🚨 **성능 회귀 방지**: 성능 테스트로 코드 변경 시 성능 저하 조기 발견
- 🚨 **멀티테넌트 필수**: 모든 테스트에서 company_id 격리 검증

---

## ✅ **모니터링 & 테스트 체크리스트**

### 🔍 **모니터링 구현 체크리스트**

- [ ] Prometheus 메트릭 수집 구현
- [ ] Grafana 대시보드 구성
- [ ] 알림 임계값 설정 (API 5초+, 에러율 5%+, 캐시 60%-)
- [ ] 구조화된 로깅 적용 (JSON, company_id 포함)
- [ ] 성능 메트릭 자동 수집 (LLM, 벡터 검색, API 응답시간)
- [ ] 비즈니스 메트릭 추적 (티켓 처리량, 만족도, 플랫폼 사용량)

### 🧪 **테스트 구현 체크리스트**

- [ ] 멀티테넌트 격리 테스트 구현
- [ ] 플랫폼 어댑터 단위 테스트
- [ ] LLM 체인 통합 테스트
- [ ] 캐시 성능 테스트 (70% 적중률 목표)
- [ ] API 부하 테스트 (100 RPS)
- [ ] 테스트 환경 격리 설정
- [ ] 테스트 데이터 픽스처 구성
- [ ] 성능 회귀 테스트 자동화

---

## 🔗 **관련 지침서 참조**

- 📚 [Quick Reference](quick-reference.instructions.md) - 즉시 참조용 핵심 패턴
- ⚡ [성능 최적화](performance-optimization.instructions.md) - 성능 향상 전략 상세
- 🔒 [멀티테넌트 보안](multitenant-security.instructions.md) - 보안 테스트 전략
- 📊 [시스템 아키텍처](system-architecture.instructions.md) - 전체 시스템 구조
- 🛠️ [에러 처리 & 디버깅](error-handling-debugging.instructions.md) - 에러 처리 패턴

**2025년 6월 21일 기준 - AI 세션 간 일관성 보장**
````
