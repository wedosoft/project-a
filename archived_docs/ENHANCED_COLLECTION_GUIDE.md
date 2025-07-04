# Enhanced Freshdesk Collection 가이드

## 🚀 개선사항 요약

### 1. Raw 데이터 저장으로 재수집 방지
- **티켓 상세정보**와 **지식베이스** 원본 데이터를 청크별로 저장
- 임베딩 실패 시 **재수집 불필요** - 저장된 원본 데이터 활용
- API 호출 비용과 시간 대폭 절약

### 2. 수백만 건 데이터 처리 최적화
- 메모리 효율적인 **조각별 저장** 방식
- 자동 **시스템 리소스 모니터링**
- 규모별 **자동 설정 최적화**

## 📁 새로운 저장 구조

```
freshdesk_enhanced_data/
├── tickets/
│   ├── basic_chunk_0000.json      # 기본 정보 (기존과 동일)
│   ├── details_chunk_0000.json    # ✨ 상세정보 (새로 추가)
│   ├── basic_chunk_0001.json
│   ├── details_chunk_0001.json
│   └── ...
├── knowledge_base/
│   ├── articles_chunk_0000.json   # ✨ 지식베이스 (새로 추가)
│   ├── articles_chunk_0001.json
│   └── ...
├── raw_data/                      # 원본 데이터 백업
├── progress.json                  # 진행 상황
├── enhanced_collection_stats.json # 상세 통계
└── enhanced_collection.log       # 로그
```

## 🎯 주요 기능

### 1. 단계별 데이터 수집
1. **기본 티켓 정보** 수집 및 청크별 저장
2. **티켓 상세정보** 수집 및 별도 저장 ✨
3. **지식베이스 문서** 수집 및 별도 저장 ✨
4. 임베딩 시 저장된 원본 데이터 활용

### 2. 지능형 리소스 관리
- **메모리 사용량** 실시간 모니터링
- **디스크 공간** 자동 체크
- 임계값 도달 시 **자동 수집 중단**

### 3. 규모별 자동 최적화
- 티켓 수에 따른 **자동 설정 선택**
- **청크 크기** 및 **날짜 분할** 최적화
- **하드웨어 요구사항** 자동 계산

## 🔧 사용 방법

### 1. 기본 실행 (자동 최적화)

```bash
cd backend/freshdesk
python enhanced_runner.py
```

### 2. 설정 확인 (DRY RUN)

```bash
python enhanced_runner.py --dry-run
```

### 3. 커스텀 설정

```bash
# 특정 기간만 수집
python enhanced_runner.py \
    --start-date "2023-01-01" \
    --end-date "2024-01-01" \
    --max-tickets 100000

# 테스트용 소량 수집
python enhanced_runner.py \
    --max-tickets 1000 \
    --max-kb-articles 100 \
    --output-dir "test_data"
```

### 4. Python 코드에서 직접 사용

```python
from enhanced_fetcher import EnhancedFreshdeskFetcher

async def collect_data():
    async with EnhancedFreshdeskFetcher("my_data") as fetcher:
        stats = await fetcher.enhanced_collect_all_tickets(
            start_date="2023-01-01",
            max_tickets=50000,
            save_detailed_tickets=True,  # 상세정보 저장
            save_kb_articles=True,       # 지식베이스 저장
        )
        print(f"수집 완료: {stats}")

# 실행
import asyncio
asyncio.run(collect_data())
```

## 📊 규모별 권장 설정

### 소규모 (10만건 이하)
```bash
python enhanced_runner.py \
    --max-tickets 100000 \
    --output-dir "freshdesk_small"
```
- **청크 크기**: 2,000개
- **날짜 분할**: 60일 단위
- **예상 시간**: 8-12시간
- **필요 공간**: 2-5GB

### 중규모 (100만건 이하)
```bash
python enhanced_runner.py \
    --max-tickets 1000000 \
    --output-dir "freshdesk_medium"
```
- **청크 크기**: 5,000개
- **날짜 분할**: 30일 단위
- **예상 시간**: 3-5일
- **필요 공간**: 20-50GB

### 대규모 (500만건 이상)
```bash
python enhanced_runner.py \
    --start-date "2015-01-01" \
    --output-dir "freshdesk_large"
```
- **청크 크기**: 10,000개
- **날짜 분할**: 14일 단위
- **예상 시간**: 2-3주
- **필요 공간**: 100-200GB

## 🔍 모니터링

### 1. 실시간 로그 확인
```bash
tail -f enhanced_collection.log
```

### 2. 진행 상황 확인
```bash
python -c "
import json
with open('freshdesk_enhanced_data/enhanced_collection_stats.json') as f:
    stats = json.load(f)
    print(f'기본 티켓: {stats.get(\"total_tickets_collected\", 0):,}개')
    enhanced = stats.get('enhanced_features', {})
    print(f'상세 티켓: {enhanced.get(\"detailed_tickets_collected\", 0):,}개')
    print(f'지식베이스: {enhanced.get(\"kb_articles_collected\", 0):,}개')
"
```

### 3. 시스템 리소스 확인
```bash
python -c "
import psutil
memory = psutil.virtual_memory()
disk = psutil.disk_usage('/')
print(f'메모리: {memory.percent:.1f}% 사용 중')
print(f'디스크: {disk.percent:.1f}% 사용 중')
print(f'사용 가능 공간: {disk.free/(1024**3):.1f}GB')
"
```

## 🔄 임베딩 시 원본 데이터 활용

### ingest.py에서 자동 활용
```python
# Enhanced 구조 자동 감지 및 원본 데이터 로드
tickets, articles = load_local_data("freshdesk_enhanced_data")

# 기존 임베딩 로직에서 바로 사용 가능
# 추가 API 호출 없이 상세정보와 지식베이스 데이터 활용
```

### 기존 코드와의 호환성
- 기존 `OptimizedFreshdeskFetcher` 완전 호환
- 기존 `load_local_data` 함수 향상 (하위 호환성 유지)
- 기존 임베딩 파이프라인 수정 없이 바로 활용 가능

## ⚠️ 주의사항

### 1. 디스크 공간 관리
- **대용량 수집 전** 충분한 디스크 공간 확보
- 청크 파일은 **압축 저장** 고려
- **정기적 백업** 및 **오래된 파일 정리**

### 2. 메모리 사용량
- **16GB 이상** 메모리 권장 (대규모 수집)
- 메모리 부족 시 **청크 크기 감소**
- **백그라운드 프로세스** 최소화

### 3. 네트워크 안정성
- **유선 네트워크** 환경 권장
- **VPN 연결** 시 안정성 확인
- **Rate limit** 준수를 위한 요청 간격 유지

## 🎉 예상 효과

### 1. API 호출 비용 절감
- 상세정보 **재수집 불필요** → **80% 이상** API 호출 감소
- 지식베이스 **중복 수집 방지** → **시간 및 비용 절약**

### 2. 처리 속도 향상
- 임베딩 시 **실시간 API 호출 제거**
- 로컬 파일 읽기로 **10배 이상** 속도 향상

### 3. 안정성 개선
- **네트워크 오류** 영향 최소화
- **중단-재개** 기능으로 **데이터 손실 방지**
- **메모리 효율성**으로 **대용량 처리** 안정화

## 🚀 시작하기

1. **설정 확인**:
   ```bash
   python enhanced_runner.py --dry-run
   ```

2. **테스트 실행**:
   ```bash
   python enhanced_runner.py --max-tickets 1000
   ```

3. **전체 수집**:
   ```bash
   python enhanced_runner.py
   ```

이제 **재수집 걱정 없이** 안전하고 효율적으로 대용량 Freshdesk 데이터를 수집할 수 있습니다! 🎉
