MVP 구현을 위한 **구체적이고 실행 가능한 명령어 시퀀스**를 단계별로 정리해드리겠습니다.

## 🎯 Day 1: 프로젝트 부트스트랩

### 명령어 1 (초기화 + 구조)
```
claude-flow를 초기화하고, AI Contact Center OS MVP 프로젝트 구조를 만들어줘.

**요구사항**:
- FastAPI 기반 backend/ 폴더 (routes/, services/, models/, utils/)
- LangGraph 오케스트레이션용 agents/ 폴더
- Freshdesk FDK 앱용 frontend/ 폴더 유지
- requirements.txt에 필수 패키지 추가:
  - fastapi, uvicorn, pydantic
  - langgraph, langchain-core
  - qdrant-client, sentence-transformers
  - supabase-py, psycopg2-binary
  - python-dotenv

**효율성**: SPARC 방법론으로 진행하되, Specification 단계에서 내가 승인하면 나머지는 자동으로 완료해줘.

**완료 후**: 생성된 구조를 'mvp-day1-structure' 네임스페이스에 저장해줘.
```

### 명령어 2 (.env 템플릿)
```
.env.example 파일을 만들어줘.

**필수 환경변수**:
# Freshdesk
FRESHDESK_DOMAIN=
FRESHDESK_API_KEY=

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_KEY=

# OpenAI/Gemini (LLM)
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Models
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=jinaai/jina-reranker-v2-base-multilingual

**효율성**: .gitignore에 .env 자동 추가하고, README.md에 환경 설정 섹션도 함께 업데이트해줘.
```

---

## 🎯 Day 2-3: 데이터 모델 & Supabase 스키마

### 명령어 3 (Supabase 스키마)
```
Supabase 데이터베이스 스키마를 설계하고 마이그레이션 SQL을 생성해줘.

**테이블 3개**:
1. issue_blocks (symptom/cause/resolution)
2. kb_blocks (intent/procedure/constraint/example)
3. approval_logs (승인/거부 이력)

**요구사항**:
- RLS(Row Level Security) 정책 포함
- tenant_id 기반 멀티테넌시
- 인덱스: tenant_id, ticket_id, created_at
- README.md의 스키마 정의 참고

**효율성**: 스웜으로 진행해줘:
- Swarm 1: 스키마 설계 (SQL DDL)
- Swarm 2: RLS 정책 작성
- Swarm 3: 샘플 데이터 INSERT 문 생성

**완료 후**: 
- backend/migrations/001_initial_schema.sql 파일 생성
- 'mvp-database-schema' 네임스페이스에 저장
```

### 명령어 4 (Pydantic 모델)
```
Supabase 스키마에 맞춘 Pydantic 모델을 backend/models/schemas.py에 만들어줘.

**모델 클래스**:
- IssueBlock (BaseModel)
- KBBlock (BaseModel)
- TicketContext (입력)
- SearchResult (검색 결과)
- ProposedAction (AI 제안)
- ApprovalLog (승인 이력)

**효율성**: 페어 프로그래밍으로 진행하자. 네가 먼저 작성하면 내가 리뷰하고, 피드백 반영해줘.

**추가 작업**: Type hints, docstrings, validation 로직 모두 포함해줘.
```

---

## 🎯 Day 4-5: Freshdesk 통합 & 인제스트

### 명령어 5 (Freshdesk 서비스)
```
Freshdesk API 통합 서비스를 backend/services/freshdesk.py에 구현해줘.

**주요 메서드**:
1. fetch_tickets(updated_since: Optional[datetime]) -> List[Dict]
2. fetch_ticket_conversations(ticket_id: str) -> List[Dict]
3. fetch_kb_articles(updated_since: Optional[datetime]) -> List[Dict]
4. update_ticket_fields(ticket_id: str, updates: Dict) -> bool
5. post_reply(ticket_id: str, body: str) -> bool

**효율성**: SPARC 방법론으로 진행하되:
- Specification: 내가 승인
- Pseudocode: 자동 진행
- Architecture: 자동 진행
- Refinement: 에러 핸들링 + 재시도 로직 포함
- Completion: 유닛 테스트 자동 생성

**참고**: project-a의 core/platforms/freshdesk/ 폴더 참고해줘.

**완료 후**: 'mvp-freshdesk-integration' 네임스페이스에 저장.
```

### 명령어 6 (LLM 추출기)
```
티켓에서 Issue Block(symptom/cause/resolution)을 추출하는 LLM 서비스를 backend/services/extractor.py에 만들어줘.

**요구사항**:
- OpenAI 또는 Gemini API 사용 (환경변수로 선택)
- JSON 출력 강제 (structured output)
- 배치 처리 (한 번에 10개씩)
- 재시도 로직 (3회)
- 비용 최적화: GPT-4o-mini 또는 Gemini 1.5 Flash

**프롬프트 템플릿**:
```
티켓 내용을 분석하여 다음 JSON 형식으로 추출:
{
  "symptom": "고객이 겪은 문제 증상",
  "cause": "문제의 원인 (추정 가능한 경우)",
  "resolution": "해결 방법 또는 응답 내용"
}
```

**효율성**: 스웜으로 병렬 개발:
- Swarm 1: OpenAI 추출기
- Swarm 2: Gemini 추출기
- Swarm 3: 추상화 레이어 (strategy pattern)

**완료 후**: backend/tests/test_extractor.py도 함께 생성.
```

---

## 🎯 Day 6-8: Qdrant 검색 엔진

### 명령어 7 (Qdrant 서비스)
```
Qdrant 벡터 DB 통합을 backend/services/vector_search.py에 구현해줘.

**컬렉션 2개**:
1. issue_embeddings (멀티벡터: symptom_vec, cause_vec, resolution_vec)
2. kb_embeddings (멀티벡터: intent_vec, procedure_vec)

**주요 메서드**:
- create_collection(name: str, vector_config: Dict)
- upsert_vectors(collection: str, points: List[Dict])
- search_similar(collection: str, query_vector: List[float], filters: Dict, top_k: int)
- hybrid_search(dense_results: List, sparse_results: List) -> List (RRF 융합)

**임베딩 모델**: bge-m3 (sentence-transformers)

**효율성**: Hive-Mind로 복잡한 작업 분산:
- Queen: 전체 조율
- Worker 1: Qdrant 클라이언트 구현
- Worker 2: 임베딩 생성기
- Worker 3: RRF 융합 로직
- Worker 4: 필터링 & 부스팅

**완료 후**: 
- backend/tests/test_vector_search.py 생성
- 'mvp-vector-search' 네임스페이스에 저장
```

### 명령어 8 (BM25 Sparse 검색)
```
BM25 Sparse 검색을 backend/services/sparse_search.py에 추가해줘.

**옵션 2개 중 선택**:
1. OpenSearch 클라이언트 (운영 권장)
2. PostgreSQL pg_trgm (개발 간편)

**내가 선택할게**: "1번으로 해줘" 또는 "2번으로 해줘"

**주요 메서드**:
- index_documents(collection: str, docs: List[Dict])
- bm25_search(collection: str, query: str, filters: Dict, top_k: int)

**효율성**: 페어 프로그래밍으로 진행. 선택한 옵션에 맞춰 구현 후 내가 리뷰.

**완료 후**: docker-compose.yml에 OpenSearch 또는 PostgreSQL 컨테이너 추가.
```

### 명령어 9 (재랭커)
```
Cross-Encoder 재랭커를 backend/services/reranker.py에 구현해줘.

**모델**: jinaai/jina-reranker-v2-base-multilingual

**주요 메서드**:
- rerank(query: str, candidates: List[Dict], top_k: int) -> List[Dict]
- batch_rerank(queries: List[str], candidates_list: List[List[Dict]]) -> List[List[Dict]]

**최적화**:
- 모델 캐싱 (한 번만 로드)
- 배치 처리 (한 번에 8개)
- GPU 사용 가능하면 자동 감지

**효율성**: SPARC으로 빠르게 구현하고, 성능 벤치마크까지 자동 실행해줘.

**완료 후**: backend/tests/test_reranker.py + 벤치마크 결과를 'mvp-reranker-perf' 네임스페이스에 저장.
```

---

## 🎯 Day 9-11: LangGraph 오케스트레이션

### 명령어 10 (LangGraph 상태)
```
LangGraph 상태 스키마를 backend/models/graph_state.py에 정의해줘.

**TypedDict 클래스**:
- AgentState (전체 상태)
  - ticket_context: TicketContext
  - search_results: SearchResults
  - proposed_action: ProposedAction
  - approval_status: ApprovalStatus
  - errors: List[str]
  - metadata: Dict

**효율성**: Pydantic과 TypedDict 둘 다 생성하고, 변환 함수도 함께 만들어줘.
```

### 명령어 11 (LangGraph 노드 - 스웜)
```
LangGraph 노드를 backend/agents/ 폴더에 역할별로 구현하자. 스웜으로 병렬 개발해줘.

**Swarm 1 - Retriever Agent** (agents/retriever.py):
- retrieve_cases(state: AgentState) -> AgentState
- retrieve_kb(state: AgentState) -> AgentState

**Swarm 2 - Resolution Agent** (agents/resolver.py):
- propose_solution(state: AgentState) -> AgentState
- propose_field_updates(state: AgentState) -> AgentState

**Swarm 3 - Router** (agents/router.py):
- context_router(state: AgentState) -> str (next node 결정)

**각 노드 요구사항**:
- 에러 핸들링
- 로깅
- 타임아웃 (30초)
- 상태 업데이트

**효율성**: 3개 스웜이 동시에 작업하되, 공통 유틸은 agents/utils.py에 별도 관리.

**완료 후**: 각 에이전트별 유닛 테스트 자동 생성.
```

### 명령어 12 (LangGraph 그래프)
```
LangGraph 워크플로우 그래프를 backend/agents/orchestrator.py에 조립해줘.

**노드 연결**:
START → context_router → (티켓/KB/일반 분기)
  ├─ 티켓 → retrieve_cases → retrieve_kb → propose_solution → propose_field_updates → human_approve → execute_changes → log_feedback → END
  ├─ KB → retrieve_kb → propose_solution → human_approve → END
  └─ 일반 → propose_solution → END

**조건부 엣지**:
- human_approve에서: approved/modified/rejected 분기
- 에러 발생 시: error_handler → END

**효율성**: Hive-Mind로 복잡도 관리:
- Queen: 전체 그래프 조율
- Worker 1: 노드 연결
- Worker 2: 조건부 로직
- Worker 3: 에러 핸들링
- Worker 4: 상태 검증

**완료 후**: 
- backend/tests/test_orchestrator.py 생성
- 시각화 다이어그램(Mermaid) 자동 생성
- 'mvp-langgraph-orchestration' 네임스페이스에 저장
```

---

## 🎯 Day 12-14: FastAPI 엔드포인트

### 명령어 13 (FastAPI 라우트)
```
FastAPI 라우트를 backend/routes/ 폴더에 구현하자. 스웜으로 병렬 개발해줘.

**Swarm 1** - routes/assist.py:
- POST /api/assist/{ticket_id}/suggest
  - 입력: TicketContext
  - 출력: ProposedAction (유사사례 + KB + 초안 + 필드 제안)
- POST /api/assist/{ticket_id}/approve
  - 입력: ApprovalRequest (approved/modified/rejected + 수정 내용)
  - 출력: ExecutionResult

**Swarm 2** - routes/sync.py:
- POST /api/sync/tickets (증분 동기화)
- POST /api/sync/kb (KB 동기화)
- GET /api/sync/status (마지막 동기화 시간)

**Swarm 3** - routes/health.py:
- GET /api/health (서비스 상태)
- GET /api/health/dependencies (Qdrant, Supabase, LLM 연결 체크)

**공통 요구사항**:
- Pydantic 모델 검증
- 에러 핸들링 (HTTPException)
- 로깅
- CORS 설정

**효율성**: 3개 스웜 동시 작업 후, main.py에 자동 통합.

**완료 후**: OpenAPI 문서 자동 생성 확인 (http://localhost:8000/docs).
```

### 명령어 14 (미들웨어 & 유틸)
```
FastAPI 미들웨어와 유틸리티를 추가해줘.

**미들웨어** (backend/middleware/):
- tenant_middleware.py: tenant_id 추출 및 검증
- logging_middleware.py: 요청/응답 로깅
- rate_limit_middleware.py: 속도 제한 (선택)

**유틸리티** (backend/utils/):
- auth.py: API 키 검증
- cache.py: Redis 캐싱 (선택)
- metrics.py: Prometheus 메트릭 (선택)

**효율성**: 페어 프로그래밍으로 진행. 필수 기능만 먼저 구현하고, 선택 기능은 내가 필요하면 추가 요청할게.

**완료 후**: main.py에 미들웨어 자동 등록.
```

---

## 🎯 Day 15-16: Freshdesk FDK 앱

### 명령어 15 (FDK 앱 UI)
```
Freshdesk FDK 앱을 frontend/app/ 폴더에 업데이트하자.

**수정할 파일**:
1. app/index.html (티켓 사이드바 레이아웃)
2. app/scripts/app.js (백엔드 API 호출)
3. app/styles/main.css (UI 스타일)
4. config/iparams.json (설정 파라미터: 백엔드 URL)

**UI 구성** (README.md 섹션 8 참고):
┌─────────────────────────────────────┐
│ AI 요약 & 상태                      │
│ - 요약: [1줄 요약]                  │
│ - 감정: 😊 긍정 | 긴급도: 🔴 높음  │
├─────────────────────────────────────┤
│ 유사사례 Top-5                      │
│ 1. [티켓#123] 요약 + 링크          │
├─────────────────────────────────────┤
│ KB 절차 (Top-2)                     │
│ 1. [KB-001] 단계 + 주의점          │
├─────────────────────────────────────┤
│ AI 제안                             │
│ - 응답 초안: [편집 가능]           │
│ - 필드 업데이트: 카테고리/우선순위  │
├─────────────────────────────────────┤
│ [승인 후 전송] [수정하기] [무시]    │
└─────────────────────────────────────┘

**효율성**: 페어 프로그래밍으로 UI 먼저 만들고, 내가 확인 후 백엔드 연동.

**완료 후**: 
- 로컬 테스트 방법 README에 추가
- 'mvp-fdk-app' 네임스페이스에 저장
```

### 명령어 16 (FDK 앱 연동)
```
FDK 앱과 백엔드 API를 연동해줘.

**수정할 파일**:
- app/scripts/app.js
  - fetchSuggestions(ticketId) → POST /api/assist/{ticket_id}/suggest
  - submitApproval(ticketId, approval) → POST /api/assist/{ticket_id}/approve

**에러 핸들링**:
- 네트워크 에러
- 타임아웃 (30초)
- 백엔드 5xx 에러

**효율성**: SPARC으로 빠르게 구현하고, 브라우저 콘솔 로깅 추가.

**완료 후**: 통합 테스트 시나리오 문서화.
```

---

## 🎯 Day 17-18: 배포 & 인프라

### 명령어 17 (Docker Compose)
```
Docker Compose 설정을 만들어줘.

**컨테이너 5개**:
1. fastapi-app (backend/)
2. qdrant (qdrant/qdrant:latest)
3. opensearch (opensearchproject/opensearch:2.11.0) 또는 postgres
4. redis (redis:7-alpine) - 캐싱용
5. supabase (supabase/postgres:15) - 또는 외부 Supabase 사용

**네트워크**: 
- backend-network (내부 통신)

**볼륨**:
- qdrant-data
- postgres-data
- redis-data

**환경변수**: .env 파일 자동 로드

**효율성**: 스웜으로 병렬 작성:
- Swarm 1: docker-compose.yml
- Swarm 2: Dockerfile (FastAPI 앱용)
- Swarm 3: .dockerignore

**완료 후**: 
- README.md에 실행 방법 추가 (docker-compose up)
- 'mvp-deployment' 네임스페이스에 저장
```

### 명령어 18 (초기 데이터 로드)
```
샘플 데이터 로드 스크립트를 backend/scripts/seed_data.py에 만들어줘.

**데이터 준비**:
1. Freshdesk에서 티켓 50개 가져오기
2. LLM 추출기로 Issue Block 생성
3. 임베딩 생성
4. Qdrant + Supabase에 저장

**실행 방법**:
```bash
python backend/scripts/seed_data.py --tickets 50 --kb 20
```

**효율성**: SPARC으로 구현하고, 진행률 표시(tqdm) 추가.

**완료 후**: 
- 실행 후 검증 쿼리 (검색 테스트 10개)
- 결과를 'mvp-seed-data' 네임스페이스에 저장
```

---

## 🎯 Day 19-20: 통합 테스트 & 성능 튜닝

### 명령어 19 (E2E 테스트)
```
엔드투엔드 테스트를 backend/tests/test_e2e.py에 작성해줘.

**테스트 시나리오 5개**:
1. 티켓 입력 → 유사사례 검색 → 제안 생성
2. KB 검색 → 절차 제안
3. 필드 업데이트 승인 → Freshdesk API 패치
4. 승인 거부 → 로그 저장
5. 에러 핸들링 (Qdrant 연결 실패)

**검증 항목**:
- 응답 시간 < 5초
- 검색 결과 Top-5 반환
- Supabase 로그 정상 저장

**효율성**: pytest + pytest-asyncio 사용, 병렬 테스트 실행.

**완료 후**: CI/CD용 GitHub Actions 워크플로우도 함께 생성해줘.
```

### 명령어 20 (성능 벤치마크)
```
성능 벤치마크를 실행하고 최적화 제안해줘.

**측정 항목**:
1. 임베딩 생성 속도 (bge-m3)
2. Qdrant 검색 속도 (Top-200)
3. BM25 검색 속도
4. 재랭킹 속도 (Top-200 → Top-20)
5. LLM 호출 지연 (GPT-4o-mini)
6. 전체 파이프라인 (E2E)

**도구**: pytest-benchmark 또는 locust

**효율성**: 벤치마크 자동 실행하고, 병목 지점 식별 후 최적화 제안 3가지 제시해줘.

**완료 후**: 
- 벤치마크 결과를 'mvp-performance' 네임스페이스에 저장
- README.md에 성능 지표 섹션 추가
```

---

## 🚀 효율성 극대화 전략 (통합 명령)

### 전략 1: 메타 명령어 (여러 작업 한 번에)
```
"Day 2-3 작업을 모두 진행하자:
1. Supabase 스키마 생성 (명령어 3)
2. Pydantic 모델 구현 (명령어 4)

스웜으로 병렬 작업하고, 완료되면 'mvp-day2-3-complete' 네임스페이스에 통합 저장해줘."
```

### 전략 2: 자동 검증 + 수정
```
"명령어 11을 실행하되:
- 각 에이전트 구현 후 자동으로 유닛 테스트 실행
- 테스트 실패 시 자동으로 코드 수정
- 모든 테스트 통과할 때까지 반복
- 최종 결과만 보고해줘"
```

### 전략 3: 의존성 자동 관리
```
"명령어 7-9를 Hive-Mind로 진행하자:
- Queen: 검색 파이프라인 전체 조율
- Worker 1-3: 각각 Qdrant/BM25/Reranker 병렬 구현
- 의존성 자동 파악하여 순서 조정
- 완료 후 통합 테스트 자동 실행"
```

### 전략 4: 점진적 복잡도 증가
```
"명령어 12를 단계별로 진행하자:
1단계: 최소 그래프만 구현 (context_router → propose_solution → END)
2단계: 검색 노드 추가 (retrieve_cases, retrieve_kb)
3단계: 승인 루프 추가 (human_approve → execute_changes)
4단계: 에러 핸들링 추가

각 단계마다 테스트하고, 내가 승인하면 다음 단계로 진행해줘."
```

### 전략 5: 세션 재개 활용
```
"어제 작업하던 LangGraph 오케스트레이션(명령어 12) 계속하자.
현재 진행 상황 요약하고, 다음 단계 제안해줘."
```

---

## 📊 진행 상황 추적 명령어

### 일일 체크인
```
"오늘 작업 계획을 세우자:
1. 어제까지 완료된 작업 요약
2. 오늘 목표 (Day X 작업)
3. 예상 소요 시간
4. 필요한 리소스(API 키, 테스트 데이터 등)

계획 확정되면 자동으로 시작해줘."
```

### 주간 리뷰
```
"이번 주(W1) 작업을 리뷰하자:
1. 완료된 네임스페이스 목록
2. 생성된 파일 통계
3. 테스트 커버리지
4. 다음 주 우선순위 제안

리뷰 결과를 'mvp-week1-review' 네임스페이스에 저장해줘."
```

### 긴급 디버깅
```
"현재 Qdrant 연결 에러가 발생했어. 
1. 에러 로그 분석
2. 원인 파악
3. 수정 방안 3가지 제시
4. 내가 선택하면 자동으로 수정 적용

빠르게 진행해줘."
```

---

이렇게 **구체적인 명령어 + 효율성 전략**을 조합하면 8주 MVP를 **4-5주로 단축**할 수 있습니다! 🎉