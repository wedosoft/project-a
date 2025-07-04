# 📊 데이터 워크플로우 인덱스

_AI 참조 최적화 버전 - 분할된 지침서들의 통합 인덱스_

## 🎯 데이터 워크플로우 개요

**Freshdesk 기반 RAG 시스템의 전체 데이터 파이프라인 참조 가이드**

이 지침서는 세부 구현을 각 전문 지침서로 분할하고, 전체 워크플로우의 인덱스 역할을 합니다.

---

## ⚡ **TL;DR - 핵심 데이터 파이프라인 요약** (2025-06-26)

### 💡 **즉시 참조용 워크플로우**

**현재 데이터 흐름 (ORM 기반)**:
```
Freshdesk API → 데이터 검증 → 통합 객체 생성 → ORM 저장 (UPSERT) → LLM 요약 → 벡터 저장 → 검색 준비
```

**핵심 변화사항**:
- **ORM 우선**: SQLAlchemy Repository 패턴 사용
- **통합 객체 중심**: integrated_objects 테이블 기반
- **Freshdesk 전용**: 멀티플랫폼 제거, 최적화 완료
- **중복 방지**: UPSERT 패턴으로 중복 저장 해결 중

**현재 해결 중인 문제**:
- **중복 저장**: store_integrated_object_to_sqlite 함수 UPSERT 적용
- **백엔드 정리**: backend/freshdesk → core/platforms/freshdesk 통합

### 🚨 **데이터 워크플로우 핵심 원칙**

- ⚠️ **company_id 필수**: 모든 데이터에 테넌트 식별자 자동 태깅
- ⚠️ **비용 최적화**: LLM 호출 최소화 (필터링 + 캐싱 + 배치)
- ⚠️ **기존 로직 재활용**: 검증된 파이프라인 90% 이상 유지

---

## 📋 **작업별 참조 가이드**

### 🔄 **데이터 수집 작업**
1. **시작**: [data-collection-patterns.md](data-collection-patterns.instructions.md)
2. **플랫폼 확장**: [platform-adapters](../specialized/platform-adapters-multiplatform.instructions.md)
3. **보안 체크**: [multitenant-security](../core/multitenant-security.instructions.md)

### 🧠 **LLM 처리 작업**
1. **시작**: [data-processing-llm.md](data-processing-llm.instructions.md)
2. **비용 최적화**: [performance-optimization](../core/performance-optimization.instructions.md)
3. **에러 처리**: [error-handling](../development/error-handling-debugging.instructions.md)

### 💾 **저장소 작업**
1. **벡터 저장**: [vector-storage-core.md](vector-storage-core.instructions.md)
2. **DB 추상화**: [storage-abstraction-core.md](storage-abstraction-core.instructions.md)
3. **아키텍처**: [system-architecture](../core/system-architecture.instructions.md)

---

## 🔧 **핵심 데이터 처리 패턴**

### 🎯 **company_id 자동 태깅 (모든 작업 필수)**
```python
# 모든 데이터 처리에 company_id 필수
def extract_company_id(domain: str) -> str:
    return domain.split('.')[0]  # "wedosoft.freshdesk.com" → "wedosoft"

async def process_data(data: dict, company_id: str):
    data["company_id"] = company_id  # 자동 태깅
    data["platform"] = "freshdesk"   # 플랫폼 식별
```

### ⚡ **비용 최적화 필수 패턴**
```python
# LLM 비용 절감 - 캐싱 + 필터링
@cache_llm_response(ttl=86400)  # 24시간 캐싱
async def summarize_ticket(company_id: str, ticket: dict) -> dict:
    # 해결된 티켓만 요약 (비용 절감)
    if ticket.get("status") != "Resolved":
        return {"summary": "미해결 티켓 - 요약 생략"}
```

### 🔄 **기존 로직 재활용 원칙**
```python
# 세션이 바뀌어도 동일한 처리 패턴 유지
from core.ingest import ingest  # 기존 검증된 함수 재사용

# 새로운 처리 방식 임의 변경 금지
result = await ingest(
    company_id=company_id,
    platform="freshdesk",
    # 기존 매개변수 유지
)
```

---

## 📚 **관련 참조 지침서**

### 📂 **Data (현재 디렉터리)**
- **data-collection-patterns.md** - 플랫폼별 수집 패턴
- **data-processing-llm.md** - LLM 요약 및 구조화
- **vector-storage-core.md** - 벡터 저장소 핵심 패턴
- **vector-search-advanced.md** - 고급 벡터 검색 기능
- **storage-abstraction-core.md** - 스토리지 추상화 핵심 패턴

### 🏗️ **Core (핵심 아키텍처)**
- **../core/system-architecture.md** - 전체 시스템 설계
- **../core/multitenant-security.md** - 보안 및 격리
- **../core/performance-optimization.md** - 성능 최적화

### 🎯 **Specialized (특화 기능)**
- **../specialized/platform-adapters-multiplatform.md** - 멀티플랫폼 지원

### 💻 **Development (개발 패턴)**
- **../development/error-handling-debugging.md** - 오류 처리

---

## 🎯 **데이터 워크플로우 체크리스트**

### ✅ **수집 단계**
- [ ] company_id 자동 추출 및 태깅
- [ ] 플랫폼별 어댑터 사용
- [ ] 데이터 검증 및 필터링

### ✅ **처리 단계**  
- [ ] LLM 비용 최적화 (캐싱 확인)
- [ ] 구조화된 요약 생성
- [ ] 에러 처리 및 재시도

### ✅ **저장 단계**
- [ ] 벡터 임베딩 생성
- [ ] 멀티테넌트 격리 확인
- [ ] 백업 및 복구 전략

---

*📝 이 인덱스는 데이터 워크플로우의 전체 구조를 제공하며, 세부 구현은 각 전문 지침서를 참조하세요.*

**🔗 Next Steps**: 특정 작업에 따라 위의 관련 지침서들을 참조하여 세부 구현을 진행하세요.
