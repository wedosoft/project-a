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

# Raw 데이터도 함께 수집하기 (임베딩 실패 시 재수집 방지)
./scripts/run_full_collection.sh --raw-all

# 진행 상황 모니터링
./scripts/monitor_collection.sh -w
```

#### B. 직접 실행
```bash
# 기본 실행
python run_collection.py
# 메뉴에서 '1. 전체 수집 (무제한)' 선택

# 명령행 옵션으로 직접 실행 (Raw 데이터 수집 포함)
python run_collection.py --full-collection --raw-all

# 티켓 상세정보만 Raw 데이터로 수집
python run_collection.py --full-collection --raw-details

# 대화내역만 Raw 데이터로 수집
python run_collection.py --full-collection --raw-conversations

# 지식베이스만 Raw 데이터로 수집
python run_collection.py --full-collection --raw-kb
```

#### C. 기존 티켓 데이터에서 Raw 데이터만 추가 수집
```python
# 이미 수집된 티켓 기본정보를 사용하여 raw 데이터만 추가 수집
from freshdesk.optimized_fetcher import collect_only_raw_data
import asyncio

# 실행
asyncio.run(collect_only_raw_data())
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

#### 명령행 테스트 옵션
```bash
# 기본 테스트 (티켓 100건, 지식베이스 100건)
python run_collection.py --quick-test

# Raw 데이터도 함께 수집 (티켓 100건, 지식베이스 100건)
python run_collection.py --quick-test --raw-all
```

> 참고: 테스트 수집은 티켓 100건과 지식베이스 100건으로 제한하여 빠르게 전체 워크플로우를 테스트합니다.

## 주요 최적화 전략

### 1. 날짜 기반 분할 수집
- **문제**: Freshdesk API는 기본적으로 최대 30,000개 티켓만 반환 (300페이지 × 100개)
- **해결책**: 
  - 날짜 범위를 더 작은 단위로 분할하여 `updated_since` 파라미터 활용
  - 대규모 수집 시 14일 단위 권장 (500만건 이상)
  - 초대규모 수집 시 7일 단위 권장 (1000만건 이상)

### 2. 메모리 사용량 최적화
- **청크 크기 축소**: 5,000개 단위로 저장하여 메모리 사용량 감소
- **주기적인 메모리 모니터링**: 80% 이상 사용 시 경고 및 조치

### 3. 디스크 공간 관리
- **최소 필요 공간**: 
  - 10만건: 약 2-5GB (대화내역 포함 시)
  - 500만건: 약 100GB 이상 권장
- **자동 디스크 체크**: 90% 이상 사용 시 수집 일시 중단

### 4. 자동 복구 메커니즘
- **진행 상황 상세 저장**: 각 날짜 범위별 진행 정보 저장
- **날짜 기반 분할**: 30/14/7일 단위로 분할하여 개별 처리
- **중단 지점 재개**: 오류 발생 시 중단된 날짜 범위부터 재개
- **실패 범위 추적**: 오류 발생 날짜 범위 별도 기록하여 나중에 재시도 가능

### 5. 네트워크 안정성
- **적응형 요청 간격**: 
  - 서버 응답에 따라 자동으로 요청 속도 조절
  - Rate limit 발생 시 점진적으로 속도 감소
  - 정상 응답 시 서서히 원래 속도로 복귀
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
├── summary_report.json         # 요약 리포트
└── raw_data/                   # 원본 데이터 저장 디렉토리 (선택사항)
    ├── ticket_details/         # 티켓 상세정보 원본 데이터
    │   ├── chunk_0000.json     # 티켓 상세정보 청크
    │   └── ...
    ├── conversations/          # 티켓 대화내역 원본 데이터
    │   ├── chunk_0000.json     # 대화내역 청크
    │   └── ...
    └── knowledge_base/         # 지식베이스 원본 데이터
        ├── chunk_0000.json     # 지식베이스 청크
        └── ...
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
A: 충분한 디스크 공간(최소 100GB), 안정적인 네트워크 환경, 장기간 실행 모니터링이 필요합니다. 또한 `days_per_chunk`를 14일 또는 7일로 설정하세요.

**Q: 더 빠르게 수집할 수 있나요?**
A: `adaptive_rate=True` 설정을 사용하면 서버 응답에 따라 자동으로 최적의 속도를 찾습니다. Rate limit이 없는 환경에서는 자연스럽게 더 빠른 속도로 수집합니다.

**Q: 수집이 너무 느린데 이유는 무엇인가요?**
A: 다음을 확인하세요:
   1. Rate limiting (429 응답) - 로그에서 확인 가능
   2. 네트워크 안정성 - 유선 연결 권장
   3. Freshdesk 서버 응답 시간 - 피크 시간 피하기
   4. 대화내역과 첨부파일 수집 - 비활성화하면 빨라짐

**Q: Raw 데이터 수집은 무엇이고 왜 필요한가요?**
A: Raw 데이터 수집은 티켓 상세정보, 대화내역, 지식베이스의 원본 데이터를 JSON 형태로 저장합니다. 임베딩 처리 실패 시 원본 데이터 재수집 없이 다시 시도할 수 있습니다. 대용량 데이터에서는 특히 유용합니다.

**Q: Raw 데이터 수집은 저장 공간이 얼마나 더 필요한가요?**
A: 원본 데이터의 크기에 따라 다르지만, 일반적으로 기본 수집 크기의 2-3배 정도의 추가 저장 공간이 필요합니다. 전체 500만 티켓에서는 약 200-300GB 추가 공간이 필요할 수 있습니다.

**Q: 이미 수집된 티켓에 대해 나중에 Raw 데이터만 수집할 수 있나요?**
A: 네, `collect_only_raw_data()` 함수를 사용하여 이미 수집된 티켓 기본정보를 바탕으로 Raw 데이터만 추가로 수집할 수 있습니다.

## 첨부파일/이미지 저장 정책
- 벡터DB에는 pre-signed URL(attachment_url)을 저장하지 않고, attachment_id, name, content_type, size, updated_at 등 메타데이터만 저장합니다.
- 프론트엔드에서 이미지를 표시할 때마다 Freshdesk API로 최신 pre-signed URL을 발급받아야 합니다.
- description(HTML) 내 인라인 이미지도 URL이 아닌 id 등만 별도 필드에 저장하며, 실제 URL은 표시 시점에 발급받아야 합니다.
