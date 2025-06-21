# Core 폴더 정리 계획

## 🚨 현재 상황
- **33개 파일/디렉터리**가 core 폴더에 직접 위치
- 개발자가 필요한 파일을 찾기 어려운 상황
- 관련 기능들이 분산되어 있음

## 🎯 제안하는 정리 구조

```
core/
├── __init__.py
├── config.py                    # 전역 설정 (유지)
├── exceptions.py                # 전역 예외 (유지)
├── constants.py                 # 전역 상수 (유지)
├── dependencies.py              # FastAPI 의존성 (유지)
├── middleware.py               # 미들웨어 (유지)
├── logger.py                   # 로깅 설정 (유지)
├── settings.py                 # 전역 설정 (유지)
├── utils.py                    # 전역 유틸리티 (유지)
├── database/                   # 데이터베이스 관련
│   ├── __init__.py
│   ├── database.py            # 기존 database.py
│   ├── vectordb.py            # 기존 vectordb.py
│   └── migrations/            # 기존 migration/
├── data/                       # 데이터 처리 관련
│   ├── __init__.py
│   ├── validator.py           # 기존 data_validator.py
│   ├── merger.py              # 기존 data_merger.py
│   ├── schemas.py             # 기존 schemas.py
│   └── doc_id_utils.py        # 기존 doc_id_utils.py
├── search/                     # 검색 관련
│   ├── __init__.py
│   ├── retriever.py           # 기존 retriever.py
│   ├── langchain_retriever.py # 기존 langchain_retriever.py
│   ├── hybrid.py              # 기존 search_hybrid.py
│   ├── optimizer.py           # 기존 search_optimizer.py
│   └── embeddings/            # 임베딩 관련
│       ├── __init__.py
│       ├── embedder.py        # 기존 embedder.py
│       └── embedder_gpu.py    # 기존 embedder_gpu.py
├── llm/                        # LLM 통합 (최종 이름)
│   ├── __init__.py
│   ├── manager.py             
│   ├── models/
│   ├── providers/
│   ├── integrations/
│   ├── utils/
│   └── filters/
├── platforms/                  # 플랫폼 통합 (유지)
│   └── ... (기존 내용 유지)
├── ingest/                     # 데이터 수집 (유지)
│   └── ... (기존 내용 유지)
├── processing/                 # 처리 로직
│   ├── __init__.py
│   ├── context_builder.py     # 기존 context_builder.py
│   └── filters/
│       ├── __init__.py
│       └── progressive_filter_upgrade.py
└── legacy/                     # 레거시 코드 (백업용)
    ├── __init__.py
    ├── llm_router_legacy_20250621.py
    └── ... (기타 레거시 파일들)
```

## 📋 정리 단계

### Phase 1: 백업 및 계획 확정
- [ ] 현재 core 폴더 전체 백업
- [ ] 정리 계획 검토 및 승인

### Phase 2: 새 구조 생성
- [ ] 새로운 디렉터리 구조 생성
- [ ] 각 카테고리별 __init__.py 생성

### Phase 3: 파일 이동 및 임포트 수정
- [ ] database/ 관련 파일들 이동
- [ ] data/ 관련 파일들 이동  
- [ ] search/ 관련 파일들 이동
- [ ] processing/ 관련 파일들 이동
- [ ] 모든 임포트 경로 수정

### Phase 4: LLM 통합 완료
- [ ] llm_unified 작업 완료
- [ ] 기존 llm, langchain 폴더 정리
- [ ] llm_unified → llm 이름 변경

### Phase 5: 테스트 및 검증
- [ ] 모든 기능 테스트
- [ ] 성능 테스트
- [ ] 문서 업데이트

## 🎯 기대 효과

1. **가독성 향상**: 33개 → 약 12개 주요 항목
2. **유지보수 개선**: 관련 기능들이 그룹화됨
3. **확장성**: 새 기능 추가가 더 체계적
4. **개발자 경험**: 필요한 파일을 쉽게 찾을 수 있음
