# AI Contact Center OS - MVP Day 1 Structure

**Generated**: 2025-10-31
**Namespace**: mvp-day1-structure

## 📁 Generated Structure

### New Directories
```
project-a-spinoff/
├── agents/                    # 🆕 LangGraph agents
├── tests/                     # 🆕 pytest tests
│   ├── test_agents/
│   └── test_backend/
├── scripts/                   # 🆕 setup utilities
└── [existing backend, frontend, docs]
```

### Key Files Created

#### Configuration & Infrastructure
- `requirements.txt` - Unified Python dependencies (22 packages)
- `.env.example` - Environment variable template
- `docker-compose.yml` - Local development stack (FastAPI, Qdrant, PostgreSQL, Redis)
- `Dockerfile` - Container image definition

#### Backend Updates (`backend/`)
```
backend/
├── config.py              # Pydantic settings management
├── main.py                # FastAPI app with router registration
├── routes/
│   ├── tickets.py         # Freshdesk ticket API
│   ├── assist.py          # AI assist endpoints
│   └── metrics.py         # KPI analytics
├── services/
│   ├── orchestrator.py    # LangGraph integration layer
│   ├── freshdesk.py       # Freshdesk API client
│   └── supabase_client.py # Supabase logging client
├── models/
│   ├── ticket.py          # TicketContext
│   ├── proposal.py        # AIProposal, SimilarCase, KBProcedure
│   └── feedback.py        # ApprovalLog, ApprovalStatus
└── utils/
    ├── logger.py          # Logging utilities
    └── validators.py      # Input validation
```

#### Agents Implementation (`agents/`)
```
agents/
├── orchestrator.py        # Workflow controller (LangGraph)
├── retriever.py           # Hybrid search (Qdrant + BM25 + re-ranker)
├── resolution.py          # Solution synthesis (LLM)
├── human.py               # Approval interface
├── state.py               # AgentState schema (TypedDict)
└── graph.py               # Compiled workflow
```

#### Tests (`tests/`)
```
tests/
├── conftest.py                      # Fixtures (ticket context, cases, KB)
├── test_agents/
│   └── test_orchestrator.py        # Orchestrator tests
└── test_backend/
    └── test_config.py               # Settings tests
```

#### Scripts (`scripts/`)
```
scripts/
├── setup.sh               # Development environment setup
└── init_db.py             # Supabase + Qdrant initialization
```

## 📦 Package Dependencies

### FastAPI Core
- fastapi, uvicorn, pydantic, pydantic-settings, python-dotenv

### LangGraph & LangChain
- langgraph, langchain-core, langchain-openai

### Vector DB & Search
- qdrant-client, sentence-transformers

### Database
- supabase, psycopg2-binary

### HTTP & Utilities
- httpx, python-multipart

### Testing & Development
- pytest, pytest-asyncio, pytest-cov, black, flake8, mypy

## 🔧 Environment Variables

Required in `.env`:
```env
# LLM
OPENAI_API_KEY=your_key

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key

# Freshdesk
FRESHDESK_DOMAIN=your-domain.freshdesk.com
FRESHDESK_API_KEY=your_key
```

## 🚀 Quick Start

```bash
# 1. Setup
./scripts/setup.sh

# 2. Update .env
cp .env.example .env
# Edit .env with your API keys

# 3. Start services
docker-compose up -d

# 4. Run backend
source venv/bin/activate
uvicorn backend.main:app --reload

# 5. Run tests
pytest tests/
```

## 📊 API Endpoints

### Health & Status
- `GET /` - API info
- `GET /health` - Health check

### Tickets
- `GET /api/tickets/{ticket_id}` - Get ticket details
- `GET /api/tickets/` - List tickets

### AI Assist
- `POST /api/assist/{ticket_id}/suggest` - Generate AI proposal
- `POST /api/assist/{ticket_id}/approve` - Process approval

### Metrics
- `GET /api/metrics/` - Get KPIs (approval rate, response time, etc.)

## 🔄 LangGraph Workflow

```
Input: Ticket Context
  ↓
Orchestrator → route_context
  ↓
Retriever → retrieve (similar_cases + kb_procedures)
  ↓
Resolution → generate_proposal (draft_response + field_updates)
  ↓
Output: AI Proposal
  ↓
Human Agent → approval (via FDK app)
  ↓
Execute: Freshdesk API PATCH + Supabase log
```

## 📝 Agent Responsibilities

### 1. Orchestrator Agent
- Workflow control
- Routing logic
- Error handling
- Approval loop coordination

### 2. Retriever Agent
- Structured query building (LLM)
- Hybrid search (Dense + Sparse)
- Meta filtering (tenant, product, version)
- Re-ranking (Cross-Encoder)
- Time decay & boosting

### 3. Resolution Agent
- Similar case pattern analysis
- KB procedure application
- Draft response generation
- Field update proposals
- Justification with links

### 4. Human Agent
- FDK app UI rendering
- Approval feedback collection
- Freshdesk API execution
- Supabase logging

## 🗃️ Database Schema

### Supabase: `approval_logs`
```sql
CREATE TABLE approval_logs (
  id UUID PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  ticket_id TEXT NOT NULL,
  draft_response TEXT,
  final_response TEXT,
  field_updates JSONB,
  approval_status TEXT CHECK (approval_status IN ('approved','modified','rejected')),
  agent_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Qdrant Collections
- `similar_cases` - Ticket embeddings (multi-vector)
- `kb_procedures` - KB document embeddings

## ✅ Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Directory structure | ✅ Complete | All folders created |
| Configuration | ✅ Complete | config.py, .env.example |
| Backend routes | ✅ Skeleton | 501 Not Implemented |
| Backend services | ✅ Skeleton | Integration pending |
| Backend models | ✅ Complete | Pydantic schemas |
| Agents | ✅ Skeleton | TODO: LLM/Search integration |
| Tests | ✅ Skeleton | Basic fixtures |
| Docker | ✅ Complete | docker-compose.yml |
| Documentation | ✅ Complete | AGENTS.md, SPECIFICATION |

## 🎯 Next Steps (Week 1)

1. **Retriever Implementation**
   - Qdrant client setup
   - BM25 integration (OpenSearch/pg_trgm)
   - Re-ranker model (jina-reranker-v2)
   - Query builder (LLM)

2. **Resolution Implementation**
   - LLM client (OpenAI/Anthropic)
   - Prompt templates
   - Response synthesis
   - Field extraction

3. **Human Agent**
   - FDK app UI components
   - Approval API endpoints
   - Freshdesk API integration
   - Supabase logging

4. **Orchestrator**
   - LangGraph graph completion
   - Error handling
   - Retry logic
   - Approval loop

5. **Testing**
   - Unit tests for agents
   - Integration tests for API
   - E2E workflow tests

## 📚 Reference Documents

- [AGENTS.md](./AGENTS.md) - Agent architecture details
- [SPECIFICATION-mvp-structure.md](./SPECIFICATION-mvp-structure.md) - Full specification
- [README.md](../README.md) - Project overview
- [API.md](./API.md) - API documentation (TODO)

---

**Status**: MVP structure complete, ready for implementation
**Next**: Implement Retriever Agent (Qdrant + BM25)
