# POC Implementation Plan - AI Assistant Workflow

## Overview
Implement a complete AI Assistant workflow with agent orchestration visualization, tenant-based embedding mode switching, and approval/refinement loops.

## Architecture Summary

```
Frontend (FDK App)
├── index.html (UI with progress tracker, references, proposals, chat)
└── scripts/app.js (streaming handler, approval actions)
    ↓ HTTP Streaming
Backend API
├── routes/assist.py (analyze, approve, refine endpoints)
├── repositories/tenant_repository.py (tenant config management)
├── agents/resolver.py (direct analysis mode)
└── migrations/002_tenant_configs.sql
    ↓ Database
Supabase
└── tenant_configs table
```

## Component Breakdown

### 1. Frontend FDK App
**Location**: `frontend/app/`

**Files to create/modify**:
- `frontend/app/index.html` - Complete UI overhaul
- `frontend/app/scripts/app.js` - New streaming + approval logic
- `frontend/app/scripts/sse-client.js` - SSE connection manager with reconnect
- `frontend/app/styles/style.css` - Styles for progress tracker, chat

**Key Features**:
- ✅ Trigger button for ticket analysis
- ✅ Real-time orchestration progress (3-step tracker: Router → Retriever → Resolution)
- ✅ Reference display (similar cases, KB articles)
- ✅ AI proposal with reasoning, draft response, field updates, confidence
- ✅ Approval actions (approve, reject, refine)
- ✅ Chat interface for refinement requests
- ✅ **NEW**: SSE reconnection logic with exponential backoff
- ✅ **NEW**: Heartbeat monitoring (30s timeout)
- ✅ **NEW**: HMAC signature for API authentication

**Streaming Events**:
```javascript
{
  type: "router_decision",
  decision: "retrieve_cases" | "propose_solution_direct",
  reasoning: string,
  embedding_mode: boolean
}

{
  type: "retriever_start",
  mode: "embedding" | "kb"
}

{
  type: "retriever_results",
  results: {
    similar_cases: [...],  // PII-masked
    kb_articles: [...]
  }
}

{
  type: "retriever_fallback",  // NEW: 검색 실패 시
  reason: "no_results" | "qdrant_error" | "timeout",
  fallback_to: "direct_analysis"
}

{
  type: "resolution_start"
}

{
  type: "resolution_complete",
  proposal: {
    id: string,
    draft_response: string,
    field_updates: {},
    confidence: "high" | "medium" | "low",
    mode: "synthesis" | "direct" | "fallback",
    ...
  }
}

{
  type: "heartbeat"  // NEW: 30초마다
}

{
  type: "error",
  message: string,
  recoverable: boolean
}
```

**Dependencies**:
- FDK client API for ticket data, field updates, editor insertion
- Backend streaming endpoint
- WebSocket or SSE for real-time updates

**Potential Issues**:
- ❗ CORS configuration for streaming
- ❗ FDK API limitations for field updates
- ❗ Error handling for network failures
- ❗ UI responsiveness during long operations

---

### 2. Backend API Routes
**Location**: `backend/routes/assist.py`

**Endpoints**:

#### POST `/api/v1/assist/analyze`
- **Input**: `{ ticket_id, stream_progress: true }`
- **Headers**:
  - `X-Tenant-ID`, `X-Platform`
  - `X-Signature` (HMAC-SHA256 of body + timestamp)
  - `X-Timestamp` (Unix timestamp for replay protection)
- **Response**: SSE stream with progress events
- **Logic**:
  1. **NEW**: Validate HMAC signature (prevent unauthorized access)
  2. Fetch tenant config (embedding_enabled)
  3. Fetch ticket + conversations from Freshdesk
  4. **NEW**: Check token count, apply chunking if needed
  5. Create initial AgentState
  6. Execute workflow with streaming callbacks + fallback
  7. **NEW**: Send heartbeat every 30s
  8. Emit events: router_decision → retriever_* (with fallback) → resolution_*

#### POST `/api/v1/assist/approve`
- **Input**: `{ ticket_id, proposal_id, action: "approve" | "reject", final_response? }`
- **Headers**: Same authentication as above
- **Logic**:
  1. **NEW**: Validate signature
  2. **NEW**: Fetch proposal from DB (not in-memory)
  3. **NEW**: Update proposal status (draft → approved/rejected)
  4. Save approval log to database
  5. If approved: Update Freshdesk ticket fields **with retry logic**
  6. **NEW**: Validate field_updates against JSON schema
  7. Return field_updates + final_response for FDK insertion

#### POST `/api/v1/assist/refine`
- **Input**: `{ ticket_id, proposal_id, refinement_request }`
- **Headers**: Same authentication
- **Logic**:
  1. **NEW**: Validate signature
  2. Fetch original proposal **from DB**
  3. Call LLM with refinement instructions
  4. **NEW**: Validate refined output against schema
  5. **NEW**: Update proposal in DB (create new version)
  6. Return refined_response

#### **NEW**: POST `/api/v1/admin/tenants`
- **Input**: `{ tenant_id, platform, config_updates }`
- **Headers**: Admin API Key
- **Logic**: Create or update tenant configuration

#### **NEW**: GET `/api/v1/admin/tenants/{tenant_id}`
- **Response**: Tenant configuration
- **Logic**: Fetch tenant config with caching

**Dependencies**:
- TenantRepository for config lookup
- FreshdeskService for ticket operations
- LLMService for refinement
- Workflow graph execution

**Potential Issues**:
- ❗ Streaming buffer issues (X-Accel-Buffering: no)
- ❗ Timeout for long-running workflows
- ❗ Error handling mid-stream
- ❗ Proposal storage/retrieval mechanism

---

### 3. Tenant Repository
**Location**: `backend/repositories/tenant_repository.py`

**Class**: `TenantRepository`
**Methods**:
- `get_config(tenant_id, platform) -> TenantConfig`
- Returns config or defaults if not found

**Model**: `TenantConfig`
```python
{
  tenant_id: str,
  platform: str,
  embedding_enabled: bool,
  analysis_depth: str,  # "full" | "summary" | "minimal"
  llm_max_tokens: int
}
```

**Dependencies**:
- Supabase client
- Settings for connection

**Potential Issues**:
- ❗ Caching strategy for frequently accessed configs
- ❗ Fallback behavior when DB is unavailable

---

### 4. Database Migration
**Location**: `backend/migrations/002_tenant_configs.sql`

**Schema 1: tenant_configs**
```sql
CREATE TABLE tenant_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    embedding_enabled BOOLEAN DEFAULT true,
    analysis_depth TEXT DEFAULT 'full',
    llm_max_tokens INTEGER DEFAULT 1500,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, platform)
);

CREATE INDEX idx_tenant_configs_lookup ON tenant_configs(tenant_id, platform);
```

**Schema 2: proposals (NEW)**
```sql
CREATE TABLE proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    proposal_version INTEGER DEFAULT 1,

    -- Proposal content
    draft_response TEXT NOT NULL,
    field_updates JSONB,
    reasoning TEXT,
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    mode TEXT CHECK (mode IN ('synthesis', 'direct', 'fallback')),

    -- References
    similar_cases JSONB,
    kb_references JSONB,

    -- Status tracking
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected', 'superseded')),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    rejection_reason TEXT,

    -- Metadata
    analysis_time_ms INTEGER,
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    FOREIGN KEY (tenant_id) REFERENCES tenant_configs(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_proposals_ticket ON proposals(ticket_id, created_at DESC);
CREATE INDEX idx_proposals_status ON proposals(tenant_id, status);
```

**Schema 3: approval_logs (for audit trail)**
```sql
CREATE TABLE approval_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES proposals(id),
    action TEXT NOT NULL CHECK (action IN ('approve', 'reject', 'refine')),
    agent_email TEXT,
    feedback TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_approval_logs_proposal ON approval_logs(proposal_id, created_at);
```

**Sample Data**:
- `demo-tenant` + `freshdesk` → embedding_enabled = true
- `privacy-tenant` + `freshdesk` → embedding_enabled = false

**Migration Notes**:
- ✅ Rollback script included
- ✅ RLS policies for tenant isolation
- ✅ Indexes for performance

---

### 5. Direct Analysis Agent
**Location**: `backend/agents/resolver.py`

**Function**: `propose_solution_direct(state: AgentState) -> AgentState`

**Logic**:
1. Extract ticket_context (subject, description, conversations)
2. **NEW**: Count tokens and check against limit
3. **NEW**: If tokens > limit, apply chunking strategy:
   - Keep subject + latest 5 conversations
   - Summarize older conversations
4. Concatenate full_content
5. Call LLM with direct analysis prompt (no retrieval)
6. **NEW**: Validate response against Pydantic schema
7. Parse response for draft_response + field_updates
8. **NEW**: Store proposal in DB (not in-memory)
9. Return proposal with mode="direct", confidence="low"

**Dependencies**:
- LLMService.analyze_ticket_direct()
- **NEW**: TokenCounter utility
- **NEW**: ChunkingService for long tickets
- **NEW**: ProposalRepository for DB storage

**Chunking Strategy**:
```python
def chunk_ticket(ticket_context, max_tokens=4000):
    """
    Keep recent context, summarize old context
    """
    subject = ticket_context['subject']
    conversations = ticket_context['conversations']

    # Keep last 5 conversations
    recent = conversations[-5:]

    # Summarize older ones
    if len(conversations) > 5:
        old = conversations[:-5]
        summary = summarize_conversations(old)
    else:
        summary = ""

    return {
        'subject': subject,
        'summary': summary,
        'recent_conversations': recent
    }
```

---

### 6. Workflow Event Streaming
**Location**: `backend/routes/assist.py` (helper function)

**Function**: `stream_workflow_events(workflow, initial_state)`

**Logic**:
1. Execute workflow nodes sequentially
2. After each node, yield SSE event
3. **NEW**: Send heartbeat every 30s
4. **NEW**: Handle retriever failures with fallback
5. **NEW**: Mask PII in all events
6. Handle errors gracefully with error events

**Event Sequence with Fallback**:
```
router_decision (embedding check)
  ↓ if embedding_mode
retriever_start
  ↓ try retrieval
retriever_results (similar_cases, kb_articles) ✅
  ↓ OR (on failure)
retriever_fallback (reason, fallback_to="direct_analysis") ⚠️
  ↓ continue to
resolution_start
resolution_complete (proposal)
```

**Heartbeat Implementation**:
```python
async def stream_with_heartbeat(events):
    last_heartbeat = time.time()

    async for event in events:
        yield event

        # Send heartbeat if >30s since last event
        if time.time() - last_heartbeat > 30:
            yield {"type": "heartbeat", "timestamp": time.time()}
            last_heartbeat = time.time()
```

**Error Handling**:
- Retriever errors → automatic fallback to direct analysis
- LLM errors → recoverable error event, allow retry
- DB errors → non-recoverable error, stop workflow

---

### 7. PII Masking Utility (NEW)
**Location**: `backend/utils/pii_masker.py`

**Function**: `mask_pii(text: str) -> str`

**Detection Rules**:
- Email addresses → `***@***.***`
- Phone numbers → `***-***-****`
- Credit card numbers → `****-****-****-****`
- SSN/주민번호 → `******`
- Custom patterns (names, addresses via NER)

**Implementation**:
```python
import re
from typing import Dict, Pattern

PII_PATTERNS: Dict[str, Pattern] = {
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'phone': re.compile(r'\b\d{3}[-.]?\d{3,4}[-.]?\d{4}\b'),
    'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    'card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
}

def mask_pii(text: str) -> str:
    """Mask PII in text"""
    for pii_type, pattern in PII_PATTERNS.items():
        if pii_type == 'email':
            text = pattern.sub('***@***.***', text)
        elif pii_type == 'phone':
            text = pattern.sub('***-***-****', text)
        # ... other patterns

    return text
```

**Usage**:
- Apply to all SSE events before sending
- Apply to similar_cases and kb_articles
- Store original (unmasked) in DB for audit

---

### 8. Authentication Middleware (NEW)
**Location**: `backend/middleware/auth.py`

**HMAC Signature Validation**:
```python
import hmac
import hashlib
import time
from fastapi import HTTPException, Header

SECRET_KEY = os.getenv("FDK_SIGNING_SECRET")

def verify_signature(
    body: bytes,
    timestamp: str,
    signature: str
) -> bool:
    """
    Verify HMAC-SHA256 signature
    """
    # Prevent replay attacks (5 min window)
    if abs(time.time() - int(timestamp)) > 300:
        raise HTTPException(401, "Request expired")

    # Compute expected signature
    message = f"{timestamp}.{body.decode()}"
    expected = hmac.new(
        SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected, signature)
```

**Middleware**:
```python
@app.middleware("http")
async def validate_request(request: Request, call_next):
    if request.url.path.startswith("/api/v1/assist"):
        body = await request.body()
        timestamp = request.headers.get("X-Timestamp")
        signature = request.headers.get("X-Signature")

        if not verify_signature(body, timestamp, signature):
            raise HTTPException(403, "Invalid signature")

    return await call_next(request)
```

**Frontend Integration**:
```javascript
// app.js
function signRequest(body) {
    const timestamp = Math.floor(Date.now() / 1000);
    const message = `${timestamp}.${JSON.stringify(body)}`;
    const signature = CryptoJS.HmacSHA256(message, SECRET_KEY).toString();

    return {
        'X-Timestamp': timestamp,
        'X-Signature': signature
    };
}
```

---

### 9. Tenant Repository Enhancement (NEW)
**Location**: `backend/repositories/tenant_repository.py`

**New Methods**:
```python
class TenantRepository:
    def __init__(self):
        self.client = create_client(...)
        self.cache = {}  # Simple in-memory cache

    async def get_config(self, tenant_id, platform) -> TenantConfig:
        """Get config with caching"""
        cache_key = f"{tenant_id}:{platform}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        config = await self._fetch_from_db(tenant_id, platform)
        self.cache[cache_key] = config
        return config

    async def update_config(
        self,
        tenant_id: str,
        platform: str,
        updates: Dict[str, Any]
    ) -> TenantConfig:
        """Update tenant configuration"""
        response = self.client.table("tenant_configs").update(
            updates
        ).eq("tenant_id", tenant_id).eq("platform", platform).execute()

        # Invalidate cache
        cache_key = f"{tenant_id}:{platform}"
        if cache_key in self.cache:
            del self.cache[cache_key]

        return TenantConfig(response.data[0])

    async def create_config(
        self,
        tenant_id: str,
        platform: str,
        config: Dict[str, Any]
    ) -> TenantConfig:
        """Create new tenant configuration"""
        response = self.client.table("tenant_configs").insert({
            "tenant_id": tenant_id,
            "platform": platform,
            **config
        }).execute()

        return TenantConfig(response.data[0])
```

---

### 10. Proposal Repository (NEW)
**Location**: `backend/repositories/proposal_repository.py`

**Methods**:
```python
class ProposalRepository:
    async def create(self, proposal_data: Dict) -> Proposal:
        """Create new proposal"""
        pass

    async def get_by_id(self, proposal_id: str) -> Proposal:
        """Fetch proposal by ID"""
        pass

    async def update_status(
        self,
        proposal_id: str,
        status: str,
        approved_by: str = None
    ) -> Proposal:
        """Update proposal status"""
        pass

    async def create_version(
        self,
        original_id: str,
        refined_data: Dict
    ) -> Proposal:
        """Create new version for refinement"""
        # Increment version, set original as superseded
        pass
```

---

## Implementation Order

1. **Database First** (no dependencies)
   - Create migration SQL
   - Run migration in Supabase
   - Insert sample data

2. **Backend Core** (depends on DB)
   - Implement TenantRepository
   - Implement direct analysis in resolver.py
   - Create assist.py routes with streaming

3. **Frontend** (depends on backend)
   - Create HTML UI structure
   - Implement app.js with streaming handler
   - Wire up approval actions

4. **Integration Testing**
   - Test embedding=true scenario
   - Test embedding=false scenario
   - Test refinement loop

---

## Risk Assessment

### High Risk
- ❗ **Streaming reliability**: Network failures, timeout handling
- ❗ **FDK API limitations**: Field update capabilities, editor insertion
- ❗ **Error recovery**: Mid-workflow failures

### Medium Risk
- ⚠️ **LLM quality**: Direct mode may produce lower-quality responses
- ⚠️ **Performance**: Long tickets may exceed token limits
- ⚠️ **UX**: Progress visualization clarity

### Low Risk
- ✅ Tenant config management (straightforward CRUD)
- ✅ Database schema (simple table)

---

## Testing Strategy

### Unit Tests
- TenantRepository.get_config()
- propose_solution_direct() with mock LLM
- Stream event generation

### Integration Tests
- End-to-end analysis flow (embedding=true)
- End-to-end analysis flow (embedding=false)
- Approval → field update → editor insertion
- Refinement loop

### Manual Testing
- FDK app UI interactions
- Streaming progress visualization
- Error scenarios

---

## Success Criteria

✅ **Functional**:
- Tenant-based embedding mode switching works
- Progress visualization shows 3 clear stages
- Approval applies field updates and inserts response
- Refinement chat produces improved responses

✅ **Non-Functional**:
- Analysis completes within 10 seconds
- No data loss on network failures
- Clear error messages for user

---

## Open Questions

1. **Proposal Storage**: Where do we store proposals for approval/refine?
   - Option A: In-memory cache (simple, ephemeral)
   - Option B: Database table (persistent, auditable)
   - **Recommendation**: Database for auditability

2. **Streaming Protocol**: SSE vs WebSocket?
   - **Recommendation**: SSE (simpler, HTTP-based, works with FDK)

3. **Error Recovery**: How to handle mid-workflow errors?
   - **Recommendation**: Emit error event, allow user to retry

4. **Field Update Validation**: How to ensure LLM output is valid?
   - **Recommendation**: JSON schema validation before applying

---

## Next Steps After POC

1. Add metrics tracking (analysis time, approval rate, LLM cost)
2. Implement proposal persistence for audit trail
3. Add chunking for long tickets (>4000 tokens)
4. Fine-tune reranker for better retrieval
5. Add confidence score calibration

---

## File Checklist

### To Create

#### Frontend
- [ ] `frontend/app/index.html` (updated UI with progress tracker)
- [ ] `frontend/app/scripts/app.js` (streaming + approval logic)
- [ ] `frontend/app/scripts/sse-client.js` (**NEW**: SSE connection manager)
- [ ] `frontend/app/styles/style.css` (updated styles)

#### Backend - Routes
- [ ] `backend/routes/assist.py` (analyze, approve, refine endpoints)
- [ ] `backend/routes/admin.py` (**NEW**: tenant management API)

#### Backend - Repositories
- [ ] `backend/repositories/tenant_repository.py` (with cache + CRUD)
- [ ] `backend/repositories/proposal_repository.py` (**NEW**: proposal CRUD)

#### Backend - Utilities
- [ ] `backend/utils/pii_masker.py` (**NEW**: PII detection/masking)
- [ ] `backend/utils/token_counter.py` (**NEW**: token counting)
- [ ] `backend/utils/chunking.py` (**NEW**: ticket chunking strategy)

#### Backend - Middleware
- [ ] `backend/middleware/auth.py` (**NEW**: HMAC authentication)

#### Backend - Agents
- [ ] `backend/agents/resolver.py` (add `propose_solution_direct` with chunking)

#### Database
- [ ] `backend/migrations/002_tenant_and_proposals.sql` (**NEW**: 3 tables)
- [ ] `backend/migrations/003_rls_policies.sql` (**NEW**: Row-Level Security)

### To Modify

#### Backend - Services
- [ ] `backend/services/llm_service.py` (add `analyze_ticket_direct`, `refine_response`, `summarize_conversations`)
- [ ] `backend/agents/orchestrator.py` (add fallback logic to workflow)
- [ ] `backend/agents/retriever.py` (handle failures gracefully)

#### Configuration
- [ ] `.env.example` (add `FDK_SIGNING_SECRET`)
- [ ] `backend/config.py` (add auth settings)

---

## Codex Feedback Resolution Summary

✅ **Critical Issues Addressed**:
1. ✅ Retriever fallback logic added (search fail → direct analysis)
2. ✅ SSE heartbeat + reconnect with exponential backoff
3. ✅ Proposals DB table with status tracking
4. ✅ HMAC authentication for FDK → Backend
5. ✅ PII masking utility for all SSE events
6. ✅ Token limit handling with chunking strategy
7. ✅ Tenant management API (create/update/get)

✅ **Architecture Improvements**:
- Proposal versioning for refinement loop
- Audit trail with approval_logs table
- Tenant isolation with RLS policies
- Error classification (recoverable vs non-recoverable)
- Retry logic for external API calls
- Cache invalidation strategy

✅ **Security Enhancements**:
- HMAC-SHA256 request signing
- Replay attack prevention (5-min window)
- PII masking before transmission
- Row-Level Security for multi-tenant isolation

---

This enhanced plan provides a production-ready foundation for the POC with proper security, error handling, and tenant management.
