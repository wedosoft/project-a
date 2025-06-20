---
applyTo: "**"
---

# 🏗️ 핵심 아키텍처 & 성능 설계 지침서

*모델 참조 최적화 버전 - 아키텍처, 기술스택, 성능 설계 전용*

## 🎯 시스템 목표

**Freshdesk 기반 글로벌 SaaS 멀티테넌트 AI 상담사 지원 시스템**

- **성능 목표**: LLM 응답 5~10초 → 1~2초 단축  
- **확장성**: Freshdesk → Zendesk → ServiceNow 순차 확장
- **멀티테넌트**: company_id 기반 완전 데이터 격리
- **글로벌화**: i18n 다국어 지원 내장

---

## 🚀 리팩토링 핵심 프레임워크

### ⚠️ **리팩토링 철칙 (절대 준수 필수)**

**기존 코드 재활용 원칙**:
- **기존 코드 90% 이상 재활용**: 임의로 새로운 코딩 절대 금지
- **레거시 코드 로직 보존**: 안정적으로 작동하던 기존 로직을 벗어나지 않음
- **점진적 개선만**: 기존 코드를 다듬어 사용, 전면 재작성 금지
- **검증된 로직 유지**: 기존 비즈니스 로직과 데이터 처리 방식 최대한 보존

### 🆕 성능 최적화 스택

```
langchain (LLM 통합) + Redis (캐싱) + orjson (JSON 2-3배) + Pydantic v2 (검증 5-50배)
```

#### 핵심 프레임워크
- **langchain**: LLM 통합 및 체인 관리
- **langchain-qdrant**: 벡터 저장소 통합
- **redis & aioredis**: 비동기 캐싱 및 세션 관리

#### 추가 성능 프레임워크
- **orjson**: JSON 직렬화 성능 향상 (2-3배)
- **pydantic v2**: 데이터 검증 성능 향상 (5-50배)
- **asyncpg**: PostgreSQL 비동기 드라이버 (3배)
- **fastapi-cache2**: FastAPI 캐싱 데코레이터
- **prometheus-client**: 메트릭 수집 및 모니터링

---

## 🏗️ 플랫폼 지원 정책

### 현재 (MVP)
- **완전 지원**: Freshdesk만 완전 구현
- **추상화 유지**: Zendesk는 NotImplementedError로 향후 확장 대비
- **완전 제거**: ServiceNow, Jira 등 다른 플랫폼 코드 완전 삭제

### 확장 구조
```
팩토리 패턴 → 플랫폼별 Adapter → 공통 데이터 모델 → 통합 API
```

---

## 📡 API 아키텍처 (단순화)

### 9개 핵심 엔드포인트
1. `/init` - 티켓 초기 데이터 (Redis 캐싱)
2. `/query` - AI 채팅 (langchain 체인)
3. `/reply` - 추천 답변 생성
4. `/ingest` - 관리자용 데이터 수집 (멀티플랫폼)
5. `/health` - 헬스체크 (멀티 서비스)
6. `/metrics` - 성능 메트릭 (Prometheus)
7. `/query/stream` - 실시간 스트리밍 채팅 (SSE)
8. `/reply/stream` - 실시간 스트리밍 답변
9. `/attachments/*` - 첨부파일 접근 (멀티테넌트 보안)

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
│   │   ├── query.py                # /query, /query/stream
│   │   ├── generate_reply.py       # /generate_reply, /generate_reply/stream
│   │   ├── ingest.py               # /ingest
│   │   ├── health.py               # /health
│   │   ├── metrics.py              # /metrics
│   │   └── attachments.py          # /attachments/*
│   ├── middleware.py               # 공통 미들웨어
│   ├── dependencies.py             # FastAPI 의존성
│   └── main.py                     # FastAPI 앱 진입점
├── core/
│   ├── abstractions/               # 추상화 인터페이스 (확장 가능)
│   │   ├── __init__.py
│   │   ├── platform_adapter.py     # 플랫폼 어댑터 인터페이스 (Freshdesk/Zendesk)
│   │   ├── data_store.py           # 데이터 저장소 인터페이스
│   │   └── search_engine.py        # 검색 엔진 인터페이스
│   ├── langchain/                  # 🆕 langchain 통합 모듈
│   │   ├── __init__.py
│   │   ├── llm_manager.py          # langchain LLM 통합 관리
│   │   ├── vector_store.py         # langchain-qdrant 통합
│   │   ├── embeddings.py           # 임베딩 모델 관리
│   │   ├── chains/                 # langchain 체인 구현
│   │   │   ├── __init__.py
│   │   │   ├── summarization.py    # 요약 체인
│   │   │   ├── qa_chain.py         # 질답 체인
│   │   │   └── search_chain.py     # 검색 체인
│   │   ├── prompts/                # langchain 프롬프트 템플릿
│   │   │   ├── __init__.py
│   │   │   ├── ticket_summary.py   # 티켓 요약 프롬프트
│   │   │   ├── query_response.py   # 쿼리 응답 프롬프트
│   │   │   └── reply_generation.py # 답변 생성 프롬프트
│   │   └── callbacks/              # langchain 콜백
│   │       ├── __init__.py
│   │       ├── streaming.py        # 스트리밍 콜백
│   │       └── metrics.py          # 메트릭 수집 콜백
│   ├── cache/                      # 🆕 Redis 캐싱 계층
│   │   ├── __init__.py
│   │   ├── redis_client.py         # Redis 클라이언트 설정
│   │   ├── cache_manager.py        # 캐시 매니저
│   │   ├── strategies/             # 캐싱 전략
│   │   │   ├── __init__.py
│   │   │   ├── llm_cache.py        # LLM 응답 캐싱
│   │   │   ├── vector_cache.py     # 벡터 검색 캐싱
│   │   │   └── session_cache.py    # 세션 기반 캐싱
│   │   └── decorators.py           # 캐싱 데코레이터
│   ├── platforms/                  # 플랫폼별 어댑터 (확장 가능)
│   │   ├── __init__.py
│   │   ├── factory.py              # 플랫폼 팩토리 (Freshdesk/Zendesk 지원)
│   │   ├── freshdesk/              # Freshdesk 완전 구현
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py          # Freshdesk 어댑터
│   │   │   ├── models.py           # Freshdesk 데이터 모델
│   │   │   ├── client.py           # Freshdesk API 클라이언트
│   │   │   └── collector.py        # 데이터 수집기
│   │   └── zendesk/                # Zendesk 추상화 (향후 구현용)
│   │       ├── __init__.py
│   │       ├── adapter.py          # Zendesk 어댑터 (NotImplementedError)
│   │       └── models.py           # Zendesk 데이터 모델 (스켈레톤)
│   ├── search/                     # 검색 엔진 모듈 (langchain 통합)
│   │   ├── __init__.py
│   │   ├── factory.py              # 검색 엔진 팩토리
│   │   ├── vector/                 # 벡터 검색 구현
│   │   │   ├── __init__.py
│   │   │   └── qdrant.py           # Qdrant 구현 (langchain 기반)
│   │   ├── hybrid/                 # 하이브리드 검색
│   │   │   ├── __init__.py
│   │   │   └── reranker.py         # 검색 결과 재순위
│   │   └── filters/                # 검색 필터
│   │       ├── __init__.py
│   │       └── company_filter.py   # company_id 필터
│   ├── data/                       # 데이터 처리
│   │   ├── __init__.py
│   │   ├── models/                 # 공통 데이터 모델 (플랫폼 독립적)
│   │   │   ├── __init__.py
│   │   │   ├── ticket.py           # 통합 티켓 모델
│   │   │   ├── knowledge_base.py   # KB 모델
│   │   │   └── unified.py          # 통합 데이터 모델
│   │   ├── processors/             # 데이터 처리기
│   │   │   ├── __init__.py
│   │   │   ├── text_processor.py   # 텍스트 전처리
│   │   │   ├── attachment_processor.py # 첨부파일 처리
│   │   │   └── summarizer.py       # 요약 처리기
│   │   └── stores/                 # 저장소 구현
│   │       ├── __init__.py
│   │       ├── file_store.py       # 파일 기반 저장소
│   │       └── postgres_store.py   # PostgreSQL 저장소
│   ├── services/                   # 비즈니스 로직 서비스 (플랫폼 독립적)
│   │   ├── __init__.py
│   │   ├── init_service.py         # /init 엔드포인트 서비스
│   │   ├── query_service.py        # /query 엔드포인트 서비스
│   │   ├── reply_service.py        # /generate_reply 서비스
│   │   ├── ingest_service.py       # /ingest 서비스
│   │   └── search_service.py       # 검색 서비스
│   └── migration/                  # 🆕 기존 코드 마이그레이션
│       ├── __init__.py
│       ├── legacy_wrapper.py       # 기존 코드 호환 래퍼
│       ├── llm_router_adapter.py   # 기존 LLM Router 어댑터
│       └── main_api_adapter.py     # 기존 main.py 어댑터
├── config/                         # 설정 관리
│   ├── __init__.py
│   ├── settings.py                 # 메인 설정 (pydantic v2)
│   ├── langchain_config.py         # 🆕 langchain 설정
│   ├── cache_config.py             # 🆕 Redis 캐시 설정
│   ├── platform_config.py          # 플랫폼 설정 (Freshdesk/Zendesk)
│   └── performance_config.py       # 🆕 성능 최적화 설정
├── utils/                          # 공통 유틸리티
│   ├── __init__.py
│   ├── json_utils.py               # 🆕 orjson 기반 JSON 처리
│   ├── async_utils.py              # 🆕 비동기 유틸리티
│   ├── cache_utils.py              # 캐싱 유틸리티
│   ├── metrics.py                  # 메트릭 (prometheus)
│   └── logging.py                  # 구조화된 로깅
├── tests/                          # 테스트 디렉토리
│   ├── __init__.py
│   ├── unit/                       # 단위 테스트
│   ├── integration/                # 통합 테스트
│   └── performance/                # 성능 테스트
└── migrations/                     # 데이터베이스 마이그레이션
    └── alembic/                    # Alembic 마이그레이션 스크립트
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
  "X-Platform-Type": "freshdesk|zendesk",     // 플랫폼 타입
  "X-Platform-Domain": "*.freshdesk.com",     // 플랫폼 도메인
  "X-Platform-API-Key": "api_key",            // 플랫폼별 API 키
  "X-Tenant-ID": "company_id",                // 고객사 ID (격리용)
  "X-Locale": "ko-KR|en-US",                  // 다국어 지원
};
```

---

## ⚡ 성능 최적화 전략

### 캐싱 계층 (Redis)
```
세션 캐싱 → LLM 응답 캐싱 → 벡터 검색 캐싱 → 메타데이터 캐싱
```

### langchain 체인 최적화
```
요약 체인 → 질답 체인 → 검색 체인 → 스트리밍 콜백
```

### 성능 목표
- **응답 시간**: 평균 3초 이하
- **캐시 적중률**: 70% 이상  
- **동시 요청**: 100 RPS 이상
- **에러율**: 1% 미만

---

## 🗄️ 데이터베이스 구성

### MVP (현재)
- **Vector DB**: Qdrant Cloud (임베딩 검색)
- **App DB**: 파일 기반 JSON (로컬 개발)
- **캐시**: Redis (성능 최적화)

### 프로덕션
- **Vector DB**: Qdrant Cloud (멀티테넌트 네임스페이스)
- **App DB**: PostgreSQL (AWS RDS, Row-level Security)
- **캐시**: Redis Cluster (고가용성)
- **Secrets**: AWS Secrets Manager (API 키 관리)

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

## 🛡️ 보안 & 규정 준수

### 멀티테넌트 보안
- **데이터 격리**: company_id 기반 완전 분리
- **API 키 관리**: Secrets Manager 중앙화
- **Row-level Security**: PostgreSQL 데이터베이스 수준 격리
- **네임스페이스**: Qdrant 벡터 DB 테넌트별 격리

### 글로벌 규정 준수
- **GDPR**: 유럽 데이터 보호법 준수
- **SOC 2**: 보안 프레임워크 적용
- **암호화**: 전송 및 저장 시 암호화

---

## 📊 모니터링 & 메트릭

### 핵심 메트릭 (Prometheus)
```python
# 성능 메트릭
llm_request_duration = Histogram("llm_request_duration_seconds")
vector_search_duration = Histogram("vector_search_duration_seconds") 
cache_hit_rate = Gauge("cache_hit_rate_percent")

# 비즈니스 메트릭  
ticket_processed_counter = Counter("tickets_processed_total")
user_satisfaction_gauge = Gauge("user_satisfaction_score")
```

### 알림 & 대시보드
- **Grafana**: 실시간 성능 대시보드
- **알림**: 응답시간/에러율 임계값 알림
- **로그**: 구조화된 JSON 로깅 (ELK Stack)

---

## 🚀 확장성 로드맵

### Phase 1: MVP (Freshdesk)
- 파일 기반 스토리지
- 단일 테넌트
- 기본 성능 최적화

### Phase 2: SaaS (멀티테넌트)
- PostgreSQL 도입
- Redis 클러스터
- 완전한 테넌트 격리

### Phase 3: 글로벌 (다중 플랫폼)  
- Zendesk 플랫폼 추가
- 다국어 지원 완성
- 글로벌 배포 인프라

---

이 아키텍처 지침서는 **성능 최적화**와 **글로벌 확장성**을 동시에 고려한 균형잡힌 설계를 제공합니다. 모든 기술적 결정은 이 문서를 기준으로 평가하고 구현하시면 됩니다.
