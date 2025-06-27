# 🎯 대용량 요약 처리 시스템 사용 가이드

## 📋 개요

100만건 이상의 대용량 데이터를 처리하면서도 고품질의 요약을 보장하는 시스템입니다.

### 🔧 주요 개선사항

1. **적응형 컨텍스트 관리**: 데이터셋 크기에 따른 컨텍스트 최적화
2. **품질 보장 시스템**: 대용량 처리 시에도 품질 기준 유지
3. **스케일러블 배치 처리**: 메모리와 성능을 고려한 동적 배치 크기 조정
4. **리소스 모니터링**: 실시간 메모리 사용량 추적 및 GC 관리

## 🚀 사용법

### 1. 기본 요약 생성 (기존과 동일)

```python
from backend.core.llm.summarizer import generate_summary

# 단일 요약 생성
summary = await generate_summary(
    content="티켓 내용...",
    content_type="ticket",
    subject="문제 제목",
    ui_language="ko"
)
```

### 2. 대용량 처리 모드 활성화

```python
from backend.core.llm.summarizer import enable_large_scale_processing

# 100만건 데이터셋 처리 시
enable_large_scale_processing(dataset_size=1000000)

# 이후 generate_summary 호출 시 자동으로 최적화 적용
```

### 3. 스케일러블 배치 처리

```python
from backend.core.llm.scalable_summarizer import ScalableSummarizer, ScalabilityConfig

# 설정 정의
config = ScalabilityConfig(
    initial_batch_size=30,
    max_concurrency=5,
    quality_priority_mode=True,
    min_quality_threshold=0.85
)

# 스케일러블 요약기 생성
summarizer = ScalableSummarizer(config)

# 대용량 데이터 처리
results, metrics = await summarizer.process_large_dataset(
    data_generator=your_data_generator,
    total_count=1000000,
    progress_callback=your_progress_callback
)
```

### 4. 데이터베이스에서 직접 처리

```python
from backend.core.llm.scalable_summarizer import process_million_scale_dataset

# 100만건 규모 처리 예시
metrics = await process_million_scale_dataset(
    db_path="path/to/your/database.db",
    output_path="path/to/results"
)
```

## 📊 성능 테스트

### 테스트 실행

```bash
cd /Users/alan/GitHub/project-a
python backend/tests/test_large_scale_summarization.py
```

### 테스트 결과 확인

- `test_results/summary_scaling/scalability_test_YYYYMMDD_HHMMSS.json`: 상세 테스트 결과
- `test_results/summary_scaling/test_report_YYYYMMDD_HHMMSS.md`: 요약 리포트

## ⚙️ 설정 최적화

### ScalabilityConfig 주요 설정

```python
config = ScalabilityConfig(
    # 메모리 관리
    max_memory_usage_percent=75.0,  # 메모리 사용률 제한
    gc_threshold=70.0,              # GC 실행 임계값
    
    # 배치 크기
    initial_batch_size=30,          # 초기 배치 크기 (보수적)
    max_batch_size=100,             # 최대 배치 크기
    
    # 동시성
    base_concurrency=3,             # 기본 동시성
    max_concurrency=10,             # 최대 동시성
    
    # 품질 vs 처리량
    quality_priority_mode=True,     # 품질 우선 모드
    min_quality_threshold=0.85,     # 최소 품질 기준
    
    # 오류 처리
    max_retry_attempts=3,           # 최대 재시도 횟수
    error_threshold_percent=10.0    # 에러율 임계값
)
```

### 환경별 권장 설정

#### 🖥️ 로컬 개발 환경
```python
config = ScalabilityConfig(
    initial_batch_size=10,
    max_batch_size=50,
    base_concurrency=2,
    max_concurrency=5,
    max_memory_usage_percent=70.0
)
```

#### 🏢 서버 환경 (중간 규모)
```python
config = ScalabilityConfig(
    initial_batch_size=50,
    max_batch_size=200,
    base_concurrency=5,
    max_concurrency=20,
    max_memory_usage_percent=80.0
)
```

#### 🚀 클라우드 환경 (대용량)
```python
config = ScalabilityConfig(
    initial_batch_size=100,
    max_batch_size=500,
    base_concurrency=10,
    max_concurrency=50,
    max_memory_usage_percent=85.0
)
```

## 🔍 품질 보장 메커니즘

### 1. 적응형 컨텍스트 최적화

- **압축**: 대용량 시 의미적 컨텍스트 압축
- **핵심 추출**: 관련성 높은 정보만 선별
- **토큰 관리**: 모델 한계 내에서 최적 정보 유지

### 2. 품질 검증 시스템

- **구조 검증**: 4개 섹션 완성도 확인
- **내용 완성도**: 핵심 정보 누락 방지
- **언어 품질**: 오류 메시지 및 불완전한 응답 감지

### 3. 자동 재시도 로직

- **품질 기준 미달 시**: 자동으로 더 강력한 프롬프트로 재생성
- **일시적 오류 시**: 지수 백오프로 재시도
- **최종 폴백**: 구조화된 오류 메시지 제공

## 📈 모니터링 및 지표

### 실시간 지표

```python
# ProcessingMetrics 확인
print(f"성공률: {metrics.successful / metrics.total_processed * 100:.1f}%")
print(f"평균 품질: {metrics.average_quality_score:.3f}")
print(f"처리량: {metrics.throughput_per_minute:.1f}건/분")
print(f"메모리 사용량: {metrics.memory_usage_peak:.1f}%")
```

### 로그 모니터링

```bash
# 실시간 로그 확인
tail -f backend/logs/summarization.log | grep "대용량\|배치\|품질"
```

## ⚠️ 주의사항

### 1. 메모리 관리

- 대용량 처리 시 메모리 사용량을 지속적으로 모니터링
- `max_memory_usage_percent` 설정을 시스템 사양에 맞게 조정
- 필요시 배치 크기를 줄여서 메모리 부담 감소

### 2. API 사용량 관리

- OpenAI API 사용량 및 비용 모니터링
- Rate Limit에 주의하여 동시성 설정
- 큰 배치 처리 전 API 할당량 확인

### 3. 품질 vs 성능 균형

- `quality_priority_mode=True`: 품질 우선 (처리 시간 증가)
- `quality_priority_mode=False`: 처리량 우선 (품질 약간 저하 가능)

## 🔧 문제 해결

### 일반적인 문제들

#### 1. 메모리 부족 오류
```python
# 설정 조정
config.max_memory_usage_percent = 60.0
config.initial_batch_size = 10
config.max_concurrency = 2
```

#### 2. API Rate Limit 초과
```python
# 동시성 감소
config.base_concurrency = 1
config.max_concurrency = 3
```

#### 3. 품질 저하
```python
# 품질 기준 강화
config.quality_priority_mode = True
config.min_quality_threshold = 0.90
config.max_retry_attempts = 5
```

### 디버깅

```python
# 상세 로깅 활성화
import logging
logging.getLogger('backend.core.llm').setLevel(logging.DEBUG)

# 개별 아이템 처리 확인
result = await summarizer._process_single_item_with_retry(test_item)
print(f"품질 점수: {result['quality_score']}")
```

## 📚 참고자료

- `backend/core/llm/optimized_summarizer.py`: 핵심 요약 로직
- `backend/core/llm/scalable_summarizer.py`: 대용량 처리 시스템
- `backend/core/processing/context_builder.py`: 컨텍스트 최적화
- `backend/tests/test_large_scale_summarization.py`: 성능 테스트

## 🎯 성능 목표

| 규모 | 목표 성공률 | 목표 품질 점수 | 목표 처리량 |
|------|-------------|----------------|-------------|
| 100건 | 98%+ | 0.95+ | 20+건/분 |
| 1,000건 | 95%+ | 0.90+ | 15+건/분 |
| 10,000건 | 90%+ | 0.85+ | 10+건/분 |
| 100만건+ | 85%+ | 0.80+ | 5+건/분 |
