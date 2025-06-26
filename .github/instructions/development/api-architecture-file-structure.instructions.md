````instructions
---
applyTo: "**"
---

# 📡 API 아키텍처 & 파일 구조 지침서

_AI 참조 최적화 버전 - API 설계와 백엔드 구조 가이드_

## 📋 **TL;DR - API 아키텍처 핵심 요약**

### 🚀 **8개 핵심 엔드포인트**
1. `/init` - 티켓 초기 데이터 (Redis 캐싱)
2. `/query` - AI 채팅 (langchain 체인)
3. `/reply` - 추천 답변 생성
4. `/ingest` - 관리자용 데이터 수집 (멀티플랫폼)
5. `/health` - 헬스체크 (멀티 서비스)
6. `/metrics` - 성능 메트릭 (Prometheus)
7. `/attachments/*` - 첨부파일 접근 (멀티테넌트 보안)
8. 스트리밍 엔드포인트 - 각 라우터 내부 구현

### ⚡ **API 구조 특징**
- **버전 관리 없음**: `/api/routes/` 직접 구조
- **확장 가능**: 필요시 버전 관리 추가 가능한 구조
- **단순성**: 복잡도 최소화, 유지보수성 최대화

---

## 📁 **백엔드 파일 구조 (리팩토링 아키텍처)**

### 🏗️ **모듈화 완료 상태 (2025년 6월 21일 기준)**

```
backend/
├── api/
│   ├── routes/                     # 엔드포인트별 라우트 (버전 관리 없음)
│   │   ├── __init__.py
│   │   ├── init.py                 # /init 엔드포인트
│   │   ├── query.py                # /query 엔드포인트
│   │   ├── reply.py                # /reply 엔드포인트
│   │   ├── ingest.py               # /ingest 엔드포인트 (단순 래퍼)
│   │   ├── health.py               # /health 엔드포인트
│   │   ├── metrics.py              # /metrics 엔드포인트
│   │   └── attachments.py          # /attachments/*
│   ├── models/                     # API 모델 정의
│   │   └── ingest_job.py           # Ingest Job 모델
│   ├── dependencies.py             # FastAPI 의존성
│   ├── multi_platform_attachments.py # 레거시 지원
│   ├── ingest_legacy_20250621.py   # 백업된 모노리식 파일 (1,400+ 라인)
│   └── main.py                     # FastAPI 앱 진입점
├── core/
│   ├── platforms/                  # 플랫폼별 어댑터 (확장 가능)
│   │   ├── __init__.py
│   │   ├── freshdesk/              # Freshdesk 완전 구현
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py          # Freshdesk 어댑터
│   │   │   ├── models.py           # Freshdesk 데이터 모델
│   │   │   └── optimized_fetcher.py # 데이터 수집기
│   │       ├── __init__.py
│   ├── llm/                        # LLM 모듈 (모듈화 완료)
│   │   ├── __init__.py
│   │   ├── router.py               # LLM 라우팅 로직 (메인)
│   │   ├── clients.py              # LLM 클라이언트 (OpenAI, Anthropic 등)
│   │   ├── models.py               # LLM 요청/응답 모델
│   │   ├── utils.py                # LLM 유틸리티 (캐싱, API 키 검증 등)
│   │   └── metrics.py              # LLM 메트릭 및 성능 추적
│   ├── ingest/                     # 데이터 수집/처리 모듈 (2025년 6월 21일 모듈화 완료)
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

## 🚨 **API 개발 필수 체크리스트**

### ✅ **라우트 개발 시 필수사항**

**1. 멀티테넌트 필수**
```python
# 모든 API에 필수
async def get_company_id(request: Request) -> str:
    company_id = request.headers.get("X-Company-ID")
    if not company_id:
        raise HTTPException(status_code=400, detail="X-Company-ID header required")
    return company_id
```

**2. 에러 처리 표준화**
```python
# 표준 에러 응답
from core.exceptions import ValidationError, AuthenticationError

@router.post("/endpoint")
async def endpoint(company_id: str = Depends(get_company_id)):
    try:
        # 비즈니스 로직
        pass
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
```

**3. 응답 모델 정의**
```python
# pydantic v2 모델 사용
from pydantic import BaseModel, Field

class APIResponse(BaseModel):
    success: bool = True
    data: dict | list | None = None
    message: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### ✅ **FastAPI 설정 체크리스트**

**1. CORS 설정**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**2. 미들웨어 순서**
```python
# 1. CORS
# 2. 로깅 미들웨어
# 3. 인증 미들웨어
# 4. 레이트 리미팅
```

---

## 🔧 **모듈 Import 패턴**

### 📦 **표준 Import 구조**

**API 라우터에서 코어 모듈 사용**
```python
# api/routes/ingest.py
from core.ingest import ingest  # 핵심 함수
from core.ingest.validator import validate_data
from core.ingest.storage import save_to_qdrant
```

**코어 모듈 간 상호 참조**
```python
# core/ingest/processor.py
from core.llm.router import route_llm_request
from core.platforms.factory import get_platform_adapter
from core.config import get_settings
```

### ⚠️ **Import 금지사항**

**❌ 절대 금지**
- `from api.ingest_legacy_20250621 import *` (레거시 파일)
- 순환 import 패턴
- 플랫폼별 하드코딩 import

---

## 📊 **성능 최적화 패턴**

### ⚡ **비동기 처리**

**1. 모든 DB 작업은 비동기**
```python
async def fetch_data(company_id: str):
    async with get_db_session() as session:
        result = await session.execute(query)
        return result.fetchall()
```

**2. 병렬 처리 활용**
```python
import asyncio

async def parallel_processing():
    tasks = [
        fetch_tickets(company_id),
        fetch_articles(company_id),
        fetch_contacts(company_id)
    ]
    results = await asyncio.gather(*tasks)
    return results
```

### 🚀 **캐싱 전략**

**1. Redis 캐싱**
```python
import aioredis

async def get_cached_response(key: str):
    redis = await aioredis.from_url("redis://localhost")
    cached = await redis.get(key)
    if cached:
        return orjson.loads(cached)
    return None
```

---

## 🔗 **관련 지침서 참조**

- 📚 [Quick Reference](quick-reference.instructions.md) - 즉시 참조용 핵심 패턴
- 🔒 [멀티테넌트 보안](multitenant-security.instructions.md) - 보안 구현 상세
- ⚡ [성능 최적화](performance-optimization.instructions.md) - 성능 향상 전략
- 🏗️ [플랫폼 어댑터](platform-adapters-multiplatform.instructions.md) - 어댑터 패턴
- 🔧 [백엔드 구현 패턴](backend-implementation-patterns.instructions.md) - 백엔드 개발 가이드

---

## ⚠️ **주의사항**

1. **기존 디렉터리 구조 변경 금지** - 점진적 개선만 허용
2. **company_id 없는 API 절대 금지** - 모든 엔드포인트에 멀티테넌트 필수
3. **레거시 파일 직접 수정 금지** - 새로운 모듈화된 코드만 사용
4. **플랫폼별 하드코딩 금지** - 반드시 어댑터 패턴 사용

**2025년 6월 21일 기준 - AI 세션 간 일관성 보장**
````
