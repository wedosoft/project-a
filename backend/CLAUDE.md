# Backend API Core - CLAUDE.md

## 🎯 컨텍스트 & 목적

이 디렉토리는 **Backend API Core**로 Copilot Canvas의 FastAPI 기반 Python 백엔드를 담당합니다. RAG (Retrieval-Augmented Generation) 기능을 통한 Freshdesk 티켓 분석과 지식베이스 통합을 제공합니다.

**주요 영역:**
- IoC 컨테이너 패턴을 활용한 FastAPI 애플리케이션
- 벡터 데이터베이스 (Qdrant) 통합 및 관리
- LLM 오케스트레이션 및 응답 생성
- 멀티테넌트 데이터 수집 파이프라인
- 실시간 스트리밍 및 비동기 처리

## 🏗️ 디렉토리 구조

```
backend/
├── api/                    # FastAPI 애플리케이션 레이어
│   ├── main.py            # 메인 애플리케이션 진입점
│   ├── routers/           # API 라우터들
│   ├── middleware/        # 커스텀 미들웨어
│   └── container.py       # IoC 컨테이너 설정
├── core/                  # 핵심 비즈니스 로직
│   ├── database/          # 데이터베이스 추상화 레이어
│   ├── llm/              # LLM 관리 및 통합
│   ├── ingest/           # 데이터 수집 파이프라인
│   └── search/           # 검색 엔진 로직
├── platforms/            # 플랫폼별 통합
│   └── freshdesk/        # Freshdesk API 통합
├── tests/               # 테스트 스위트
└── config/              # 설정 파일들
```

## 🚀 개발 명령어

### 환경 설정
```bash
# 가상환경 활성화 (필수)
source venv/bin/activate

# 개발 서버 시작
python -m api.main

# Docker 개발 환경
docker-compose up -d

# 테스트 실행
pytest tests/

# 특정 컴포넌트 테스트
python tests/test_vectordb.py
python tests/test_llm_simple.py
```

### API 엔드포인트 테스트
```bash
# /init 엔드포인트 테스트
curl -X GET "http://localhost:8000/init/12345" \
     -H "X-Freshdesk-Domain: $FRESHDESK_DOMAIN.freshdesk.com" \
     -H "X-Freshdesk-API-Key: $FRESHDESK_API_KEY"

# 헬스체크
curl http://localhost:8000/health

# 메트릭 확인
curl http://localhost:8000/metrics
```

## 🔧 핵심 컴포넌트

### 1. API 레이어 (`api/`)
IoC 컨테이너를 활용한 의존성 주입으로 테스트 가능한 구조를 제공합니다.

**주요 라우터:**
- `/init` - 티켓 초기화 및 분석
- `/query` - 벡터 검색 쿼리
- `/reply` - AI 응답 생성
- `/ingest` - 데이터 수집 관리
- `/health` - 시스템 상태 확인
- `/metrics` - 성능 메트릭

### 2. 벡터 데이터베이스 (`core/database/`)
```python
# 사용 예시
from core.database.vectordb import get_vector_db

async def search_documents(query: str, tenant_id: str):
    vector_db = get_vector_db()
    results = await vector_db.search(
        collection_name="documents",
        query_text=query,
        filters={"tenant_id": tenant_id},
        limit=10
    )
    return results
```

### 3. LLM 관리 (`core/llm/`)
```python
# 사용 예시
from core.llm.manager import LLMManager

async def analyze_ticket(ticket_data: dict):
    llm_manager = LLMManager()
    analysis = await llm_manager.generate_response(
        query=f"분석: {ticket_data['subject']}",
        context=ticket_data['description'],
        use_case="ticket_view"
    )
    return analysis
```

### 4. 데이터 수집 (`core/ingest/`)
```python
# 사용 예시
from core.ingest.manager import IngestionManager

async def ingest_freshdesk_data(tenant_id: str):
    manager = IngestionManager()
    await manager.ingest_platform_data(
        platform="freshdesk",
        tenant_id=tenant_id,
        config={"include_attachments": True}
    )
```

## ⚠️ 중요 사항

### 개발 환경
- **필수**: Python 명령어는 반드시 `backend/` 디렉토리에서 가상환경 활성화 후 실행
- **디버깅**: VS Code의 Python 디버거 또는 내장 breakpoint() 함수 활용
- **로깅**: structlog를 통한 구조화된 로깅 사용

### 성능 최적화
- 모든 I/O 작업은 async/await 패턴 사용
- LLM API 호출에 타임아웃 및 재시도 로직 구현
- 벡터 검색 결과 캐싱으로 응답 속도 개선
- Prometheus 메트릭을 통한 성능 모니터링

### 보안 고려사항
- API 키 및 민감 정보는 환경변수로 관리
- 모든 외부 입력에 대한 검증 필수
- 멀티테넌트 데이터 격리 철저히 준수

---

*상세한 컴포넌트별 가이드는 각 `core/*/CLAUDE.md` 파일을 참조하세요.*
- **Repository Pattern**: Clean separation between business logic and data access

## 🚀 Development Commands

### Environment Setup
```bash
# Virtual environment setup (first time only)
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Daily development workflow
source venv/bin/activate  # Always activate before running Python code

# Alternative activation script (if available)
./activate.sh
```

**⚠️ CRITICAL**: Always run Python commands from the `backend/` directory with the virtual environment activated.

### Running the Application
```bash
# Development server with auto-reload
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Docker environment
docker-compose up -d

# View logs
docker logs -f project-a-backend
```

### Testing & Debugging
```bash
# Run specific tests
python -m pytest tests/test_ingest.py -v

# Test vector DB connection
python -c "from core.database.vectordb import get_vector_db_adapter; print('✅ Vector DB OK')"

# Test ORM models
python -c "from core.database.models import Ticket; print('✅ ORM Models OK')"

# Integration test
python test_orm_integration.py
```

## 🔧 Key Environment Variables

```bash
# Database Configuration
USE_ORM=true                    # Enable ORM mode
DATABASE_URL=sqlite:///dev.db   # Database connection

# Vector DB Configuration  
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=documents

# Multi-tenant Configuration
DEFAULT_TENANT_ID=wedosoft
PLATFORM=freshdesk

# LLM Configuration
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
LLM_CACHE_TTL=3600

# Performance
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
```

## 📁 Directory Structure

```
backend/
├── api/                    # FastAPI application
│   ├── main.py            # Application entry point
│   ├── routes/            # API route handlers
│   └── middleware/        # Custom middleware
├── core/                  # Core business logic
│   ├── database/          # Database adapters & models
│   ├── llm/              # LLM management
│   ├── ingest/           # Data ingestion pipeline
│   ├── search/           # Vector search & embeddings
│   ├── platforms/        # Platform adapters (Freshdesk, etc.)
│   └── container.py      # IoC container
├── config/               # Configuration files
├── tests/               # Test suites
└── docs/               # Backend-specific documentation
```

## 🔍 Common Tasks

### Adding New API Endpoints
```bash
# 1. Create route handler in api/routes/
# 2. Register in api/main.py
# 3. Add tests in tests/
# 4. Update OpenAPI documentation
```

### Vector DB Operations
```bash
# Check collection status
python -c "from core.database.vectordb import get_vector_db_adapter; adapter = get_vector_db_adapter(); print(adapter.get_collection_info())"

# Rebuild vector index
python -c "from core.ingest.processor import rebuild_vector_index; rebuild_vector_index()"
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Check migration status
alembic current
```

## 🚨 Important Notes

### Multi-tenant Security
- **NEVER** create queries without tenant_id filtering
- Always validate tenant access in API endpoints
- Use platform-neutral ID format: `{tenant_id}_{platform}_{original_id}`

### Performance Considerations
- Vector searches are cached with Redis (default 1 hour TTL)
- LLM responses are cached to reduce API costs
- Use async/await for all I/O operations
- Batch processing for large data ingestion

### Error Handling
- All exceptions are caught by custom error handling middleware
- Structured logging with tenant_id context
- Graceful degradation when external services are unavailable

## 🔗 Integration Points

### Frontend FDK Integration
```javascript
// Frontend calls this backend via:
const response = await client.request.invoke('backendApi', {
  url: '/api/init/{{ticket_id}}',
  headers: {
    'X-Tenant-ID': tenantId,
    'X-Platform': 'freshdesk'
  }
});
```

### External Services
- **Freshdesk API**: Platform adapter handles authentication and rate limiting
- **Qdrant Cloud**: Vector database for similarity search
- **OpenAI/Anthropic**: LLM providers for text generation
- **Redis**: Caching layer for performance optimization

## 📚 Key Files to Know

- `api/main.py` - Application entry point and configuration
- `core/container.py` - Dependency injection container
- `core/database/vectordb.py` - Vector database interface
- `core/llm/manager.py` - LLM provider management
- `core/ingest/processor.py` - Main data ingestion pipeline
- `core/platforms/freshdesk/adapter.py` - Freshdesk integration
- `.env` - Environment configuration (see `.env-example`)

## 🔄 Development Workflow

1. **Start Development**: `source venv/bin/activate && python -m uvicorn api.main:app --reload`
2. **Make Changes**: Edit files in `core/` or `api/`
3. **Test**: Run relevant tests in `tests/`
4. **Debug**: Use structured logging and built-in error handling
5. **Deploy**: Docker build and deploy to cloud environment

---

*This worktree focuses exclusively on backend API development. For frontend development, switch to the frontend worktree. For documentation updates, use the docs/instructions worktree.*
