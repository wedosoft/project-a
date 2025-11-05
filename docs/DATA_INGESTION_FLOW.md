# 데이터 인제스트 및 저장 구조

**날짜**: 2025-11-05
**프로젝트**: AI Contact Center OS

---

## 📊 이중 저장 아키텍처

이 프로젝트는 **PostgreSQL + Qdrant 이중 저장 구조**를 사용합니다:

```
┌─────────────────────────────────────────────────────────┐
│         Freshdesk 티켓 & KB 문서                         │
└────────────────────┬────────────────────────────────────┘
                     ↓
        ┌────────────┴─────────────┐
        ↓                          ↓
┌───────────────────┐    ┌──────────────────┐
│   PostgreSQL      │    │     Qdrant       │
│  (Supabase)       │    │  (Vector DB)     │
│                   │    │                  │
│  - BM25 검색      │    │  - Dense 검색    │
│  - 스파스 인덱스  │    │  - 벡터 임베딩   │
│  - 텍스트 매칭    │    │  - 의미 검색     │
└───────┬───────────┘    └────────┬─────────┘
        │                         │
        └────────────┬────────────┘
                     ↓
        ┌────────────────────────┐
        │  Hybrid Search Service │
        │  (RRF Fusion)          │
        └────────────────────────┘
```

---

## 1️⃣ PostgreSQL (Supabase) 저장

### **목적**: BM25 스파스 검색

**테이블 구조**: `search_documents`

```sql
CREATE TABLE search_documents (
    id TEXT PRIMARY KEY,
    collection_name TEXT NOT NULL,
    content TEXT NOT NULL,
    content_tsvector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', content)
    ) STORED,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**인덱스**:
- `idx_search_documents_tsvector` (GIN): Full-text search
- `idx_search_documents_trigram` (GIN): Similarity search
- `idx_search_documents_collection`: Collection filtering

**검색 방식**: [sparse_search.py](backend/services/sparse_search.py:175-250)
```python
# BM25-like ranking with ts_rank_cd
SELECT
    id,
    content,
    metadata,
    ts_rank_cd(content_tsvector, to_tsquery('simple', query)) AS score
FROM search_documents
WHERE collection_name = 'support_tickets'
  AND content_tsvector @@ to_tsquery('simple', query)
ORDER BY score DESC
LIMIT 10
```

**저장 데이터**:
```python
{
    "id": "ticket-123",
    "collection_name": "support_tickets",
    "content": "Database connection error: timeout after 30s...",
    "metadata": {
        "ticket_id": "123",
        "priority": "high",
        "status": "resolved",
        "created_at": "2025-11-01"
    }
}
```

---

## 2️⃣ Qdrant 저장

### **목적**: Dense 벡터 의미 검색

**컬렉션 구조**:

#### **support_tickets 컬렉션**

**멀티벡터 설계**:
```python
vectors_config = {
    "symptom_vec": VectorParams(size=1024, distance=COSINE),
    "cause_vec": VectorParams(size=1024, distance=COSINE),
    "resolution_vec": VectorParams(size=1024, distance=COSINE)
}
```

**임베딩 모델**: `BAAI/bge-m3` (1024 차원)

**저장 데이터** ([vector_search.py](backend/services/vector_search.py:122-167)):
```python
{
    "id": "ticket-123",
    "vectors": {
        "symptom_vec": [0.123, 0.456, ...],  # 1024 dimensions
        "cause_vec": [0.789, 0.012, ...],    # 1024 dimensions
        "resolution_vec": [0.345, 0.678, ...] # 1024 dimensions
    },
    "payload": {
        "ticket_id": "123",
        "subject": "Database connection error",
        "content": "Full ticket content...",
        "priority": "high",
        "status": "resolved",
        "symptom": "Connection timeout",
        "cause": "Network configuration issue",
        "resolution": "Update firewall rules"
    }
}
```

#### **kb_procedures 컬렉션**

**멀티벡터 설계**:
```python
vectors_config = {
    "intent_vec": VectorParams(size=1024, distance=COSINE),
    "procedure_vec": VectorParams(size=1024, distance=COSINE)
}
```

**저장 데이터**:
```python
{
    "id": "kb-001",
    "vectors": {
        "intent_vec": [0.111, 0.222, ...],     # 질문/의도 임베딩
        "procedure_vec": [0.333, 0.444, ...]   # 절차/답변 임베딩
    },
    "payload": {
        "kb_id": "001",
        "title": "How to setup email integration",
        "content": "Step 1: ...",
        "category": "configuration",
        "tags": ["email", "integration", "setup"]
    }
}
```

---

## 🔄 데이터 인제스트 플로우

### **전체 프로세스**:

```
1. Freshdesk API 조회
   ↓
2. LLM 추출 (Symptom/Cause/Resolution)
   ↓
3. 임베딩 생성 (BGE-M3)
   ↓
4. 병렬 저장
   ├→ PostgreSQL: BM25 인덱싱
   └→ Qdrant: 벡터 저장
```

### **상세 코드 플로우**:

#### **1단계: Freshdesk 티켓 조회** ([freshdesk.py](backend/services/freshdesk.py))
```python
from backend.services.freshdesk import FreshdeskClient

freshdesk = FreshdeskClient()
tickets = await freshdesk.fetch_tickets(
    updated_since=datetime.now() - timedelta(days=30),
    per_page=30,
    max_tickets=500
)
```

#### **2단계: LLM 추출** ([extractor.py](backend/services/extractor.py))
```python
from backend.services.extractor import IssueBlockExtractor

extractor = IssueBlockExtractor(provider=LLMProvider.GEMINI)

for ticket in tickets:
    issue_block = await extractor.extract_from_ticket(ticket)
    # issue_block = {
    #     "symptom": "Connection timeout",
    #     "cause": "Network configuration",
    #     "resolution": "Update firewall"
    # }
```

#### **3단계: 임베딩 생성** ([vector_search.py](backend/services/vector_search.py:101-120))
```python
from backend.services.vector_search import VectorSearchService

vector_service = VectorSearchService()

# 각 필드별 임베딩 생성
symptom_embeddings = vector_service.generate_embeddings([issue_block["symptom"]])
cause_embeddings = vector_service.generate_embeddings([issue_block["cause"]])
resolution_embeddings = vector_service.generate_embeddings([issue_block["resolution"]])
```

#### **4단계: Qdrant 저장** ([vector_search.py](backend/services/vector_search.py:122-167))
```python
# Qdrant에 멀티벡터 저장
points = [{
    "id": ticket["id"],
    "vectors": {
        "symptom_vec": symptom_embeddings[0].tolist(),
        "cause_vec": cause_embeddings[0].tolist(),
        "resolution_vec": resolution_embeddings[0].tolist()
    },
    "payload": {
        "ticket_id": ticket["id"],
        "subject": ticket["subject"],
        "content": ticket["description_text"],
        "symptom": issue_block["symptom"],
        "cause": issue_block["cause"],
        "resolution": issue_block["resolution"],
        "priority": ticket["priority"],
        "status": ticket["status"]
    }
}]

await vector_service.upsert_vectors(
    collection_name="support_tickets",
    points=points
)
```

#### **5단계: PostgreSQL 저장** ([sparse_search.py](backend/services/sparse_search.py:126-174))
```python
from backend.services.sparse_search import SparseSearchService

sparse_service = SparseSearchService()

# PostgreSQL BM25 인덱싱
documents = [{
    "id": ticket["id"],
    "content": f"{ticket['subject']}\n\n{ticket['description_text']}",
    "metadata": {
        "ticket_id": ticket["id"],
        "priority": ticket["priority"],
        "status": ticket["status"],
        "created_at": ticket["created_at"]
    }
}]

await sparse_service.index_documents(
    collection_name="support_tickets",
    documents=documents
)
```

---

## 🔍 하이브리드 검색 플로우

### **검색 프로세스** ([hybrid_search.py](backend/services/hybrid_search.py:65-131))

```python
from backend.services.hybrid_search import HybridSearchService

hybrid_service = HybridSearchService()

results = await hybrid_service.search(
    collection_name="support_tickets",
    query="Database connection timeout",
    top_k=5,
    use_reranking=True
)
```

### **내부 동작**:

#### **1. Dense + Sparse 병렬 검색**
```python
# 병렬 실행
dense_results, sparse_results = await asyncio.gather(
    vector_service.search(query, top_k=10),  # Qdrant
    sparse_service.bm25_search(query, top_k=10)  # PostgreSQL
)
```

#### **2. RRF Fusion** ([hybrid_search.py](backend/services/hybrid_search.py:172-238))
```python
# Reciprocal Rank Fusion 알고리즘
rrf_score(doc) = Σ(weight_i / (k + rank_i(doc)))

# Dense 결과 스코어링
for rank, result in enumerate(dense_results, 1):
    rrf_scores[doc_id] += dense_weight / (60 + rank)

# Sparse 결과 스코어링
for rank, result in enumerate(sparse_results, 1):
    rrf_scores[doc_id] += sparse_weight / (60 + rank)

# 결합 및 정렬
fused_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
```

#### **3. Cross-Encoder Reranking** ([reranker.py](backend/services/reranker.py))
```python
# Jina AI Reranker v2로 최종 재랭킹
from backend.services.reranker import RerankerService

reranker = RerankerService()
final_results = reranker.rerank_results(
    query=query,
    search_results=fused_results,
    top_k=5
)
```

---

## 📈 검색 성능 비교

### **각 방식의 장단점**:

| 방식 | 장점 | 단점 | 사용 케이스 |
|------|------|------|------------|
| **Dense (Qdrant)** | 의미 이해, 다국어 지원 | 계산 비용 높음 | "연결 오류" → "timeout 문제" 매칭 |
| **Sparse (PostgreSQL)** | 정확한 키워드 매칭, 빠름 | 의미 이해 불가 | "error code 500" → 정확한 에러 코드 매칭 |
| **Hybrid (RRF)** | 양쪽 장점 결합 | 복잡도 증가 | 대부분의 실제 검색 시나리오 |

### **검색 품질 지표**:

- **Recall@10**: 관련 문서 10개 중 몇 개를 찾는가
- **nDCG@10**: 순위를 고려한 검색 품질
- **RRF 스코어**: Dense + Sparse 결합 점수

---

## 🚀 실제 인제스트 실행

### **현재 상태**: 벡터 DB 비어있음 ⚠️

**확인 방법**:
```python
from backend.services.vector_search import VectorSearchService

vector_service = VectorSearchService()
info = vector_service.get_collection_info("support_tickets")
print(f"Points count: {info['points_count']}")  # 현재: 0
```

### **데이터 인제스트 스크립트 작성 필요**:

현재 `scripts/test_integration.py`는 단순 LLM 추출 테스트만 수행하므로, **전체 인제스트 스크립트**를 새로 작성해야 합니다:

```python
# scripts/data_ingestion.py (작성 필요)

import asyncio
from backend.services.freshdesk import FreshdeskClient
from backend.services.extractor import IssueBlockExtractor, LLMProvider
from backend.services.vector_search import VectorSearchService
from backend.services.sparse_search import SparseSearchService

async def ingest_tickets():
    """
    Freshdesk 티켓을 Qdrant + PostgreSQL에 저장
    """
    # 1. Freshdesk 티켓 조회
    freshdesk = FreshdeskClient()
    tickets = await freshdesk.fetch_tickets(max_tickets=500)

    # 2. LLM 추출기 초기화
    extractor = IssueBlockExtractor(provider=LLMProvider.GEMINI)

    # 3. 서비스 초기화
    vector_service = VectorSearchService()
    sparse_service = SparseSearchService()

    # 4. PostgreSQL 스키마 초기화
    await sparse_service.initialize_search_schema()

    # 5. Qdrant 컬렉션 생성
    vector_service.create_collection(
        collection_name="support_tickets",
        vector_names=["symptom_vec", "cause_vec", "resolution_vec"]
    )

    # 6. 각 티켓 처리
    for ticket in tickets:
        # 6a. LLM 추출
        issue_block = await extractor.extract_from_ticket(ticket)

        # 6b. 임베딩 생성
        symptom_emb = vector_service.generate_embeddings([issue_block["symptom"]])
        cause_emb = vector_service.generate_embeddings([issue_block["cause"]])
        resolution_emb = vector_service.generate_embeddings([issue_block["resolution"]])

        # 6c. Qdrant 저장
        await vector_service.upsert_vectors(
            collection_name="support_tickets",
            points=[{
                "id": ticket["id"],
                "vectors": {
                    "symptom_vec": symptom_emb[0].tolist(),
                    "cause_vec": cause_emb[0].tolist(),
                    "resolution_vec": resolution_emb[0].tolist()
                },
                "payload": {
                    "ticket_id": ticket["id"],
                    "subject": ticket["subject"],
                    "content": ticket["description_text"],
                    **issue_block
                }
            }]
        )

        # 6d. PostgreSQL 저장
        await sparse_service.index_documents(
            collection_name="support_tickets",
            documents=[{
                "id": ticket["id"],
                "content": f"{ticket['subject']}\n\n{ticket['description_text']}",
                "metadata": {"ticket_id": ticket["id"]}
            }]
        )

if __name__ == "__main__":
    asyncio.run(ingest_tickets())
```

---

## 📊 저장 용량 추정

### **500개 티켓 기준**:

**PostgreSQL**:
- 텍스트 크기: ~500 KB (평균 1KB/티켓)
- 인덱스 크기: ~2 MB (GIN 인덱스)
- **총합**: ~2.5 MB

**Qdrant**:
- 벡터 크기: ~6 MB (500건 × 3벡터 × 1024차원 × 4바이트)
- Payload 크기: ~1 MB
- **총합**: ~7 MB

**전체**: ~10 MB (500개 티켓 기준)

---

## 🎯 요약

### ✅ **이중 저장 이유**:

1. **PostgreSQL (BM25)**:
   - 정확한 키워드 매칭 (에러 코드, 제품명)
   - 빠른 텍스트 검색
   - 한국어 전문 검색

2. **Qdrant (Dense)**:
   - 의미 기반 검색 (유사 증상)
   - 다국어 지원
   - 멀티벡터 (증상/원인/해결 각각 검색)

3. **하이브리드 (RRF + Reranking)**:
   - 양쪽 장점 결합
   - Cross-encoder로 최종 재랭킹
   - 검색 품질 최대화

### ⚠️ **현재 작업 필요**:
1. 전체 데이터 인제스트 스크립트 작성
2. Freshdesk → Qdrant + PostgreSQL 파이프라인 실행
3. 검색 품질 검증 및 튜닝

---

**작성일**: 2025-11-05
**작성자**: AI Assistant
