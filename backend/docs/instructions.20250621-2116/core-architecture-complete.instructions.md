---
applyTo: "**"
---

# 🏗️ 핵심 아키텍처 & 성능 설계 지침서

_AI 참조 최적화 버전 - 세션 간 일관성 보장을 위한 아키텍처 가이드_

## 🎯 시스템 목표

**Freshdesk 기반 글로벌 SaaS 멀티테넌트 AI 상담사 지원 시스템**

- **성능 목표**: LLM 응답 5~10초 → 1~2초 단축
- **확장성**: Freshdesk → Zendesk → ServiceNow 순차 확장
- **멀티테넌트**: company_id 기반 완전 데이터 격리
- **글로벌화**: i18n 다국어 지원 내장

---

## 🚀 **TL;DR - 핵심 아키텍처 요약**

### 💡 **즉시 참조용 핵심 포인트**

**디렉터리 구조 (2025년 6월 21일 모듈화 완료)**:

```
backend/
├── api/           # FastAPI 라우터 & 엔드포인트
│   ├── routes/    # API 엔드포인트 (reply.py, ingest.py)
│   │   └── ingest.py     # ingest API 엔드포인트 (단순 래퍼)
│   ├── models/    # API 모델 (ingest_job.py)
│   ├── ingest_legacy_20250621.py  # 백업된 모노리식 파일
│   └── main.py    # FastAPI 애플리케이션
├── core/          # 핵심 비즈니스 로직
│   ├── llm/       # LLM 라우팅 & 관리 (모듈화 완료)
│   │   ├── clients.py    # LLM 클라이언트 구현
│   │   ├── router.py     # LLM 라우터 로직
│   │   ├── models.py     # LLM 모델 정의
│   │   ├── utils.py      # LLM 유틸리티
│   │   ├── metrics.py    # LLM 메트릭
│   │   └── __init__.py   # 모듈 인터페이스
│   ├── ingest/    # 데이터 수집 파이프라인 (모듈화 완료)
│   │   ├── processor.py  # 핵심 ingest 함수 (주요 비즈니스 로직)
│   │   ├── validator.py  # 데이터 검증 및 필터링
│   │   ├── integrator.py # 통합 객체 생성 및 병합
│   │   ├── storage.py    # 저장소 관리 (Qdrant, SQLite)
│   │   └── __init__.py   # 모듈 인터페이스 (ingest 함수 export)
│   ├── config.py  # 설정 관리
│   └── __init__.py
├── data/          # 데이터 처리 (storage 인터페이스)
└── freshdesk/     # 플랫폼별 구현
```

**기술 스택**:

- **Backend**: FastAPI + asyncio + langchain
- **Vector DB**: Qdrant Cloud (단일 컬렉션)
- **Cache**: Redis (LLM 응답 캐싱 필수)
- **DB**: PostgreSQL (프로덕션) / JSON 파일 (MVP)

**멀티테넌트 전략**:

- company_id 자동 추출: `domain.split('.')[0]`
- Row-level Security (PostgreSQL) + Filter (Qdrant)
- 모든 API에 X-Company-ID 헤더 필수

**성능 최적화**:

- **orjson**: JSON 직렬화 2-3배 향상
- **pydantic v2**: 데이터 검증 5-50배 향상
- **Redis**: LLM 응답 캐싱으로 비용/지연시간 대폭 감소

### 🚨 **아키텍처 주의사항 (2025년 6월 21일 기준)**

- ⚠️ 기존 디렉터리 구조 변경 금지 → 점진적 개선만
- ⚠️ company_id 없는 컴포넌트 절대 금지 → 멀티테넌트 필수
- ⚠️ 플랫폼별 하드코딩 금지 → 추상화 패턴 필수 적용
- ⚠️ 성능 최적화는 점진적 도입 → 기존 코드 안정성 우선

### ✅ **모듈화 작업 완료 상태 (2025년 6월 21일)**

**LLM 라우터 모듈화 (완료)**:
- 기존 `llm_router.py` → `core/llm/` 하위 5개 모듈로 분리
- 모든 import 경로 업데이트 및 정상 동작 검증

**데이터 수집 파이프라인 모듈화 (완료)**:
- 대용량 `api/ingest.py` (1,400+ 라인) → `ingest_legacy_20250621.py`로 백업
- `core/ingest/` 하위 4개 모듈로 완전 분리:
  - `processor.py`: 핵심 ingest 함수 및 비즈니스 로직
  - `validator.py`: 데이터 검증 및 필터링
  - `integrator.py`: 통합 객체 생성 및 병합  
  - `storage.py`: 저장소 관리 (Qdrant, SQLite)
- API 엔드포인트 `api/routes/ingest.py`는 단순 래퍼 역할로 분리
- 모든 import 경로 변경: `from api.ingest import ingest` → `from core.ingest import ingest`

---

## ⚠️ **리팩토링 철칙 (AI 세션 간 일관성 핵심)**

### 🔄 **기존 코드 재활용 원칙**

**목적**: 세션이 바뀌어도 동일한 아키텍처 유지

- **기존 코드 90% 이상 재활용**: 임의로 새로운 코딩 절대 금지
- **레거시 코드 로직 보존**: 안정적으로 작동하던 기존 로직을 벗어나지 않음
- **점진적 개선만**: 기존 코드를 다듬어 사용, 전면 재작성 금지
- **검증된 로직 유지**: 기존 비즈니스 로직과 데이터 처리 방식 최대한 보존

### 🆕 **성능 최적화 스택 (AI 구현 시 권장 적용)**

**핵심 성능 프레임워크**:

```
langchain (LLM 통합) + Redis (캐싱) + FastAPI + Pydantic v2
```

**현재 구현 완료**:

- **langchain**: LLM 통합 및 체인 관리 (✅ 완료)
- **pydantic v2**: 데이터 검증 성능 향상 (✅ 완료)
- **redis**: 캐싱 인프라 준비 (✅ 완료)
- **FastAPI**: 기본 비동기 성능 (✅ 완료)

**향후 성능 가속화 로드맵**:

- **orjson**: JSON 직렬화 성능 향상 (2-3배) → 향후 추가 예정
- **asyncpg**: PostgreSQL 비동기 드라이버 (3배) → 프로덕션 마이그레이션 시
- **fastapi-cache2**: FastAPI 캐싱 데코레이터 → 향후 추가 예정
- **prometheus-client**: 메트릭 수집 및 모니터링 (✅ 부분 완료)

**AI 구현 시 현재 import 패턴**:

```python
from pydantic import BaseModel, Field  # v2 사용 (완료)
import redis  # 캐싱 인프라 (완료)
from langchain.llms import OpenAI  # LLM 통합 (완료)
from langchain_qdrant import Qdrant  # 벡터 DB 통합 (완료)
```

---

## 🏗️ **플랫폼별 어댑터 패턴 (AI 구현 필수 체크리스트)**

### ✅ **플랫폼 확장 체크리스트**

**현재 MVP 상태**:

- [x] Freshdesk 어댑터 완전 구현 (`backend/core/platforms/freshdesk/`)
- [x] Zendesk 어댑터 스켈레톤 (`NotImplementedError` 패턴)
- [x] 다른 플랫폼(ServiceNow, Jira) 코드 완전 제거
- [x] 팩토리 패턴 기반 플랫폼 감지 자동화

**확장 시 필수 단계**:

- [ ] `factory.py`에서 새 플랫폼 어댑터 등록 (`register_adapter`)
- [ ] 새 플랫폼 디렉터리에 `adapter.py`, `models.py`, `client.py` 구현
- [ ] 공통 인터페이스 (`PlatformAdapter`) 준수
- [ ] company_id 자동 추출 로직 구현

### 🔄 **플랫폼 어댑터 핵심 코드 패턴**

**플랫폼 감지 패턴** (`config.py`):

```python
@property
def extracted_company_id(self) -> str:
    """도메인에서 company_id를 자동으로 추출"""
    domain = self.FRESHDESK_DOMAIN

    if ".freshdesk.com" in domain:
        company_id = domain.replace(".freshdesk.com", "")
    else:
        company_id = domain

    return company_id
```

**어댑터 팩토리 패턴** (`factory.py`):

```python
class PlatformFactory:
    """플랫폼 어댑터 팩토리"""

    @classmethod
    def create_adapter(cls, platform: str, config: dict) -> PlatformAdapter:
        """플랫폼별 어댑터 생성"""
        platform_key = platform.lower()

        if platform_key not in cls._adapters:
            raise ValueError(f"지원하지 않는 플랫폼: {platform}")

        adapter_class = cls._adapters[platform_key]
        return adapter_class(config)
```

**company_id 추출 패턴** (실제 구현):

```python
# config.py에서 자동 추출
@property
def extracted_company_id(self) -> str:
    """FRESHDESK_DOMAIN에서 company_id를 자동으로 추출"""
    domain = self.FRESHDESK_DOMAIN

    if ".freshdesk.com" in domain:
        company_id = domain.replace(".freshdesk.com", "")
    else:
        company_id = domain

    return company_id

# 사용 예시
from core.config import get_settings
settings = get_settings()
company_id = settings.extracted_company_id  # "wedosoft"
```

### ⚠️ **플랫폼 어댑터 주의사항**

- 🚨 **절대 금지**: 플랫폼별 하드코딩, 조건문 남발
- 🚨 **필수 준수**: 모든 어댑터는 `PlatformAdapter` 인터페이스 구현
- 🚨 **company_id 필수**: 모든 플랫폼 작업에 테넌트 ID 포함
- 🚨 **에러 처리**: `ImportError`를 활용한 향후 확장 준비

---

## 📡 API 아키텍처 (단순화)

### 8개 핵심 엔드포인트 (실제 구현)

1. `/init` - 티켓 초기 데이터 (Redis 캐싱)
2. `/query` - AI 채팅 (langchain 체인)
3. `/reply` - 추천 답변 생성
4. `/ingest` - 관리자용 데이터 수집 (멀티플랫폼)
5. `/health` - 헬스체크 (멀티 서비스)
6. `/metrics` - 성능 메트릭 (Prometheus)
7. `/attachments/*` - 첨부파일 접근 (멀티테넌트 보안)
8. 스트리밍 엔드포인트는 각 라우터 내부에 구현

### API 구조 특징

- **버전 관리 없음**: `/api/routes/` 직접 구조
- **확장 가능**: 필요시 버전 관리 추가 가능한 구조
- **단순성**: 복잡도 최소화, 유지보수성 최대화

---

## 📁 백엔드 파일 구조 (리팩토링 아키텍처)

```
backend/
├── api/
│   ├── routes/                     # 엔드포인트별 라우트 (버전 관리 없음)
│   │   ├── __init__.py
│   │   ├── init.py                 # /init 엔드포인트
│   │   ├── query.py                # /query 엔드포인트
│   │   ├── reply.py                # /reply 엔드포인트
│   │   ├── ingest.py               # /ingest 엔드포인트
│   │   ├── health.py               # /health 엔드포인트
│   │   ├── metrics.py              # /metrics 엔드포인트
│   │   └── attachments.py          # /attachments/*
│   ├── dependencies.py             # FastAPI 의존성
│   ├── multi_platform_attachments.py # 레거시 지원
│   └── main.py                     # FastAPI 앱 진입점
├── core/
│   ├── platforms/                  # 플랫폼별 어댑터 (확장 가능)
│   │   ├── __init__.py
│   │   ├── factory.py              # 플랫폼 팩토리 (Freshdesk/Zendesk 지원)
│   │   ├── freshdesk/              # Freshdesk 완전 구현
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py          # Freshdesk 어댑터
│   │   │   ├── models.py           # Freshdesk 데이터 모델
│   │   │   └── optimized_fetcher.py # 데이터 수집기
│   │   └── zendesk/                # Zendesk 추상화 (향후 구현용)
│   │       ├── __init__.py
│   │       └── adapter.py          # Zendesk 어댑터 (ImportError 처리)
│   ├── llm/                        # LLM 모듈 (모듈화 완료)
│   │   ├── __init__.py
│   │   ├── router.py               # LLM 라우팅 로직 (메인)
│   │   ├── clients.py              # LLM 클라이언트 (OpenAI, Anthropic 등)
│   │   ├── models.py               # LLM 요청/응답 모델
│   │   ├── utils.py                # LLM 유틸리티 (캐싱, API 키 검증 등)
│   │   └── metrics.py              # LLM 메트릭 및 성능 추적
   ├── ingest/                     # 데이터 수집/처리 모듈 (2025년 6월 21일 모듈화 완료)
│   │   ├── __init__.py
│   │   ├── processor.py            # 메인 ingest 함수 (핵심 로직, 1400+ 라인에서 분리)
│   │   ├── validator.py            # 데이터 검증 및 필터링
│   │   ├── integrator.py           # 통합 객체 생성 및 병합
│   │   └── storage.py              # 저장소 관리 (SQLite, Qdrant)
│   ├── langchain/                  # langchain 통합 모듈
│   │   ├── __init__.py
│   │   └── (기타 langchain 모듈들)
│   ├── migration/                  # 기존 코드 마이그레이션
│   │   └── (마이그레이션 유틸리티들)
│   ├── config.py                   # 메인 설정 (pydantic v2, company_id 자동 추출)
│   ├── database.py                 # SQLite 데이터베이스 관리 (멀티테넌트 지원)
│   ├── vectordb.py                 # Qdrant 벡터 DB 연동
│   ├── embedder.py                 # 임베딩 처리
│   ├── context_builder.py          # 컨텍스트 구성
│   ├── data_merger.py              # 데이터 병합
│   ├── retriever.py                # 검색 로직
│   ├── search_optimizer.py         # 검색 최적화
│   ├── schemas.py                  # 데이터 스키마
│   ├── exceptions.py               # 예외 처리
│   ├── utils.py                    # 공통 유틸리티
│   └── logger.py                   # 로깅 설정
├── freshdesk/                      # Freshdesk 특화 모듈
│   └── fetcher.py                  # Freshdesk 데이터 수집
├── data/                           # 데이터 저장소 (JSON 기반 MVP)
└── tests/                          # 테스트 디렉터리
```

---

## 🌍 멀티테넌트 글로벌 아키텍처

### 데이터 격리 전략

```python
# company_id 기반 완전 격리
with tenant_context(company_id):
    # Qdrant 네임스페이스: {company_id}_{data_type}
    # PostgreSQL Row-level Security 적용
    data = await query_tenant_data(company_id, data_type)
```

### 다중 플랫폼 헤더 구조

```javascript
const headers = {
  "X-Platform-Type": "freshdesk|zendesk", // 플랫폼 타입
  "X-Platform-Domain": "*.freshdesk.com", // 플랫폼 도메인
  "X-Platform-API-Key": "api_key", // 플랫폼별 API 키
  "X-Tenant-ID": "company_id", // 고객사 ID (격리용)
  "X-Locale": "ko-KR|en-US", // 다국어 지원
};
```

---

## ⚡ **성능 최적화 & 캐싱 전략 (AI 구현 필수 체크리스트)**

### ✅ **모듈화된 데이터 수집 파이프라인 사용 패턴 (2025년 6월 21일 완료)**

**모노리식 파일 분해 완료**:
- 기존: `api/ingest.py` (1,400+ 라인 단일 파일)
- 현재: `core/ingest/` 하위 4개 모듈로 완전 분리

**새로운 import 패턴**:
```python
# ✅ 권장 사용법 - 모듈화된 구조
from core.ingest import ingest  # 핵심 ingest 함수
from core.ingest.validator import validate_ticket_data, validate_article_data
from core.ingest.storage import QdrantStorage, SQLiteStorage
from core.ingest.integrator import create_integrated_objects

# API 엔드포인트에서 사용
@router.post("/ingest")
async def ingest_endpoint(request: IngestRequest):
    result = await ingest(
        company_id=request.company_id,
        platform=request.platform,
        data_types=request.data_types
    )
    return result
```

**모듈별 역할 분담**:
- **processor.py**: 핵심 ingest 함수 및 주요 비즈니스 로직
- **validator.py**: 플랫폼별 데이터 검증 및 필터링
- **integrator.py**: 통합 객체 생성 및 데이터 병합
- **storage.py**: Qdrant, SQLite 저장소 관리

### ✅ **성능 최적화 현재 구현 체크리스트**

**langchain 통합 최적화** (✅ 완료):

- [x] LLM 체인 병렬 처리 (InitParallelChain 구현)
- [x] 체인 기반 구조화 (SummarizationChain, SearchChain)
- [x] 프롬프트 템플릿 관리 (PromptTemplates)
- [ ] LLM 응답 캐싱 (Redis 기반, 구현 예정)

**라이브러리 성능 가속화** (부분 완료):

- [x] **pydantic v2**: 데이터 검증 5-50배 향상 (완료)
- [x] **FastAPI**: 기본 비동기 성능 (완료)
- [x] **Redis**: 캐싱 인프라 (준비 완료)
- [ ] **orjson**: JSON 직렬화 2-3배 향상 (향후 추가)
- [ ] **asyncpg**: PostgreSQL 비동기 드라이버 (프로덕션 시)

### 🚀 **캐싱 계층 핵심 패턴**

**LLM 응답 캐싱 패턴** (비용 절감 핵심):

```python
@cache_llm_response(ttl=3600)  # 1시간 캐싱
async def generate_ai_response(company_id: str, query: str, context: str) -> str:
    """LLM 응답 캐싱으로 비용/지연시간 대폭 감소"""
    cache_key = f"llm:{company_id}:{hash(query + context)}"

    # 캐시 확인
    cached = await redis_client.get(cache_key)
    if cached:
        return orjson.loads(cached)

    # LLM 호출 및 캐싱
    response = await llm_chain.arun(query=query, context=context)
    await redis_client.setex(cache_key, 3600, orjson.dumps(response))
    return response
```

**벡터 검색 캐싱 패턴**:

```python
@cache_vector_search(ttl=1800)  # 30분 캐싱
async def search_similar_tickets(company_id: str, query_vector: List[float]) -> List[dict]:
    """벡터 검색 결과 캐싱"""
    cache_key = f"vector:{company_id}:{hash(str(query_vector))}"

    cached = await redis_client.get(cache_key)
    if cached:
        return orjson.loads(cached)

    results = await qdrant_search_with_filter(company_id, query_vector)
    await redis_client.setex(cache_key, 1800, orjson.dumps(results))
    return results
```

**세션 기반 캐싱 패턴**:

```python
async def cache_session_context(session_id: str, company_id: str, context: dict):
    """세션별 컨텍스트 캐싱 (티켓 메타데이터, 사용자 프로필 등)"""
    session_key = f"session:{company_id}:{session_id}"
    await redis_client.setex(session_key, 7200, orjson.dumps(context))  # 2시간
```

### 📊 **성능 모니터링 핵심 패턴**

**Prometheus 메트릭 수집**:

```python
from prometheus_client import Histogram, Counter, Gauge

# 핵심 성능 메트릭
llm_request_duration = Histogram("llm_request_duration_seconds", "LLM 요청 처리 시간")
vector_search_duration = Histogram("vector_search_duration_seconds", "벡터 검색 시간")
cache_hit_rate = Gauge("cache_hit_rate_percent", "캐시 적중률")

@llm_request_duration.time()
async def timed_llm_request(query: str):
    """LLM 요청 시간 측정"""
    return await llm_chain.arun(query)
```

### 🎯 **성능 목표 & SLA**

**응답 시간 목표**:

- `/init` 엔드포인트: **< 2초** (병렬 처리 + 캐싱)
- `/query` 엔드포인트: **< 3초** (LLM 응답 캐싱 적용)
- `/reply` 엔드포인트: **< 5초** (복잡한 답변 생성)

**캐시 성능 목표**:

- **LLM 캐시 적중률**: 70% 이상
- **벡터 검색 캐시**: 50% 이상
- **Redis 응답시간**: < 10ms

### ⚠️ **성능 최적화 주의사항 (현재 구현 기준)**

- 🚨 **점진적 도입**: 성능 라이브러리는 기존 코드 안정성 확인 후 도입
- 🚨 **비동기 필수**: 모든 I/O 작업은 async/await 패턴 적용
- 🚨 **캐시 설계**: Redis 캐싱 로직 도입 시 무효화 전략 필수 고려
- 🚨 **메모리 관리**: 대용량 데이터 스트리밍 처리로 메모리 누수 방지

---

## 💾 **데이터 계층 & 스토리지 (AI 구현 필수 체크리스트)**

### ✅ **데이터베이스 아키텍처 체크리스트**

**MVP 데이터베이스 전략**:

- [x] **SQLite**: 테스트 및 개발용 로컬 데이터베이스 (`backend/core/database.py`)
- [x] **Qdrant Cloud**: 벡터 검색 전용 (단일 `documents` 컬렉션)
- [ ] **PostgreSQL**: 프로덕션 전환 시 Row-level Security 적용
- [x] **Redis**: LLM 응답 캐싱 (비용 절약 필수)

**SQLite 데이터베이스 구조** (`database.py`):

```python
# 핵심 테이블 스키마
tables = {
    "tickets": "company_id + platform + freshdesk_id (멀티테넌트 격리)",
    "conversations": "ticket_id 연결 + company_id 격리",
    "knowledge_base_articles": "company_id + platform 기반 분리",
    "attachments": "parent_type/parent_id 참조 + company_id",
    "collection_logs": "job_id + company_id 기반 수집 작업 추적"
}
```

**데이터 저장 전략**:

- **원본 데이터**: SQLite (테스트용) → PostgreSQL (프로덕션)
- **벡터 임베딩**: Qdrant Cloud 단일 컬렉션
- **멀티테넌트 격리**: 모든 테이블에 `company_id` 필수
- **100건 제한**: 테스트 환경에서 비용 및 성능 최적화

### 🔄 **데이터 파이프라인 핵심 패턴**

**SQLite 연동 패턴** (`core/database.py`):

```python
from core.database import SQLiteDatabase

# 데이터 수집 시 SQLite 저장
db = SQLiteDatabase("freshdesk_test_data.db")  # 100건 제한용
db.connect()
db.create_tables()

# 멀티테넌트 데이터 저장
for ticket in tickets:
    ticket['company_id'] = company_id  # 자동 태깅 필수
    ticket['platform'] = 'freshdesk'
    db.insert_ticket(ticket)

# 수집 작업 로그 기록
db.insert_collection_log({
    "job_id": job_id,
    "company_id": company_id,
    "status": "completed",
    "tickets_collected": len(tickets)
})
```

**데이터 흐름 아키텍처**:

```
Freshdesk API →
SQLite 원본 저장 (company_id 태깅) →
LLM 요약 처리 →
임베딩 생성 →
Qdrant 벡터 저장 (company_id 필터링)
```

### ⚠️ **데이터베이스 주의사항**

- 🚨 **company_id 필수**: 모든 데이터 저장 시 테넌트 식별자 자동 태깅
- 🚨 **100건 제한**: `freshdesk_test_data.db` 사용으로 비용 관리
- 🚨 **작업 로깅**: 수집 진행상황 및 오류 추적 필수
- 🚨 **점진적 마이그레이션**: SQLite → PostgreSQL 전환 시 데이터 호환성 유지

---

## 🔧 기술 스택 요약

### 백엔드 (Python 3.10)

```
FastAPI + langchain + Redis + Qdrant + PostgreSQL + orjson + Pydantic v2
```

### 프론트엔드 (Node.js v14-18)

```
Freshdesk FDK + BlockNote 에디터 + 멀티테넌트 API 클라이언트
```

### 인프라 & 배포

```
Docker + Kubernetes + AWS/GCP + Prometheus + Grafana
```

---

## 🛡️ **보안 & 멀티테넌트 아키텍처 (AI 구현 필수 체크리스트)**

### ✅ **멀티테넌트 보안 필수 구현 체크리스트**

**데이터 격리 보안**:

- [x] **company_id 기반 완전 분리**: 모든 데이터 작업에 테넌트 ID 필수
- [x] **Row-level Security**: PostgreSQL 데이터베이스 수준 격리
- [x] **네임스페이스 격리**: Qdrant 벡터 DB 테넌트별 분리
- [x] **API 키 중앙화**: AWS Secrets Manager 통합

**API 보안 헤더**:

- [x] **X-Company-ID**: 모든 요청에 테넌트 식별자 필수
- [x] **X-Platform-Type**: 플랫폼 타입 검증 (`freshdesk|zendesk`)
- [x] **X-Platform-Domain**: 도메인 화이트리스트 검증
- [x] **Authorization**: JWT/API 키 기반 인증

### 🔐 **보안 핵심 패턴**

**테넌트 컨텍스트 관리 패턴**:

```python
from contextvars import ContextVar

# 테넌트 컨텍스트 변수
current_company_id: ContextVar[str] = ContextVar('current_company_id')

async def tenant_middleware(request: Request, call_next):
    """모든 요청에 테넌트 컨텍스트 설정"""
    company_id = request.headers.get('X-Company-ID')
    if not company_id:
        raise HTTPException(status_code=400, detail="Missing X-Company-ID header")

    # 테넌트 컨텍스트 설정
    token = current_company_id.set(company_id)
    try:
        response = await call_next(request)
        return response
    finally:
        current_company_id.reset(token)
```

**도메인 검증 패턴**:

```python
ALLOWED_DOMAINS = {
    'freshdesk': ['.freshdesk.com'],
    'zendesk': ['.zendesk.com']
}

def validate_platform_domain(platform_type: str, domain: str) -> bool:
    """플랫폼별 도메인 화이트리스트 검증"""
    allowed = ALLOWED_DOMAINS.get(platform_type, [])
    return any(domain.endswith(suffix) for suffix in allowed)
```

**API 키 안전 관리 패턴**:

```python
import boto3
from functools import lru_cache

@lru_cache(maxsize=128)
async def get_platform_credentials(company_id: str, platform_type: str) -> dict:
    """AWS Secrets Manager에서 플랫폼별 자격증명 조회"""
    secret_name = f"{platform_type}/{company_id}/api_credentials"

    session = boto3.Session()
    client = session.client('secretsmanager')

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return orjson.loads(response['SecretString'])
    except ClientError as e:
        logger.error(f"Failed to retrieve credentials for {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Credential retrieval failed")
```

### 📋 **GDPR & 규정 준수 패턴**

**데이터 처리 동의 관리**:

```python
class GDPRConsent(BaseModel):
    """GDPR 동의 관리 모델"""
    company_id: str
    user_email: str
    consent_type: str = Field(..., regex="^(data_processing|ai_analysis|storage)$")
    consent_given: bool
    consent_date: datetime
    expiry_date: Optional[datetime]

async def check_gdpr_consent(company_id: str, user_email: str, consent_type: str) -> bool:
    """GDPR 동의 확인"""
    consent = await get_user_consent(company_id, user_email, consent_type)
    return consent and consent.consent_given and (
        not consent.expiry_date or consent.expiry_date > datetime.utcnow()
    )
```

**데이터 삭제 요청 처리**:

```python
async def process_gdpr_deletion(company_id: str, user_email: str):
    """GDPR 데이터 삭제 요청 처리"""
    # 1. PostgreSQL에서 사용자 데이터 삭제
    await delete_user_data_from_postgres(company_id, user_email)

    # 2. Qdrant에서 벡터 데이터 삭제
    await delete_user_vectors_from_qdrant(company_id, user_email)

    # 3. Redis 캐시 삭제
    await delete_user_cache_from_redis(company_id, user_email)

    # 4. 삭제 로그 기록
    await log_gdpr_deletion(company_id, user_email)
```

### 🔒 **암호화 & 전송 보안**

**데이터 암호화 패턴**:

```python
from cryptography.fernet import Fernet
import base64

class FieldEncryption:
    """민감한 필드 암호화/복호화"""

    def __init__(self, encryption_key: str):
        self.cipher_suite = Fernet(encryption_key.encode())

    def encrypt_field(self, value: str) -> str:
        """필드 값 암호화"""
        encrypted = self.cipher_suite.encrypt(value.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_field(self, encrypted_value: str) -> str:
        """필드 값 복호화"""
        encrypted = base64.b64decode(encrypted_value.encode())
        return self.cipher_suite.decrypt(encrypted).decode()
```

### ⚠️ **보안 주의사항**

- 🚨 **테넌트 누출 금지**: company_id 없는 데이터 접근 절대 금지
- 🚨 **자격증명 하드코딩 금지**: 모든 API 키는 Secrets Manager 사용
- 🚨 **로그 보안**: 민감한 정보는 로그에 기록 금지
- 🚨 **GDPR 준수**: 유럽 사용자 데이터 처리 시 동의 확인 필수

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

    # Zendesk 어댑터 생성 테스트 (NotImplementedError 예상)
    with pytest.raises(NotImplementedError):
        await create_platform_adapter("zendesk", "company2")

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

## 🚀 **확장성 로드맵 & 단계별 구현 (AI 구현 필수 체크리스트)**

### ✅ **Phase 1: MVP (Freshdesk) - 현재 완료 상태**

**완료된 기능**:

- [x] **Freshdesk 어댑터**: 완전 구현 (`backend/core/platforms/freshdesk/`)
- [x] **파일 기반 스토리지**: JSON 기반 개발 환경
- [x] **기본 성능 최적화**: orjson, pydantic v2 적용
- [x] **company_id 자동 추출**: 도메인 기반 테넌트 식별

**현재 작업 중**:

- [ ] **langchain 통합**: LLM 체인 최적화 및 캐싱
- [ ] **Redis 캐싱**: LLM 응답 캐싱으로 비용 절감
- [ ] **성능 모니터링**: Prometheus 메트릭 수집

### ✅ **Phase 2: SaaS (멀티테넌트) - 향후 3개월**

**필수 구현 목표**:

- [ ] **PostgreSQL 마이그레이션**: Row-level Security 기반 완전 격리
- [ ] **Redis Cluster**: 고가용성 캐싱 인프라
- [ ] **AWS Secrets Manager**: API 키 중앙화 관리
- [ ] **GDPR 준수**: 유럽 규정 완전 준수

**성능 목표**:

- [ ] **동시 사용자**: 1,000명 이상 지원
- [ ] **응답시간**: 평균 2초 이하 달성
- [ ] **가용성**: 99.9% SLA 달성

### ✅ **Phase 3: 글로벌 (다중 플랫폼) - 향후 6개월**

**플랫폼 확장**:

- [ ] **Zendesk 어댑터**: 완전 구현
- [ ] **ServiceNow 플랫폼**: 향후 확장 고려
- [ ] **다국어 지원**: i18n 완성

**글로벌 인프라**:

- [ ] **멀티 리전 배포**: AWS/GCP 글로벌 인프라
- [ ] **CDN 최적화**: 정적 자산 글로벌 캐싱
- [ ] **컴플라이언스**: 지역별 데이터 거버넌스

---

## 🎯 **AI 세션 간 일관성 보장 최종 체크리스트**

### ✅ **아키텍처 일관성 검증**

**코드 재활용 원칙**:

- [x] **기존 코드 90% 이상 재활용**: 임의 재작성 금지
- [x] **레거시 로직 보존**: 안정적인 기존 비즈니스 로직 유지
- [x] **점진적 개선**: 전면 재설계 대신 단계적 최적화
- [x] **검증된 패턴 활용**: 이미 검증된 아키텍처 패턴 재사용

**멀티테넌트 필수 요소**:

- [x] **company_id 필수**: 모든 데이터 작업에 테넌트 ID 포함
- [x] **격리 검증**: 테넌트 간 데이터 누출 방지 확인
- [x] **보안 헤더**: X-Company-ID 등 필수 헤더 검증
- [x] **네임스페이스**: 모든 저장소에서 테넌트별 분리

**성능 최적화 필수**:

- [x] **orjson 사용**: `import json` 대신 `import orjson` 필수
- [x] **pydantic v2**: 모든 데이터 모델에 적용
- [x] **비동기 패턴**: async/await 기반 I/O 처리
- [x] **Redis 캐싱**: LLM 응답 및 벡터 검색 캐싱

### 🚨 **절대 금지 사항 (AI 구현 시 필수 준수)**

- ❌ **기존 디렉터리 구조 변경**: `backend/api/`, `backend/core/` 구조 유지
- ❌ **company_id 없는 컴포넌트**: 모든 데이터 작업에 테넌트 ID 필수
- ❌ **플랫폼별 하드코딩**: 조건문 남발 대신 추상화 패턴 사용
- ❌ **동기 I/O 남용**: `requests` 대신 `httpx`, 비동기 패턴 선호
- ❌ **기존 코드 임의 삭제**: 90% 이상 기존 로직 재활용 원칙

### 📚 **AI 참조용 핵심 디렉터리 맵 (실제 파일 경로)**

```
MUST KNOW 핵심 파일 경로:
- backend/core/config.py               # 전체 시스템 설정 (company_id 자동 추출)
- backend/core/platforms/factory.py   # 플랫폼 어댑터 팩토리
- backend/api/main.py                  # FastAPI 앱 진입점
- backend/core/platforms/freshdesk/    # Freshdesk 완전 구현 예시
- backend/core/vectordb.py             # Qdrant 벡터 DB 연동
- backend/core/llm_router.py           # LLM 라우팅 로직
- backend/api/routes/                  # 모든 API 엔드포인트
- scripts/collect_and_process.py       # company_id 자동 적용 예시
```

---

**이 아키텍처 지침서는 AI가 세션 간 일관성을 유지하며 RAG 시스템을 구현할 수 있도록 모든 핵심 패턴과 주의사항을 포함합니다. 모든 기술적 결정은 이 문서를 기준으로 평가하고 구현하시기 바랍니다.**
