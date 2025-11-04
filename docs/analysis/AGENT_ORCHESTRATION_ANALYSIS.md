# AI Contact Center OS - 에이전트 오케스트레이션 분석 보고서

## 📋 개요

이 문서는 프로젝트의 Freshdesk 티켓 조회 플로우와 에이전트 오케스트레이션 시스템에 대한 종합 분석입니다.

**분석 일자**: 2025-11-04
**프로젝트**: AI Contact Center OS (project-a-spinoff)
**기술 스택**: LangGraph, FastAPI, Qdrant, PostgreSQL, Freshdesk API

---

## 🎯 주요 발견사항

### ✅ 완료된 구현
1. **Freshdesk API 클라이언트**: 완전히 구현됨
2. **LangGraph 워크플로우**: 4개 핵심 에이전트 구현 완료
3. **벡터 검색 시스템**: Qdrant + 하이브리드 검색 준비됨
4. **테스트 커버리지**: 단위 테스트 및 통합 테스트 작성됨

### ⚠️ 진행 중/미완성
1. **벡터 DB 데이터**: 현재 비어있음 (데이터 인제스트 필요)
2. **Human Approval Loop**: 현재 자동 승인 플레이스홀더
3. **Freshdesk FDK 앱**: 아직 구현되지 않음
4. **프로덕션 배포**: 개발 환경만 구성됨

---

## 🔍 1. Freshdesk 티켓 조회 플로우

### 1.1 FreshdeskClient 구조

**위치**: `backend/services/freshdesk.py`

#### 주요 메서드

| 메서드 | 기능 | 파라미터 |
|--------|------|----------|
| `fetch_tickets()` | 티켓 목록 조회 (페이지네이션) | `updated_since`, `per_page`, `max_tickets` |
| `get_ticket(ticket_id)` | 특정 티켓 상세 조회 | `ticket_id` |
| `fetch_ticket_conversations()` | 티켓 대화 내역 조회 | `ticket_id` |
| `fetch_kb_articles()` | KB 문서 조회 | `updated_since`, `per_page`, `max_articles` |
| `update_ticket_fields()` | 티켓 필드 업데이트 | `ticket_id`, `updates` |
| `post_reply()` | 티켓 응답 작성 | `ticket_id`, `body`, `private` |

#### 티켓 조회 예시

```python
from backend.services.freshdesk import FreshdeskClient
from datetime import datetime, timedelta

# 1. 클라이언트 초기화
freshdesk = FreshdeskClient()

# 2. 최근 30일 티켓 조회
since = datetime.now() - timedelta(days=30)
tickets = await freshdesk.fetch_tickets(
    updated_since=since,
    per_page=30,
    max_tickets=100
)

# 3. 특정 티켓 상세 조회
ticket = await freshdesk.get_ticket("12345")

# 4. 티켓 대화 내역 조회
conversations = await freshdesk.fetch_ticket_conversations("12345")
```

### 1.2 에러 처리 및 재시도 로직

**특징**:
- ✅ **재시도 로직**: 최대 3회 재시도 (지수 백오프)
- ✅ **타임아웃**: 30초 기본 타임아웃
- ✅ **Rate Limit 처리**: 429 에러 시 자동 재시도
- ✅ **서버 에러 처리**: 500, 502, 503, 504 에러 시 재시도

```python
async def _make_request(self, method: str, endpoint: str, **kwargs):
    for attempt in range(self.max_retries):
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(...)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [429, 500, 502, 503, 504]:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 지수 백오프
                    await asyncio.sleep(wait_time)
                    continue
            raise
```

### 1.3 페이지네이션 처리

```python
async def fetch_tickets(self, updated_since=None, per_page=30, max_tickets=None):
    all_tickets = []
    page = 1

    while True:
        params = {
            "per_page": min(per_page, 100),  # Freshdesk 최대 100
            "page": page,
            "order_type": "desc",
            "order_by": "updated_at"
        }

        tickets = await self._make_request("GET", "tickets", params=params)

        if not tickets:
            break

        all_tickets.extend(tickets)

        # max_tickets 도달 시 중단
        if max_tickets and len(all_tickets) >= max_tickets:
            all_tickets = all_tickets[:max_tickets]
            break

        # 마지막 페이지 감지
        if len(tickets) < per_page:
            break

        page += 1

    return all_tickets
```

---

## 🤖 2. 구현된 에이전트 종류

### 2.1 핵심 에이전트 (4종)

#### 1️⃣ **Orchestrator Agent** (오케스트레이터)

**파일**: `backend/agents/orchestrator.py`

**역할**:
- LangGraph 워크플로우 그래프 구성
- 에이전트 간 조율 및 상태 관리
- 조건부 라우팅 로직
- 에러 핸들링

**주요 노드**:
```python
graph.add_node("router_decision", router_decision_node)
graph.add_node("retrieve_cases", retrieve_cases)
graph.add_node("retrieve_kb", retrieve_kb)
graph.add_node("propose_solution", propose_solution)
graph.add_node("propose_field_updates", propose_field_updates)
graph.add_node("human_approve", human_approve)
graph.add_node("error_handler", error_handler)
```

**엔트리 포인트**:
```python
graph.set_entry_point("router_decision")
```

---

#### 2️⃣ **Router Agent** (라우터)

**파일**: `backend/agents/router.py`

**역할**:
- 티켓 컨텍스트 분석
- 다음 노드 결정 (retrieve_cases | retrieve_kb | propose_solution)
- 키워드 기반 라우팅

**라우팅 로직**:
```python
async def context_router(state: AgentState) -> str:
    ticket_context = state.get("ticket_context", {})
    subject = ticket_context.get("subject", "").lower()
    description = ticket_context.get("description", "").lower()
    combined_text = f"{subject} {description}"

    # KB 검색 키워드
    kb_keywords = ["how to", "procedure", "guide", "tutorial", "manual", "setup", "configuration"]
    if any(kw in combined_text for kw in kb_keywords):
        return "retrieve_kb"

    # 케이스 검색 키워드
    case_keywords = ["error", "issue", "problem", "bug", "failed", "not working", "broken"]
    if any(kw in combined_text for kw in case_keywords):
        return "retrieve_cases"

    # 기본값: 케이스 검색
    return "retrieve_cases"
```

**타임아웃**: 30초

---

#### 3️⃣ **Retriever Agent** (검색 에이전트)

**파일**: `backend/agents/retriever.py`

**역할**:
- 유사 티켓 검색 (`support_tickets` 컬렉션)
- KB 문서 검색 (`kb_procedures` 컬렉션)
- 하이브리드 검색 (Dense + Sparse + Reranking)

**검색 메서드**:

##### `retrieve_cases()` - 유사 티켓 검색
```python
async def retrieve_cases(state: AgentState) -> AgentState:
    # 티켓 컨텍스트에서 쿼리 생성
    ticket_context = state.get("ticket_context", {})
    query = f"{ticket_context.get('symptom')} {ticket_context.get('subject')} {ticket_context.get('description')}"

    # 하이브리드 검색 실행
    search_service = HybridSearchService()
    results = await search_service.search(
        collection_name="support_tickets",
        query=query,
        top_k=5,
        use_reranking=True
    )

    # 상태 업데이트
    state["search_results"]["similar_cases"] = results
    return state
```

##### `retrieve_kb()` - KB 문서 검색
```python
async def retrieve_kb(state: AgentState) -> AgentState:
    # KB 절차 검색
    results = await search_service.search(
        collection_name="kb_procedures",
        query=query,
        top_k=5,
        use_reranking=True
    )

    state["search_results"]["kb_procedures"] = results
    return state
```

**타임아웃**: 각 검색 30초

---

#### 4️⃣ **Resolver Agent** (해결 에이전트)

**파일**: `backend/agents/resolver.py`

**역할**:
- AI 기반 솔루션 제안 생성
- 티켓 필드 업데이트 제안
- LLM 기반 응답 초안 작성

**LLM 모델**: Google Gemini 1.5 Pro

##### `propose_solution()` - 솔루션 생성
```python
async def propose_solution(state: AgentState) -> AgentState:
    # Gemini 모델 설정
    genai.configure(api_key=settings.google_api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")

    # 검색 결과 가져오기
    similar_cases = state["search_results"]["similar_cases"]
    kb_procedures = state["search_results"]["kb_procedures"]

    # 프롬프트 구성
    prompt = f"""You are a customer support AI assistant. Generate a professional solution.

Ticket Details:
- Subject: {ticket_ctx.get('subject')}
- Description: {ticket_ctx.get('description')}
- Priority: {ticket_ctx.get('priority')}

Similar Cases:
{similar_text}

Knowledge Base Procedures:
{kb_text}

Generate a clear, actionable solution with confidence score (0.0-1.0).
"""

    # AI 응답 생성
    response = await model.generate_content(prompt)

    # 상태 업데이트
    state["proposed_action"]["draft_response"] = draft
    state["proposed_action"]["confidence"] = confidence

    return state
```

##### `propose_field_updates()` - 필드 업데이트 제안
```python
async def propose_field_updates(state: AgentState) -> AgentState:
    # AI 기반 필드 업데이트 제안
    prompt = f"""Propose ticket field updates:
- Priority: [low/medium/high/urgent]
- Status: [open/pending/resolved/closed]
- Tags: [comma-separated tags]
"""

    response = await model.generate_content(prompt)

    # 파싱 및 상태 업데이트
    updates = parse_field_updates(response.text)
    state["proposed_action"]["proposed_field_updates"] = updates

    return state
```

**타임아웃**: 각 작업 30초

---

### 2.2 지원 컴포넌트

#### Human Agent (승인 루프)
**파일**: `backend/agents/orchestrator.py` (human_approve 노드)

**현재 상태**: 자동 승인 플레이스홀더
```python
async def human_approve(state: AgentState) -> AgentState:
    # TODO: 실제 구현시 human-in-the-loop 패턴 적용
    state["approval_status"] = "approved"  # 현재는 자동 승인
    return state
```

**향후 구현 계획**:
- Freshdesk FDK 앱 개발
- 티켓 사이드바 UI
- 승인/수정/거부 인터페이스

---

## 🔄 3. 에이전트 오케스트레이션 플로우

### 3.1 전체 워크플로우 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                    START                                 │
│            (Freshdesk Ticket Input)                      │
└────────────────────┬────────────────────────────────────┘
                     ↓
        ┌────────────────────────┐
        │  router_decision_node  │
        │  (Context Analysis)    │
        └────────────┬───────────┘
                     ↓
        ┌────────────┴───────────┐
        ↓                        ↓                        ↓
┌───────────────┐      ┌───────────────┐      ┌─────────────────┐
│retrieve_cases │      │  retrieve_kb  │      │propose_solution │
│(Ticket Search)│      │  (KB Search)  │      │   (Direct AI)   │
└───────┬───────┘      └───────┬───────┘      └────────┬────────┘
        │                      │                        │
        └──────────────────────┴────────────────────────┘
                               ↓
                    ┌─────────────────────┐
                    │  propose_solution   │
                    │  (AI Response Gen)  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │propose_field_updates│
                    │ (Field Suggestions) │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │   human_approve     │
                    │ (Approval Loop)     │
                    └──────────┬──────────┘
                               ↓
                    ┌──────────┴──────────┐
                    ↓                     ↓
            ┌─────────────┐      ┌─────────────┐
            │   approved  │      │   modified  │
            │     END     │      │ → Loop Back │
            └─────────────┘      └─────────────┘
```

### 3.2 상태 전이 (State Transitions)

#### AgentState 스키마
**파일**: `backend/models/graph_state.py`

```python
class AgentState(TypedDict):
    ticket_context: NotRequired[Optional[Dict[str, Any]]]      # 입력 티켓 정보
    search_results: NotRequired[Optional[SearchResults]]       # 검색 결과
    proposed_action: NotRequired[Optional[Dict[str, Any]]]     # AI 제안
    approval_status: NotRequired[Optional[str]]                # 승인 상태
    errors: NotRequired[List[str]]                             # 에러 목록
    metadata: NotRequired[Dict[str, Any]]                      # 메타데이터
```

#### 상태 전이 순서

1. **초기 상태** (START)
```python
{
    "ticket_context": {
        "ticket_id": "12345",
        "subject": "Login error",
        "description": "Cannot login to system",
        "priority": "high"
    },
    "errors": [],
    "metadata": {"created_at": "2025-11-04T10:00:00Z"}
}
```

2. **라우터 결정 후**
```python
{
    ...ticket_context,
    "next_node": "retrieve_cases"  # 또는 "retrieve_kb" 또는 "propose_solution"
}
```

3. **검색 완료 후**
```python
{
    ...ticket_context,
    "search_results": {
        "similar_cases": [
            {"id": "ticket-123", "score": 0.89, "content": "..."},
            {"id": "ticket-456", "score": 0.82, "content": "..."}
        ],
        "kb_procedures": [
            {"id": "kb-001", "score": 0.75, "content": "..."}
        ],
        "total_results": 3
    }
}
```

4. **솔루션 제안 후**
```python
{
    ...ticket_context,
    ...search_results,
    "proposed_action": {
        "draft_response": "Based on similar cases, please try...",
        "confidence": 0.85,
        "similar_cases": [...],
        "kb_procedures": [...],
        "justification": "Generated based on 2 similar cases and 1 KB article"
    }
}
```

5. **필드 업데이트 제안 후**
```python
{
    ...proposed_action,
    "proposed_action": {
        ...draft_response,
        "proposed_field_updates": {
            "priority": "high",
            "status": "pending",
            "tags": ["login-issue", "authentication", "urgent"]
        },
        "justification": "Priority set to high due to login blocking issue"
    }
}
```

6. **승인 완료 후** (END)
```python
{
    ...all_previous_state,
    "approval_status": "approved"  # 또는 "modified" 또는 "rejected"
}
```

### 3.3 조건부 분기 로직

#### router_condition (라우터 분기)
```python
def router_condition(state: AgentState) -> Literal["retrieve_cases", "retrieve_kb", "propose_solution"]:
    next_node = state.get("next_node", "propose_solution")
    return next_node
```

#### approval_condition (승인 분기)
```python
def approval_condition(state: AgentState) -> Literal["propose_solution", "END"]:
    approval_status = state.get("approval_status", "approved")

    if approval_status == "modified":
        return "propose_solution"  # 루프백
    elif approval_status == "rejected":
        return END
    else:  # approved
        return END
```

### 3.4 에러 핸들링

```python
async def error_handler(state: AgentState) -> AgentState:
    errors = state.get("errors", [])
    if errors:
        logger.error(f"Workflow errors: {errors}")

    state["error_handled"] = True
    state["final_status"] = "error"

    return state
```

**에러 발생 시 플로우**:
```
Any Node → Exception → error_handler → END
```

---

## 💾 4. 벡터 DB 통합 및 데이터 플로우

### 4.1 Qdrant 벡터 DB 구성

**파일**: `backend/services/vector_search.py`

#### 컬렉션 구조

##### 1️⃣ support_tickets 컬렉션
```python
vectors_config = {
    "symptom_vec": VectorParams(size=1024, distance=COSINE),
    "cause_vec": VectorParams(size=1024, distance=COSINE),
    "resolution_vec": VectorParams(size=1024, distance=COSINE)
}
```

**멀티벡터 설계**:
- `symptom_vec`: 증상 임베딩
- `cause_vec`: 원인 임베딩
- `resolution_vec`: 해결방법 임베딩

##### 2️⃣ kb_procedures 컬렉션
```python
vectors_config = {
    "intent_vec": VectorParams(size=1024, distance=COSINE),
    "procedure_vec": VectorParams(size=1024, distance=COSINE)
}
```

**멀티벡터 설계**:
- `intent_vec`: 의도/질문 임베딩
- `procedure_vec`: 절차/답변 임베딩

### 4.2 임베딩 모델

**모델**: `BAAI/bge-m3` (1024 차원)

```python
from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer("BAAI/bge-m3")
embeddings = embedding_model.encode(texts, normalize_embeddings=True)
```

### 4.3 하이브리드 검색 (Hybrid Search)

**파일**: `backend/services/hybrid_search.py`

#### 검색 파이프라인

```
Query Text
    ↓
┌─────────────────────────────────┐
│  1. Query Embedding (BGE-M3)   │
└─────────────┬───────────────────┘
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
┌─────────────┐   ┌─────────────┐
│Dense Search │   │Sparse Search│
│  (Qdrant)   │   │   (BM25)    │
│  Top-200    │   │  Top-200    │
└──────┬──────┘   └──────┬──────┘
       └─────────┬────────┘
                 ↓
       ┌──────────────────┐
       │  RRF Fusion      │
       │  (Top-20)        │
       └─────────┬────────┘
                 ↓
       ┌──────────────────┐
       │  Reranking       │
       │ (Cross-Encoder)  │
       │  → Top-5         │
       └──────────────────┘
```

#### RRF (Reciprocal Rank Fusion) 알고리즘

```python
def hybrid_search(dense_results, sparse_results, k=60):
    rrf_scores = {}

    # Dense 결과 점수 계산
    for rank, result in enumerate(dense_results, 1):
        doc_id = str(result["id"])
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

    # Sparse 결과 점수 계산
    for rank, result in enumerate(sparse_results, 1):
        doc_id = str(result["id"])
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

    # 점수 기준 정렬
    sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    return [result_map[doc_id] for doc_id, score in sorted_ids]
```

### 4.4 데이터 인제스트 플로우

**스크립트**: `backend/scripts/test_freshdesk_integration.py`

```python
async def sync_to_qdrant(tickets, articles, llm, qdrant, sparse_search):
    # 1. Qdrant 컬렉션 생성
    qdrant.ensure_collection(
        collection_name="support_tickets",
        vector_names=["symptom_vec", "cause_vec", "resolution_vec"]
    )

    # 2. 각 티켓에 대해
    for ticket in tickets:
        # 2a. 임베딩 생성
        content = f"{ticket['subject']}\n\n{ticket['description']}"
        embedding = llm.generate_embedding(content)

        # 2b. 벡터 저장 (Qdrant)
        qdrant.store_vector(
            collection_name="support_tickets",
            point_id=ticket_id,
            vectors={
                "symptom_vec": embedding,
                "cause_vec": embedding,
                "resolution_vec": embedding
            },
            payload={
                "ticket_id": ticket_id,
                "subject": ticket["subject"],
                "content": content,
                ...
            }
        )

        # 2c. 스파스 인덱싱 (Postgres BM25)
        await sparse_search.index_documents(
            collection_name="support_tickets",
            documents=[{
                "id": ticket_id,
                "content": content,
                "metadata": {...}
            }]
        )
```

### 4.5 현재 상태

⚠️ **벡터 DB는 현재 비어있음**

**확인 방법**:
```bash
# Qdrant 컬렉션 확인
curl "https://<qdrant-host>:6333/collections"

# 또는 Python으로 확인
from backend.services.vector_search import VectorSearchService
service = VectorSearchService()
info = service.get_collection_info("support_tickets")
print(f"Points count: {info['points_count']}")  # 현재 0
```

**데이터 인제스트 필요**:
```bash
# 테스트 스크립트 실행
python backend/scripts/test_freshdesk_integration.py
```

---

## 📊 5. 테스트 및 검증

### 5.1 단위 테스트

#### Freshdesk Client 테스트
**파일**: `backend/tests/test_freshdesk.py`

```python
# 티켓 조회 테스트
async def test_fetch_tickets_basic(freshdesk_client):
    with patch.object(freshdesk_client, "_make_request") as mock:
        mock.return_value = [{"id": 1}, {"id": 2}]
        result = await freshdesk_client.fetch_tickets()
        assert len(result) == 2

# 페이지네이션 테스트
async def test_fetch_tickets_pagination(freshdesk_client):
    with patch.object(freshdesk_client, "_make_request") as mock:
        mock.side_effect = [
            [{"id": i} for i in range(1, 31)],  # 30 tickets
            [{"id": i} for i in range(31, 41)]  # 10 tickets
        ]
        result = await freshdesk_client.fetch_tickets(per_page=30, max_tickets=50)
        assert len(result) == 40
```

#### 오케스트레이터 테스트
**파일**: `backend/tests/test_orchestrator.py`

```python
# 워크플로우 그래프 구조 테스트
def test_graph_nodes():
    graph = build_graph()
    expected_nodes = {
        "router_decision", "retrieve_cases", "retrieve_kb",
        "propose_solution", "propose_field_updates",
        "human_approve", "error_handler"
    }
    assert all(node in graph.nodes for node in expected_nodes)

# 라우터 조건 테스트
def test_route_to_cases(mock_ticket_state):
    result = router_condition(mock_ticket_state)
    assert result == "retrieve_cases"
```

### 5.2 통합 테스트

**파일**: `backend/scripts/test_freshdesk_integration.py`

```python
async def main():
    # 1. 서비스 초기화
    freshdesk = FreshdeskClient()
    llm = LLMService()
    qdrant = QdrantService()
    hybrid_search = HybridSearchService()

    # 2. Freshdesk에서 티켓 조회
    tickets = await freshdesk.fetch_tickets(limit=10)

    # 3. KB 문서 조회
    articles = await freshdesk.fetch_kb_articles(limit=10)

    # 4. Qdrant에 데이터 동기화
    await sync_to_qdrant(tickets, articles, llm, qdrant, sparse_search)

    # 5. 하이브리드 검색 테스트
    results = await hybrid_search.search(
        collection_name="support_tickets",
        query="login error",
        top_k=5,
        use_reranking=True
    )
```

### 5.3 E2E 테스트 실행 방법

```bash
# 프로젝트 루트에서 실행 (중요!)
cd /Users/alan/GitHub/project-a-spinoff

# 가상환경 활성화
source venv/bin/activate

# 환경변수 로드 (.env 파일이 프로젝트 루트에 있어야 함)
export $(cat .env | xargs)

# 테스트 실행
pytest backend/tests/test_e2e.py -v

# 통합 테스트 실행
python backend/scripts/test_freshdesk_integration.py
```

**주의사항**:
- ⚠️ 반드시 **프로젝트 루트**에서 실행
- ⚠️ `backend/`에서 실행하면 `.env` 파일을 찾지 못함

---

## 🚀 6. 실행 가이드

### 6.1 특정 티켓 조회 예시

```python
import asyncio
from backend.services.freshdesk import FreshdeskClient
from backend.agents.orchestrator import compile_workflow
from backend.models.graph_state import create_initial_state
from backend.models.schemas import TicketContext

async def process_ticket(ticket_id: str):
    # 1. Freshdesk에서 티켓 조회
    freshdesk = FreshdeskClient()
    ticket = await freshdesk.get_ticket(ticket_id)

    # 2. 티켓 컨텍스트 생성
    ticket_context = TicketContext(
        ticket_id=ticket_id,
        subject=ticket.get("subject"),
        description=ticket.get("description_text"),
        priority=ticket.get("priority"),
        status=ticket.get("status")
    )

    # 3. 초기 상태 생성
    initial_state = create_initial_state(ticket_context)

    # 4. 워크플로우 실행
    workflow = compile_workflow()
    result = await workflow.ainvoke(initial_state)

    # 5. 결과 확인
    print("AI 제안:")
    print(f"응답 초안: {result['proposed_action']['draft_response']}")
    print(f"신뢰도: {result['proposed_action']['confidence']}")
    print(f"필드 업데이트: {result['proposed_action']['proposed_field_updates']}")

    return result

# 실행
asyncio.run(process_ticket("12345"))
```

### 6.2 에이전트 오케스트레이션 플로우 실행

```python
# 1. 티켓 입력
ticket_context = {
    "ticket_id": "TEST-001",
    "subject": "Database connection error",
    "description": "Production database error",
    "priority": "high"
}

# 2. 워크플로우 실행
workflow = compile_workflow()
result = await workflow.ainvoke({"ticket_context": ticket_context})

# 3. 각 노드 실행 흐름
# START
#   → router_decision (분석: "error" 키워드 발견)
#     → retrieve_cases (유사 티켓 검색)
#       → propose_solution (AI 응답 생성)
#         → propose_field_updates (필드 제안)
#           → human_approve (자동 승인)
#             → END

# 4. 최종 결과
print(result["approval_status"])  # "approved"
print(result["proposed_action"]["draft_response"])
```

---

## 🔧 7. 다음 단계 및 개선 사항

### 7.1 즉시 필요한 작업

#### 1️⃣ 벡터 DB 데이터 인제스트 (최우선)
```bash
# Freshdesk 티켓 및 KB 데이터를 Qdrant에 동기화
python backend/scripts/test_freshdesk_integration.py
```

**작업 내용**:
- [ ] Freshdesk에서 최근 티켓 500개 조회
- [ ] KB 문서 100개 조회
- [ ] Qdrant에 임베딩 저장
- [ ] Postgres에 BM25 인덱싱
- [ ] 검색 품질 검증

#### 2️⃣ Human Approval Loop 구현
**작업 내용**:
- [ ] Freshdesk FDK 앱 개발
- [ ] 티켓 사이드바 UI 구현
- [ ] 승인/수정/거부 버튼
- [ ] Freshdesk API 연동 (PATCH)
- [ ] 피드백 로그 저장 (Supabase)

#### 3️⃣ 검색 품질 튜닝
**작업 내용**:
- [ ] 재랭커 가중치 조정
- [ ] RRF 파라미터 최적화 (k=60 → ?)
- [ ] 시간 감쇠 추가 (최신 티켓 부스팅)
- [ ] 에러 코드 매칭 부스팅
- [ ] Recall@10, nDCG@10 측정

### 7.2 Phase 2 확장 계획

#### 4️⃣ Analyzer Agent 추가
**역할**: 티켓 의도 및 감정 분석
```python
async def analyze_ticket(state: AgentState) -> AgentState:
    ticket = state["ticket_context"]

    # 의도 분류 (문의/불만/요청/기술지원)
    intent = classify_intent(ticket["description"])

    # 감정 분석 (긍정/중립/부정/긴급)
    sentiment = analyze_sentiment(ticket["description"])

    state["analysis"] = {
        "intent": intent,
        "sentiment": sentiment,
        "urgency_score": calculate_urgency(sentiment)
    }

    return state
```

#### 5️⃣ Compliance Agent 추가
**역할**: PII 탐지 및 마스킹
```python
async def check_compliance(state: AgentState) -> AgentState:
    # PII 탐지 (이메일, 전화, 계좌, 주민번호)
    pii_entities = detect_pii(state["ticket_context"]["description"])

    # 마스킹 처리
    masked_text = mask_pii(text, pii_entities)

    state["ticket_context"]["description"] = masked_text
    state["compliance_check"] = {
        "pii_found": len(pii_entities) > 0,
        "entities": pii_entities
    }

    return state
```

### 7.3 성능 최적화

#### 캐싱 전략
```python
# Redis 캐싱
import redis
cache = redis.Redis(host='localhost', port=6379)

async def search_with_cache(query: str):
    # 캐시 확인
    cache_key = f"search:{hashlib.md5(query.encode()).hexdigest()}"
    cached = cache.get(cache_key)

    if cached:
        return json.loads(cached)

    # 검색 실행
    results = await hybrid_search.search(query)

    # 캐시 저장 (TTL 1시간)
    cache.setex(cache_key, 3600, json.dumps(results))

    return results
```

#### 비동기 배치 처리
```python
# Celery 작업 큐
from celery import Celery
app = Celery('tasks', broker='redis://localhost:6379')

@app.task
async def batch_sync_tickets():
    # 최근 24시간 티켓 동기화
    since = datetime.now() - timedelta(days=1)
    tickets = await freshdesk.fetch_tickets(updated_since=since)

    # 배치 임베딩 생성
    embeddings = await llm.batch_generate_embeddings([t["content"] for t in tickets])

    # 배치 저장
    await qdrant.batch_upsert(tickets, embeddings)
```

---

## 📈 8. 지표 및 모니터링

### 8.1 검색 품질 지표

```python
# Recall@K 계산
def calculate_recall_at_k(retrieved: List[str], relevant: List[str], k: int) -> float:
    retrieved_k = set(retrieved[:k])
    relevant_set = set(relevant)

    if not relevant_set:
        return 0.0

    return len(retrieved_k & relevant_set) / len(relevant_set)

# nDCG@K 계산
def calculate_ndcg_at_k(retrieved: List[str], relevance_scores: Dict[str, float], k: int) -> float:
    dcg = sum(relevance_scores.get(doc_id, 0) / np.log2(i + 2)
              for i, doc_id in enumerate(retrieved[:k]))

    ideal_order = sorted(relevance_scores.values(), reverse=True)
    idcg = sum(score / np.log2(i + 2) for i, score in enumerate(ideal_order[:k]))

    return dcg / idcg if idcg > 0 else 0.0
```

### 8.2 도입 효과 지표

| 지표 | 측정 방법 | 목표 |
|------|----------|------|
| 승인률 | `approved / total` | > 70% |
| 응답시간 단축 | `avg_time_before - avg_time_after` | -30% |
| FTR (First Time Resolution) | `resolved_first_time / total` | > 60% |

### 8.3 운영 지표

```python
# 지표 로깅
from backend.utils.metrics import MetricsLogger

metrics = MetricsLogger()

# 워크플로우 실행 시간
with metrics.timer("workflow_execution"):
    result = await workflow.ainvoke(state)

# 에러율
metrics.increment("workflow_errors", tags={"error_type": "timeout"})

# LLM 비용
metrics.gauge("llm_cost_per_request", cost_in_usd)
```

---

## 🎯 9. 결론 및 요약

### 9.1 구현 완료 상태

#### ✅ 완료
1. **Freshdesk API 통합**: 티켓, KB 문서 조회, 필드 업데이트, 응답 작성
2. **LangGraph 워크플로우**: 4개 핵심 에이전트 구현
3. **벡터 검색 시스템**: Qdrant + 하이브리드 검색
4. **테스트 커버리지**: 단위 테스트, 통합 테스트

#### ⚠️ 진행 중
1. **벡터 DB 데이터**: 인제스트 스크립트 준비됨, 실행 필요
2. **Human Approval**: 플레이스홀더, FDK 앱 개발 필요

#### ❌ 미구현
1. **Freshdesk FDK 앱**: 티켓 사이드바 UI
2. **Analyzer Agent**: 의도/감정 분석
3. **Compliance Agent**: PII 마스킹
4. **프로덕션 배포**: Docker, Kubernetes 구성

### 9.2 핵심 에이전트 요약

| 에이전트 | 파일 | 역할 | 상태 |
|---------|------|------|------|
| Orchestrator | `backend/agents/orchestrator.py` | 워크플로우 조율 | ✅ 완료 |
| Router | `backend/agents/router.py` | 티켓 라우팅 | ✅ 완료 |
| Retriever | `backend/agents/retriever.py` | 유사 티켓/KB 검색 | ✅ 완료 |
| Resolver | `backend/agents/resolver.py` | AI 솔루션 생성 | ✅ 완료 |
| Human | `backend/agents/orchestrator.py` | 승인 루프 | ⚠️ 플레이스홀더 |

### 9.3 오케스트레이션 플로우 요약

```
Freshdesk Ticket
    ↓
Router Agent (Context Analysis)
    ↓
Retriever Agent (Hybrid Search)
    ↓
Resolver Agent (AI Solution)
    ↓
Human Agent (Approval Loop)
    ↓
Freshdesk API (Update Fields)
```

### 9.4 즉시 실행 가능한 작업

```bash
# 1. 벡터 DB 데이터 인제스트
python backend/scripts/test_freshdesk_integration.py

# 2. 특정 티켓 조회 및 오케스트레이션 테스트
python -c "
import asyncio
from backend.services.freshdesk import FreshdeskClient

async def test():
    freshdesk = FreshdeskClient()
    ticket = await freshdesk.get_ticket('TICKET_ID')
    print(ticket)

asyncio.run(test())
"

# 3. 워크플로우 엔드투엔드 테스트
pytest backend/tests/test_e2e.py -v
```

---

## 📚 10. 참고 자료

### 10.1 핵심 파일 경로

| 구분 | 파일 경로 |
|------|----------|
| Freshdesk 클라이언트 | `backend/services/freshdesk.py` |
| 오케스트레이터 | `backend/agents/orchestrator.py` |
| 라우터 에이전트 | `backend/agents/router.py` |
| 검색 에이전트 | `backend/agents/retriever.py` |
| 해결 에이전트 | `backend/agents/resolver.py` |
| 상태 스키마 | `backend/models/graph_state.py` |
| 벡터 검색 | `backend/services/vector_search.py` |
| 하이브리드 검색 | `backend/services/hybrid_search.py` |

### 10.2 테스트 파일

| 테스트 | 파일 경로 |
|--------|----------|
| Freshdesk 테스트 | `backend/tests/test_freshdesk.py` |
| 오케스트레이터 테스트 | `backend/tests/test_orchestrator.py` |
| 통합 테스트 | `backend/scripts/test_freshdesk_integration.py` |

### 10.3 문서

| 문서 | 파일 경로 |
|------|----------|
| 에이전트 아키텍처 | `AGENTS.md` |
| 개발 가이드 | `CLAUDE.md` |
| README | `README.md` |

---

**분석 완료일**: 2025-11-04
**분석자**: AI Assistant
**프로젝트**: AI Contact Center OS (project-a-spinoff)
**버전**: 1.0.0
