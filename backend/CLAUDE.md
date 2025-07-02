# Backend API Core - CLAUDE.md

## 🎯 Context & Purpose

This is the **Backend API Core** worktree focused on the FastAPI-based Python backend for Copilot Canvas. This system provides RAG (Retrieval-Augmented Generation) capabilities for Freshdesk ticket analysis and knowledge base integration.

**Primary Focus Areas:**
- FastAPI application with IoC container pattern
- Vector Database (Qdrant) integration and management
- LLM orchestration and response generation
- Multi-tenant data ingestion pipeline
- Real-time streaming and async processing

## 🏗️ Core Architecture

### System Overview
```
FastAPI Backend → SQLAlchemy ORM → PostgreSQL/SQLite
     ↓
Qdrant (Vector DB) + Redis (Cache) + LLM Providers
```

### Core Components

1. **API Layer** (`api/`)
   - FastAPI application with IoC container for dependency injection
   - Multiple routers: init, query, reply, ingest, health, metrics
   - Middleware for CORS, performance monitoring, error handling

2. **Vector Database** (`core/database/vectordb.py`)
   - Abstract interface with Qdrant adapter implementation
   - Multi-tenant support with complete data isolation
   - Platform-neutral 3-tuple ID system: `(tenant_id, platform, original_id)`

3. **LLM Management** (`core/llm/manager.py`)
   - Centralized management of multiple LLM providers
   - Use-case based routing (ticket_view, ticket_similar, summary)
   - Response and embedding caching with TTL

4. **Data Processing** (`core/ingest/`)
   - Supports vector-only and hybrid (SQL+Vector) modes
   - Batch processing with progress tracking
   - Attachment processing with OCR support

### Key Design Patterns

- **Multi-tenancy**: Complete data isolation by tenant_id
- **Async Processing**: All I/O operations are async for better performance  
- **Dependency Injection**: IoC container pattern for better testability
- **Adapter Pattern**: Platform-agnostic integrations (Freshdesk, future platforms)
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
