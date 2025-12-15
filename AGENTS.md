# 소통방식
- Please let me know if you have any questions before making the plan!
- 사용자와의 대화는 반드시 한국어로만 소통한다.

> **Note**: The backend logic described in this document has been migrated to the `agent-platform` repository. This repository (`project-a`) now focuses on the Frontend (Freshdesk App).

# AI Contact Center OS – 다중 에이전트 아키텍처

## 개요

AI Contact Center OS는 LangGraph 기반 오케스트레이션과 역할 분리된 다중 에이전트 시스템을 통해 상담원 지원 업무를 자동화합니다. 각 에이전트는 특정 도메인에 특화되어 독립적으로 동작하며, LangGraph의 상태 기반 워크플로우를 통해 협력합니다.

> **Core Memory Space ID (spinoff)**: `cmhetlxnf3g4zqj1vf764glel`

---

## Phase 1: MVP 핵심 에이전트 (4종)

### 1. Orchestrator Agent (오케스트레이터)

**역할**: 전체 워크플로우 제어 및 에이전트 간 조율

**책임**:
- 티켓 유형 라우팅 (티켓 컨텍스트 / KB 검색 / 일반 대화)
- 에이전트 실행 순서 및 병렬 처리 제어
- 상태 관리 (LangGraph State)
- 에러 핸들링 및 재시도 로직
- 승인 루프 관리

**주요 노드**:
- `context_router`: 입력 분류 및 라우팅
- `workflow_coordinator`: 에이전트 실행 순서 결정
- `error_handler`: 에러 복구 및 fallback

**기술 스택**:
- LangGraph (상태 기반 그래프 실행)
- FastAPI (API 엔드포인트)
- Pydantic (상태 스키마 정의)

**입력/출력**:
- 입력: Freshdesk 티켓 컨텍스트 (ID, 제목, 본문, 메타데이터)
- 출력: 최종 제안 (응답 초안, 필드 업데이트, 유사사례, KB 절차)

---

### 2. Retriever Agent (검색 에이전트)

**역할**: 유사사례 및 KB 검색 엔진

**책임**:
- 구조화 쿼리 생성 (product, component, error_code, 기간 등)
- 하이브리드 검색 실행 (Dense + Sparse)
- 메타 필터링 (tenant_id, product, version 등)
- 재랭킹 (Cross-Encoder)
- 시간 감쇠 및 부스팅 적용

**주요 노드**:
- `retrieve_cases`: 유사사례 Top-200 후보 생성 → Top-5 재랭킹
- `retrieve_kb`: 관련 KB 절차 Top-20 → Top-2 재랭킹
- `query_builder`: LLM 기반 구조화 쿼리 생성

**기술 스택**:
- Qdrant (벡터 데이터베이스, 멀티벡터 인덱싱)
- OpenSearch / pg_trgm (BM25 Sparse 검색)
- jina-reranker-v2-base (크로스인코더 재랭커)
- bge-m3 / e5-mistral (임베딩 모델)

**검색 파이프라인**:
```
입력 쿼리
  ↓
Query Builder (LLM) → 구조화 쿼리 (product/component/error_code/기간)
  ↓
Hybrid Search
  ├─ Dense (Qdrant 멀티벡터) → Top-N
  ├─ Sparse (BM25) → Top-N
  └─ RRF (Reciprocal Rank Fusion) + time decay + error_code boosting
  ↓
Re-ranker (Cross-Encoder) → Top-200 → Top-20
  ↓
출력: 유사사례 Top-5 + KB 절차 Top-2
```

**입력/출력**:
- 입력: 구조화 쿼리 (티켓 메타데이터 + 본문)
- 출력:
  - `similar_cases`: Top-5 유사사례 (티켓 ID, 요약, 유사도 점수)
  - `kb_procedures`: Top-2 KB 절차 (문서 ID, 단계, 주의사항)

---

### 3. Resolution Agent (해결 에이전트)

**역할**: 솔루션 합성 및 응답 생성

**책임**:
- 유사사례 + KB 절차 결합 요약
- 응답 초안 생성 (상담원 승인용)
- 필드 업데이트 제안 (카테고리, 태그, 우선순위, 상태)
- 근거 링크 첨부 (유사사례/KB 출처)

**주요 노드**:
- `propose_solution`: 유사사례와 KB를 결합한 응답 초안 생성
- `propose_field_updates`: 티켓 필드 자동 업데이트 제안
- `draft_response`: 상담원 승인용 최종 초안

**기술 스택**:
- LLM (GPT-4o-mini / Claude 3.5 / Gemini 1.5)
- 프롬프트 템플릿 (Jinja2 / LangChain)
- 출력 구조화 (Pydantic)

**생성 프로세스**:
```
입력: 유사사례 Top-5 + KB 절차 Top-2 + 티켓 컨텍스트
  ↓
LLM Synthesis
  ├─ 유사사례 패턴 분석
  ├─ KB 절차 적용 가능성 검토
  └─ 현재 티켓에 맞춤화
  ↓
출력:
  ├─ 응답 초안 (고객에게 보낼 메시지)
  ├─ 필드 업데이트 제안 (카테고리, 태그, 우선순위 등)
  └─ 근거 (유사사례 링크 + KB 문서 링크)
```

**입력/출력**:
- 입력:
  - `similar_cases`: Retriever Agent 출력
  - `kb_procedures`: Retriever Agent 출력
  - `ticket_context`: 현재 티켓 정보
- 출력:
  - `draft_response`: 응답 초안
  - `field_updates`: 필드 업데이트 제안 (JSON)
  - `justification`: 근거 및 출처

---

### 4. Human Agent (승인 인터페이스)

**역할**: 상담원 승인 루프 관리

**책임**:
- FDK 앱 UI 렌더링 (티켓 사이드바)
- 상담원 피드백 수집 (승인 / 수정 / 거부)
- Freshdesk API 연계 (필드 패치)
- 승인 로그 저장 (피드백 루프)

**주요 노드**:
- `human_approve`: 승인/수정/거부 대기
- `execute_changes`: Freshdesk API PATCH 실행
- `log_feedback`: Supabase 로그 적재

**FDK 앱 패널 구성**:
```
┌─────────────────────────────────────┐
│ AI 요약 & 상태                      │
│ - 요약: [1줄 요약]                  │
│ - 감정: 😊 긍정 | 긴급도: 🔴 높음  │
├─────────────────────────────────────┤
│ 유사사례 Top-5                      │
│ 1. [티켓#123] 근거 링크 + 요약     │
│ 2. [티켓#456] ...                   │
├─────────────────────────────────────┤
│ KB 절차 (Top-2)                     │
│ 1. [KB-001] 단계별 절차 + 주의점   │
├─────────────────────────────────────┤
│ AI 제안                             │
│ - 응답 초안: [편집 가능 텍스트]    │
│ - 필드 업데이트:                    │
│   카테고리: [결제] → [기술지원]     │
│   우선순위: [중간] → [높음]         │
├─────────────────────────────────────┤
│ 버튼                                │
│ [승인 후 전송] [수정하기]          │
│ [필드만 업데이트] [무시]           │
└─────────────────────────────────────┘
```

**기술 스택**:
- Freshdesk FDK (티켓 사이드바 iframe 앱)
- Freshdesk API (티켓 필드 PATCH)
- Supabase (승인 로그 저장)

**승인 플로우**:
```
AI 제안 표시
  ↓
상담원 선택
  ├─ [승인 후 전송] → Freshdesk API PATCH + 로그 저장
  ├─ [수정하기] → 응답/필드 수정 → API PATCH + 로그
  ├─ [필드만 업데이트] → 필드만 PATCH + 로그
  └─ [무시] → 로그만 저장 (rejection 기록)
  ↓
피드백 루프 (학습 데이터로 활용)
```

**입력/출력**:
- 입력:
  - `draft_response`: Resolution Agent 출력
  - `field_updates`: 필드 업데이트 제안
- 출력:
  - `approval_status`: approved / modified / rejected
  - `final_response`: 최종 응답 (상담원 수정 반영)
  - `final_field_updates`: 최종 필드 업데이트
  - `feedback_log`: Supabase 로그

---

## Phase 2~3: 확장 에이전트

### 5. Analyzer Agent (분석 에이전트)

**역할**: 티켓 의도, 감정, 원인 분석

**책임**:
- 의도 분류 (문의 / 불만 / 요청 / 기술지원)
- 감정 분석 (긍정 / 중립 / 부정 / 긴급)
- 근본 원인 추론 (RCA: Root Cause Analysis)

**기술 스택**:
- LLM (분류·감정 분석)
- 경량 분류 모델 (distilbert-base-uncased-finetuned-sst-2)

---

### 6. Compliance Agent (컴플라이언스 에이전트)

**역할**: 개인정보 보호 및 정책 준수

**책임**:
- PII 탐지 및 마스킹 (이메일, 전화, 계좌, 주민번호 등)
- DLP (Data Loss Prevention) 정책 검증
- 규제 준수 검사 (GDPR, CCPA 등)

**기술 스택**:
- spaCy / Presidio (PII 탐지)
- 정규 표현식 (한국형 PII: 주민번호, 계좌번호)

---

### 7. KB-Agent (지식베이스 에이전트)

**역할**: 신규 KB 문서 제안

**책임**:
- 반복 패턴 탐지 (유사 티켓 클러스터링)
- 신규 표준 절차 제안
- KB 갭 분석 (커버리지가 낮은 영역 식별)

**기술 스택**:
- HDBSCAN (클러스터링)
- LLM (KB 초안 생성)

---

### 8. Metrics Agent (지표 집계 에이전트)

**역할**: KPI 추적 및 대시보드

**책임**:
- 검색 품질 지표 (Recall@10, nDCG@10)
- 도입 효과 지표 (승인률, 응답시간, FTR)
- 운영 지표 (에러율, 평균 지연, LLM 비용)

**기술 스택**:
- Supabase (로그 집계)
- Grafana / Metabase (대시보드)

---

## 에이전트 간 상호작용 (LangGraph 워크플로우)

### 전체 플로우 (MVP)

```
┌─────────────────────────────────────────────────────────┐
│                 Orchestrator Agent                      │
│  (context_router, workflow_coordinator, error_handler)  │
└────────────────────┬────────────────────────────────────┘
                     ↓
           ┌─────────┴─────────┐
           ↓                   ↓
   ┌──────────────┐    ┌──────────────┐
   │  Retriever   │    │  Resolution  │
   │    Agent     │    │    Agent     │
   └──────┬───────┘    └──────┬───────┘
          │                   │
          └─────────┬─────────┘
                    ↓
            ┌──────────────┐
            │    Human     │
            │    Agent     │
            └──────────────┘
                    ↓
          ┌──────────────────┐
          │  Freshdesk API   │
          │  (Field PATCH)   │
          └──────────────────┘
```

### 상세 워크플로우

```
1. 티켓 입력
   ↓
2. Orchestrator: context_router
   ├─ 티켓 컨텍스트? → Retriever Agent 호출
   ├─ KB 검색? → Retriever Agent (KB 모드)
   └─ 일반 대화? → Resolution Agent (직접)
   ↓
3. Retriever Agent (병렬 실행)
   ├─ retrieve_cases → 유사사례 Top-5
   └─ retrieve_kb → KB 절차 Top-2
   ↓
4. Resolution Agent
   ├─ propose_solution → 응답 초안
   └─ propose_field_updates → 필드 제안
   ↓
5. Human Agent
   ├─ human_approve → 상담원 승인 대기
   └─ execute_changes → Freshdesk API PATCH
   ↓
6. log_feedback → Supabase 로그 저장
   ↓
7. 완료
```

### Phase 2 확장 시

```
Analyzer Agent (의도/감정) → Orchestrator에 병렬 연결
Compliance Agent (PII 마스킹) → Retriever/Resolution 전에 실행
KB-Agent (신규 문서 제안) → 백그라운드 배치 작업
Metrics Agent (지표 집계) → 별도 스케줄러로 실행
```

---

## 구현 기술 스택 요약

| 에이전트 | 주요 기술 | 모델/라이브러리 |
|---------|----------|----------------|
| Orchestrator | LangGraph, FastAPI | Pydantic |
| Retriever | Qdrant, OpenSearch | bge-m3, jina-reranker-v2 |
| Resolution | LLM API | GPT-4o-mini / Claude 3.5 |
| Human | Freshdesk FDK, API | Supabase |
| Analyzer | LLM, 분류 모델 | distilbert-sst-2 |
| Compliance | spaCy, Presidio | 정규 표현식 |
| KB-Agent | HDBSCAN, LLM | scikit-learn |
| Metrics | Supabase, BI | Grafana |

---

## 배포 아키텍처

### 컨테이너 구성

```
Docker Compose (개발)
├─ fastapi-app (Orchestrator + Resolution + Human)
├─ qdrant (벡터 DB)
├─ opensearch (BM25)
├─ postgres (Supabase 대체 가능)
└─ redis (캐싱)

Kubernetes (프로덕션)
├─ Orchestrator Pod (FastAPI + LangGraph)
├─ Retriever Pod (검색 엔진)
├─ Resolution Pod (LLM API 호출)
└─ Worker Pods (비동기 작업)
```

### 확장 전략

- **수평 확장**: Retriever, Resolution Pod 복제
- **캐싱**: Redis로 검색 결과 캐싱
- **비동기**: Celery/RQ로 배치 작업
- **멀티테넌시**: `tenant_id` 기반 RLS + 컬렉션 분리

---

## 모니터링 & 로깅

### 필수 지표

1. **검색 품질**: Recall@10, nDCG@10
2. **도입 효과**: 승인률, 응답시간, FTR (First Time Resolution)
3. **운영**: 에러율, 평균 지연, LLM 비용/건
4. **상담원 피드백**: 수정률 (승인 대비)

### 로깅 스키마

```sql
-- Supabase 로그 테이블
create table approval_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  ticket_id text not null,
  draft_response text,
  final_response text,
  field_updates jsonb,
  approval_status text check (approval_status in ('approved','modified','rejected')),
  agent_id text,
  created_at timestamptz default now()
);
```

---

## 개발 로드맵 (8주)

| 주차 | 에이전트 작업 | 결과물 |
|-----|-------------|--------|
| W1 | Orchestrator 스캐폴드 | LangGraph 기본 그래프 |
| W2 | Retriever (인제스트) | Issue Block 저장 |
| W3 | Retriever (검색) | Qdrant + BM25 |
| W4 | Resolution | 합성 + 제안 |
| W5 | Human | FDK 앱 + 승인 루프 |
| W6 | Orchestrator (라우터) | 분기 로직 |
| W7 | 성능 튜닝 | 재랭커 가중치 |
| W8 | 파일럿 | 테넌트 1 적용 |

---

## 리스크 & 완화

| 리스크 | 완화 방안 |
|-------|----------|
| LLM 비용/지연 | 배치 추출, 캐싱, 경량 모델 전환 (Phase 2) |
| 데이터 품질 | 규칙+LLM 혼합 추출기, 하드네거티브 파인튜닝 |
| 테넌트 격리 | RLS + 벡터 페이로드 필터 + 컬렉션 분리 |
| 확장성 | 재랭킹 Top-K 조정, 비동기 워커, 캐시 |
| FDK 제약 | API 기반 자동화 중심 (브라우저 전역 제어 배제) |

---

---

## 메모리 관리 프로토콜

### Core Memory MCP 사용 가이드

**중요**: 모든 프로젝트 진행상황은 Core Memory MCP의 spinoff 스페이스에 저장합니다.

**메모리 저장 시점**:
- 각 에이전트 구현 완료 시
- 주요 마일스톤 달성 시
- 아키텍처 변경 시
- 이슈 발견 또는 해결 시
- 작업 세션 종료 전

**메모리 카테고리**:
1. **CODEBASE**: 코드베이스 구조, 파일 조직, 기술 스택
2. **MASTER_PLAN**: 프로젝트 비전, 8주 로드맵, 아키텍처
3. **COMPLETED**: 완료된 작업 (에이전트 구현, 테스트 등)
4. **PENDING**: 진행 중/예정 작업 (우선순위 포함)
5. **ISSUES**: 버그, 설계 문제, 기술 부채

**저장 방법**:
```javascript
// 세션 ID 획득
mcp__core-memory__get_session_id({ new: true })

// 메모리 저장
mcp__core-memory__memory_ingest({
  message: "구조화된 마크다운 콘텐츠...",
  sessionId: "uuid",
  spaceIds: ["cmhetlxnf3g4zqj1vf764glel"]  // spinoff space
})
```

**조회 방법**:
```javascript
// 메모리 검색
mcp__core-memory__memory_search({
  query: "Retriever Agent implementation status",
  spaceIds: ["cmhetlxnf3g4zqj1vf764glel"]
})
```

**Space ID**: `cmhetlxnf3g4zqj1vf764glel`

---

## 개발 환경 설정

### 가상환경 및 환경변수

**가상환경 위치**: 프로젝트 루트 (`/venv`)

```bash
# 가상환경 활성화
source venv/bin/activate

# 테스트 실행 (프로젝트 루트에서 실행)
pytest backend/tests/test_e2e.py -v

# 백엔드 디렉토리에서 실행 시 주의
cd backend
pytest tests/test_e2e.py -v  # ❌ .env를 찾지 못함

# 올바른 실행 방법
cd /Users/alan/GitHub/project-a-spinoff
pytest backend/tests/test_e2e.py -v  # ✅ .env를 제대로 읽음
```

**환경변수 파일**: 프로젝트 루트 (`/.env`)

**중요**: `backend/config.py`의 `env_file=".env"`는 상대 경로이므로, 테스트나 서버 실행 시 반드시 **프로젝트 루트 디렉토리에서 실행**해야 환경변수를 제대로 읽을 수 있습니다.

**환경변수 구성**:
```bash
# FastAPI
FASTAPI_ENV=development
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000

# LLM
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIzaSy...

# Qdrant (Cloud)
QDRANT_HOST=<your-qdrant-cluster>.aws.cloud.qdrant.io
QDRANT_PORT=6333
QDRANT_USE_HTTPS=true
QDRANT_API_KEY=<your-qdrant-api-key>

# Supabase
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your-anon-key>
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
SUPABASE_DB_PASSWORD=<your-db-password>
SUPABASE_DB_HOST=aws-1-ap-northeast-2.pooler.supabase.com
SUPABASE_DB_PORT=6543
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres.<your-project>

# Models
EMBEDDING_MODEL=BAAI/bge-m3
RERANKER_MODEL=jinaai/jina-reranker-v2-base-multilingual

# Freshdesk
FRESHDESK_DOMAIN=<your-domain>.freshdesk.com
FRESHDESK_API_KEY=<your-freshdesk-api-key>

# Authentication (선택사항)
ALLOWED_API_KEYS=key1,key2,key3  # 쉼표로 구분된 API 키 목록

# Logging
LOG_LEVEL=INFO
```

### 디렉토리 구조 주의사항

```
project-a-spinoff/          # 프로젝트 루트
├── venv/                   # ✅ 가상환경 (여기에 위치)
├── .env                    # ✅ 환경변수 (여기에 위치)
├── backend/
│   ├── config.py           # env_file=".env" (상대 경로)
│   ├── tests/
│   │   └── test_e2e.py
│   └── ...
└── ...
```

**실행 경로별 동작**:
- ✅ **프로젝트 루트에서 실행**: `pytest backend/tests/test_e2e.py` → `.env` 제대로 읽음
- ❌ **backend에서 실행**: `pytest tests/test_e2e.py` → `backend/.env`를 찾으려고 시도 (파일 없음)

---

## 참고 문서

- [README.md](../README.md): 전체 시스템 개요
- [CLAUDE.md](../CLAUDE.md): 개발 환경 및 메모리 관리
- [API 스펙](./API.md): REST API 계약 (예정)
- [데이터 모델](./DATA_MODEL.md): 스키마 상세 (예정)
