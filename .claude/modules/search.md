# Vector Search Engine - CLAUDE.md

## 🎯 컨텍스트 & 목적

이 디렉토리는 **Vector Search Engine**으로 벡터 데이터베이스 운영, 유사도 검색, 임베딩 생성을 담당합니다. Copilot Canvas의 모든 Qdrant 상호작용, 벡터 연산, 검색 기능을 처리합니다.

**주요 영역:**
- Qdrant 벡터 데이터베이스 통합 및 관리
- 벡터 유사도 검색 및 검색 결과 추출
- 임베딩 생성 (GPU/CPU/OpenAI)
- 벡터와 기존 검색을 결합한 하이브리드 검색
- 대규모 벡터 연산 성능 최적화

## 🏗️ 검색 구조

```
core/search/
├── engine.py           # 검색 엔진 인터페이스
├── hybrid.py          # 하이브리드 검색 구현
├── embeddings/        # 임베딩 생성 모듈
│   ├── base.py        # 임베딩 인터페이스
│   ├── openai.py      # OpenAI 임베딩
│   ├── local.py       # 로컬 모델 (GPU/CPU)
│   └── cache.py       # 임베딩 캐싱
├── filters/           # 검색 필터링
└── utils/            # 검색 유틸리티
```

## 🔧 핵심 기능

### 1. 벡터 검색 (`engine.py`)
```python
# 사용 예시
from core.search.engine import SearchEngine

async def search_similar_content(query: str, tenant_id: str):
    engine = SearchEngine()
    
    results = await engine.search(
        query_text=query,
        collection_name="documents",
        filters={"tenant_id": tenant_id},
        limit=10,
        score_threshold=0.7
    )
    
    return results
```

### 2. 하이브리드 검색 (`hybrid.py`)
벡터 검색과 키워드 검색을 결합한 고성능 검색:

```python
# 사용 예시
from core.search.hybrid import HybridSearchEngine

async def hybrid_search(query: str, tenant_id: str):
    engine = HybridSearchEngine()
    
    results = await engine.search(
        query=query,
        tenant_id=tenant_id,
        vector_weight=0.7,  # 벡터 검색 가중치
        keyword_weight=0.3, # 키워드 검색 가중치
        limit=20
    )
    
    return results
```

### 3. 임베딩 생성 (`embeddings/`)
```python
# OpenAI 임베딩
from core.search.embeddings.openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()
vector = await embeddings.embed_text("검색할 텍스트")

# 로컬 모델 임베딩 (GPU 가속)
from core.search.embeddings.local import LocalEmbeddings

local_embeddings = LocalEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vector = await local_embeddings.embed_text("검색할 텍스트")

# 배치 임베딩 처리
vectors = await embeddings.embed_batch([
    "첫 번째 문서",
    "두 번째 문서",
    "세 번째 문서"
])
```

### 4. 고급 필터링 (`filters/`)
```python
# 복합 필터 적용
search_filters = {
    "tenant_id": "company_123",
    "document_type": ["ticket", "kb"],
    "status": "published",
    "created_date": {
        "gte": "2024-01-01",
        "lte": "2024-12-31"
    }
}

results = await engine.search(
    query_text="로그인 문제",
    filters=search_filters,
    limit=15
)
```

## 🚀 성능 최적화

### 임베딩 캐싱
```python
# 임베딩 결과 캐싱으로 성능 향상
from core.search.embeddings.cache import CachedEmbeddings

cached_embeddings = CachedEmbeddings(
    embeddings=OpenAIEmbeddings(),
    cache_ttl=3600  # 1시간 캐시
)

# 동일한 텍스트 재요청 시 캐시에서 반환
vector = await cached_embeddings.embed_text("자주 검색되는 텍스트")
```

### 배치 처리
```python
# 대량 문서 처리 시 배치 최적화
async def process_documents_batch(documents: List[str], batch_size: int = 100):
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        vectors = await embeddings.embed_batch(batch)
        
        # 벡터 DB에 배치 삽입
        await vector_db.add_vectors(vectors)
```

### 검색 결과 재랭킹
```python
# 검색 결과 품질 향상을 위한 재랭킹
async def rerank_results(query: str, results: List[dict]):
    # 컨텍스트 유사도 기반 재랭킹
    reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
    
    pairs = [(query, result['content']) for result in results]
    scores = reranker.predict(pairs)
    
    # 점수 기반 재정렬
    for result, score in zip(results, scores):
        result['rerank_score'] = score
    
    return sorted(results, key=lambda x: x['rerank_score'], reverse=True)
```

## ⚠️ 중요 사항

### 성능 고려사항
- GPU 가속 임베딩 모델 우선 사용
- 임베딩 캐싱으로 중복 계산 방지
- 배치 처리로 대량 데이터 효율적 처리
- 적절한 `top_k` 값 설정으로 검색 속도 최적화

### 품질 관리
- 임베딩 모델 버전 일관성 유지
- 검색 결과 스코어 임계값 조정
- A/B 테스트를 통한 하이브리드 가중치 최적화
- 사용자 피드백 기반 검색 품질 개선

### 확장성
- 멀티테넌트 컬렉션 분리
- 수평 확장 가능한 Qdrant 클러스터 구성
- 임베딩 모델 버전 관리 체계
- 검색 로그 및 메트릭 수집

---

*벡터 데이터베이스 설정은 `core/database/CLAUDE.md`를 참조하세요.*

2. **Embedding Generation** (`search/embeddings/`)
   - **hybrid.py**: Multi-provider embedding coordination
   - **embedder_gpu.py**: GPU-accelerated local embeddings
   - **embedder.py**: CPU fallback and OpenAI embeddings
   - Embedding caching and optimization

3. **Search Operations** (`search/`)
   - **retriever.py**: High-level search interface
   - **hybrid.py**: Combined vector + traditional search
   - Performance optimization and result ranking

4. **Vector Operations**
   - Batch vector insertion and updates
   - Collection management and indexing
   - Similarity search with filters
   - Vector statistics and analytics

### Key Design Patterns

- **Adapter Pattern**: Pluggable vector database backends
- **Strategy Pattern**: Multiple embedding providers
- **Factory Pattern**: Vector DB and embedder creation
- **Caching**: Embedding and search result caching
- **Batch Processing**: Efficient bulk operations

## 🚀 Development Commands

### Environment Setup
```bash
# Virtual environment (from backend directory)
source venv/bin/activate

# GPU dependencies (optional, for local embeddings)
pip install torch sentence-transformers

# Verify Qdrant connection
python -c "from core.database.vectordb import vector_db; print('✅ Qdrant OK')"
```

### Vector Database Operations
```bash
# Test vector DB connection
python -c "from core.database.vectordb import QdrantAdapter; print('✅ Vector DB OK')"

# Check collection status
python -c "from core.database.vectordb import vector_db; print(vector_db.get_collection_info('documents'))"

# Test embedding generation
python -c "from core.search.embeddings.hybrid import embed_documents_optimized; print('✅ Embeddings OK')"
```

### Search Testing
```bash
# Test vector search
python -c "
from core.database.vectordb import vector_db
results = vector_db.search('sample query', limit=5)
print(f'Found {len(results)} results')
"

# Test hybrid search
python -c "
from core.search.hybrid import HybridSearchManager
manager = HybridSearchManager()
results = manager.search('customer issue', limit=10)
print(f'Hybrid search: {len(results)} results')
"
```

## 🔧 Key Environment Variables

```bash
# Qdrant Configuration
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=documents

# Embedding Configuration
EMBEDDING_MODEL=text-embedding-3-small
USE_GPU_FIRST=true
GPU_FALLBACK_TO_OPENAI=true
GPU_MODEL_NAME=all-MiniLM-L6-v2

# Performance Optimization
ENABLE_EMBEDDING_CACHE=true
USE_MPS_ACCELERATION=true  # Apple Silicon
EMBEDDING_PRIORITY=mps,cpu,openai

# Vector DB Settings
VECTOR_DB_CONTENT_FIELD=content
VECTOR_DB_STORE_ORIGINAL_TEXT=true
VECTOR_DB_INCLUDE_ALL_METADATA=true
```

## 📁 Directory Structure

```
core/database/
└── vectordb.py           # Vector DB interface and Qdrant adapter

core/search/
├── __init__.py
├── hybrid.py            # Hybrid search manager
├── retriever.py         # High-level search interface
└── embeddings/          # Embedding generation
    ├── __init__.py
    ├── hybrid.py         # Multi-provider coordination
    ├── embedder.py       # CPU/OpenAI embeddings
    └── embedder_gpu.py   # GPU-accelerated embeddings
```

## 🔍 Common Tasks

### Vector Database Operations
```python
# Initialize vector DB
from core.database.vectordb import vector_db, QdrantAdapter

# Create collection
await vector_db.create_collection("my_collection", dimension=384)

# Insert vectors
vectors = [
    {
        "id": "doc_1",
        "vector": [0.1, 0.2, ...],  # 384-dimensional
        "metadata": {
            "tenant_id": "wedosoft",
            "platform": "freshdesk",
            "doc_type": "ticket",
            "content": "Original text content"
        }
    }
]
await vector_db.insert_vectors("documents", vectors)

# Search vectors
results = await vector_db.search(
    collection_name="documents",
    query_vector=[0.1, 0.2, ...],
    filters={"tenant_id": "wedosoft", "doc_type": "ticket"},
    limit=10
)
```

### Embedding Generation
```python
# Generate embeddings with multiple providers
from core.search.embeddings.hybrid import embed_documents_optimized

texts = ["Customer has login issues", "Password reset required"]

# Auto-selects best available method (GPU > CPU > OpenAI)
embeddings = await embed_documents_optimized(texts)

# Force specific provider
from core.search.embeddings.embedder_gpu import GPUEmbedder
gpu_embedder = GPUEmbedder()
gpu_embeddings = await gpu_embedder.embed_documents(texts)

# OpenAI embeddings
from core.search.embeddings.embedder import OpenAIEmbedder
openai_embedder = OpenAIEmbedder()
openai_embeddings = await openai_embedder.embed_documents(texts)
```

### Hybrid Search
```python
# Combine vector search with traditional search
from core.search.hybrid import HybridSearchManager

search_manager = HybridSearchManager()

# Search with automatic ranking
results = await search_manager.search(
    query="customer login problem",
    filters={
        "tenant_id": "wedosoft",
        "platform": "freshdesk",
        "doc_type": ["ticket", "article"]
    },
    limit=20,
    hybrid_weight=0.7  # 70% vector, 30% traditional
)

# Process results
for result in results:
    print(f"Score: {result.score}")
    print(f"Content: {result.metadata['content'][:100]}...")
    print(f"Type: {result.metadata['doc_type']}")
```

### Collection Management
```python
# List collections
collections = await vector_db.list_collections()

# Get collection info
info = await vector_db.get_collection_info("documents")
print(f"Vectors: {info['vectors_count']}")
print(f"Dimension: {info['config']['params']['vectors']['size']}")

# Delete collection (careful!)
await vector_db.delete_collection("old_collection")

# Optimize collection (periodic maintenance)
await vector_db.optimize_collection("documents")
```

## 🎯 Vector Search Strategies

### Similarity Search Types
```python
# Semantic similarity (default)
semantic_results = await vector_db.search(
    collection_name="documents",
    query_text="user cannot access account",
    search_type="similarity"
)

# Diversity search (different topics)
diverse_results = await vector_db.search(
    collection_name="documents", 
    query_text="login issues",
    search_type="diversity",
    diversity_factor=0.8
)

# Filtered search
filtered_results = await vector_db.search(
    collection_name="documents",
    query_text="password problems",
    filters={
        "doc_type": "ticket",
        "status": "resolved",
        "created_date": {"gte": "2024-01-01"}
    }
)
```

### Performance Optimization
```python
# Batch operations for efficiency
from core.database.vectordb import vector_db

# Batch insert (much faster than individual inserts)
batch_vectors = []
for i, text in enumerate(large_text_list):
    embedding = await embed_single_text(text)
    batch_vectors.append({
        "id": f"batch_{i}",
        "vector": embedding,
        "metadata": {"content": text}
    })
    
    # Process in batches of 100
    if len(batch_vectors) >= 100:
        await vector_db.insert_vectors("documents", batch_vectors)
        batch_vectors = []

# Insert remaining vectors
if batch_vectors:
    await vector_db.insert_vectors("documents", batch_vectors)
```

## 🚨 Important Notes

### Multi-tenant Security
- **NEVER** search without tenant_id filtering
- Always include platform in metadata
- Use 3-tuple ID format: `{tenant_id}_{platform}_{original_id}`
- Validate tenant access in all operations

### Performance Considerations
- Use GPU embeddings when available (much faster)
- Enable embedding caching for repeated queries
- Batch vector operations for large datasets
- Regular collection optimization for search performance

### Memory Management
- GPU embeddings require significant VRAM
- CPU embeddings are slower but more memory efficient
- OpenAI embeddings have API costs but no local resources
- Monitor memory usage during large batch operations

## 🔗 Integration Points

### LLM Management Integration
```python
# Vector search results feed into LLM prompts
from core.llm.manager import LLMManager

search_results = await vector_db.search("customer issue", limit=5)
context_text = "\n".join([r.metadata['content'] for r in search_results])

llm_manager = LLMManager()
response = await llm_manager.generate_response(
    query="How to solve customer issue?",
    context=context_text,
    use_case="ticket_view"
)
```

### Data Pipeline Integration
```python
# Ingestion pipeline feeds vectors into search system
from core.ingest.processor import process_documents

# Process and index documents
documents = await fetch_fresh_documents()
processed_docs = await process_documents(documents)

# Generate embeddings and store
for doc in processed_docs:
    embedding = await embed_documents_optimized([doc.content])
    await vector_db.insert_vectors("documents", [{
        "id": doc.id,
        "vector": embedding[0],
        "metadata": doc.metadata
    }])
```

### API Layer Integration
```python
# Search endpoints use vector operations
from fastapi import APIRouter
from core.database.vectordb import vector_db

@router.post("/api/search")
async def vector_search(query: str, tenant_id: str):
    results = await vector_db.search(
        collection_name="documents",
        query_text=query,
        filters={"tenant_id": tenant_id},
        limit=20
    )
    
    return {
        "results": [
            {
                "id": r.id,
                "score": r.score,
                "content": r.metadata['content'][:200],
                "type": r.metadata['doc_type']
            }
            for r in results
        ]
    }
```

## 📚 Key Files to Know

- `core/database/vectordb.py` - Main vector DB interface and adapter
- `core/search/embeddings/hybrid.py` - Multi-provider embedding coordination
- `core/search/embeddings/embedder_gpu.py` - GPU-accelerated embeddings
- `core/search/hybrid.py` - Hybrid search manager
- `core/search/retriever.py` - High-level search interface

## 🔄 Development Workflow

1. **Start Development**: Ensure Qdrant is accessible
2. **Test Connection**: Verify vector DB connectivity
3. **Implement Feature**: Add new search capabilities
4. **Test Embeddings**: Verify embedding generation
5. **Performance Test**: Check search speed and accuracy
6. **Monitor Usage**: Track vector DB metrics

## 🚀 Advanced Features

### Custom Scoring
```python
# Implement custom relevance scoring
class CustomScorer:
    def __init__(self, weights=None):
        self.weights = weights or {
            "semantic_similarity": 0.6,
            "recency": 0.2,
            "popularity": 0.2
        }
    
    def score_results(self, results, metadata):
        scored_results = []
        for result in results:
            semantic_score = result.score
            recency_score = self.calculate_recency_score(result.metadata)
            popularity_score = self.calculate_popularity_score(result.metadata)
            
            final_score = (
                semantic_score * self.weights["semantic_similarity"] +
                recency_score * self.weights["recency"] +
                popularity_score * self.weights["popularity"]
            )
            
            result.final_score = final_score
            scored_results.append(result)
        
        return sorted(scored_results, key=lambda x: x.final_score, reverse=True)
```

### Real-time Indexing
```python
# Stream new documents for real-time indexing
async def realtime_indexing_stream():
    while True:
        new_docs = await get_new_documents()
        if new_docs:
            for doc in new_docs:
                embedding = await embed_documents_optimized([doc.content])
                await vector_db.insert_vectors("documents", [{
                    "id": doc.id,
                    "vector": embedding[0],
                    "metadata": doc.metadata
                }])
            
            logger.info(f"Indexed {len(new_docs)} new documents")
        
        await asyncio.sleep(30)  # Check every 30 seconds
```

### Vector Analytics
```python
# Analyze vector space and search patterns
class VectorAnalytics:
    async def analyze_search_patterns(self, collection_name: str):
        # Get vector distribution
        stats = await vector_db.get_collection_stats(collection_name)
        
        # Analyze clustering
        sample_vectors = await vector_db.sample_vectors(collection_name, 1000)
        clusters = self.perform_clustering(sample_vectors)
        
        # Search frequency analysis
        popular_queries = await self.get_popular_queries()
        
        return {
            "total_vectors": stats["vectors_count"],
            "clusters": len(clusters),
            "popular_queries": popular_queries,
            "avg_similarity": self.calculate_avg_similarity(sample_vectors)
        }
```

---

*This worktree focuses exclusively on vector database and search operations. For LLM management, use the llm-management worktree. For data ingestion, use the data-pipeline worktree.*
