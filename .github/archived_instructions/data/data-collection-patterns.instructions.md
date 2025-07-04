---
applyTo: "**"
---

# 📊 데이터 수집 패턴 & 멀티플랫폼 통합 지침서

_AI 참조 최적화 버전 - 플랫폼별 데이터 수집 및 통합 전략 (2025-06-22 실전 경험 반영)_

## 🎯 데이터 수집 목표

**Freshdesk 전용 고객 지원 데이터의 효율적 수집 및 통합**

- **Freshdesk 전용**: Freshdesk 플랫폼에 특화된 최적화된 수집
- **멀티테넌트 격리**: company_id 기반 완전한 데이터 분리
- **Rate Limit 대응**: Freshdesk API 제한 준수 및 청크 처리
- **중단/재개 지원**: 진행 상황 추적을 통한 안정적 수집

---

## 🚀 **TL;DR - 핵심 데이터 수집 요약**

### 🚨 **실전에서 검증된 핵심 교훈 (2025-06-22)**

**API 엔드포인트 선택**:
- ✅ `/ingest` → **즉시 실행** (테스트, 소량 데이터)
- ✅ `/ingest/jobs` → **백그라운드 실행** (대량 데이터, 스케줄링)
- ⚠️ **혼동 금지**: 목적에 맞는 엔드포인트 사용 필수

### 💡 **즉시 참조용 핵심 포인트**

**데이터 수집 흐름**:
```
API 엔드포인트 선택 → 플랫폼 API 연결 → Rate Limit 제어 → 데이터 검증 → company_id 태깅 → 중복 제거 → 즉시 저장 → 진행 추적
```

**핵심 수집 패턴**:
- **엔드포인트 구분**: 용도별 올바른 API 엔드포인트 선택
- **즉시 저장**: store_immediately=True로 데이터 손실 방지
- **청크 단위 처리**: Rate Limit 대응을 위한 배치 수집
- **자동 태깅**: company_id, platform, collected_at 필수 추가
- **중복 감지**: 플랫폼별 고유 ID 기반 중복 제거
- **진행 추적**: JSON 기반 중단/재개 지원

**멀티테넌트 데이터 격리**:
- **domain 추출**: `wedosoft.freshdesk.com` → `"wedosoft"`
- **필수 태깅**: 모든 데이터에 company_id 필수
- **테넌트별 저장**: 회사별 DB 파일 분리 (`sqlite_dbs/company_id.db`)

### 🚨 **데이터 수집 주의사항**

- ⚠️ **API 엔드포인트 혼동 금지** → `/ingest` vs `/ingest/jobs` 용도 구분 필수
- ⚠️ company_id 없는 데이터 절대 금지 → 모든 수집 데이터에 테넌트 ID 필수
- ⚠️ Rate Limit 위반 금지 → 플랫폼별 제한 준수 필수
- ⚠️ 플랫폼별 하드코딩 금지 → 어댑터 패턴으로 확장성 확보
- ⚠️ **즉시 저장 누락 금지** → 모든 수집 데이터는 store_immediately=True

---

## 🔗 **플랫폼 어댑터 패턴 (AI 구현 필수)**

### ✅ **어댑터 구현 체크리스트**

**공통 인터페이스**:
- [x] `fetch_tickets()` - 티켓 목록 수집
- [x] `fetch_conversations()` - 대화 내용 수집  
- [x] `fetch_attachments()` - 첨부파일 메타데이터 수집
- [x] `get_rate_limits()` - 플랫폼별 제한 정보 제공

**Freshdesk 어댑터** (기준 구현):
```python
class FreshdeskAdapter:
    def __init__(self, company_id: str, api_key: str):
        self.company_id = company_id
        self.base_url = f"https://{company_id}.freshdesk.com"
        self.headers = {'Authorization': f'Basic {api_key}'}
        self.rate_limit = {'requests_per_minute': 1000, 'delay': 0.06}
    
    async def fetch_tickets_chunked(
        self, 
        start_date: str, 
        end_date: str, 
        chunk_size: int = 100
    ):
        """Rate Limit 대응 청크 단위 티켓 수집"""
        page = 1
        
        while True:
            # Rate Limit 준수
            await asyncio.sleep(self.rate_limit['delay'])
            
            # API 호출
            url = f"{self.base_url}/api/v2/tickets"
            params = {
                'updated_since': start_date,
                'per_page': chunk_size,
                'page': page,
                'include': 'conversations,requester'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers, params=params) as response:
                    if response.status == 429:  # Rate Limit
                        await asyncio.sleep(60)  # 1분 대기
                        continue
                    
                    data = await response.json()
                    tickets = data.get('tickets', [])
                    
                    if not tickets:
                        break
                    
                    # company_id 자동 태깅
                    for ticket in tickets:
                        ticket['company_id'] = self.company_id
                        ticket['platform'] = 'freshdesk'
                        ticket['collected_at'] = datetime.utcnow().isoformat()
                    
                    yield tickets
                    page += 1
```

```python
    def __init__(self, company_id: str, api_token: str):
        self.company_id = company_id
        self.headers = {'Authorization': f'Bearer {api_token}'}
        self.rate_limit = {'requests_per_minute': 700, 'delay': 0.086}
    
    async def fetch_tickets_chunked(
        self, 
        start_date: str, 
        end_date: str, 
        chunk_size: int = 100
    ):
        pass
```

### 🏭 **어댑터 팩토리 패턴**

```python
class PlatformAdapterFactory:
    @staticmethod
    def create_adapter(platform: str, company_id: str, credentials: dict):
        """플랫폼별 어댑터 생성"""
        if platform.lower() == 'freshdesk':
            return FreshdeskAdapter(
                company_id=company_id,
                api_key=credentials['api_key']
            )
                company_id=company_id,
                api_token=credentials['api_token']
            )
        elif platform.lower() == 'servicenow':
            return ServiceNowAdapter(
                company_id=company_id,
                username=credentials['username'],
                password=credentials['password']
            )
        else:
            raise ValueError(f"Unsupported platform: {platform}")
```

---

## 📥 **데이터 수집 핵심 패턴**

### 🔄 **전체 수집 워크플로우**

```python
async def collect_platform_data(
    company_id: str,
    platform: str,
    credentials: dict,
    start_date: str,
    end_date: str,
    chunk_size: int = 100
):
    """
    멀티플랫폼 데이터 수집 표준 패턴
    
    Args:
        company_id: 테넌트 식별자
        credentials: 플랫폼별 인증 정보
        start_date: 수집 시작일
        end_date: 수집 종료일
        chunk_size: 청크 크기 (Rate Limit 대응)
    """
    # 1. 플랫폼별 어댑터 생성
    adapter = PlatformAdapterFactory.create_adapter(platform, company_id, credentials)

    # 2. 진행률 추적 및 중단/재개 지원
    progress_file = f"backend/data/progress/{company_id}/collection_progress.json"
    progress = load_progress(progress_file)

    # 3. Rate Limit 대응 (요청 간격 조절)
    async with AsyncHTTPClient(max_concurrent=5, delay=0.2) as client:
        collected_count = 0
        
        async for chunk in adapter.fetch_tickets_chunked(start_date, end_date, chunk_size):
            # 4. company_id 자동 태깅 (중복 방지)
            for ticket in chunk:
                if 'company_id' not in ticket:
                    ticket['company_id'] = company_id
                if 'platform' not in ticket:
                    ticket['platform'] = platform
                if 'collected_at' not in ticket:
                    ticket['collected_at'] = datetime.utcnow().isoformat()

            # 5. 중복 감지 및 저장
            unique_tickets = await filter_duplicates(company_id, platform, chunk)
            await save_unique_tickets(company_id, platform, unique_tickets)
            
            collected_count += len(unique_tickets)

            # 6. 진행 상황 업데이트
            await update_progress(progress_file, {
                'collected_count': collected_count,
                'last_processed': chunk[-1].get('updated_at') if chunk else None,
                'status': 'in_progress'
            })
            
            # 로깅
            logger.info(f"Collected {len(unique_tickets)} unique tickets for {company_id}/{platform}")

    # 7. 수집 완료 처리
    await update_progress(progress_file, {'status': 'completed'})
    logger.info(f"Collection completed: {collected_count} tickets for {company_id}/{platform}")
```

### 🔍 **중복 감지 및 필터링**

```python
async def filter_duplicates(
    company_id: str, 
    platform: str, 
    new_tickets: List[Dict]
) -> List[Dict]:
    """플랫폼별 고유 ID 기반 중복 제거"""
    
    # 1. 기존 저장된 티켓 ID 조회
    existing_ids = await get_existing_ticket_ids(company_id, platform)
    
    # 2. 플랫폼별 고유 ID 필드 매핑
    id_field_map = {
        'freshdesk': 'id',
        'servicenow': 'sys_id'
    }
    
    id_field = id_field_map.get(platform, 'id')
    
    # 3. 중복 제거
    unique_tickets = []
    for ticket in new_tickets:
        ticket_id = str(ticket.get(id_field))
        composite_key = f"{platform}_{ticket_id}"
        
        if composite_key not in existing_ids:
            unique_tickets.append(ticket)
    
    return unique_tickets
```

---

## 📊 **진행 상황 추적 & 재개**

### 💾 **진행 상황 저장 패턴**

```python
async def save_collection_progress(
    company_id: str,
    platform: str,
    progress_data: dict
):
    """진행 상황 JSON 파일 저장"""
    progress_dir = f"backend/data/progress/{company_id}"
    os.makedirs(progress_dir, exist_ok=True)
    
    progress_file = f"{progress_dir}/{platform}_progress.json"
    
    progress_data.update({
        'company_id': company_id,
        'platform': platform,
        'updated_at': datetime.utcnow().isoformat()
    })
    
    with open(progress_file, 'w') as f:
        json.dump(progress_data, f, indent=2)

async def load_collection_progress(company_id: str, platform: str) -> dict:
    """진행 상황 로드 및 재개 지점 확인"""
    progress_file = f"backend/data/progress/{company_id}/{platform}_progress.json"
    
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    
    # 초기 진행 상황
    return {
        'status': 'not_started',
        'collected_count': 0,
        'last_processed': None,
        'created_at': datetime.utcnow().isoformat()
    }
```

### 🔄 **중단/재개 지원**

```python
async def resume_collection(company_id: str, platform: str):
    """중단된 수집 작업 재개"""
    
    # 1. 이전 진행 상황 로드
    progress = await load_collection_progress(company_id, platform)
    
    if progress['status'] != 'in_progress':
        logger.info(f"No collection to resume for {company_id}/{platform}")
        return
    
    # 2. 재개 지점 계산
    last_processed = progress.get('last_processed')
    start_date = last_processed if last_processed else datetime.now() - timedelta(days=30)
    
    # 3. 수집 재개
    await collect_platform_data(
        company_id=company_id,
        platform=platform,
        start_date=start_date.isoformat(),
        end_date=datetime.utcnow().isoformat()
    )
```

---

## 🔧 **데이터 검증 & 정제**

### ✅ **필수 검증 체크리스트**

**데이터 무결성 검증**:
- [x] company_id 필수 존재 확인
- [x] platform 필드 정규화
- [x] 날짜 필드 ISO 8601 형식 변환
- [x] 필수 필드 존재 확인

```python
def validate_ticket_data(ticket: dict, platform: str) -> bool:
    """티켓 데이터 유효성 검증"""
    
    # 1. 필수 필드 확인
    required_fields = ['id', 'subject', 'status', 'created_at']
    platform_specific_fields = {
        'freshdesk': ['requester_id', 'description'],
        'servicenow': ['caller_id', 'short_description']
    }
    
    all_required = required_fields + platform_specific_fields.get(platform, [])
    
    for field in all_required:
        if field not in ticket or ticket[field] is None:
            logger.warning(f"Missing required field '{field}' in ticket {ticket.get('id')}")
            return False
    
    # 2. company_id 필수 확인
    if not ticket.get('company_id'):
        logger.error(f"Missing company_id in ticket {ticket.get('id')}")
        return False
    
    # 3. 날짜 형식 검증
    date_fields = ['created_at', 'updated_at']
    for field in date_fields:
        if field in ticket:
            try:
                datetime.fromisoformat(ticket[field].replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Invalid date format for '{field}' in ticket {ticket.get('id')}")
                return False
    
    return True

def normalize_ticket_data(ticket: dict, platform: str) -> dict:
    """플랫폼별 데이터 정규화"""
    
    # 1. 공통 필드 매핑
    normalized = {
        'platform_id': str(ticket['id']),
        'platform': platform,
        'company_id': ticket['company_id'],
        'subject': ticket.get('subject', ''),
        'status': ticket.get('status', '').lower(),
        'priority': ticket.get('priority', '').lower(),
        'created_at': ticket.get('created_at'),
        'updated_at': ticket.get('updated_at'),
        'collected_at': ticket.get('collected_at', datetime.utcnow().isoformat())
    }
    
    # 2. 플랫폼별 특수 처리
    if platform == 'freshdesk':
        normalized.update({
            'description': ticket.get('description', ''),
            'requester_id': ticket.get('requester_id'),
            'tags': ticket.get('tags', [])
        })
        normalized.update({
            'description': ticket.get('description', ''),
            'submitter_id': ticket.get('submitter_id'),
            'tags': ticket.get('tags', [])
        })
    elif platform == 'servicenow':
        normalized.update({
            'description': ticket.get('short_description', ''),
            'caller_id': ticket.get('caller_id'),
            'category': ticket.get('category', '')
        })
    
    # 3. 원본 데이터 보존
    normalized['original_data'] = ticket
    
    return normalized
```

---

## 📚 **관련 참조 지침서**

- **data-processing-llm.instructions.md** - LLM 요약 및 처리 패턴
- **vector-storage-search.instructions.md** - 벡터 저장 및 검색 전략
- **multitenant-security.instructions.md** - 멀티테넌트 보안 및 격리
- **global.instructions.md** - 전역 개발 원칙 및 파일 관리
- **quick-reference.instructions.md** - 핵심 패턴 즉시 참조

---

## 🔗 **크로스 참조**

이 지침서는 다음과 연계됩니다:
- **LLM 처리**: 수집된 데이터의 요약 및 구조화
- **벡터 검색**: 처리된 데이터의 임베딩 및 검색
- **멀티테넌트**: company_id 기반 데이터 격리 전략
- **에러 처리**: 수집 과정의 예외 상황 대응

**세션 간 일관성**: 이 패턴들은 AI 세션이 바뀌어도 동일하게 적용되어야 합니다.
