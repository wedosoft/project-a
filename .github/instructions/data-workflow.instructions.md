---
applyTo: "**"
---

# 📊 데이터 워크플로우 & 처리 지침서

*모델 참조 최적화 버전 - 데이터 수집/처리/저장/검색 워크플로우 전용*

## 🎯 데이터 처리 목표

**Freshdesk 기반 RAG 시스템의 효율적인 데이터 파이프라인 구축**

- **유사 티켓 추천**: 과거 해결 사례 기반 자동 추천
- **자동 요약 생성**: LLM 기반 구조화된 티켓 요약
- **피드백 기반 개선**: 사용자 피드백으로 추천 정확도 향상
- **멀티테넌트 격리**: company_id 기반 완전한 데이터 분리

---

## 🔄 전체 데이터 흐름

```
[Step 1] 플랫폼 데이터 수집 (Freshdesk API) →
[Step 2] 데이터 병합 (티켓+대화+첨부파일) →
[Step 3] LLM 요약 (이슈/해결방법 구조화) →
[Step 4] 임베딩 생성 (OpenAI/Azure) →
[Step 5] Vector DB 저장 (Qdrant + 메타데이터) →
[Step 6] 검색 & 추천 (유사도 기반) →
[Step 7] 피드백 수집 & 개선 (학습 루프)
```

---

## 🗄️ 데이터베이스 전략

### MVP 단계 (현재)
```
파일 기반 JSON → 로컬 개발 → 단순한 구조 → 빠른 프로토타이핑
```

- **Vector DB**: Qdrant Cloud (임베딩 검색)
- **App Data**: 파일 기반 JSON 저장
- **Progress**: 진행 상황 추적 JSON
- **Cache**: Redis (성능 최적화)

### 프로덕션 단계
```
PostgreSQL + Qdrant → AWS RDS → 멀티테넌트 → 확장성 확보
```

- **Vector DB**: Qdrant Cloud (멀티테넌트 네임스페이스)
- **App DB**: PostgreSQL (AWS RDS, Row-level Security)
- **Secrets**: AWS Secrets Manager (API 키 관리)
- **Cache**: Redis Cluster (고가용성)

---

## 📁 데이터 저장 구조

### MVP 파일 기반 구조
```
project-a/
├── data/
│   ├── raw/                    # 원본 데이터
│   │   ├── tickets/           # 병합된 티켓 JSON
│   │   └── kb/                # 지식베이스 문서
│   ├── processed/             # LLM 요약된 데이터
│   │   ├── tickets/           # 요약된 티켓 데이터
│   │   └── kb/                # 요약된 KB 데이터
│   ├── embeddings/            # 생성된 임베딩
│   │   ├── tickets/           # 티켓 임베딩
│   │   └── kb/                # KB 임베딩
│   └── progress/              # 진행 상황 추적
│       ├── progress.json      # 전체 진행 상황
│       ├── collection.log     # 수집 로그
│       └── processing.log     # 처리 로그
```

### 프로덕션 DB 스키마
```sql
-- 티켓 원본 및 메타데이터
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    ticket_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed_data JSONB,
    summary JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform, ticket_id)
);

-- LLM 처리 큐
CREATE TABLE processing_queue (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    item_type VARCHAR(50) NOT NULL,
    item_id VARCHAR(100) NOT NULL,
    priority INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 피드백 데이터
CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    recommendation_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100),
    feedback_type VARCHAR(50), -- 'thumbs_up', 'thumbs_down'
    feedback_score INTEGER,
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Row-level Security 설정
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY tickets_company_isolation ON tickets
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));
```

---

## 🔧 핵심 데이터 처리 단계

### 1. 데이터 수집 (Freshdesk API)

**특징**:
- 티켓 + 대화 + 첨부파일 **하나로 병합**
- 해시값으로 **중복 감지**
- **청크 단위** 처리 (Rate Limit 대응)

**수집 전략**:
```python
# 대용량 데이터 수집 최적화
async def collect_freshdesk_data(
    company_id: str,
    start_date: str,
    end_date: str,
    chunk_size: int = 100
):
    """
    Freshdesk 대용량 데이터 수집 (500만건+ 최적화)
    
    Args:
        company_id: 고객사 ID (멀티테넌트 격리)
        start_date: 수집 시작일
        end_date: 수집 종료일
        chunk_size: 청크 크기 (Rate Limit 대응)
    """
    # 1. 진행률 추적 및 중단/재개 지원
    # 2. Rate Limit 대응 (요청 간격 조절)
    # 3. 에러 복구 및 재시도 로직
    # 4. 메모리 사용량 최적화
```

### 2. LLM 요약 처리

**특징**:
- 이슈/해결 방법 **구조화 요약**
- **비용 최적화** (필터링 + 배치 처리)
- **병렬 처리** 지원

**요약 전략**:
```python
# LLM 요약 템플릿
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

JSON 형식으로 응답해주세요.
"""

# 배치 처리 및 비용 최적화
async def process_tickets_batch(
    tickets: List[Dict],
    batch_size: int = 10,
    cost_filter: bool = True
):
    """
    티켓 배치 처리 및 LLM 비용 최적화
    
    - 필터링: 해결되지 않은 티켓 제외
    - 배치 처리: 10개씩 묶어서 처리
    - 병렬 처리: 여러 LLM 제공자 동시 활용
    """
```

### 3. 벡터 검색 및 저장

**특징**:
- **요약 텍스트만** 임베딩 (비용 절약)
- 원본은 **메타데이터로만** 저장
- **company_id 기반** 격리

**벡터 처리**:
```python
# Qdrant 멀티테넌트 설정
async def store_embeddings(
    company_id: str,
    embeddings: List[List[float]],
    metadata: List[Dict],
    data_type: str = "ticket"
):
    """
    멀티테넌트 벡터 저장
    
    Args:
        company_id: 고객사 ID
        embeddings: 임베딩 벡터 리스트
        metadata: 메타데이터 (원본 데이터 포함)
        data_type: 데이터 타입 (ticket/kb)
    """
    collection_name = f"{company_id}_{data_type}"
    
    # Qdrant 컬렉션 생성 (테넌트별)
    await qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=1536,  # OpenAI text-embedding-3-small
            distance=Distance.COSINE
        )
    )
    
    # 벡터 저장 (메타데이터 포함)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "company_id": company_id,
                "data_type": data_type,
                "ticket_id": metadata[i].get("ticket_id"),
                "summary": metadata[i].get("summary"),
                "original_data": metadata[i].get("original_data"),
                "created_at": datetime.now().isoformat()
            }
        )
        for i, embedding in enumerate(embeddings)
    ]
    
    await qdrant_client.upsert(
        collection_name=collection_name,
        points=points
    )
```

---

## 🎨 추상화 레이어 설계

### 장점
- **저장소 변경 용이**: 파일 → DB 전환 시 비즈니스 로직 불변
- **테스트 편의성**: 인터페이스 기반 모킹 가능
- **멀티플랫폼 확장**: Freshdesk → Zendesk 추가 시 최소 변경

### 구현 방식
```
인터페이스 정의 → 파일 구현 → PostgreSQL 구현 → 환경변수로 전환
```

**스토리지 인터페이스**:
```python
from abc import ABC, abstractmethod

class StorageInterface(ABC):
    """데이터 저장소 추상화 인터페이스"""
    
    @abstractmethod
    async def save_ticket(self, company_id: str, ticket_data: Dict) -> str:
        """티켓 데이터 저장"""
        pass
    
    @abstractmethod
    async def get_ticket(self, company_id: str, ticket_id: str) -> Dict:
        """티켓 데이터 조회"""
        pass
    
    @abstractmethod
    async def list_tickets(self, company_id: str, **filters) -> List[Dict]:
        """티켓 목록 조회 (필터 지원)"""
        pass
    
    @abstractmethod
    async def update_processing_status(
        self, 
        company_id: str, 
        ticket_id: str, 
        status: str
    ) -> bool:
        """처리 상태 업데이트"""
        pass

# 파일 기반 구현 (MVP)
class FileStorage(StorageInterface):
    """파일 기반 스토리지 (개발/테스트용)"""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
    
    async def save_ticket(self, company_id: str, ticket_data: Dict) -> str:
        # 파일 시스템에 JSON 저장
        pass

# PostgreSQL 구현 (프로덕션)
class PostgresStorage(StorageInterface):
    """PostgreSQL 기반 스토리지 (프로덕션용)"""
    
    def __init__(self, connection_string: str):
        self.engine = create_async_engine(connection_string)
    
    async def save_ticket(self, company_id: str, ticket_data: Dict) -> str:
        # PostgreSQL 데이터베이스에 저장
        pass
```

---

## 🚀 멀티플랫폼 확장 전략

### MVP 우선순위
- **Freshdesk만** 집중 구현
- **기반 구조**는 확장 고려 설계
- **Adapter 패턴** 준비

### 향후 확장 계획
```
Freshdesk (완전 구현) → Zendesk (추상화 기반)
```

**플랫폼 어댑터 패턴**:
```python
class BasePlatformAdapter(ABC):
    """플랫폼 어댑터 기본 인터페이스"""
    
    @abstractmethod
    async def fetch_tickets(self, start_date: str, end_date: str) -> List[Dict]:
        """티켓 데이터 수집"""
        pass
    
    @abstractmethod
    async def fetch_knowledge_base(self) -> List[Dict]:
        """지식베이스 수집"""
        pass

class FreshdeskAdapter(BasePlatformAdapter):
    """Freshdesk 완전 구현"""
    
    async def fetch_tickets(self, start_date: str, end_date: str) -> List[Dict]:
        # Freshdesk API 호출 및 데이터 정규화
        pass

class ZendeskAdapter(BasePlatformAdapter):
    """Zendesk 추상화 (향후 구현)"""
    
    async def fetch_tickets(self, start_date: str, end_date: str) -> List[Dict]:
        raise NotImplementedError("Zendesk 어댑터는 향후 구현 예정")
```

---

## 📈 추천 개선 워크플로우

### 피드백 수집 전략
- 추천 묶음 단위 **👍/👎** 평가
- **날짜/시간** 기록으로 트렌드 분석
- **API로 저장** 후 배치 처리

### 개선 알고리즘
```
피드백 데이터 → 점수 재조정 → 임베딩 모델 미세조정 → LLM reranking
```

**피드백 처리 플로우**:
```python
# 1. 피드백 수집
async def collect_feedback(
    company_id: str,
    recommendation_id: str,
    feedback_type: str,  # 'thumbs_up', 'thumbs_down'
    user_id: str = None
):
    """사용자 피드백 수집 및 저장"""
    
# 2. 점수 재조정
async def recalculate_similarity_scores(company_id: str):
    """피드백 기반 유사도 점수 재조정"""
    
# 3. 모델 개선
async def retrain_recommendation_model(company_id: str):
    """추천 모델 재학습 (주기적 실행)"""
```

---

## 🔐 멀티테넌트 보안 워크플로우

### 고객별 설정 관리
- **DB에 저장** (암호화된 API 키)
- **동적 로드** (런타임 설정 변경)
- **캐싱 적용** (성능 최적화)

### 데이터 격리 전략
```
company_id 필터링 → Row-level 보안 → API 키 검증 → 네임스페이스 분리
```

**보안 구현**:
```python
# 테넌트 컨텍스트 관리
@contextmanager
async def tenant_context(company_id: str):
    """멀티테넌트 컨텍스트 관리"""
    
    # 1. company_id 검증
    if not validate_company_id(company_id):
        raise UnauthorizedError("Invalid company_id")
    
    # 2. 데이터베이스 세션에 컨텍스트 설정
    async with get_db_session() as session:
        await session.execute(
            text("SET app.current_company_id = :company_id"),
            {"company_id": company_id}
        )
        
        # 3. Qdrant 네임스페이스 설정
        qdrant_collection = f"{company_id}_tickets"
        
        yield {
            "session": session,
            "qdrant_collection": qdrant_collection,
            "company_id": company_id
        }

# 사용 예시
async def search_similar_tickets(company_id: str, query: str):
    async with tenant_context(company_id) as context:
        # 완전히 격리된 환경에서 검색 수행
        results = await vector_search(
            collection=context["qdrant_collection"],
            query=query
        )
        return results
```

---

## 📋 단계별 구현 로드맵

### Phase 1: MVP (2-4주)
**목표**: 파일 기반 기본 기능 완성
- ✅ Freshdesk 데이터 수집
- ✅ LLM 요약 생성
- ✅ 벡터 검색 구현
- ✅ 단일 고객 테스트

### Phase 2: 스테이징 (1-2주)
**목표**: 클라우드 DB 도입 및 멀티테넌트 검증
- 🔄 PostgreSQL 마이그레이션
- 🔄 Redis 캐싱 도입
- 🔄 멀티테넌트 보안 검증
- 🔄 성능 최적화

### Phase 3: 프로덕션 (2-3주)
**목표**: 전체 시스템 운영 준비
- 🔄 전체 마이그레이션
- 🔄 모니터링 구축
- 🔄 자동화 완성
- 🔄 Zendesk 확장 준비

---

## ✅ 핵심 설계 원칙

1. **MVP 우선** - 복잡도 최소화, 빠른 검증
2. **점진적 개선** - 단계별 확장, 안정성 우선
3. **추상화 적용** - 변경 용이성, 테스트 가능성
4. **보안 중시** - 데이터 격리, 규정 준수
5. **비용 효율** - 리소스 최적화, LLM 비용 관리

---

이 데이터 워크플로우 지침서는 **효율적인 데이터 파이프라인**과 **확장 가능한 멀티테넌트 구조**를 균형있게 제공합니다. 모든 데이터 처리 작업은 이 문서를 기준으로 설계하고 구현하시면 됩니다.
