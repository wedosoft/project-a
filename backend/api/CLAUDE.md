# Backend API & Core - CLAUDE.md

## 🎯 Context & Purpose

This is the **Backend API & Core** worktree focused on the FastAPI application layer, routing, middleware, and dependency injection container. This handles all HTTP endpoints and request/response management for Copilot Canvas.

**Primary Focus Areas:**
- FastAPI route handlers and middleware
- IoC container and dependency injection patterns
- Request validation and response formatting
- CORS, authentication, and security middleware
- Health checks and monitoring endpoints

## 🏗️ API Architecture

### System Overview
```
Client Request → Middleware → Route Handler → Core Services → Response
      ↓              ↓             ↓             ↓            ↓
   CORS/Auth    Validation    Business Logic   Database    JSON/Streaming
```

### Core Components

1. **Main Application** (`main.py`)
   - FastAPI app initialization
   - Middleware registration
   - Route mounting
   - Global error handling

2. **Route Handlers** (`routes/`)
   - **init.py**: Ticket initialization and analysis
   - **query.py**: Agent query processing
   - **reply.py**: Reply suggestion generation
   - **ingest.py**: Data ingestion endpoints
   - **health.py**: Health check endpoints
   - **metrics.py**: Performance monitoring

3. **Middleware** (`middleware/`)
   - CORS configuration
   - Request/response logging
   - Performance monitoring
   - Error handling

4. **Services** (`services/`)
   - Job management
   - Background task coordination
   - Service layer abstractions

### Key Design Patterns

- **Dependency Injection**: IoC container pattern for loose coupling
- **Middleware Pipeline**: Request/response processing chain
- **Router Pattern**: Modular endpoint organization
- **Service Layer**: Business logic abstraction
- **Error Boundary**: Centralized exception handling

## 🚀 Development Commands

### Environment Setup
```bash
# Virtual environment setup (first time only)
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**⚠️ CRITICAL**: Always run Python commands from the `backend/` directory with the virtual environment activated.

### Running the Application
```bash
# Development server with auto-reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production server
uvicorn api.main:app --host 0.0.0.0 --port 8000

# With specific workers
uvicorn api.main:app --workers 4 --host 0.0.0.0 --port 8000
```

### Testing & Debugging
```bash
# Test specific route
python -c "from api.routes.health import router; print('✅ Health Route OK')"

# Test IoC container
python -c "from core.container import get_container; print('✅ Container OK')"

# Test specific endpoint (requires running server)
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/init/123 -H "X-Tenant-ID: test"
```

## 🔧 Key Environment Variables

```bash
# Server Configuration
HOST=localhost
PORT=8000
ENVIRONMENT=development
DEBUG=false

# Multi-tenant Configuration
DEFAULT_TENANT_ID=wedosoft
PLATFORM=freshdesk

# API Performance
API_RATE_LIMIT_GLOBAL=1000
CONNECTION_POOL_SIZE=20
QUERY_TIMEOUT=30

# Security
JWT_SECRET=your-jwt-secret-key
SESSION_TIMEOUT_HOURS=24
```

## 📁 Directory Structure

```
api/
├── main.py                # FastAPI application entry point
├── middleware/            # Custom middleware
│   ├── __init__.py
│   ├── cors.py           # CORS configuration
│   ├── logging.py        # Request/response logging
│   └── error_handler.py  # Global error handling
├── routes/               # API route handlers
│   ├── __init__.py       # Route aggregation
│   ├── init.py          # Ticket initialization endpoints
│   ├── query.py         # Agent query endpoints
│   ├── reply.py         # Reply suggestion endpoints
│   ├── ingest.py        # Data ingestion endpoints
│   ├── health.py        # Health check endpoints
│   └── metrics.py       # Performance monitoring
├── services/            # Service layer
│   ├── __init__.py
│   └── job_manager.py   # Background job management
└── dependencies.py      # Dependency injection helpers
```

## 🔍 Common Tasks

### Adding New Endpoints
```python
# 1. Create route handler in routes/
from fastapi import APIRouter, Depends
from core.container import get_container

router = APIRouter(prefix="/api/new-feature", tags=["new-feature"])

@router.post("/action")
async def new_action(
    data: RequestModel,
    container = Depends(get_container)
):
    service = container.get_service("new_service")
    result = await service.process(data)
    return {"status": "success", "data": result}

# 2. Register in routes/__init__.py
from .new_feature import router as new_feature_router
# Add to routers list

# 3. Test the endpoint
curl -X POST http://localhost:8000/api/new-feature/action \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: test" \
  -d '{"key": "value"}'
```

### Dependency Injection Usage
```python
# Using container in route handlers
from core.container import get_container

@router.get("/example")
async def example_endpoint(container = Depends(get_container)):
    # Get services from container
    llm_manager = container.get_service("llm_manager")
    vector_db = container.get_service("vector_db")
    
    # Use services
    result = await llm_manager.generate_response(query)
    return result

# Registering new services in container
from core.container import Container

container = Container()
container.register_service("my_service", MyService())
```

### Middleware Development
```python
# Custom middleware example
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pre-processing
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Post-processing
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

# Register in main.py
app.add_middleware(CustomMiddleware)
```

## 🎯 API Endpoints Overview

### Core Endpoints
- **POST `/api/init/{ticket_id}`**: Initialize ticket analysis
- **POST `/api/query`**: Process agent queries
- **POST `/api/reply`**: Generate reply suggestions
- **GET `/api/health`**: Health check
- **GET `/api/metrics`**: Performance metrics

### Data Management
- **POST `/api/ingest/start`**: Start data ingestion
- **GET `/api/ingest/status`**: Check ingestion status
- **POST `/api/ingest/reset`**: Reset vector database

### Request/Response Format
```python
# Standard request headers
{
  "X-Tenant-ID": "wedosoft",
  "X-Platform": "freshdesk",
  "Content-Type": "application/json"
}

# Standard response format
{
  "status": "success|error",
  "data": {...},
  "message": "Optional message",
  "request_id": "uuid",
  "timestamp": "2025-07-02T10:00:00Z"
}
```

## 🚨 Important Notes

### Security & Authentication
- All endpoints require `X-Tenant-ID` header
- JWT authentication for sensitive operations
- CORS configured for Freshdesk domains
- Rate limiting applied globally

### Performance Considerations
- All I/O operations use async/await
- Connection pooling for database connections
- Response streaming for large data
- Request timeout configuration

### Error Handling
- Global exception handler catches all errors
- Structured error responses with request IDs
- Detailed logging with tenant context
- Graceful degradation patterns

## 🔗 Integration Points

### Core Services Integration
```python
# Typical service usage in routes
from core.llm.manager import LLMManager
from core.database.vectordb import vector_db
from core.platforms.factory import PlatformFactory

# Service dependencies are injected via container
llm_manager = container.get_service("llm_manager")
vector_db = container.get_service("vector_db")
platform_adapter = container.get_service("platform_adapter")
```

### Frontend Integration
- FDK apps call these endpoints via configured proxy
- Real-time updates through WebSocket connections
- Streaming responses for better UX
- Error propagation to frontend UI

### External Services
- Platform APIs (Freshdesk) via adapter pattern
- Vector database through abstraction layer
- LLM providers through manager service
- Caching layer through Redis integration

## 📚 Key Files to Know

- `main.py` - Application entry point and configuration
- `routes/__init__.py` - Central route registration
- `routes/init.py` - Main ticket analysis endpoint
- `routes/query.py` - Agent query processing
- `middleware/error_handler.py` - Global error handling
- `services/job_manager.py` - Background job coordination
- `../core/container.py` - IoC container (shared with core)

## 🔄 Development Workflow

1. **Start Development**: `uvicorn api.main:app --reload`
2. **Add New Feature**: Create route handler + register in `__init__.py`
3. **Test Endpoint**: Use curl or Postman for API testing
4. **Check Logs**: Monitor console output for errors
5. **Performance Check**: Use `/api/metrics` endpoint
6. **Deploy**: Package with Docker or direct deployment

## 🚀 Advanced Features

### Streaming Responses
```python
from fastapi.responses import StreamingResponse

@router.post("/stream")
async def stream_response(request: RequestModel):
    async def generate():
        for chunk in process_data_stream(request):
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/plain"
    )
```

### Background Jobs
```python
from api.services.job_manager import job_manager

@router.post("/background-task")
async def start_background_task(request: RequestModel):
    job_id = await job_manager.start_job("data_processing", request.dict())
    return {"job_id": job_id, "status": "started"}

@router.get("/job/{job_id}/status")
async def get_job_status(job_id: str):
    status = await job_manager.get_job_status(job_id)
    return {"job_id": job_id, "status": status}
```

### WebSocket Support
```python
from fastapi import WebSocket

@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            # Process real-time data
            response = await process_realtime_data(data, tenant_id)
            await websocket.send_text(json.dumps(response))
    except Exception as e:
        await websocket.close()
```

---

*This worktree focuses exclusively on API layer development. For core business logic, use the appropriate specialized worktrees (vector-db, llm-management, data-pipeline, database-orm).*
