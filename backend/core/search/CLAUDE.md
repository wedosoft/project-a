# Vector DB & Search - CLAUDE.md

## 🎯 Context & Purpose

This is the **Vector DB & Search** worktree focused on vector database operations, similarity search, and embedding generation for Copilot Canvas. This handles all Qdrant interactions, vector operations, and search functionality.

**Primary Focus Areas:**
- Qdrant vector database integration and management
- Vector similarity search and retrieval
- Embedding generation (GPU/CPU/OpenAI)
- Hybrid search combining vector and traditional search
- Performance optimization for large-scale vector operations

## 🏗️ Vector Search Architecture

### System Overview
```
Text Input → Embedding Generation → Vector Search → Similarity Results
     ↓              ↓                    ↓               ↓
  Preprocessing   GPU/CPU/API         Qdrant DB      Post-processing
```

### Core Components

1. **Vector Database Interface** (`database/vectordb.py`)
   - Abstract VectorDBInterface for pluggable backends
   - QdrantAdapter implementation
   - Multi-tenant collection management
   - Metadata filtering and search optimization

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
