# 하이브리드 검색 개선 계획 (Hybrid Search Enhancement Plan)

## 📋 프로젝트 개요

**브랜치**: `feature/hybrid-search-enhancement`  
**시작일**: 2025년 6월 29일  
**목표**: `/init` 및 `/query` 엔드포인트의 기본 벡터 검색을 고품질 하이브리드 검색 (SQL + Vector)으로 개선

## 🎯 현재 상황 분석 (수정됨)

### 현재 구현 상태 ✅
- **고도화된 하이브리드 검색 시스템 존재**: `core/search/hybrid.py`에 완전한 `HybridSearchManager` 구현
- **벡터 + SQL 통합 검색**: 벡터 유사도와 메타데이터 필터링을 결합한 검색
- **LLM 강화 기능**: 검색 결과의 LLM 기반 컨텍스트 강화 및 품질 평가
- **고급 기능들**: 재순위(reranking), 의도 분석, 품질 점수, 커스텀 필드 검색
- **멀티테넌트 지원**: tenant_id 기반 격리 및 최적화
- **성능 최적화**: 캐싱, GPU 임베딩, 배치 처리

### 실제 문제점 (재분석)
1. **`/init` 엔드포인트에서 하이브리드 검색 미활용**: 기본 벡터 검색만 사용
2. **고급 기능의 엔드포인트 연결 부족**: 하이브리드 매니저의 고급 기능이 `/init`에 연결되지 않음
3. **품질 임계값 미적용**: `min_similarity` 파라미터가 `/init`에서 활용되지 않음
4. **검색 결과 로깅 부족**: 현재 `/init`에서 검색 품질 메트릭 로깅 부족

## 🚀 개선 목표 (수정됨)

### 단기 목표 (1주) - 하이브리드 검색 연결
1. **`/init` 엔드포인트 하이브리드 검색 적용**
   - 현재 `llm_manager.execute_init_sequential()` 대신 `HybridSearchManager` 직접 활용
   - 품질 임계값 적용 (similarity ≥ 0.7)
   - 검색 결과 품질 로깅 추가

2. **검색 품질 개선**
   - `min_similarity` 파라미터 활용
   - 검색 결과 재순위(reranking) 적용
   - LLM 기반 컨텍스트 강화 활성화

### 중기 목표 (2주) - 최적화 및 모니터링
3. **성능 최적화**
   - 검색 응답 시간 모니터링 강화
   - 캐싱 효율성 개선
   - 배치 처리 최적화

4. **품질 메트릭 대시보드**
   - 검색 품질 점수 시계열 분석
   - 테넌트별 검색 패턴 분석
   - A/B 테스트 프레임워크 구축

### 장기 목표 (1개월) - 고급 기능 확장
5. **AI 인사이트 고도화**
   - 검색 의도 분석 정확도 개선
   - 개인화된 검색 결과 순위 조정
   - 예측적 문서 추천 시스템

6. **멀티모달 검색 확장**
   - 첨부파일 내용 검색 통합
   - 이미지 내 텍스트 검색
   - 대화 히스토리 패턴 분석

## 📁 파일 구조 및 변경 계획

### 주요 파일
```
backend/
├── api/routes/
│   ├── init.py                 # 🔧 하이브리드 검색 호출 방식 변경
│   └── query.py               # 🔧 쿼리 엔드포인트 개선
├── core/search/
│   ├── hybrid.py              # 🔧 핵심 하이브리드 검색 로직 구현
│   ├── filters.py             # 🆕 SQL 필터링 로직
│   └── quality.py             # 🆕 품질 점수 및 임계값 관리
├── core/database/
│   ├── vectordb.py            # 🔧 벡터 검색 개선
│   └── metadata.py            # 🆕 메타데이터 관리 강화
└── core/models/
    └── search_models.py       # 🆕 검색 결과 모델 정의
```

### 새로 생성할 파일
- `core/search/filters.py`: SQL 기반 사전 필터링
- `core/search/quality.py`: 품질 점수 관리
- `core/database/metadata.py`: 메타데이터 처리 강화
- `core/models/search_models.py`: 검색 결과 데이터 모델

## 🔄 3단계 작업 프로세스

프로젝트 지침에 따라 모든 변경사항은 다음 단계를 따릅니다:

### 1단계: 제안 (Proposal)
- 구체적인 변경 사항 제안
- 영향 범위 및 리스크 분석
- 기대 효과 명시

### 2단계: 확인 (Confirmation) 
- 제안 내용 검토 및 승인
- 우선순위 및 일정 확정
- 구현 방식 합의

### 3단계: 단계별 실행 (Step-by-step Execution)
- 단계별 구현 및 테스트
- 각 단계별 검증
- 문서 업데이트

## 📝 1차 제안 (Phase 1) - 수정됨

### 제안 제목: `/init` 엔드포인트에 기존 하이브리드 검색 시스템 연결

### 현재 발견 사항:
- ✅ **고도화된 `HybridSearchManager` 이미 존재** (`core/search/hybrid.py`)
- ✅ **고급 기능들 완전 구현됨**: 재순위, LLM 강화, 품질 점수, 커스텀 필드 검색
- ❌ **`/init` 엔드포인트에서 미활용**: `llm_manager.execute_init_sequential()` 경로 사용

### 구체적 변경사항:

#### 1. `init.py` 개선 (핵심 변경)
```python
# 현재 (127-135행):
result = await llm_manager.execute_init_sequential(
    ticket_data=structured_ticket_data,
    qdrant_client=qdrant_client,
    tenant_id=tenant_id,
    top_k_tickets=top_k_tickets if include_similar_tickets else 0,
    top_k_kb=top_k_kb if include_kb_docs else 0,
    include_summary=include_summary
)

# 개선 후:
from core.search.hybrid import HybridSearchManager

# 하이브리드 검색 매니저 초기화
hybrid_manager = HybridSearchManager()

# 검색 쿼리 구성
search_query = f"{structured_ticket_data['subject']} {structured_ticket_data['description_text']}"

# 하이브리드 검색 실행 (고품질, 재순위, LLM 강화)
search_results = await hybrid_manager.hybrid_search(
    query=search_query,
    tenant_id=tenant_id,
    platform=platform,
    top_k=max(top_k_tickets, top_k_kb),
    enable_llm_enrichment=True,
    rerank_results=True,
    min_similarity=0.7,  # 품질 임계값
)

# 기존 요약 생성 (별도 유지)
if include_summary:
    summary_result = await llm_manager.execute_summary_task(...)
```

#### 2. 응답 구조 개선
- 하이브리드 검색 품질 메트릭 추가
- 검색 방법론 투명성 제공
- 상세 로깅 및 성능 측정

#### 3. 품질 보장 기능 활성화
- `min_similarity=0.7`: 낮은 품질 결과 자동 필터링
- `rerank_results=True`: AI 기반 결과 재순위
- `enable_llm_enrichment=True`: 컨텍스트 강화

### 기대 효과:
- 🎯 **즉시 품질 개선**: 기존 고도화된 시스템 활용으로 검색 품질 대폭 향상
- 📊 **투명한 품질 메트릭**: 검색 품질 점수와 방법론 제공
- 🚀 **제로 위험**: 기존 시스템 재활용으로 안정성 보장
- 📈 **상세 모니터링**: 검색 성능 및 품질 지표 실시간 추적

### 리스크 평가:
- **매우 낮음**: 기존 고도화된 시스템 활용
- **API 호환성**: 기존 응답 구조 100% 유지
- **성능**: 하이브리드 검색으로 약간의 응답 시간 증가 가능 (캐싱으로 완화)

## 📊 성공 지표

### 정량적 지표
- **검색 정확도**: 관련성 있는 결과 비율 > 85%
- **응답 시간**: 평균 응답 시간 < 2초 유지
- **품질 점수**: 평균 similarity score > 0.75

### 정성적 지표
- **사용자 만족도**: 검색 결과의 유용성 개선
- **개발자 경험**: 명확한 로깅 및 디버깅 정보
- **유지보수성**: 모듈화된 코드 구조

## 📅 일정 계획

### Week 1: 하이브리드 검색 연결
- [ ] 1단계: 제안 확정 ✅
- [ ] 2단계: 상세 설계 확인
- [ ] 3단계: `/init` 엔드포인트 하이브리드 검색 연결 구현

### Week 2: 품질 및 모니터링 강화
- [ ] 검색 품질 메트릭 로깅 강화
- [ ] 성능 벤치마크 및 최적화
- [ ] 테스트 케이스 추가 및 검증

### Week 3-4: 고도화 및 최적화
- [ ] A/B 테스트 프레임워크 구축
- [ ] 개인화 기능 실험
- [ ] 문서화 및 가이드 완성

## 🔍 다음 단계

**현재 상태**: 1단계 (제안) 완료  
**다음 필요사항**: 2단계 (확인) - 이 계획에 대한 승인 및 우선순위 확정

---

## 📋 변경 로그

| 날짜 | 내용 | 상태 |
|------|------|------|
| 2025-06-29 | 초기 계획 문서 작성 | ✅ 완료 |
| 2025-06-29 | **중요 발견**: 고도화된 `HybridSearchManager` 이미 존재 | ✅ 확인 |
| 2025-06-29 | 1차 제안 수정: 기존 시스템 연결로 변경 | ✅ 완료 |
| | 2단계 확인 대기: `/init` 하이브리드 검색 연결 | 🟡 대기 중 |

---

**참고 문서**: 
- **[⭐ 실시간 프로젝트 상태](./HYBRID_SEARCH_STATUS.md)** - 세션 간 컨텍스트 유지용 마스터 상태 파일
- `.github/instructions/INDEX.md` - 프로젝트 작업 프로세스
- `docs/SEQUENTIAL_ARCHITECTURE_UPDATE_20250628.md` - 기존 아키텍처 분석
- `backend/core/search/hybrid.py` - 현재 하이브리드 검색 구현
- `backend/scripts/check-hybrid-status.sh` - 빠른 상태 확인 스크립트
