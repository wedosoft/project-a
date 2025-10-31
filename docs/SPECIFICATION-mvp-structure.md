# AI Contact Center OS - MVP 프로젝트 구조 Specification

## 1. 목표 (Goal)

AI Contact Center OS의 MVP 개발을 위한 표준 프로젝트 구조를 생성합니다.

## 2. 현재 상태 분석 (Current State)

### 기존 구조
```
project-a-spinoff/
├── backend/              ✅ 존재 (기본 구조 있음)
│   ├── routes/          ✅
│   ├── services/        ✅
│   ├── models/          ✅
│   ├── utils/           ✅
│   ├── main.py          ✅
│   └── requirements.txt ✅
├── frontend/            ✅ 존재 (Freshdesk FDK 앱)
├── docs/                ✅ 존재
└── README.md            ✅
```

### 누락된 구조
- `agents/` 폴더 (LangGraph 오케스트레이션)
- 루트 `requirements.txt` (통합 패키지 관리)
- Backend 상세 하위 구조
- Agents 초기 파일

## 3. 요구사항 (Requirements)

### 3.1 디렉토리 구조

```
project-a-spinoff/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 엔트리포인트
│   ├── config.py                  # 환경 설정
│   ├── requirements.txt           # Backend 전용 패키지
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── tickets.py            # 티켓 관련 API
│   │   ├── assist.py             # AI 어시스트 API
│   │   └── metrics.py            # 지표 API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── orchestrator.py       # LangGraph 오케스트레이터 연계
│   │   ├── freshdesk.py          # Freshdesk API 클라이언트
│   │   └── supabase_client.py    # Supabase 클라이언트
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ticket.py             # 티켓 모델
│   │   ├── proposal.py           # AI 제안 모델
│   │   └── feedback.py           # 피드백 로그 모델
│   └── utils/
│       ├── __init__.py
│       ├── logger.py             # 로깅 유틸
│       └── validators.py         # 입력 검증
│
├── agents/                         # 🆕 LangGraph 에이전트
│   ├── __init__.py
│   ├── orchestrator.py            # Orchestrator Agent
│   ├── retriever.py               # Retriever Agent
│   ├── resolution.py              # Resolution Agent
│   ├── human.py                   # Human Agent
│   ├── graph.py                   # LangGraph 그래프 정의
│   └── state.py                   # 상태 스키마
│
├── frontend/                       # ✅ 유지 (기존)
│   └── ...
│
├── tests/                          # 🆕 테스트
│   ├── __init__.py
│   ├── test_agents/
│   ├── test_backend/
│   └── conftest.py
│
├── docs/                           # ✅ 유지
│   ├── AGENTS.md                  ✅
│   ├── README.md
│   └── API.md
│
├── scripts/                        # 🆕 유틸리티 스크립트
│   ├── setup.sh
│   └── init_db.py
│
├── .env.example                    # 🆕 환경 변수 예제
├── requirements.txt                # 🆕 통합 패키지
├── docker-compose.yml              # 🆕 로컬 개발 환경
├── README.md                       ✅
└── CLAUDE.md                       ✅
```

### 3.2 필수 패키지 (requirements.txt)

**Backend Core**
- `fastapi>=0.104.0`
- `uvicorn[standard]>=0.24.0`
- `pydantic>=2.5.0`
- `python-dotenv>=1.0.0`

**LangGraph & LangChain**
- `langgraph>=0.0.25`
- `langchain-core>=0.1.0`
- `langchain-openai>=0.0.5`  # LLM 연동

**Vector DB & Search**
- `qdrant-client>=1.7.0`
- `sentence-transformers>=2.2.0`

**Database**
- `supabase>=2.0.0`
- `psycopg2-binary>=2.9.9`

**Utilities**
- `httpx>=0.25.0`  # 비동기 HTTP
- `python-multipart>=0.0.6`  # 파일 업로드
- `pydantic-settings>=2.0.0`  # 설정 관리

### 3.3 환경 변수 (.env.example)

```env
# FastAPI
FASTAPI_ENV=development
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000

# LLM
OPENAI_API_KEY=your_openai_key_here
# ANTHROPIC_API_KEY=your_anthropic_key_here

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key_here

# Freshdesk
FRESHDESK_DOMAIN=your-domain.freshdesk.com
FRESHDESK_API_KEY=your_freshdesk_key_here

# Logging
LOG_LEVEL=INFO
```

## 4. 파일별 초기 내용

### 4.1 backend/config.py

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # FastAPI
    fastapi_env: str = "development"
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    # LLM
    openai_api_key: str

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""

    # Supabase
    supabase_url: str
    supabase_key: str

    # Freshdesk
    freshdesk_domain: str
    freshdesk_api_key: str

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### 4.2 backend/main.py (개선)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.routes import tickets, assist, metrics

settings = get_settings()

app = FastAPI(
    title="AI Contact Center OS",
    description="MVP Backend API",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(assist.router, prefix="/api/assist", tags=["assist"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

@app.get("/")
async def root():
    return {"message": "AI Contact Center OS API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### 4.3 agents/orchestrator.py (스켈레톤)

```python
from typing import Dict, Any
from langgraph.graph import StateGraph
from agents.state import AgentState

class OrchestratorAgent:
    """
    Orchestrator Agent - 전체 워크플로우 제어
    """

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """LangGraph 그래프 구성"""
        graph = StateGraph(AgentState)

        # 노드 추가 (향후 구현)
        # graph.add_node("context_router", self.route_context)
        # graph.add_node("retrieve_cases", ...)
        # ...

        return graph.compile()

    async def process(self, ticket_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 컨텍스트를 받아 AI 제안 생성
        """
        # TODO: LangGraph 실행
        pass
```

### 4.4 agents/state.py

```python
from typing import TypedDict, List, Optional, Dict, Any

class AgentState(TypedDict):
    """LangGraph 상태 스키마"""

    # 입력
    ticket_id: str
    ticket_content: str
    ticket_meta: Dict[str, Any]

    # 중간 상태
    similar_cases: Optional[List[Dict[str, Any]]]
    kb_procedures: Optional[List[Dict[str, Any]]]

    # 출력
    draft_response: Optional[str]
    field_updates: Optional[Dict[str, Any]]
    justification: Optional[str]

    # 제어
    current_step: str
    error: Optional[str]
```

### 4.5 backend/routes/assist.py (스켈레톤)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()

class AssistRequest(BaseModel):
    ticket_id: str
    ticket_content: str
    ticket_meta: Dict[str, Any]

class AssistResponse(BaseModel):
    draft_response: str
    field_updates: Dict[str, Any]
    similar_cases: list
    kb_procedures: list

@router.post("/{ticket_id}/suggest", response_model=AssistResponse)
async def suggest_solution(ticket_id: str, request: AssistRequest):
    """
    AI 제안 생성 (유사사례 + KB + 응답 초안)
    """
    # TODO: Orchestrator Agent 호출
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{ticket_id}/approve")
async def approve_suggestion(ticket_id: str, approval_data: Dict[str, Any]):
    """
    상담원 승인 처리 및 Freshdesk API 패치
    """
    # TODO: Human Agent 승인 로직
    raise HTTPException(status_code=501, detail="Not implemented")
```

## 5. 구현 순서

1. ✅ **현재 상태 분석** (완료)
2. 🔄 **사용자 승인 대기** (현재 단계)
3. ⏳ **디렉토리 구조 생성**
   - `agents/` 폴더 및 하위 파일
   - `tests/` 폴더
   - `scripts/` 폴더
4. ⏳ **파일 생성**
   - `requirements.txt` (루트)
   - `.env.example`
   - Backend 파일 업데이트 (config.py, main.py 개선)
   - Agents 스켈레톤 파일
   - Route 파일 개선
5. ⏳ **Memory 저장**
   - `mvp-day1-structure` 네임스페이스에 구조 저장

## 6. 검증 기준

- [ ] 모든 디렉토리가 생성되었는가?
- [ ] `requirements.txt`에 필수 패키지가 모두 포함되었는가?
- [ ] `.env.example`이 생성되었는가?
- [ ] Backend `main.py`가 라우터를 정상적으로 등록하는가?
- [ ] Agents 스켈레톤 파일이 생성되었는가?
- [ ] Memory에 구조가 저장되었는가?

## 7. 승인 요청

**승인 시**: 위 설계대로 자동으로 구현을 진행합니다.
**수정 요청 시**: 피드백을 반영하여 설계를 수정합니다.

---

**승인하시겠습니까? (승인/수정)**
