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
PostgreSQL + Qdrant → AWS RDS → 멀티플랫폼/멀티테넌트 → 확장성 확보
```

- **Vector DB**: Qdrant Cloud (단일 `documents` 컬렉션, platform/company_id 필터링)
- **App DB**: PostgreSQL (AWS RDS, Row-level Security, 멀티플랫폼 지원)
- **Secrets**: AWS Secrets Manager (통합 API 키 관리)
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
-- 티켓 원본 및 메타데이터 (멀티플랫폼 지원)
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL, -- 'freshdesk', 'zendesk', 'servicenow' 등
    ticket_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed_data JSONB,
    summary JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform, ticket_id)
);

-- 지식베이스 문서 (멀티플랫폼 지원)
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    kb_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed_data JSONB,
    summary JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform, kb_id)
);

-- LLM 처리 큐
CREATE TABLE processing_queue (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    item_type VARCHAR(50) NOT NULL, -- 'ticket', 'kb'
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
    platform VARCHAR(50) NOT NULL,
    recommendation_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100),
    feedback_type VARCHAR(50), -- 'thumbs_up', 'thumbs_down'
    feedback_score INTEGER,
    feedback_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 플랫폼별 API 설정 관리
CREATE TABLE platform_configs (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    config_data JSONB NOT NULL, -- API 키는 secrets manager 참조 ID만 저장
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform)
);

-- Row-level Security 설정 (멀티테넌트 격리)
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY tickets_company_isolation ON tickets
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;
CREATE POLICY kb_company_isolation ON knowledge_base
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

ALTER TABLE processing_queue ENABLE ROW LEVEL SECURITY;
CREATE POLICY queue_company_isolation ON processing_queue
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY feedback_company_isolation ON feedback
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

ALTER TABLE platform_configs ENABLE ROW LEVEL SECURITY;
CREATE POLICY configs_company_isolation ON platform_configs
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

-- 인덱스 최적화 (멀티플랫폼 쿼리 성능)
CREATE INDEX idx_tickets_company_platform ON tickets(company_id, platform);
CREATE INDEX idx_tickets_status ON tickets(company_id, platform, status);
CREATE INDEX idx_kb_company_platform ON knowledge_base(company_id, platform);
CREATE INDEX idx_queue_company_platform_status ON processing_queue(company_id, platform, status);
CREATE INDEX idx_feedback_company_platform ON feedback(company_id, platform);
```
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
async def collect_platform_data(
    company_id: str,
    platform: str,  # 'freshdesk', 'zendesk', 'servicenow'
    start_date: str,
    end_date: str,
    chunk_size: int = 100
):
    """
    멀티플랫폼 대용량 데이터 수집 (500만건+ 최적화)
    
    Args:
        company_id: 고객사 ID (멀티테넌트 격리)
        platform: 플랫폼 타입 (freshdesk/zendesk/servicenow)
        start_date: 수집 시작일
        end_date: 수집 종료일
        chunk_size: 청크 크기 (Rate Limit 대응)
    """
    # 1. 진행률 추적 및 중단/재개 지원
    # 2. Rate Limit 대응 (요청 간격 조절)
    # 3. 에러 복구 및 재시도 로직
    # 4. 메모리 사용량 최적화
    # 5. 플랫폼별 Adapter 패턴 적용
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
# Qdrant 통합 컬렉션 설정 (멀티플랫폼/멀티테넌트)
async def store_embeddings(
    company_id: str,
    platform: str,  # 'freshdesk', 'zendesk', 'servicenow'
    embeddings: List[List[float]],
    metadata: List[Dict],
    data_type: str = "ticket"  # 'ticket' or 'kb'
):
    """
    멀티플랫폼/멀티테넌트 벡터 저장 (단일 컬렉션 사용)
    
    Args:
        company_id: 고객사 ID
        platform: 플랫폼 타입
        embeddings: 임베딩 벡터 리스트
        metadata: 메타데이터 (원본 데이터 포함)
        data_type: 데이터 타입 (ticket/kb)
    """
    collection_name = "documents"  # 단일 컬렉션 사용
    
    # Qdrant 컬렉션 생성 (최초 1회만)
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
    
    # 벡터 저장 (플랫폼 및 테넌트 정보 포함)
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "company_id": company_id,
                "platform": platform,
                "data_type": data_type,
                "item_id": metadata[i].get("ticket_id") or metadata[i].get("kb_id"),
                "summary": metadata[i].get("summary"),
                "original_data": metadata[i].get("original_data"),
                "created_at": datetime.now().isoformat(),
                # 필터링을 위한 복합 키
                "tenant_key": f"{company_id}_{platform}_{data_type}"
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
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환"""
        pass

class FreshdeskAdapter(BasePlatformAdapter):
    """Freshdesk 완전 구현"""
    
    def get_platform_name(self) -> str:
        return "freshdesk"
    
    async def fetch_tickets(self, start_date: str, end_date: str) -> List[Dict]:
        # Freshdesk API 호출 및 데이터 정규화
        pass

class ZendeskAdapter(BasePlatformAdapter):
    """Zendesk 구현"""
    
    def get_platform_name(self) -> str:
        return "zendesk"
    
    async def fetch_tickets(self, start_date: str, end_date: str) -> List[Dict]:
        # Zendesk API 호출 및 데이터 정규화
        pass

class ServiceNowAdapter(BasePlatformAdapter):
    """ServiceNow 구현 (향후 확장)"""
    
    def get_platform_name(self) -> str:
        return "servicenow"
    
    async def fetch_tickets(self, start_date: str, end_date: str) -> List[Dict]:
        raise NotImplementedError("ServiceNow 어댑터는 향후 구현 예정")

# 플랫폼 어댑터 팩토리
class PlatformAdapterFactory:
    """플랫폼별 어댑터 생성 팩토리"""
    
    _adapters = {
        "freshdesk": FreshdeskAdapter,
        "zendesk": ZendeskAdapter,
        "servicenow": ServiceNowAdapter
    }
    
    @classmethod
    def create_adapter(cls, platform: str, company_id: str) -> BasePlatformAdapter:
        """플랫폼별 어댑터 생성"""
        if platform not in cls._adapters:
            raise ValueError(f"Unsupported platform: {platform}")
        
        adapter_class = cls._adapters[platform]
        return adapter_class(company_id=company_id)
```
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
    platform: str,  # 플랫폼 정보 추가
    recommendation_id: str,
    feedback_type: str,  # 'thumbs_up', 'thumbs_down'
    user_id: str = None
):
    """사용자 피드백 수집 및 저장 (멀티플랫폼 지원)"""
    
# 2. 점수 재조정
async def recalculate_similarity_scores(company_id: str, platform: str = None):
    """피드백 기반 유사도 점수 재조정 (플랫폼별 또는 전체)"""
    
# 3. 모델 개선
async def retrain_recommendation_model(company_id: str, platform: str = None):
    """추천 모델 재학습 (주기적 실행, 플랫폼별 또는 통합)"""
```

---

## 🔐 멀티테넌트 보안 워크플로우

### 고객별 설정 관리
- **DB에 저장** (암호화된 API 키는 secrets manager 참조)
- **동적 로드** (런타임 설정 변경)
- **캐싱 적용** (성능 최적화)
- **플랫폼별 설정** (각 플랫폼마다 별도 API 키 및 설정)

### 데이터 격리 전략
```
company_id + platform 필터링 → Row-level 보안 → API 키 검증 → 단일 컬렉션 내 논리적 분리
```

**보안 구현**:
```python
# 테넌트 + 플랫폼 컨텍스트 관리
@contextmanager
async def tenant_platform_context(company_id: str, platform: str):
    """멀티플랫폼/멀티테넌트 컨텍스트 관리"""
    
    # 1. company_id + platform 검증
    if not validate_company_platform(company_id, platform):
        raise UnauthorizedError(f"Invalid company_id or platform: {company_id}/{platform}")
    
    # 2. 데이터베이스 세션에 컨텍스트 설정
    async with get_db_session() as session:
        await session.execute(
            text("SET app.current_company_id = :company_id"),
            {"company_id": company_id}
        )
        
        # 3. Qdrant 단일 컬렉션에서 필터링 조건 설정
        qdrant_collection = "documents"
        qdrant_filter = Filter(
            must=[
                FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                FieldCondition(key="platform", match=MatchValue(value=platform))
            ]
        )
        
        yield {
            "session": session,
            "qdrant_collection": qdrant_collection,
            "qdrant_filter": qdrant_filter,
            "company_id": company_id,
            "platform": platform
        }

# 사용 예시
async def search_similar_tickets(company_id: str, platform: str, query: str):
    async with tenant_platform_context(company_id, platform) as context:
        # 완전히 격리된 환경에서 검색 수행
        results = await vector_search(
            collection=context["qdrant_collection"],
            query=query,
            filter=context["qdrant_filter"]  # 플랫폼별 필터링
        )
        return results

# 멀티플랫폼 통합 검색 (선택적)
async def search_across_platforms(company_id: str, query: str, platforms: List[str] = None):
    """여러 플랫폼에서 통합 검색 (회사 내에서만)"""
    
    # company_id는 동일하지만 여러 플랫폼에서 검색
    platform_filter = platforms or ["freshdesk", "zendesk", "servicenow"]
    
    qdrant_filter = Filter(
        must=[
            FieldCondition(key="company_id", match=MatchValue(value=company_id)),
            FieldCondition(key="platform", match=MatchAny(any=platform_filter))
        ]
    )
    
    results = await vector_search(
        collection="documents",
        query=query,
        filter=qdrant_filter
    )
    
    return results
```
```

---

## 📋 단계별 구현 로드맵

### Phase 1: MVP (2-4주)
**목표**: 파일 기반 기본 기능 완성 (Freshdesk 우선)
- ✅ Freshdesk 데이터 수집
- ✅ LLM 요약 생성
- ✅ 벡터 검색 구현 (단일 컬렉션)
- ✅ 단일 고객 테스트
- 🔄 Zendesk 어댑터 추가

### Phase 2: 스테이징 (1-2주)
**목표**: 클라우드 DB 도입 및 멀티플랫폼/멀티테넌트 검증
- 🔄 PostgreSQL 마이그레이션 (멀티플랫폼 스키마)
- 🔄 Redis 캐싱 도입
- 🔄 멀티플랫폼/멀티테넌트 보안 검증
- 🔄 통합 컬렉션 성능 최적화

### Phase 3: 프로덕션 (2-3주)
**목표**: 전체 시스템 운영 준비
- 🔄 전체 마이그레이션
- 🔄 모니터링 구축 (플랫폼별 메트릭)
- 🔄 자동화 완성
- 🔄 ServiceNow 확장 준비

---

## ✅ 핵심 설계 원칙

1. **MVP 우선** - 복잡도 최소화, 빠른 검증 (Freshdesk 우선)
2. **점진적 개선** - 단계별 확장, 안정성 우선 (플랫폼별 순차 확장)
3. **추상화 적용** - 변경 용이성, 테스트 가능성 (멀티플랫폼 지원)
4. **보안 중시** - 데이터 격리, 규정 준수 (테넌트/플랫폼별 격리)
5. **비용 효율** - 리소스 최적화, LLM 비용 관리 (단일 인프라 활용)

---

이 데이터 워크플로우 지침서는 **효율적인 데이터 파이프라인**과 **확장 가능한 멀티테넌트 구조**를 균형있게 제공합니다. 모든 데이터 처리 작업은 이 문서를 기준으로 설계하고 구현하시면 됩니다.
