# Data Pipeline & Ingestion - CLAUDE.md

## 🎯 컨텍스트 & 목적

이 디렉토리는 **Data Pipeline & Ingestion**으로 데이터 수집, 처리, 저장 파이프라인을 담당합니다. Copilot Canvas의 모든 Freshdesk 데이터 수집, 전처리, SQL과 벡터 데이터베이스 간 저장 조정을 처리합니다.

**주요 영역:**
- Freshdesk API 통합 및 데이터 수집
- 다중 모달 데이터 처리 (티켓, 대화, 첨부파일, KB 문서)
- Vector 전용 및 하이브리드 (SQL+Vector) 처리 모드
- 진행 상황 추적 및 오류 복구를 통한 배치 처리
- 플랫폼 독립적 데이터 변환 및 정규화

## 🏗️ 데이터 파이프라인 구조

```
core/ingest/
├── processor.py        # 메인 수집 오케스트레이터
├── manager.py         # 수집 관리자
├── freshdesk/         # Freshdesk 플랫폼 통합
│   ├── collector.py   # Freshdesk API 수집기
│   ├── transformer.py # 데이터 변환
│   └── validator.py   # 데이터 검증
├── processors/        # 데이터 타입별 처리기
│   ├── ticket.py      # 티켓 처리
│   ├── conversation.py # 대화 처리
│   ├── attachment.py  # 첨부파일 처리
│   └── kb_article.py  # KB 문서 처리
└── utils/            # 유틸리티 및 헬퍼
```

## 🔧 핵심 기능

### 1. 메인 프로세서 (`processor.py`)
전체 수집 파이프라인을 오케스트레이션합니다:

```python
# 사용 예시
from core.ingest.processor import MainProcessor

async def run_full_ingestion(tenant_id: str):
    processor = MainProcessor()
    
    # 하이브리드 모드로 전체 수집 실행
    await processor.process_all_data(
        tenant_id=tenant_id,
        platform="freshdesk",
        mode="hybrid",  # vector_only 또는 hybrid
        batch_size=100
    )
```

### 2. Freshdesk 수집기 (`freshdesk/collector.py`)
```python
# Freshdesk 데이터 수집
from core.ingest.freshdesk.collector import FreshdeskCollector

collector = FreshdeskCollector(
    domain="company.freshdesk.com",
    api_key="your_api_key"
)

# 티켓 수집
tickets = await collector.collect_tickets(
    updated_since="2024-01-01",
    include_conversations=True,
    include_attachments=True
)

# KB 문서 수집
articles = await collector.collect_kb_articles(
    category_id=123,
    published_only=True
)
```

### 3. 데이터 변환 (`processors/`)
플랫폼별 데이터를 표준 형식으로 변환:

```python
# 티켓 데이터 변환
from core.ingest.processors.ticket import TicketProcessor

processor = TicketProcessor()

# Freshdesk 티켓을 표준 형식으로 변환
standard_ticket = await processor.transform(
    raw_data=freshdesk_ticket,
    tenant_id="company_123",
    platform="freshdesk"
)

# 벡터 임베딩 생성
embeddings = await processor.generate_embeddings(standard_ticket)

# 저장소에 저장
await processor.store(standard_ticket, embeddings)
```

### 4. 배치 처리 및 진행 추적
```python
# 진행 상황 모니터링을 통한 배치 처리
from core.ingest.manager import IngestionManager

manager = IngestionManager()

async def monitor_ingestion():
    job_id = await manager.start_ingestion(
        tenant_id="company_123",
        data_types=["tickets", "kb_articles"],
        batch_size=50
    )
    
    # 진행 상황 모니터링
    while True:
        status = await manager.get_job_status(job_id)
        print(f"진행률: {status.progress}%, 오류: {status.error_count}")
        
        if status.completed:
            break
        
        await asyncio.sleep(10)
```

## 🚀 처리 모드

### 1. Vector-Only 모드
벡터 데이터베이스에만 저장하는 경량 모드:

```python
# 환경변수 설정
PROCESSING_MODE=vector_only

# 벡터 데이터만 저장
await processor.process_data(
    data=ticket_data,
    mode="vector_only",
    generate_embeddings=True,
    store_metadata_only=True
)
```

### 2. Hybrid 모드
SQL과 벡터 데이터베이스 모두 활용하는 완전한 모드:

```python
# 환경변수 설정
PROCESSING_MODE=hybrid

# 완전한 데이터 저장
await processor.process_data(
    data=ticket_data,
    mode="hybrid",
    store_full_data=True,
    generate_embeddings=True,
    update_relationships=True
)
```

## 🔄 데이터 흐름

### 수집 → 처리 → 저장
```
1. Freshdesk API 호출
2. 속도 제한 관리
3. 데이터 검증 및 정규화
4. 임베딩 생성
5. SQL 저장 (Hybrid 모드)
6. 벡터 DB 저장
7. 진행 상황 업데이트
```

### 오류 처리 및 복구
```python
# 오류 복구 메커니즘
class IngestionError(Exception):
    def __init__(self, message, recoverable=True):
        self.message = message
        self.recoverable = recoverable

async def process_with_retry(data, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await process_data(data)
        except IngestionError as e:
            if not e.recoverable or attempt == max_retries - 1:
                raise
            
            await asyncio.sleep(2 ** attempt)  # 지수 백오프
```

## ⚠️ 중요 사항

### 성능 최적화
- API 속도 제한 준수 (Freshdesk: 분당 200개 요청)
- 배치 처리로 대량 데이터 효율적 처리
- 중복 제거 및 증분 업데이트
- 임베딩 생성 병렬 처리

### 데이터 품질 관리
- 입력 데이터 검증 및 정제
- 중복 데이터 감지 및 제거
- 첨부파일 OCR 처리 (이미지 → 텍스트)
- 다국어 콘텐츠 처리

### 모니터링 및 로깅
- 수집 진행 상황 실시간 추적
- 오류 발생 시 상세 로깅
- 데이터 품질 메트릭 수집
- 성능 지표 모니터링

---

*플랫폼별 API 통합 세부사항은 `platforms/*/CLAUDE.md`를 참조하세요.*

2. **Platform Adapters** (`platforms/freshdesk/`)
   - **adapter.py**: Main Freshdesk integration
   - **fetcher.py**: API data retrieval with rate limiting
   - **optimized_fetcher.py**: Performance-optimized batch operations
   - **run_collection.py**: CLI tools for data collection

3. **Data Processing** (`ingest/`)
   - **storage.py**: Storage coordination layer
   - Platform-neutral data transformation
   - Metadata normalization and enrichment
   - Attachment processing with OCR support

4. **Metadata Management** (`metadata/`)
   - **normalizer.py**: Cross-platform data normalization
   - Schema validation and transformation
   - Custom field handling

### Key Design Patterns

- **Pipeline Pattern**: Sequential data processing stages
- **Adapter Pattern**: Platform-agnostic data sources
- **Strategy Pattern**: Multiple storage strategies (Vector-only vs Hybrid)
- **Batch Processing**: Efficient large-scale data handling
- **Circuit Breaker**: API failure resilience

## 🚀 Development Commands

### Environment Setup
```bash
# Virtual environment (from backend directory)
source venv/bin/activate

# Verify platform adapters
python -c "from core.platforms.factory import PlatformFactory; print('✅ Platforms OK')"

# Test Freshdesk connection
python -c "
from core.platforms.freshdesk.adapter import FreshdeskAdapter
adapter = FreshdeskAdapter()
print('✅ Freshdesk adapter ready')
"
```

### Data Collection Operations
```bash
# Test main processor
python -c "
from core.ingest.processor import ingest_all_data_with_vectordb
print('✅ Processor ready')
"

# Run data collection (Vector-only mode)
python -c "
import asyncio
from core.ingest.processor import ingest_vector_only_mode
asyncio.run(ingest_vector_only_mode())
"

# Run full collection workflow
python -c "
import asyncio
from core.platforms.freshdesk.run_collection import full_collection_workflow
asyncio.run(full_collection_workflow())
"
```

### Platform Testing
```bash
# Test Freshdesk fetcher
python -c "
from core.platforms.freshdesk.fetcher import FreshdeskFetcher
fetcher = FreshdeskFetcher()
print('✅ Freshdesk fetcher ready')
"

# Test optimized fetcher
python -c "
from core.platforms.freshdesk.optimized_fetcher import OptimizedFreshdeskFetcher
fetcher = OptimizedFreshdeskFetcher()
print('✅ Optimized fetcher ready')
"
```

## 🔧 Key Environment Variables

```bash
# Processing Mode Selection
ENABLE_FULL_STREAMING_MODE=true       # Vector-only mode
# ENABLE_FULL_STREAMING_MODE=false    # Hybrid SQL+Vector mode

# Freshdesk Configuration
TENANT_ID=wedosoft
FRESHDESK_API_KEY=your-api-key
FRESHDESK_DOMAIN=wedosoft.freshdesk.com

# Collection Control
ENABLE_LLM_SUMMARY_GENERATION=false   # Disable for Vector-only
ENABLE_SQL_PROGRESS_LOGS=false        # Disable for Vector-only
VECTOR_ONLY_MODE_MINIMAL_SQL=true     # Minimize SQL usage

# Vector Storage Configuration
VECTOR_DB_CONTENT_FIELD=content       # Store original content
VECTOR_DB_STORE_ORIGINAL_TEXT=true    # Keep original text
VECTOR_DB_INCLUDE_ALL_METADATA=true   # Include all metadata

# Performance Settings
COLLECTION_BATCH_SIZE=100
RATE_LIMIT_DELAY=1.0
MAX_CONCURRENT_REQUESTS=5
```

## 📁 Directory Structure

```
core/ingest/
├── __init__.py
├── processor.py           # Main ingestion orchestrator
└── storage.py            # Storage coordination

core/platforms/
├── __init__.py
├── factory.py            # Platform factory
└── freshdesk/            # Freshdesk integration
    ├── __init__.py
    ├── adapter.py         # Main Freshdesk adapter
    ├── fetcher.py         # API data retrieval
    ├── optimized_fetcher.py # Performance-optimized fetching
    └── run_collection.py  # CLI collection tools

core/metadata/
├── __init__.py
└── normalizer.py         # Data normalization
```

## 🔍 Common Tasks

### Basic Data Collection
```python
# Vector-only data collection
import asyncio
from core.ingest.processor import ingest_vector_only_mode

async def collect_data():
    await ingest_vector_only_mode(
        tenant_id="wedosoft",
        platform="freshdesk",
        collect_tickets=True,
        collect_conversations=True,
        collect_kb_articles=True
    )

# Run collection
asyncio.run(collect_data())
```

### Platform Adapter Usage
```python
# Initialize Freshdesk adapter
from core.platforms.freshdesk.adapter import FreshdeskAdapter

adapter = FreshdeskAdapter(
    domain="wedosoft.freshdesk.com",
    api_key="your-api-key"
)

# Fetch tickets
tickets = await adapter.fetch_tickets(
    start_date="2024-01-01",
    limit=100
)

# Fetch KB articles
articles = await adapter.fetch_kb_articles()

# Fetch conversations for ticket
conversations = await adapter.fetch_conversations(ticket_id=123)
```

### Batch Processing
```python
# Process large datasets in batches
from core.ingest.processor import process_batch_data

async def process_large_dataset():
    # Get data in batches
    batch_size = 100
    total_processed = 0
    
    while True:
        batch = await fetch_data_batch(
            offset=total_processed,
            limit=batch_size
        )
        
        if not batch:
            break
        
        # Process batch
        await process_batch_data(
            batch_data=batch,
            processing_mode="vector_only"
        )
        
        total_processed += len(batch)
        print(f"Processed {total_processed} items")

asyncio.run(process_large_dataset())
```

### Data Transformation
```python
# Transform platform data to normalized format
from core.metadata.normalizer import normalize_ticket_data

# Raw Freshdesk ticket
freshdesk_ticket = {
    "id": 123,
    "subject": "Login issues",
    "description": "User cannot log in",
    "status": 2,  # Freshdesk status code
    "priority": 1,
    "created_at": "2024-01-01T10:00:00Z"
}

# Normalize to platform-neutral format
normalized_ticket = normalize_ticket_data(
    ticket_data=freshdesk_ticket,
    platform="freshdesk",
    tenant_id="wedosoft"
)

# Result:
# {
#   "id": "wedosoft_freshdesk_123",
#   "original_id": "123",
#   "subject": "Login issues",
#   "content": "User cannot log in",
#   "status": "open",  # Normalized status
#   "priority": "high",  # Normalized priority
#   "platform": "freshdesk",
#   "tenant_id": "wedosoft",
#   "created_at": "2024-01-01T10:00:00Z"
# }
```

### Storage Coordination
```python
# Coordinate storage between Vector DB and SQL
from core.ingest.storage import store_integrated_object_to_sqlite

# Store with automatic routing
await store_integrated_object_to_sqlite(
    integrated_object={
        "id": "wedosoft_freshdesk_123",
        "content": "Ticket content...",
        "metadata": {"type": "ticket", "status": "open"},
        "platform": "freshdesk",
        "tenant_id": "wedosoft"
    },
    storage_mode="vector_only"  # or "hybrid"
)
```

## 🎯 Processing Modes

### Vector-Only Mode
```python
# Configure for Vector-only processing
import os
os.environ["ENABLE_FULL_STREAMING_MODE"] = "true"

from core.ingest.processor import ingest_vector_only_mode

async def vector_only_collection():
    """
    Vector-only mode:
    - Stores original content (no LLM summarization)
    - Minimal SQL usage (metadata only)
    - Optimized for search performance
    - Lower processing costs
    """
    await ingest_vector_only_mode(
        tenant_id="wedosoft",
        platform="freshdesk",
        reset_vector_db=False,  # Preserve existing data
        collect_raw_details=True,
        collect_raw_conversations=True,
        collect_raw_kb=True
    )

asyncio.run(vector_only_collection())
```

### Hybrid Mode (SQL + Vector)
```python
# Configure for Hybrid processing
import os
os.environ["ENABLE_FULL_STREAMING_MODE"] = "false"

from core.ingest.processor import ingest_legacy_hybrid_mode

async def hybrid_collection():
    """
    Hybrid mode:
    - Stores both original content and LLM summaries
    - Full SQL database usage
    - Supports complex queries
    - Higher processing costs but more features
    """
    await ingest_legacy_hybrid_mode(
        tenant_id="wedosoft",
        platform="freshdesk",
        enable_summaries=True,
        store_conversations=True,
        process_attachments=True
    )

asyncio.run(hybrid_collection())
```

### Mode Switching
```python
# Dynamic mode switching based on requirements
async def adaptive_processing(data_size: int, performance_priority: bool):
    if performance_priority or data_size > 10000:
        # Use Vector-only for large datasets or performance priority
        await ingest_vector_only_mode()
    else:
        # Use Hybrid for smaller datasets requiring full features
        await ingest_legacy_hybrid_mode()
```

## 🚨 Important Notes

### API Rate Limiting
- Freshdesk has strict rate limits (varies by plan)
- Implement exponential backoff for failed requests
- Use batch operations when available
- Monitor API usage to avoid quota exhaustion

### Data Consistency
- Always use 3-tuple ID format: `{tenant_id}_{platform}_{original_id}`
- Validate data schemas before storage
- Handle partial failures gracefully
- Implement data integrity checks

### Memory Management
- Process large datasets in batches
- Clear processed data from memory
- Monitor memory usage during collection
- Use streaming for very large files

## 🔗 Integration Points

### Vector Database Integration
```python
# Pipeline feeds processed data to vector storage
from core.database.vectordb import vector_db

async def store_to_vector_db(processed_data: dict):
    # Generate embeddings
    from core.search.embeddings.hybrid import embed_documents_optimized
    
    embeddings = await embed_documents_optimized([processed_data["content"]])
    
    # Store in vector DB
    await vector_db.insert_vectors("documents", [{
        "id": processed_data["id"],
        "vector": embeddings[0],
        "metadata": processed_data["metadata"]
    }])
```

### LLM Integration
```python
# Optional LLM processing during ingestion
from core.llm.summarizer import generate_optimized_summary

async def process_with_llm(content: str, doc_type: str):
    if os.getenv("ENABLE_LLM_SUMMARY_GENERATION") == "true":
        summary = await generate_optimized_summary(
            content=content,
            summary_type=doc_type,
            max_length=200
        )
        return summary
    else:
        return content  # Return original content
```

### API Layer Integration
```python
# Ingestion endpoints trigger pipeline operations
from fastapi import APIRouter
from core.ingest.processor import ingest_vector_only_mode

@router.post("/api/ingest/start")
async def start_ingestion(tenant_id: str, platform: str = "freshdesk"):
    # Start background ingestion
    task = asyncio.create_task(
        ingest_vector_only_mode(tenant_id=tenant_id, platform=platform)
    )
    
    return {
        "status": "started",
        "tenant_id": tenant_id,
        "platform": platform,
        "task_id": str(id(task))
    }

@router.get("/api/ingest/status")
async def get_ingestion_status(tenant_id: str):
    # Check ingestion progress
    from core.ingest.processor import get_ingestion_status
    
    status = await get_ingestion_status(tenant_id)
    return status
```

## 📚 Key Files to Know

- `core/ingest/processor.py` - Main pipeline orchestrator
- `core/platforms/freshdesk/adapter.py` - Freshdesk integration
- `core/platforms/freshdesk/run_collection.py` - CLI collection tools
- `core/metadata/normalizer.py` - Data normalization
- `core/ingest/storage.py` - Storage coordination

## 🔄 Development Workflow

1. **Start Development**: Verify platform API access
2. **Test Connection**: Check adapter connectivity
3. **Implement Feature**: Add new data sources or processing
4. **Test Processing**: Verify data transformation
5. **Performance Test**: Check batch processing efficiency
6. **Monitor Collection**: Track progress and errors

## 🚀 Advanced Features

### Progress Tracking
```python
# Implement detailed progress tracking
class IngestionProgressTracker:
    def __init__(self):
        self.progress = {
            "total_items": 0,
            "processed_items": 0,
            "failed_items": 0,
            "current_stage": "initializing",
            "start_time": None,
            "estimated_completion": None
        }
    
    def update_progress(self, processed: int, failed: int = 0):
        self.progress["processed_items"] += processed
        self.progress["failed_items"] += failed
        
        # Calculate ETA
        if self.progress["start_time"]:
            elapsed = time.time() - self.progress["start_time"]
            rate = self.progress["processed_items"] / elapsed
            remaining = self.progress["total_items"] - self.progress["processed_items"]
            eta = remaining / rate if rate > 0 else None
            self.progress["estimated_completion"] = eta
    
    def get_status(self):
        return {
            **self.progress,
            "completion_percentage": (
                self.progress["processed_items"] / self.progress["total_items"] * 100
                if self.progress["total_items"] > 0 else 0
            )
        }
```

### Error Recovery
```python
# Implement robust error recovery
class RobustIngestionPipeline:
    def __init__(self):
        self.retry_count = 3
        self.backoff_factor = 2
        self.checkpoint_interval = 100
    
    async def process_with_recovery(self, data_items: list):
        checkpoints = []
        failed_items = []
        
        for i, item in enumerate(data_items):
            try:
                result = await self.process_single_item(item)
                
                # Create checkpoint every N items
                if i % self.checkpoint_interval == 0:
                    checkpoints.append(i)
                    await self.save_checkpoint(i, failed_items)
                
            except Exception as e:
                # Retry with exponential backoff
                retry_success = await self.retry_item(item, e)
                if not retry_success:
                    failed_items.append((item, str(e)))
        
        return {
            "processed": len(data_items) - len(failed_items),
            "failed": len(failed_items),
            "failure_details": failed_items
        }
    
    async def retry_item(self, item, original_error):
        for attempt in range(self.retry_count):
            try:
                await asyncio.sleep(self.backoff_factor ** attempt)
                await self.process_single_item(item)
                return True
            except Exception as e:
                if attempt == self.retry_count - 1:
                    logger.error(f"Final retry failed for item {item}: {e}")
                    return False
        return False
```

### Custom Data Processors
```python
# Create custom processors for different data types
class CustomDataProcessor:
    def __init__(self, processor_type: str):
        self.processor_type = processor_type
        self.processors = {
            "ticket": self.process_ticket,
            "conversation": self.process_conversation,
            "article": self.process_article,
            "attachment": self.process_attachment
        }
    
    async def process(self, data: dict, context: dict = None):
        processor = self.processors.get(self.processor_type)
        if not processor:
            raise ValueError(f"Unknown processor type: {self.processor_type}")
        
        return await processor(data, context)
    
    async def process_ticket(self, ticket_data: dict, context: dict):
        # Custom ticket processing logic
        normalized = self.normalize_ticket(ticket_data)
        enriched = await self.enrich_with_context(normalized, context)
        return enriched
    
    async def process_conversation(self, conv_data: dict, context: dict):
        # Custom conversation processing logic
        filtered = self.filter_conversation(conv_data)
        summarized = await self.summarize_if_enabled(filtered)
        return summarized
```

---

*This worktree focuses exclusively on data pipeline and ingestion operations. For vector storage, use the vector-db worktree. For LLM processing, use the llm-management worktree.*
