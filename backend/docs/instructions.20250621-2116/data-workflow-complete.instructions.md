---
applyTo: "**"
---

# 📊 데이터 워크플로우 통합 지침서

_AI 참조 최적화 버전 - 분할된 지침서들의 통합 인덱스_

## 🎯 데이터 워크플로우 개요

**Freshdesk 기반 RAG 시스템의 전체 데이터 파이프라인 참조 가이드**

이 지침서는 세부 구현을 각 전문 지침서로 분할하고, 전체 워크플로우의 인덱스 역할을 합니다.

---

## ⚡ **TL;DR - 핵심 데이터 파이프라인 요약**

### 💡 **즉시 참조용 워크플로우**

**전체 데이터 흐름**:

```
플랫폼 수집 → 데이터 검증 → 통합 객체 생성 → LLM 요약 → 임베딩 생성 → Vector DB 저장 → 검색/추천 → 피드백 루프
```

**핵심 구성 요소**:

1. **[데이터 수집](data-collection-patterns.instructions.md)**: 플랫폼별 티켓/KB 수집
2. **[LLM 처리](data-processing-llm.instructions.md)**: 구조화된 요약 생성
3. **[벡터 저장](vector-storage-search.instructions.md)**: Qdrant 기반 임베딩 관리
4. **[플랫폼 어댑터](platform-adapters-multiplatform.instructions.md)**: 멀티플랫폼 확장
5. **[스토리지 추상화](storage-abstraction-database.instructions.md)**: 파일→DB 전환
6. **[멀티테넌트 보안](multitenant-security.instructions.md)**: company_id 기반 격리

### 🚨 **데이터 워크플로우 핵심 원칙**

- ⚠️ **company_id 필수**: 모든 데이터에 테넌트 식별자 자동 태깅
- ⚠️ **비용 최적화**: LLM 호출 최소화 (필터링 + 캐싱 + 배치)
- ⚠️ **기존 로직 재활용**: 검증된 파이프라인 90% 이상 유지

---

## ⚠️ **데이터 처리 철칙 (AI 세션 간 일관성 핵심)**

### 🔄 **기존 데이터 파이프라인 재활용 원칙**

**목적**: 세션이 바뀌어도 동일한 데이터 처리 패턴 유지

- **기존 처리 로직 90% 이상 재활용**: 새로운 데이터 처리 방식 임의 변경 금지
- **검증된 워크플로우 보존**: 안정적으로 작동하던 수집/처리/저장 패턴 유지
- **점진적 최적화**: 전면 재설계 대신 기존 파이프라인 개선
- **데이터 일관성**: 기존 데이터 스키마와 호환성 유지

### 📋 **AI 데이터 작업 시 필수 체크포인트**

1. **company_id 자동 태깅**: 모든 데이터에 테넌트 식별자 필수 포함
2. **플랫폼 추상화**: Freshdesk 중심이지만 다른 플랫폼 확장 가능하게
3. **비용 최적화**: LLM 호출 최소화 (필터링 + 캐싱 + 배치)
4. **데이터 격리**: 테넌트 간 데이터 누출 방지

---

## 💾 **데이터베이스 전략 (AI 구현 필수 체크리스트)**

### ✅ **MVP → 프로덕션 전환 체크리스트**

**MVP 현재 상태** (파일 기반):

- [x] **Vector DB**: Qdrant Cloud (단일 `documents` 컬렉션)
- [x] **App Data**: JSON 파일 저장 (`backend/data/`)
- [x] **Progress**: JSON 기반 진행 상황 추적
- [x] **Cache**: 메모리 기반 (개발용)

**프로덕션 마이그레이션 필수 단계**:

- [ ] **PostgreSQL**: Row-level Security 기반 멀티테넌트 격리
- [ ] **Redis Cluster**: 캐싱 계층 고가용성
- [ ] **AWS Secrets**: API 키 중앙화 관리
- [ ] **Qdrant**: 단일 컬렉션 내 테넌트/플랫폼별 필터링 최적화

### �️ **데이터 저장 구조 핵심 패턴**

**MVP 파일 구조** (현재):

```
backend/data/
├── raw/                    # 원본 데이터 (company_id별 분리)
│   └── {company_id}/
│       ├── tickets/        # 병합된 티켓 JSON
│       └── kb/             # 지식베이스 문서
├── processed/              # LLM 요약된 데이터
│   └── {company_id}/
│       ├── tickets/        # 요약된 티켓 데이터
│       └── kb/             # 요약된 KB 데이터
├── embeddings/             # 생성된 임베딩
│   └── {company_id}/
│       ├── tickets/        # 티켓 임베딩
│       └── kb/             # KB 임베딩
└── progress/               # 진행 상황 추적
    └── {company_id}/
        ├── progress.json   # 전체 진행 상황
        ├── collection.log  # 수집 로그
        └── processing.log  # 처리 로그
```

**프로덕션 PostgreSQL 스키마** (목표):

```sql
-- 멀티플랫폼/멀티테넌트 티켓 테이블
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    ticket_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed_data JSONB,
    summary JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform, ticket_id)
);

-- Row-level Security (테넌트 격리)
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY tickets_company_isolation ON tickets
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));
```

### ⚠️ **데이터베이스 주의사항**

- 🚨 **company_id 필수**: 모든 테이블에 테넌트 식별자 포함
- 🚨 **플랫폼 구분**: 멀티플랫폼 지원을 위한 platform 컬럼 필수
- 🚨 **점진적 마이그레이션**: JSON → PostgreSQL 데이터 손실 방지
- 🚨 **성능 최적화**: company_id + platform 복합 인덱스 필수

---

## 🔧 **핵심 데이터 처리 단계 (AI 구현 필수 체크리스트)**

### ✅ **데이터 수집 필수 구현 체크리스트**

**플랫폼 데이터 수집 (Freshdesk API)**:

- [x] 티켓 + 대화 + 첨부파일 **하나로 병합**
- [x] 해시값으로 **중복 감지** 및 스킵
- [x] **청크 단위** 처리 (Rate Limit 대응)
- [x] **company_id 자동 태깅** (도메인 기반 추출)

**에러 처리 및 복구**:

- [x] **재시도 로직**: 지수 백오프 + 최대 3회
- [x] **진행 상황 추적**: JSON 기반 중단/재개 지원
- [x] **메모리 최적화**: 스트리밍 처리로 대용량 데이터 대응

### 🔄 **데이터 수집 핵심 패턴**

**멀티플랫폼 데이터 수집 패턴**:

```python
async def collect_platform_data(
    company_id: str,
    start_date: str,
    end_date: str,
    chunk_size: int = 100
):
    """
    멀티플랫폼 대용량 데이터 수집 (500만건+ 최적화)

    Args:
        company_id: 고객사 ID (테넌트 격리)
        platform: 플랫폼 타입
        start_date: 수집 시작일
        end_date: 수집 종료일
        chunk_size: 청크 크기 (Rate Limit 대응)
    """
    # 1. 플랫폼별 어댑터 생성
    adapter = PlatformAdapterFactory.create_adapter(platform, company_id)

    # 2. 진행률 추적 및 중단/재개 지원
    progress_file = f"backend/data/progress/{company_id}/collection_progress.json"
    progress = load_progress(progress_file)

    # 3. Rate Limit 대응 (요청 간격 조절)
    async with AsyncHTTPClient(max_concurrent=5, delay=0.2) as client:
        async for chunk in adapter.fetch_tickets_chunked(start_date, end_date, chunk_size):
            # 4. company_id 자동 태깅
            for ticket in chunk:
                ticket['company_id'] = company_id
                ticket['platform'] = platform
                ticket['collected_at'] = datetime.utcnow().isoformat()

            # 5. 중복 감지 및 저장
            await save_unique_tickets(company_id, platform, chunk)

            # 6. 진행 상황 업데이트
            await update_progress(progress_file, len(chunk))
```

**데이터 병합 패턴** (티켓+대화+첨부파일):

```python
async def merge_ticket_data(company_id: str, platform: str, ticket_id: str) -> dict:
    """티켓, 대화, 첨부파일을 하나의 문서로 병합"""

    # 1. 기본 티켓 정보
    ticket = await get_ticket_info(company_id, platform, ticket_id)

    # 2. 모든 대화 수집
    conversations = await get_ticket_conversations(company_id, platform, ticket_id)

    # 3. 첨부파일 메타데이터 (내용은 별도 저장)
    attachments = await get_ticket_attachments(company_id, platform, ticket_id)

    # 4. 하나의 통합 문서로 병합
    merged_document = {
        "company_id": company_id,
        "platform": platform,
        "ticket_id": ticket_id,
        "subject": ticket.get("subject", ""),
        "description": ticket.get("description", ""),
        "full_conversation": "\n".join([conv["body"] for conv in conversations]),
        "status": ticket.get("status", ""),
        "priority": ticket.get("priority", ""),
        "tags": ticket.get("tags", []),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "attachments_info": [{"name": att["name"], "size": att["size"]} for att in attachments],
        "original_data": {
            "ticket": ticket,
            "conversations": conversations,
            "attachments": attachments
        }
    }

    return merged_document
```

### ✅ **LLM 요약 처리 필수 구현 체크리스트**

**비용 최적화 전략**:

- [x] **필터링**: 해결되지 않은 티켓 제외
- [x] **배치 처리**: 10개씩 묶어서 LLM 호출
- [x] **캐싱**: Redis 기반 중복 요약 방지
- [x] **병렬 처리**: 여러 LLM 제공자 동시 활용

### 🧠 **LLM 요약 핵심 패턴**

**구조화된 요약 생성 패턴**:

```python
TICKET_SUMMARY_PROMPT = """
당신은 고객 지원 티켓을 분석하는 전문가입니다.
다음 티켓 내용을 분석하여 구조화된 요약을 생성해주세요.

티켓 내용: {ticket_content}

다음 형식으로 요약해주세요:
1. 문제 (Problem): 고객이 겪고 있는 주요 문제
2. 원인 (Cause): 문제의 근본 원인 (파악된 경우)
3. 해결방법 (Solution): 제시된 해결 방법
4. 결과 (Result): 최종 해결 여부 및 결과
5. 태그 (Tags): 관련 키워드 (최대 5개)

JSON 형식으로 응답해주세요:
{{
    "problem": "문제 설명",
    "cause": "원인 설명 (또는 '미파악')",
    "solution": "해결방법 설명",
    "result": "해결 결과",
    "tags": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}
"""

@cache_llm_response(ttl=86400)  # 24시간 캐싱
async def process_tickets_batch(
    company_id: str,
    tickets: List[Dict],
    batch_size: int = 10,
    cost_filter: bool = True
):
    """
    티켓 배치 처리 및 LLM 비용 최적화
    """
    # 1. 비용 필터링 (해결된 티켓만 처리)
    if cost_filter:
        tickets = [t for t in tickets if t.get('status') in ['resolved', 'closed']]

    # 2. 배치 단위로 묶어서 처리
    for i in range(0, len(tickets), batch_size):
        batch = tickets[i:i + batch_size]

        # 3. 병렬 LLM 요청
        tasks = [
            summarize_single_ticket(company_id, ticket)
            for ticket in batch
        ]

        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. 결과 저장 (company_id별 분리)
        await save_ticket_summaries(company_id, summaries)

async def summarize_single_ticket(company_id: str, ticket: dict) -> dict:
    """단일 티켓 요약 (캐싱 적용)"""

    # 캐시 키 생성 (company_id 포함)
    content_hash = hash(ticket["full_conversation"] + ticket["description"])
    cache_key = f"summary:{company_id}:{content_hash}"

    # 캐시 확인
    cached_summary = await redis_client.get(cache_key)
    if cached_summary:
        return orjson.loads(cached_summary)

    # LLM 호출
    response = await llm_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{
            "role": "user",
            "content": TICKET_SUMMARY_PROMPT.format(
                ticket_content=ticket["full_conversation"]
            )
        }],
        temperature=0.1
    )

    summary = orjson.loads(response.choices[0].message.content)

    # 캐시 저장
    await redis_client.setex(cache_key, 86400, orjson.dumps(summary))

    return summary
```

### ⚠️ **데이터 처리 주의사항**

- 🚨 **비용 폭증 방지**: LLM 호출 전 필터링 + 캐싱 필수
- 🚨 **company_id 태깅**: 모든 데이터에 테넌트 식별자 필수
- 🚨 **메모리 관리**: 대용량 데이터는 스트리밍 처리
- 🚨 **에러 복구**: 진행 상황 추적으로 중단 지점에서 재개

---

## 🔍 **벡터 검색 & 저장 (AI 구현 필수 체크리스트)**

### ✅ **벡터 처리 필수 구현 체크리스트**

**비용 최적화 전략**:

- [x] **요약 텍스트만** 임베딩 (원본은 메타데이터로만 저장)
- [x] **단일 컬렉션** 사용 (Qdrant `documents` 컬렉션)
- [x] **company_id 기반** 격리 (필터링으로 테넌트 분리)
- [x] **플랫폼별 구분** (platform 필드로 멀티플랫폼 지원)

**성능 최적화**:

- [x] **배치 처리**: 임베딩 생성 시 여러 문서 동시 처리
- [x] **캐싱 적용**: 동일한 텍스트 중복 임베딩 방지
- [x] **비동기 처리**: 대용량 데이터 스트리밍 업로드

### 🔄 **벡터 저장 핵심 패턴**

**멀티테넌트 벡터 저장 패턴**:

```python
async def store_embeddings(
    company_id: str,
    embeddings: List[List[float]],
    metadata: List[Dict],
    data_type: str = "ticket"  # 'ticket' or 'kb'
):
    """
    멀티플랫폼/멀티테넌트 벡터 저장 (단일 컬렉션 사용)
    """
    collection_name = "documents"  # 단일 컬렉션 사용

    # 1. Qdrant 컬렉션 생성 (최초 1회만)
    try:
        await qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=1536,  # OpenAI text-embedding-3-small
                distance=Distance.COSINE
            )
        )
    except Exception:
        # 이미 컬렉션이 존재하는 경우 무시
        pass

    # 2. 벡터 포인트 생성 (테넌트/플랫폼 정보 포함)
    points = []
    for i, embedding in enumerate(embeddings):
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                # 멀티테넌트 필수 필드
                "company_id": company_id,
                "platform": platform,
                "data_type": data_type,

                # 검색 최적화 복합 키
                "tenant_key": f"{company_id}_{platform}_{data_type}",

                # 비즈니스 데이터
                "item_id": metadata[i].get("ticket_id") or metadata[i].get("kb_id"),
                "summary": metadata[i].get("summary", {}),
                "tags": metadata[i].get("tags", []),
                "status": metadata[i].get("status", ""),
                "priority": metadata[i].get("priority", ""),

                # 메타데이터 (원본 데이터 포함)
                "original_data": metadata[i].get("original_data", {}),
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        )
        points.append(point)

    # 3. 배치 업로드 (성능 최적화)
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        await qdrant_client.upsert(
            collection_name=collection_name,
            points=batch
        )

        # 진행 상황 로깅
        logger.info(f"Uploaded batch {i//batch_size + 1}/{len(points)//batch_size + 1} for {company_id}/{platform}")
```

**멀티테넌트 벡터 검색 패턴**:

```python
async def search_similar_content(
    company_id: str,
    platform: str,
    query_text: str,
    data_type: str = "ticket",
    limit: int = 10,
    score_threshold: float = 0.7
) -> List[Dict]:
    """
    테넌트/플랫폼별 격리된 벡터 검색
    """
    # 1. 쿼리 임베딩 생성
    query_embedding = await generate_embedding(query_text)

    # 2. 멀티테넌트 필터 설정
    search_filter = Filter(
        must=[
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            ),
            FieldCondition(
                key="platform",
                match=MatchValue(value=platform)
            ),
            FieldCondition(
                key="data_type",
                match=MatchValue(value=data_type)
            )
        ]
    )

    # 3. 벡터 검색 실행
    search_result = await qdrant_client.search(
        collection_name="documents",
        query_vector=query_embedding,
        query_filter=search_filter,
        limit=limit,
        score_threshold=score_threshold
    )

    # 4. 결과 후처리
    results = []
    for scored_point in search_result:
        result = {
            "id": scored_point.id,
            "score": scored_point.score,
            "summary": scored_point.payload.get("summary", {}),
            "tags": scored_point.payload.get("tags", []),
            "item_id": scored_point.payload.get("item_id"),
            "created_at": scored_point.payload.get("created_at")
        }
        results.append(result)

    return results

# 멀티플랫폼 통합 검색 (선택적)
async def search_across_platforms(
    company_id: str,
    query_text: str,
    platforms: List[str] = None,
    data_type: str = "ticket"
) -> List[Dict]:
    """여러 플랫폼에서 통합 검색 (동일 테넌트 내에서만)"""


    # 동일 company_id 내에서 여러 플랫폼 검색
    search_filter = Filter(
        must=[
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            ),
            FieldCondition(
                key="platform",
                match=MatchAny(any=platform_filter)
            ),
            FieldCondition(
                key="data_type",
                match=MatchValue(value=data_type)
            )
        ]
    )

    query_embedding = await generate_embedding(query_text)

    search_result = await qdrant_client.search(
        collection_name="documents",
        query_vector=query_embedding,
        query_filter=search_filter,
        limit=20  # 멀티플랫폼이므로 더 많은 결과
    )

    # 플랫폼별 그룹화 및 정렬
    platform_results = {}
    for scored_point in search_result:
        platform = scored_point.payload["platform"]
        if platform not in platform_results:
            platform_results[platform] = []
        platform_results[platform].append({
            "score": scored_point.score,
            "platform": platform,
            "summary": scored_point.payload.get("summary", {}),
            "item_id": scored_point.payload.get("item_id")
        })

    return platform_results
```

### ⚠️ **벡터 처리 주의사항**

- 🚨 **테넌트 격리 필수**: 모든 검색에 company_id 필터 적용
- 🚨 **비용 최적화**: 요약 텍스트만 임베딩, 원본은 메타데이터
- 🚨 **성능 고려**: 배치 처리로 대용량 데이터 효율적 처리
- 🚨 **플랫폼 구분**: 멀티플랫폼 지원을 위한 platform 필드 필수

---

## 🎨 **추상화 레이어 설계 (AI 구현 필수 체크리스트)**

### ✅ **스토리지 추상화 필수 구현 체크리스트**

**추상화 레이어 장점**:

- [x] **저장소 변경 용이**: 파일 → DB 전환 시 비즈니스 로직 불변
- [x] **테스트 편의성**: 인터페이스 기반 모킹 가능
- [x] **환경별 구현**: 개발(파일) → 프로덕션(PostgreSQL) 동적 전환

**구현 전략**:

```
인터페이스 정의 → 파일 구현 → PostgreSQL 구현 → 환경변수로 전환
```

### 🔄 **스토리지 인터페이스 핵심 패턴**

**추상화 인터페이스 정의**:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class StorageInterface(ABC):
    """데이터 저장소 추상화 인터페이스 (멀티플랫폼/멀티테넌트 지원)"""

    @abstractmethod
    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """티켓 데이터 저장"""
        pass

    @abstractmethod
    async def get_ticket(self, company_id: str, platform: str, ticket_id: str) -> Optional[Dict]:
        """티켓 데이터 조회"""
        pass

    @abstractmethod
    async def list_tickets(
        self,
        company_id: str,
        platform: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """티켓 목록 조회 (필터 지원)"""
        pass

    @abstractmethod
    async def update_processing_status(
        self,
        company_id: str,
        platform: str,
        ticket_id: str,
        status: str
    ) -> bool:
        """처리 상태 업데이트"""
        pass

    @abstractmethod
    async def save_summary(
        self,
        company_id: str,
        platform: str,
        item_id: str,
        summary_data: Dict
    ) -> bool:
        """LLM 요약 결과 저장"""
        pass

    @abstractmethod
    async def get_processing_progress(
        self,
        company_id: str,
        platform: str
    ) -> Dict:
        """처리 진행 상황 조회"""
        pass
```

**파일 기반 구현 (MVP)**:

```python
import orjson
from pathlib import Path
import aiofiles

class FileStorage(StorageInterface):
    """파일 기반 스토리지 (개발/테스트용)"""

    def __init__(self, base_path: str = "backend/data"):
        self.base_path = Path(base_path)
        # company_id별 디렉터리 구조 생성
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_company_path(self, company_id: str, platform: str) -> Path:
        """company_id + platform별 경로 생성"""
        return self.base_path / company_id / platform

    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """티켓 데이터를 JSON 파일로 저장"""
        company_path = self._get_company_path(company_id, platform)
        company_path.mkdir(parents=True, exist_ok=True)

        ticket_id = ticket_data.get("ticket_id")
        file_path = company_path / "tickets" / f"{ticket_id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # company_id와 platform 자동 태깅
        ticket_data.update({
            "company_id": company_id,
            "platform": platform,
            "saved_at": datetime.utcnow().isoformat()
        })

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(orjson.dumps(ticket_data, option=orjson.OPT_INDENT_2))

        return str(file_path)

    async def get_ticket(self, company_id: str, platform: str, ticket_id: str) -> Optional[Dict]:
        """티켓 데이터 조회"""
        file_path = self._get_company_path(company_id, platform) / "tickets" / f"{ticket_id}.json"

        if not file_path.exists():
            return None

        async with aiofiles.open(file_path, 'rb') as f:
            data = await f.read()
            return orjson.loads(data)

    async def list_tickets(
        self,
        company_id: str,
        platform: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """티켓 목록 조회 (필터링 지원)"""
        tickets = []

        if platform:
            platforms = [platform]
        else:
            # 모든 플랫폼에서 검색
            company_path = self.base_path / company_id
            platforms = [p.name for p in company_path.iterdir() if p.is_dir()]

        for plt in platforms:
            tickets_path = self._get_company_path(company_id, plt) / "tickets"
            if not tickets_path.exists():
                continue

            for file_path in tickets_path.glob("*.json"):
                async with aiofiles.open(file_path, 'rb') as f:
                    data = await f.read()
                    ticket = orjson.loads(data)

                    # 상태 필터링
                    if status and ticket.get("status") != status:
                        continue

                    tickets.append(ticket)

        # 페이지네이션
        return tickets[offset:offset + limit]
```

**PostgreSQL 구현 (프로덕션)**:

```python
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

class PostgresStorage(StorageInterface):
    """PostgreSQL 기반 스토리지 (프로덕션용)"""

    def __init__(self, connection_string: str):
        self.engine = create_async_engine(connection_string)

    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """PostgreSQL 데이터베이스에 티켓 저장"""
        async with AsyncSession(self.engine) as session:
            # Row-level Security를 위한 컨텍스트 설정
            await session.execute(
                text("SET app.current_company_id = :company_id"),
                {"company_id": company_id}
            )

            # 티켓 데이터 삽입
            stmt = text("""
                INSERT INTO tickets (company_id, platform, ticket_id, raw_data, status, created_at)
                VALUES (:company_id, :platform, :ticket_id, :raw_data, :status, NOW())
                ON CONFLICT (company_id, platform, ticket_id)
                DO UPDATE SET raw_data = EXCLUDED.raw_data, updated_at = NOW()
                RETURNING id
            """)

            result = await session.execute(stmt, {
                "company_id": company_id,
                "platform": platform,
                "ticket_id": ticket_data.get("ticket_id"),
                "raw_data": orjson.dumps(ticket_data).decode(),
                "status": ticket_data.get("status", "pending")
            })

            await session.commit()
            return str(result.scalar())

    async def list_tickets(
        self,
        company_id: str,
        platform: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """PostgreSQL에서 티켓 목록 조회"""
        async with AsyncSession(self.engine) as session:
            # Row-level Security 컨텍스트 설정
            await session.execute(
                text("SET app.current_company_id = :company_id"),
                {"company_id": company_id}
            )

            # 동적 쿼리 생성
            where_clauses = ["company_id = :company_id"]
            params = {"company_id": company_id, "limit": limit, "offset": offset}

            if platform:
                where_clauses.append("platform = :platform")
                params["platform"] = platform

            if status:
                where_clauses.append("status = :status")
                params["status"] = status

            query = f"""
                SELECT ticket_id, platform, raw_data, processed_data, status, created_at
                FROM tickets
                WHERE {' AND '.join(where_clauses)}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """

            result = await session.execute(text(query), params)

            tickets = []
            for row in result:
                ticket_data = orjson.loads(row.raw_data)
                ticket_data.update({
                    "platform": row.platform,
                    "status": row.status,
                    "created_at": row.created_at.isoformat()
                })
                tickets.append(ticket_data)

            return tickets
```

**스토리지 팩토리 패턴**:

```python
import os
from typing import Union

class StorageFactory:
    """환경에 따른 스토리지 구현 선택"""

    @staticmethod
    def create_storage() -> StorageInterface:
        """환경변수에 따라 적절한 스토리지 구현 반환"""
        storage_type = os.getenv("STORAGE_TYPE", "file")

        if storage_type == "postgresql":
            connection_string = os.getenv("DATABASE_URL")
            if not connection_string:
                raise ValueError("PostgreSQL storage requires DATABASE_URL environment variable")
            return PostgresStorage(connection_string)

        elif storage_type == "file":
            base_path = os.getenv("DATA_PATH", "backend/data")
            return FileStorage(base_path)

        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

# 사용 예시
storage = StorageFactory.create_storage()
await storage.save_ticket("wedosoft", "freshdesk", ticket_data)
```

### ⚠️ **추상화 레이어 주의사항**

- 🚨 **인터페이스 일관성**: 모든 구현체는 동일한 인터페이스 준수 필수
- 🚨 **company_id 필수**: 모든 메서드에 테넌트 식별자 포함
- 🚨 **성능 고려**: 추상화로 인한 성능 저하 최소화
- 🚨 **에러 처리**: 구현체별 에러를 공통 예외로 변환

---

## 🚀 **멀티플랫폼 확장 전략 (AI 구현 필수 체크리스트)**

### ✅ **플랫폼 어댑터 필수 구현 체크리스트**

**MVP 우선순위**:

- [x] **Freshdesk 완전 구현**: 모든 기능 검증 완료
- [x] **기반 구조 확장 설계**: Adapter 패턴 기반 추상화
- [x] **ServiceNow 제거**: 리소스 집중을 위한 범위 축소

**향후 확장 단계**:

- [ ] **ServiceNow 어댑터**: 추후 시장 요구에 따라 확장
- [ ] **Microsoft Teams**: Enterprise 고객 요구 시 추가

### 🔄 **플랫폼 어댑터 핵심 패턴**

**추상화 인터페이스 정의**:

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator

class BasePlatformAdapter(ABC):
    """플랫폼 어댑터 기본 인터페이스"""

    def __init__(self, company_id: str, api_credentials: Dict[str, str]):
        self.company_id = company_id
        self.api_credentials = api_credentials

    @abstractmethod
    async def fetch_tickets(
        self,
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict], None]:
        """티켓 데이터 청크 단위 수집"""
        pass

    @abstractmethod
    async def fetch_knowledge_base(self) -> List[Dict]:
        """지식베이스 수집"""
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환"""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """API 자격증명 검증"""
        pass

    @abstractmethod
    def normalize_ticket_data(self, raw_ticket: Dict) -> Dict:
        """플랫폼별 데이터를 공통 형식으로 정규화"""
        pass
```

**Freshdesk 완전 구현**:

```python
import aiohttp
from typing import AsyncGenerator

class FreshdeskAdapter(BasePlatformAdapter):
    """Freshdesk 완전 구현"""

    def get_platform_name(self) -> str:
        return "freshdesk"

    async def validate_credentials(self) -> bool:
        """Freshdesk API 자격증명 검증"""
        domain = self.api_credentials.get("domain")
        api_key = self.api_credentials.get("api_key")

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(api_key, "X")
            url = f"https://{domain}/api/v2/tickets"

            try:
                async with session.get(url, auth=auth, params={"per_page": 1}) as response:
                    return response.status == 200
            except Exception:
                return False

    async def fetch_tickets(
        self,
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict], None]:
        """Freshdesk 티켓 청크 단위 수집"""
        domain = self.api_credentials.get("domain")
        api_key = self.api_credentials.get("api_key")

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(api_key, "X")
            page = 1

            while True:
                url = f"https://{domain}/api/v2/tickets"
                params = {
                    "updated_since": start_date,
                    "per_page": chunk_size,
                    "page": page
                }

                async with session.get(url, auth=auth, params=params) as response:
                    if response.status != 200:
                        break

                    tickets = await response.json()
                    if not tickets:
                        break

                    # 데이터 정규화 및 company_id 태깅
                    normalized_tickets = []
                    for ticket in tickets:
                        normalized = self.normalize_ticket_data(ticket)
                        normalized.update({
                            "company_id": self.company_id,
                            "platform": self.get_platform_name()
                        })
                        normalized_tickets.append(normalized)

                    yield normalized_tickets
                    page += 1

                    # Rate limiting
                    await asyncio.sleep(0.2)

    def normalize_ticket_data(self, raw_ticket: Dict) -> Dict:
        """Freshdesk 데이터를 공통 형식으로 정규화"""
        return {
            "ticket_id": str(raw_ticket.get("id")),
            "subject": raw_ticket.get("subject", ""),
            "description": raw_ticket.get("description_text", ""),
            "status": raw_ticket.get("status_name", "").lower(),
            "priority": raw_ticket.get("priority_name", "").lower(),
            "requester_email": raw_ticket.get("requester", {}).get("email", ""),
            "agent_email": raw_ticket.get("responder", {}).get("email", ""),
            "tags": raw_ticket.get("tags", []),
            "created_at": raw_ticket.get("created_at"),
            "updated_at": raw_ticket.get("updated_at"),
            "original_data": raw_ticket  # 원본 데이터 보존
        }
```


```python

    def get_platform_name(self) -> str:

    async def validate_credentials(self) -> bool:
        subdomain = self.api_credentials.get("subdomain")
        email = self.api_credentials.get("email")
        api_token = self.api_credentials.get("api_token")

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(f"{email}/token", api_token)

            try:
                async with session.get(url, auth=auth, params={"per_page": 1}) as response:
                    return response.status == 200
            except Exception:
                return False

    async def fetch_tickets(
        self,
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict], None]:

    def normalize_ticket_data(self, raw_ticket: Dict) -> Dict:
```

**플랫폼 어댑터 팩토리**:

```python
class PlatformAdapterFactory:
    """플랫폼별 어댑터 생성 팩토리"""

    _adapters = {
        "freshdesk": FreshdeskAdapter,
        # "servicenow": ServiceNowAdapter,  # 향후 확장
    }

    @classmethod
    def create_adapter(
        cls,
        platform: str,
        company_id: str,
        api_credentials: Dict[str, str]
    ) -> BasePlatformAdapter:
        """플랫폼별 어댑터 생성"""
        if platform not in cls._adapters:
            raise ValueError(f"Unsupported platform: {platform}")

        adapter_class = cls._adapters[platform]
        return adapter_class(company_id, api_credentials)

    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """지원되는 플랫폼 목록 반환"""
        return list(cls._adapters.keys())

# 사용 예시
async def collect_multi_platform_data(company_id: str, platforms_config: Dict):
    """멀티플랫폼 데이터 수집"""

    for platform, config in platforms_config.items():
        try:
            # 플랫폼별 어댑터 생성
            adapter = PlatformAdapterFactory.create_adapter(
                platform,
                company_id,
                config["credentials"]
            )

            # 자격증명 검증
            if not await adapter.validate_credentials():
                logger.error(f"Invalid credentials for {platform}")
                continue

            # 데이터 수집
            async for tickets_chunk in adapter.fetch_tickets(
                config["start_date"],
                config["end_date"]
            ):
                await process_tickets_chunk(company_id, platform, tickets_chunk)

        except NotImplementedError:
            logger.warning(f"Platform {platform} not yet implemented")
        except Exception as e:
            logger.error(f"Error collecting from {platform}: {e}")
```

### ⚠️ **멀티플랫폼 확장 주의사항**

- 🚨 **공통 인터페이스**: 모든 어댑터는 BasePlatformAdapter 준수 필수
- 🚨 **데이터 정규화**: 플랫폼별 차이를 공통 스키마로 변환
- 🚨 **에러 처리**: NotImplementedError로 미구현 기능 명시

---

## 🔐 **멀티테넌트 보안 워크플로우 (AI 구현 필수 체크리스트)**

### ✅ **보안 필수 구현 체크리스트**

**company_id 자동 관리 전략**:

- [x] **도메인 기반 추출**: `company.freshdesk.com` → `company_id: "company"`
- [x] **플랫폼별 규칙**: Freshdesk 도메인 첫 번째 서브도메인을 company_id로 사용
- [x] **자동 검증**: 도메인 형식 및 company_id 유효성 실시간 확인
- [x] **일관성 보장**: 모든 데이터에 동일한 company_id 자동 태깅

**데이터 격리 전략**:

```
도메인 → company_id 자동 추출 → platform 필터링 → Row-level 보안 → API 키 검증 → 단일 컬렉션 내 논리적 분리
```

### 🔄 **보안 핵심 패턴**

**company_id 자동 추출 및 검증**:

```python
def extract_company_id(domain: str) -> str:
    """Freshdesk 도메인에서 company_id 자동 추출

    Args:
        domain: "wedosoft.freshdesk.com" 형태

    Returns:
        company_id: "wedosoft"
    """
    if not domain.endswith('.freshdesk.com'):
        raise ValueError(f"올바르지 않은 Freshdesk 도메인: {domain}")

    company_id = domain.split('.')[0]
    if not company_id or len(company_id) < 2:
        raise ValueError(f"유효하지 않은 company_id: {company_id}")

    return company_id

def validate_company_platform(company_id: str, platform: str) -> bool:
    """company_id와 플랫폼 조합 검증"""

    # 허용된 플랫폼 목록

    if platform not in allowed_platforms:
        return False

    # company_id 형식 검증 (영숫자, 하이픈만 허용)
    import re
    if not re.match(r'^[a-zA-Z0-9\-]+$', company_id):
        return False

    return True
```

**테넌트 컨텍스트 관리**:

```python
from contextvars import ContextVar
from contextlib import asynccontextmanager

# 테넌트 컨텍스트 변수
current_company_id: ContextVar[str] = ContextVar('current_company_id')
current_platform: ContextVar[str] = ContextVar('current_platform')

@asynccontextmanager
async def tenant_platform_context(domain: str, platform: str):
    """도메인에서 자동 추출한 company_id로 컨텍스트 생성"""
    company_id = extract_company_id(domain)

    # 1. company_id + platform 검증
    if not validate_company_platform(company_id, platform):
        raise UnauthorizedError(f"Invalid company_id or platform: {company_id}/{platform}")

    # 2. 컨텍스트 설정
    company_token = current_company_id.set(company_id)
    platform_token = current_platform.set(platform)

    try:
        # 3. 데이터베이스 세션에 컨텍스트 설정
        async with get_db_session() as session:
            await session.execute(
                text("SET app.current_company_id = :company_id"),
                {"company_id": company_id}
            )
            await session.execute(
                text("SET app.current_platform = :platform"),
                {"platform": platform}
            )

            # 4. Qdrant 필터링 조건 설정
            qdrant_filter = Filter(
                must=[
                    FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                    FieldCondition(key="platform", match=MatchValue(value=platform))
                ]
            )

            yield {
                "session": session,
                "qdrant_collection": "documents",
                "qdrant_filter": qdrant_filter,
                "company_id": company_id,
                "platform": platform
            }
    finally:
        current_company_id.reset(company_token)
        current_platform.reset(platform_token)
```

**멀티테넌트 데이터 접근 패턴**:

```python
async def search_similar_tickets(domain: str, platform: str, query: str):
    """도메인 기반 자동 company_id 적용"""
    async with tenant_platform_context(domain, platform) as context:
        # 완전히 격리된 환경에서 검색 수행
        results = await vector_search(
            collection=context["qdrant_collection"],
            query=query,
            filter=context["qdrant_filter"]  # 플랫폼별 필터링
        )
        return results

async def search_across_platforms(domain: str, query: str, platforms: List[str] = None):
    """도메인에서 추출한 company_id로 멀티플랫폼 검색"""
    company_id = extract_company_id(domain)
    results = []

    for platform in target_platforms:
        async with tenant_platform_context(domain, platform) as context:
            platform_results = await search_platform_data(
                query,
                context["qdrant_filter"]
            )
            results.extend(platform_results)

    return results
```

**API 키 보안 관리**:

```python
import boto3
from functools import lru_cache

@lru_cache(maxsize=128)
async def get_platform_credentials(company_id: str, platform: str) -> dict:
    """AWS Secrets Manager에서 플랫폼별 자격증명 조회"""
    secret_name = f"{platform}/{company_id}/api_credentials"

    session = boto3.Session()
    client = session.client('secretsmanager')

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return orjson.loads(response['SecretString'])
    except ClientError as e:
        logger.error(f"Failed to retrieve credentials for {company_id}: {e}")
        raise HTTPException(status_code=500, detail="Credential retrieval failed")

async def validate_api_access(company_id: str, platform: str, api_key_hash: str) -> bool:
    """API 키 해시 검증"""
    stored_credentials = await get_platform_credentials(company_id, platform)
    stored_hash = stored_credentials.get("api_key_hash")

    # 해시 비교 (실제 API 키는 저장하지 않음)
    return stored_hash == api_key_hash
```

### ⚠️ **멀티테넌트 보안 주의사항**

- 🚨 **company_id 필수**: 모든 데이터 접근에 테넌트 식별자 검증 필수
- 🚨 **도메인 검증**: 신뢰할 수 있는 도메인에서만 company_id 추출
- 🚨 **API 키 보안**: 실제 API 키는 secrets manager에만 저장, 해시만 비교
- 🚨 **컨텍스트 정리**: 요청 완료 후 테넌트 컨텍스트 완전 해제

---

## 📋 **단계별 구현 로드맵 (AI 참조용 체크리스트)**

### ✅ **Phase 1: MVP (2-4주) - 현재 진행**

**완료 목표**:

- [x] **Freshdesk 데이터 수집**: API 기반 티켓/KB 수집 완료
- [x] **LLM 요약 생성**: 구조화된 요약 생성 및 비용 최적화
- [x] **벡터 검색 구현**: Qdrant 단일 컬렉션 기반 멀티테넌트 검색
- [x] **파일 기반 스토리지**: MVP용 JSON 기반 데이터 관리

### ✅ **Phase 2: 스테이징 (1-2주) - 향후 계획**

**완료 목표**:

- [ ] **PostgreSQL 마이그레이션**: Row-level Security 기반 멀티테넌트
- [ ] **Redis 캐싱 도입**: LLM 응답 및 벡터 검색 캐싱
- [ ] **멀티플랫폼 보안 검증**: 테넌트별 완전 격리 확인
- [ ] **성능 최적화**: orjson, pydantic v2, 비동기 처리 적용

### ✅ **Phase 3: 프로덕션 (2-3주) - 최종 목표**

**완료 목표**:

- [ ] **전체 마이그레이션**: 파일 → PostgreSQL 완전 전환
- [ ] **모니터링 구축**: 플랫폼별 메트릭 및 알림 시스템
- [ ] **자동화 완성**: CI/CD 파이프라인 및 배포 자동화
- [ ] **ServiceNow 확장 준비**: 차세대 플랫폼 지원 기반 구축

---

## 🎯 **AI 세션 간 일관성 보장 최종 체크리스트**

### ✅ **데이터 워크플로우 일관성 검증**

**기존 파이프라인 재활용**:

- [x] **90% 이상 기존 로직 재사용**: 검증된 데이터 처리 방식 유지
- [x] **점진적 개선만**: 전면 재설계 대신 단계적 최적화
- [x] **데이터 호환성**: 기존 JSON 구조와 PostgreSQL 스키마 호환

**멀티테넌트 필수 요소**:

- [x] **company_id 자동 태깅**: 모든 데이터에 테넌트 식별자 필수
- [x] **플랫폼별 구분**: 멀티플랫폼 지원을 위한 platform 필드
- [x] **격리 검증**: 테넌트 간 데이터 누출 방지 확인

**비용 최적화 필수**:

- [x] **LLM 비용 관리**: 필터링 + 캐싱 + 배치 처리
- [x] **벡터 DB 최적화**: 요약 텍스트만 임베딩, 원본은 메타데이터
- [x] **스토리지 효율성**: 단일 컬렉션 + 필터링으로 관리 간소화

### 🚨 **절대 금지 사항 (AI 구현 시 필수 준수)**

- ❌ **company_id 없는 데이터**: 모든 데이터에 테넌트 식별자 필수
- ❌ **플랫폼별 하드코딩**: 조건문 남발 대신 추상화 패턴 사용
- ❌ **LLM 비용 무시**: 필터링 없는 무분별한 LLM 호출 금지
- ❌ **데이터 격리 무시**: 테넌트 간 데이터 접근 절대 금지

### 📚 **AI 참조용 핵심 워크플로우 맵**

```
MUST KNOW 핵심 데이터 플로우:
1. collect_platform_data()        # 플랫폼별 데이터 수집
2. merge_ticket_data()           # 티켓+대화+첨부파일 병합
3. process_tickets_batch()       # LLM 요약 (배치+캐싱)
4. store_embeddings()           # 벡터 저장 (멀티테넌트)
5. search_similar_content()     # 격리된 검색
6. collect_feedback()           # 피드백 수집 및 개선
```

---

**이 데이터 워크플로우 지침서는 AI가 세션 간 일관성을 유지하며 효율적인 데이터 파이프라인을 구현할 수 있도록 모든 핵심 패턴과 주의사항을 포함합니다. 모든 데이터 처리 작업은 이 문서를 기준으로 설계하고 구현하시기 바랍니다.**
