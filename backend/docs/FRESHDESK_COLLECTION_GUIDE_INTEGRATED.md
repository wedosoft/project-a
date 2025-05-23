# Freshdesk 티켓 수집 통합 가이드

이 가이드는 Freshdesk 티켓 데이터를 다양한 규모로 효율적으로 수집하는 방법을 제공합니다. 소규모(10만건) 및 대규모(500만건 이상) 수집 모두 지원합니다.

## 수집 규모별 전략

| 규모 | 특징 | 실행 방법 | 소요 시간 | 필요 디스크 공간 |
|------|------|----------|----------|----------------|
| 테스트 (100건) | 기능 확인 목적 | 메뉴 옵션 2 | 5-10분 | 10MB |
| 소규모 (10만건) | 일반 분석용 | 기존 `collect_all_tickets` 함수 | 8-20시간 | 2-5GB |
| 대규모 (500만건 이상) | 전체 데이터 분석용 | 메뉴 옵션 1 또는 `run_full_collection.sh` | 2-3주 이상 | 100GB 이상 |

## 실행 방법

### 1. 대규모 수집 (500만건 이상, 권장)

#### A. 백그라운드 실행 (권장)
```bash
# 실행 권한 부여
chmod +x scripts/run_full_collection.sh scripts/monitor_collection.sh

# 백그라운드에서 실행
./scripts/run_full_collection.sh

# 진행 상황 모니터링
./scripts/monitor_collection.sh -w
```

#### B. 직접 실행
```bash
python run_collection.py
# 메뉴에서 '1. 전체 수집 (무제한)' 선택
```

### 2. 소규모 수집 (10만건 이하)

```python
from optimized_fetcher import OptimizedFreshdeskFetcher

async def collect_tickets():
    async with OptimizedFreshdeskFetcher("output_directory") as fetcher:
        stats = await fetcher.collect_all_tickets(
            start_date="2020-01-01",
            max_tickets=100000,  # 10만건 제한
            include_conversations=True,
            include_attachments=False
        )
        print(f"수집 완료: {stats}")

# 실행
import asyncio
asyncio.run(collect_tickets())
```

### 3. 테스트 수집 (100건)
```bash
python run_collection.py
# 메뉴에서 '2. 빠른 테스트 (100건)' 선택
```

## 주요 최적화 전략

### 1. 날짜 기반 분할 수집
- **문제**: Freshdesk API는 기본적으로 최대 30,000개 티켓만 반환 (300페이지 × 100개)
- **해결책**: 30일 단위로 날짜 범위를 분할하여 `updated_since` 파라미터 활용

### 2. 메모리 사용량 최적화
- **청크 크기 축소**: 5,000개 단위로 저장하여 메모리 사용량 감소
- **주기적인 메모리 모니터링**: 80% 이상 사용 시 경고 및 조치

### 3. 디스크 공간 관리
- **최소 필요 공간**: 
  - 10만건: 약 2-5GB (대화내역 포함 시)
  - 500만건: 약 100GB 이상 권장
- **자동 디스크 체크**: 90% 이상 사용 시 수집 일시 중단

### 4. 자동 복구 메커니즘
- **진행 상황 저장**: 500개 티켓마다 진행 상황 저장
- **날짜 기반 분할**: 30일 단위로 분할하여 개별 처리
- **중단 지점 재개**: 오류 발생 시 중단된 날짜 범위부터 재개

### 5. 네트워크 안정성
- **요청 간격 최적화**: 
  - 소규모: 0.3초 (Enterprise 플랜 기준)
  - 대규모: 0.5초 (더 보수적인 설정)
- **자동 재시도 증가**: 최대 10회 재시도로 일시적 장애 극복
- **Rate Limit 자동 감지**: 응답 헤더 기반 대기 시간 조정

## 모니터링

### 실시간 진행 상황 (대규모 수집용)
```bash
# 계속 업데이트되는 모니터링 (5분 간격)
./monitor_collection.sh -w

# 현재 상태만 확인
./monitor_collection.sh
```

### 로그 확인
```bash
# 실시간 로그 확인
tail -f freshdesk_full_collection.log

# 마지막 100줄 확인
tail -n 100 freshdesk_full_collection.log
```

### 수집 통계 확인
```python
import json
with open("freshdesk_full_data/collection_stats.json") as f:
    stats = json.load(f)
    print(f"수집 완료: {stats['total_tickets_collected']:,}개")
```

### 수집 중단
```bash
# PID 파일 이용해 중단
kill $(cat freshdesk_collection.pid)
```

## 파일 구조

### 대규모 수집
```
freshdesk_full_data/
├── tickets_chunk_0000.json      # 첫 번째 청크
├── tickets_chunk_0001.json      # 두 번째 청크
├── ...
├── progress.json                # 진행 상황 추적
├── collection_stats.json        # 수집 통계
├── all_tickets.json            # 병합된 전체 데이터
├── tickets_export.csv          # CSV 내보내기
└── summary_report.json         # 요약 리포트
```

### 소규모 수집
```
freshdesk_100k_data/
├── tickets_chunk_0000.json    # 첫 번째 청크 (0-9,999)
├── tickets_chunk_0001.json    # 두 번째 청크 (10,000-19,999)
├── ...
└── 기타 파일 (대규모 수집과 동일)
```

## 예상 소요 시간

| 티켓 수 | 기본 정보만 | 대화내역 포함 | 필요 디스크 공간 |
|---------|------------|--------------|----------------|
| 100건 | 5-10분 | 10-15분 | 10MB |
| 1만건 | 1-2시간 | 2-4시간 | 200-500MB |
| 10만건 | 8-10시간 | 16-20시간 | 2-5GB |
| 500만건 | 2-3주 | 3-4주 | 100-150GB |
| 1000만건 | 1-2개월 | 2-3개월 | 200-300GB |

* 네트워크 상태, 서버 응답 시간에 따라 달라질 수 있음

## 주의사항

1. **장기간 실행 필요**: 백그라운드에서 실행하고 정기적으로 모니터링
2. **충분한 디스크 공간**: 최소 티켓 수 * 20KB + 여유 공간
3. **네트워크 안정성**: 유선 네트워크 환경 권장
4. **정기적 백업**: 수집된 청크 파일 주기적 백업 권장
5. **API 키 보안**: .env 파일 사용, 버전 관리에서 제외
6. **Freshdesk 플랜 확인**: Rate limit은 플랜에 따라 다름
7. **법적 준수**: 데이터 사용 목적과 개인정보 처리 방침 확인

## 문제 해결

### 메모리 부족
- `large_scale_config.py`에서 `CHUNK_SIZE`를 더 낮게 조정 (예: 2000)
- 서버 메모리 증설 고려

### 디스크 공간 부족
- 기존 청크 백업 후 이동/삭제
- 필요 시 수집 일시 중단 후 디스크 공간 확보

### 네트워크 문제
- `REQUEST_DELAY` 값 증가 (예: 1.0초)
- 안정적인 네트워크 환경으로 변경

### Rate Limit 오류
```
HTTP 429 Too Many Requests
```
- **해결**: REQUEST_DELAY 값을 늘리거나 (0.5초 이상)
- **자동 재시도**: 코드에서 Retry-After 헤더 기반 대기

## FAQ

**Q: 중간에 중단된 수집을 재개할 수 있나요?**
A: 네, `progress.json` 파일을 통해 자동으로 재개됩니다. 메뉴에서 '3. 중단된 수집 재개' 옵션을 선택하거나 같은 스크립트를 다시 실행하세요.

**Q: 특정 날짜 범위만 수집할 수 있나요?**
A: `start_date`와 `end_date` 파라미터로 지정 가능합니다.

**Q: 메모리 사용량을 더 줄일 수 있나요?**
A: `CHUNK_SIZE`를 줄이고, conversations/attachments 수집을 비활성화하세요.

**Q: 500만건 이상 수집 시 주의사항은?**
A: 충분한 디스크 공간(최소 100GB), 안정적인 네트워크 환경, 장기간 실행 모니터링이 필요합니다.

**Q: 더 빠르게 수집할 수 있나요?**
A: Rate limit 범위 내에서 `REQUEST_DELAY`를 줄이거나, 병렬 처리를 구현하세요.
