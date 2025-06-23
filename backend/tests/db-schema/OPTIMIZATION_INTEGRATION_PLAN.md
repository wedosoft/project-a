# 📊 최적화 스크립트 통합 계획

## 🎯 목표
기존 비효율적인 데이터베이스를 최적화된 스키마로 전환하고, 대량 요약 처리 기능을 백엔드 API에 통합

## 📁 파일 분류 및 처리 계획

### 1. 🚀 일회성 마이그레이션 스크립트 (완료 후 삭제)
```
backend/
├── create_optimized_schema.py          [삭제 예정] - 스키마 생성 완료 후
├── collect_optimized_data.py           [삭제 예정] - 데이터 마이그레이션 완료 후
└── migrate_legacy_summaries.py         [삭제 예정] - 기존 요약 데이터 이전
```

### 2. 🔧 백엔드 API 통합 모듈 (영구 유지)
```
backend/api/
├── summarization.py                    [새로 생성] - 요약 API 엔드포인트
├── batch_processing.py                 [새로 생성] - 배치 처리 API
└── monitoring.py                       [새로 생성] - 모니터링 API

backend/core/
├── llm/
│   ├── batch_summarizer.py            [유지] - 배치 처리 엔진
│   ├── summarizer.py                  [유지] - 요약 생성 로직
│   └── manager.py                     [유지] - LLM 관리
├── database/
│   ├── optimized_models.py            [새로 생성] - 최적화된 DB 모델
│   └── repository.py                  [새로 생성] - 데이터 접근 레이어
└── services/
    ├── summary_service.py              [새로 생성] - 요약 비즈니스 로직
    └── batch_service.py                [새로 생성] - 배치 처리 서비스
```

### 3. 🛠️ 운영 도구 (선택적 유지)
```
backend/tools/
├── optimized_large_scale_summarization.py  [유지] - 대량 배치 실행
├── optimized_monitor.py                     [유지] - 운영 모니터링
├── data_quality_checker.py                  [유지] - 데이터 품질 검사
└── performance_analyzer.py                  [유지] - 성능 분석
```

## 📈 통합 단계

### Phase 1: 스키마 최적화 (현재)
- ✅ 최적화된 스키마 설계 완료
- ✅ 스키마 생성 스크립트 작성 완료
- 🔄 스키마 생성 및 검증

### Phase 2: 데이터 마이그레이션
- 📋 기존 데이터를 새 스키마로 이전
- 📋 데이터 품질 검증
- 📋 성능 벤치마크

### Phase 3: 백엔드 API 통합
- 📋 요약 API 엔드포인트 구현
- 📋 배치 처리 API 구현
- 📋 모니터링 대시보드 API

### Phase 4: 레거시 정리
- 📋 일회성 스크립트 삭제
- 📋 기존 비효율 코드 제거
- 📋 문서 업데이트

## 🔄 최종 백엔드 구조

```
backend/
├── api/
│   ├── main.py                         # FastAPI 메인
│   ├── tickets.py                      # 티켓 관리 API
│   ├── summarization.py               # 요약 API ⭐ 새로운 핵심 기능
│   └── monitoring.py                  # 모니터링 API
├── core/
│   ├── llm/                           # LLM 처리 엔진 (최적화됨)
│   ├── database/                      # 데이터베이스 레이어 (새로운 스키마)
│   └── services/                      # 비즈니스 로직
├── tools/                             # 운영 도구 (선택적)
└── data/
    └── wedosoft_freshdesk_data_optimized.db  # 최적화된 DB
```

## 💡 핵심 개선 사항

### 이전 (비효율적)
- 단일 테이블에 모든 데이터 저장
- 중복 데이터 대량 발생
- 인덱스 부족으로 느린 조회
- 메모리 과다 사용

### 이후 (최적화됨)
- 정규화된 다중 테이블 구조
- 중복 제거 및 압축
- 최적화된 인덱스
- 배치 처리로 효율성 극대화

## 📊 예상 성능 개선

| 항목 | 이전 | 이후 | 개선율 |
|------|------|------|---------|
| DB 크기 | ~500MB | ~150MB | 70% 감소 |
| 조회 속도 | 2-5초 | 100-300ms | 90% 향상 |
| 메모리 사용 | 1-2GB | 200-500MB | 75% 감소 |
| 처리 처리량 | 100건/시간 | 1000건/시간 | 10배 향상 |

## 🗂️ 파일 정리 일정

### 즉시 삭제 가능
- 개발 중 생성된 임시 파일들

### 1개월 후 삭제
- `create_optimized_schema.py`
- `collect_optimized_data.py`
- 기존 비효율적인 스크립트들

### 영구 보관
- `core/llm/` 디렉토리 내 모든 파일
- `api/` 디렉토리 내 통합된 API
- `tools/` 디렉토리 내 운영 도구

---

📝 **결론**: 현재 생성되는 대부분의 스크립트는 일회성이며, 핵심 로직만 백엔드에 통합됩니다. 최종적으로는 깔끔하고 효율적인 백엔드 구조가 완성됩니다.
