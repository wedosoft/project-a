# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG-based Freshdesk Custom App built with FastAPI backend and Freshdesk FDK frontend. The system provides AI-powered customer support assistance through natural language processing, vector database search, and multi-LLM routing capabilities.

**Architecture**: Vector DB-only architecture with RESTful streaming for real-time ticket search and analysis.

## Development Guidelines

- python을 실행할 때는 반드시 backend/venv에서 작업을 해주세요.

## Key Development Commands

### Backend Development (Python FastAPI)

**Virtual Environment Setup**:
```bash
# Create and activate virtual environment (required for Python work)
cd backend
python -m venv venv
source venv/bin/activate  # On Mac/Linux
# or: venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

**Running the Backend**:
```bash
cd backend
python api/main.py
# or: uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Testing**:
```bash
# Run backend tests (from project root)
pytest

# Run specific test files
pytest backend/tests/test_specific.py

# Run with coverage
pytest --cov=backend/core --cov-report=html
```

**Linting and Code Quality**:
```bash
# Check code style (if available)
cd backend && python -m flake8 .
cd backend && python -m black --check .
```

**Docker Environment**:
```bash
cd backend
docker-compose up -d        # Start services
docker logs -f project-a    # View logs
docker-compose down         # Stop services
```

### Frontend Development (Freshdesk FDK)

**FDK Commands**:
```bash
cd frontend
fdk run          # Start development server
fdk validate     # Validate app structure
fdk pack         # Package for deployment
```

**Frontend Testing**:
```bash
cd frontend
npm test                # Run Jest tests
npm run test:coverage   # Run with coverage
npm run lint            # ESLint code check
npm run format          # Prettier formatting
```

**Quality Checks**:
```bash
cd frontend
npm run validate        # Full validation (lint + test)
npm run docs:generate   # Generate JSDoc documentation
```

## Architecture Overview

### Backend Structure (FastAPI + IoC Container)
```
backend/
├── api/                    # FastAPI routes and main application
│   ├── main.py            # Application entry point with lifespan management
│   ├── routes/            # API endpoint modules
│   └── models/            # Pydantic request/response models
├── core/                  # Core business logic
│   ├── container.py       # IoC container for dependency injection
│   ├── llm/              # Multi-LLM management system
│   ├── search/           # Vector search and retrieval
│   ├── database/         # Qdrant vector DB and PostgreSQL
│   ├── platforms/        # Freshdesk API integration
│   └── ingest/           # Data collection and processing
└── requirements.txt       # Python dependencies
```

### Frontend Structure (Freshdesk FDK)
```
frontend/
├── manifest.json          # FDK app configuration
├── app/
│   ├── index.html         # Main application UI
│   ├── scripts/
│   │   ├── app.js         # Main application logic
│   │   └── utils.js       # Utility functions
│   └── styles/
└── config/
    ├── iparams.json       # Installation parameters
    └── requests.json      # OAuth and request permissions
```

### Key Architectural Patterns
- **IoC Container**: Dependency injection pattern for loose coupling
- **Multi-LLM Routing**: Supports OpenAI, Anthropic Claude, Google Gemini
- **Vector-First Architecture**: All data stored in Qdrant with rich metadata
- **RESTful Streaming**: Server-sent events for real-time responses
- **Constitutional AI**: Anthropic prompt engineering for quality responses

## Development Workflows

### Adding New API Endpoints
1. Create route module in `backend/api/routes/`
2. Define Pydantic models in `backend/api/models/`
3. Implement business logic in appropriate `backend/core/` module
4. Register route in `backend/api/main.py`
5. Add tests in `backend/tests/`

### Frontend Feature Development
1. Update UI in `frontend/app/index.html`
2. Implement logic in `frontend/app/scripts/app.js`
3. Add API integration with backend endpoints
4. Write tests in `frontend/tests/`
5. Validate with `fdk validate`

### Adding New LLM Providers
1. Create provider class in `backend/core/llm/providers/`
2. Implement base provider interface
3. Register in `backend/core/llm/registry.py`
4. Update environment configuration
5. Add integration tests

## Environment Configuration

**Required Environment Variables**:
```bash
# Core Platform
FRESHDESK_DOMAIN=yourcompany.freshdesk.com
FRESHDESK_API_KEY=your_api_key
TENANT_ID=your_company_id

# Vector Database
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_api_key

# LLM APIs
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key

# Model Configuration (per use case)
REALTIME_LLM_PROVIDER=openai
REALTIME_LLM_MODEL=gpt-4-turbo
BATCH_LLM_PROVIDER=anthropic
BATCH_LLM_MODEL=claude-3-haiku-20240307
```

## Testing Strategy

**Backend Testing**:
- Unit tests with pytest
- API integration tests
- Vector database tests with test data
- Multi-LLM provider mocking

**Frontend Testing**:
- Jest unit tests for utility functions
- FDK integration testing
- UI component testing
- API communication testing

**Performance Testing**:
- Load testing for API endpoints
- Vector search performance benchmarks
- Memory usage monitoring
- Response time optimization

## Data Processing Pipeline

### Freshdesk Data Ingestion
1. **Collection**: Fetch tickets, KB articles, contacts via Freshdesk API
2. **Processing**: Text extraction, metadata enrichment, chunking
3. **Embedding**: Generate vectors using OpenAI text-embedding-3-small
4. **Storage**: Store in Qdrant with comprehensive metadata
5. **Indexing**: Create searchable indexes for efficient retrieval

### Real-time Query Processing
1. **Intent Analysis**: Classify user query type (search, summary, action)
2. **Vector Search**: Find relevant documents using semantic similarity
3. **Context Building**: Assemble relevant context for LLM
4. **Response Generation**: Route to appropriate LLM provider
5. **Streaming**: Send real-time response chunks to frontend

## Key Integration Points

### Freshdesk FDK Integration
- **Location**: Ticket top navigation
- **Events**: Ticket create/update handlers
- **Interface**: Modal and notification API
- **Permissions**: Ticket read, contact info, KB access

### Vector Database (Qdrant)
- **Collections**: Separate for tickets, KB articles, conversations
- **Metadata**: Rich filtering by type, status, date, customer
- **Search**: Hybrid keyword + semantic search
- **Scalability**: Cloud-hosted with API key authentication

### Multi-LLM System
- **Providers**: OpenAI, Anthropic, Google Gemini
- **Routing**: Use case specific model selection
- **Fallback**: Automatic provider switching on failure
- **Caching**: Response caching for common queries

## Performance Considerations

### Backend Optimizations
- Async/await for all I/O operations
- Connection pooling for external APIs
- Response caching with Redis
- Vector search result pagination
- Streaming responses for large payloads

### Frontend Optimizations
- Lazy loading of tab content
- Debounced API calls
- Local caching of frequently accessed data
- Efficient DOM updates
- Progressive rendering of search results

## Security Practices

### API Security
- Tenant-based data isolation
- API key validation on all requests
- Rate limiting on external API calls
- Input sanitization and validation
- Secure environment variable management

### Data Protection
- No sensitive data in logs
- Encrypted API key storage
- Secure inter-service communication
- Regular security dependency updates
- GDPR compliance for customer data

## Common Troubleshooting

### Backend Issues
- **Import Errors**: Ensure virtual environment is activated and in `backend/` directory
- **API Failures**: Check environment variables and external service status
- **Vector Search**: Verify Qdrant connection and collection existence
- **LLM Errors**: Validate API keys and model availability

### Frontend Issues
- **FDK Errors**: Validate manifest.json and run `fdk validate`
- **API Connectivity**: Check backend URL configuration
- **UI Rendering**: Verify CSS and JavaScript loading
- **Modal Issues**: Check FDK client initialization

### Development Environment
- **Docker Issues**: Ensure Docker daemon is running and ports are available
- **Dependencies**: Use exact versions specified in requirements.txt and package.json
- **Environment Variables**: Verify all required variables are set
- **Virtual Environment**: Always activate before Python development
```