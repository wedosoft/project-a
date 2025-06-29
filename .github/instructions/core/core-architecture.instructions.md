# 🏗️ 핵심 아키텍처 인덱스

_AI 참조 최적화 버전 - 분할된 아키텍처 지침서들의 인덱스_

## 🎯 핵심 아키텍처 참조 가이드

**세션 간 일관성 보장을 위한 아키텍처 인덱스**

이 지침서는 아키텍처 관련 세부 구현을 전문 지침서로 분할하고, 통합 참조 역할을 합니다.

---

## ⚡ **TL;DR - 핵심 아키텍처 요약**

### 💡 **즉시 참조용 핵심 포인트**

**아키텍처 분할 구조**:
```
🏗️ Core Architecture Index (현재 파일)
├── system-architecture.md (전체 시스템 설계)
├── multitenant-security.md (보안 및 격리)  
├── performance-optimization.md (성능 최적화)
└── global.md (전역 규칙)
```

**핵심 기술 스택**:
- **Backend**: FastAPI + asyncio + langchain + Redis
- **Vector DB**: Qdrant Cloud (단일 `documents` 컬렉션)
- **Cache**: Redis (LLM 응답 캐싱)
- **DB**: SQLite (개발) → PostgreSQL (프로덕션)

**멀티테넌트 전략**:
- company_id 자동 추출: `domain.split('.')[0]`
- 모든 컴포넌트에 테넌트 격리 적용
- X-Tenant-ID 헤더 기반 API 보안

### 🚨 **아키텍처 주의사항**

- ⚠️ 기존 모듈 구조 변경 금지 → 점진적 개선만 허용
- ⚠️ tenant_id 없는 컴포넌트 절대 금지 → 멀티테넌트 필수
- ⚠️ 플랫폼별 하드코딩 금지 → 어댑터 패턴 적용

---

## 📋 **아키텍처별 참조 가이드**

### 🏗️ **전체 시스템 설계**
**파일**: [system-architecture.instructions.md](system-architecture.instructions.md)
- 모듈화 아키텍처 패턴
- LLM 라우터 모듈 (완료)
- 데이터 수집 모듈 (완료)
- 플랫폼 어댑터 패턴
- 비동기 처리 패턴

### 🔐 **보안 & 멀티테넌트**
**파일**: [multitenant-security.instructions.md](multitenant-security.instructions.md)
- 테넌트 식별 & 자동 태깅
- API 레벨 보안 패턴
- 데이터베이스 레벨 보안
- Row-Level Security (RLS) 설정

### ⚡ **성능 최적화**
**파일**: [performance-optimization.instructions.md](performance-optimization.instructions.md)
- JSON 직렬화 최적화 (orjson)
- Pydantic v2 데이터 검증
- Redis 캐싱 최적화
- 비동기 배치 처리

### 🌐 **전역 규칙**
**파일**: [global.instructions.md](global.instructions.md)
- 코딩 표준 및 규칙
- 프로젝트 전체 가이드라인
- 개발 환경 설정

---

## 🔧 **핵심 아키텍처 패턴 요약**

### 🏗️ **모듈화 구조 (2025년 6월 21일 완료)**
```
backend/
├── api/           # FastAPI 라우터 & 엔드포인트
├── core/          # 핵심 비즈니스 로직
│   ├── llm/       # LLM 라우팅 & 관리 (모듈화 완료)
│   └── ingest/    # 데이터 수집 파이프라인 (모듈화 완료)
├── data/          # 데이터 저장소
└── freshdesk/     # 플랫폼별 구현
```

### 🔐 **멀티테넌트 패턴**
```python
# 모든 데이터 처리에 tenant_id 필수
async def process_data(data: dict, tenant_id: str):
    data["tenant_id"] = tenant_id
    # Row-level Security 자동 적용
```

### ⚡ **성능 최적화 패턴**
```python
# orjson + Redis 캐싱 + 비동기 처리
import orjson
from redis import asyncio as aioredis

@cache_result(ttl=3600)
async def optimized_operation(data: dict) -> dict:
    return orjson.loads(orjson.dumps(result))
```

---

## 🎯 **작업별 아키텍처 참조**

### 🚀 **새 기능 개발**
1. **전체 설계**: [system-architecture.md](system-architecture.instructions.md)
2. **보안 고려**: [multitenant-security.md](multitenant-security.instructions.md)
3. **성능 고려**: [performance-optimization.md](performance-optimization.instructions.md)

### 🔧 **성능 개선**
1. **성능 최적화**: [performance-optimization.md](performance-optimization.instructions.md)
2. **시스템 병목**: [system-architecture.md](system-architecture.instructions.md)
3. **캐싱 전략**: [performance-optimization.md](performance-optimization.instructions.md)

### 🔐 **보안 강화**
1. **멀티테넌트**: [multitenant-security.md](multitenant-security.instructions.md)
2. **API 보안**: [multitenant-security.md](multitenant-security.instructions.md)
3. **데이터 격리**: [multitenant-security.md](multitenant-security.instructions.md)

---

## ⚠️ **아키텍처 철칙 (AI 세션 간 일관성 핵심)**

### 🔄 **기존 아키텍처 재활용 원칙**

**목적**: 세션이 바뀌어도 동일한 아키텍처 유지

- **기존 모듈 구조 90% 이상 재활용**: 임의로 새로운 아키텍처 변경 금지
- **검증된 패턴 보존**: 안정적으로 작동하던 모듈화 구조 유지
- **점진적 최적화**: 전면 재설계 대신 기존 구조 개선
- **모듈 일관성**: 기존 모듈 인터페이스와 호환성 유지

### 📋 **AI 아키텍처 작업 시 필수 체크포인트**

1. **tenant_id 멀티테넌트**: 모든 컴포넌트에 테넌트 격리 필수
2. **모듈화 구조 유지**: 기존 core/llm, core/ingest 구조 보존
3. **성능 최적화 점진 도입**: 기존 코드 안정성 우선
4. **플랫폼 추상화**: Freshdesk 중심이지만 확장 가능하게

---

## 📚 **관련 참조 지침서**

### 🏗️ **Core (현재 디렉터리)**
- **system-architecture.md** - 전체 시스템 설계
- **multitenant-security.md** - 보안 및 데이터 격리
- **performance-optimization.md** - 성능 최적화 전략
- **global.md** - 전역 개발 규칙

### 📊 **Data (데이터 워크플로우)**
- **../data/data-workflow.md** - 데이터 파이프라인 전체

### 💻 **Development (구현 패턴)**
- **../development/backend-implementation-patterns.md** - 백엔드 구현

### 🎯 **Specialized (특화 기능)**
- **../specialized/platform-adapters-multiplatform.md** - 플랫폼 확장

---

## 🎯 **아키텍처 체크리스트**

### ✅ **설계 단계**
- [ ] 전체 시스템 아키텍처 검토
- [ ] 멀티테넌트 격리 확인
- [ ] 성능 요구사항 분석

### ✅ **구현 단계**
- [ ] 모듈화 구조 준수
- [ ] company_id 자동 태깅
- [ ] 에러 처리 및 모니터링

### ✅ **최적화 단계**
- [ ] 캐싱 전략 적용
- [ ] 비동기 처리 최적화
- [ ] 데이터베이스 성능 튜닝

---

*📝 이 인덱스는 핵심 아키텍처의 전체 구조를 제공하며, 세부 구현은 각 전문 지침서를 참조하세요.*

**🔗 Next Steps**: 특정 아키텍처 작업에 따라 위의 관련 지침서들을 참조하여 세부 구현을 진행하세요.
