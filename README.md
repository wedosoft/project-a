# AI Contact Center OS – MVP

## Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- PostgreSQL (or Supabase account)
- Qdrant (local or cloud)
- Freshdesk account with API access

### Environment Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd project-a-spinoff
```

2. **Set up environment variables**
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
- `OPENAI_API_KEY` - OpenAI API key for LLM extraction
- `GOOGLE_API_KEY` - Google API key for Gemini (optional)
- `QDRANT_URL` - Qdrant server URL (default: http://localhost:6333)
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_KEY` - Supabase anon/public key
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key (for admin operations)
- `SUPABASE_DB_*` - Direct database connection parameters
- `FRESHDESK_DOMAIN` - Your Freshdesk domain (e.g., yourcompany.freshdesk.com)
- `FRESHDESK_API_KEY` - Freshdesk API key

3. **Create Python virtual environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

4. **Run database migrations**
```bash
# Using Supabase CLI or SQL editor, run:
psql <your-connection-string> -f migrations/001_initial_schema.sql
```

5. **Start services**
```bash
# Start Qdrant (if running locally)
docker run -p 6333:6333 qdrant/qdrant

# Start FastAPI backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

6. **Verify installation**
```bash
# Run tests
pytest tests/ -v

# Check API health
curl http://localhost:8000/health
```

---

# AI Contact Center OS – MVP 개발 지침서 (Final v1.0)

## 0. 팩트체크 요약 (현실성·구현 가능성)

* **Context-First 대화 UX**: Freshdesk/FSDK 앱이 `ticket` 컨텍스트를 전달하여 AI가 “현재 티켓 기준”으로 대화·추천 수행 → **가능**. (FDK iframe 제약 내에서 동작, 브라우저 전역 제어는 제외)
* **자동 필드 업데이트**: 상담원 승인 후 Freshdesk API로 카테고리/태그/우선순위 등 패치 → **가능**.
* **Issue Block 구조(Symptom/Cause/Resolution) 추출**: LLM 기반 추출기로 인제스트 시 분해 후 저장 → **가능**. (초기엔 API 호출형, 추후 경량 모델로 대체)
* **RAG 품질 개선(멀티벡터+하이브리드+재랭킹)**: Qdrant + BM25(OpenSearch/PG_trgm 대체안) + Cross-Encoder 재랭커 → **가능**. (오픈소스/온프렘 가용)
* **LangGraph 오케스트레이션**: 상태 기반 노드/분기/승인 루프 구현 → **가능**. (LangChain 대비 단순)
* **다중 에이전트(역할 분리, 상호 통신)**: MVP는 3~5개 핵심 에이전트부터 시작 → **가능**.
* **온프렘/프라이빗 클라우드 배치**: FastAPI + Supabase(Postgres 대체 가능) + Qdrant(Cloud/온프렘) → **가능**.
* **리스크**: LLM 추출·재랭킹 비용/지연, 데이터 품질 편차, 멀티테넌시/RLS 설계, 초기 평가셋 부족 → **완화안 포함**(아래 참조).

---

## 1. MVP 목표(8주)

### 기능 범위(Scope)

1. **현재 티켓 맥락 대화**: AI가 티켓 요약/의도/감정/유사사례/KB를 제안
2. **자동 필드 제안/업데이트**: 카테고리, 태그, 우선순위, 상태 추천 → 승인 후 패치
3. **유사사례+KB 융합 RAG**: 멀티벡터+하이브리드 검색, 재랭킹으로 Top-5 케이스 & 1~2개 표준 절차 제시
4. **승인 루프**: 상담원 승인/수정/거부 → 로그로 적재(피드백 루프)

### 비범위(Out of Scope)

* 브라우저 전역 자동화(코멧형 오버레이/확장)
* 옴니채널 전면 통합, 음성 실시간 대기열 자동화
* 에이전트 풀(10개+) 완전체 → **MVP는 핵심 에이전트 4종부터**

---

## 2. 시스템 아키텍처(요약)

**구성**: FastAPI(코어) + LangGraph(오케스트레이션) + Qdrant(벡터) + Postgres/Supabase(메타) + Freshdesk App(승인 UI)

```
[Freshdesk App (FDK)]  ←현재 티켓→  [FastAPI+LangGraph]
       │                                 │
승인/수정 UI ───────────────▶  Orchestrator (router, state)
       │                                 ├─ Retrieval Engine (Qdrant + BM25)
FD API 패치 ◀───────────────  ├─ KB Engine (KB embeddings)
       │                                 ├─ Reasoner/Generator (LLM)
       └──────── 로깅/지표 ──▶  └─ Governance (logs, metrics)
```

배포: Docker Compose(개발) → K8s/VM(운영), Qdrant Cloud 또는 온프렘 Qdrant 선택, Supabase(관리형 Postgres) 또는 자체 Postgres.

---

## 3. 데이터 모델(최소 스키마)

### 3.1 Issue Blocks (티켓 지식 = 경험)

* `block_type`: `symptom | cause | resolution`
* `content`: 추출된 핵심 문장/요약(최대 512~1,024자)
* `meta`: `tenant_id, ticket_id, product, component, error_code, created_at, lang, tags[]`

**Postgres (Supabase)**

```sql
create table issue_blocks (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  ticket_id text not null,
  block_type text check (block_type in ('symptom','cause','resolution')),
  product text, component text, error_code text,
  content text not null,
  meta jsonb,
  embedding_id text unique,
  created_at timestamptz default now()
);
```

**Qdrant (컬렉션: `issue_embeddings`)**

* 멀티벡터: `symptom_vec`, `cause_vec`, `resolution_vec`
* 페이로드: 위 메타 + `content`

### 3.2 KB Blocks (정책/절차 = 규범)

* `intent`, `procedure(step)`, `constraint`, `example`
* 멀티벡터: `intent_vec`, `procedure_vec`

**Postgres**

```sql
create table kb_blocks (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  article_id text,
  intent text,
  step text,
  constraint text,
  example text,
  meta jsonb,
  embedding_id text unique,
  created_at timestamptz default now()
);
```

**Qdrant (컬렉션: `kb_embeddings`)**

---

## 4. 인제스트 & 추출 파이프라인

### 4.1 흐름

1. 티켓/코멘트/노트 수집(Freshdesk API)
2. **LLM 추출기**: `symptom/cause/resolution` JSON 생성(비용 절감 위해 배치·비동기)
3. 필드별 임베딩 생성(e5/bge 계열, L2 normalize)
4. Qdrant 업서트 + Postgres 메타 저장
5. 증분: 업데이트 해시로 변경 감지(본문/메타), 재인덱싱 최소화

### 4.2 모델 제안(온프렘 친화·한/영 혼용)

* **Embedding**: `bge-m3` 또는 `e5-mistral`
* **Reranker**: `jina-reranker-v2-base`(크로스인코더)
* **LLM(추출/합성)**: 클라우드 우선(GPT-4o-mini/Claude 3.5/Gemini 1.5) → 이후 경량 온프렘 대체

> 팩트체크: 위 모델들은 공개 가용/온프렘 배치 가능(LLM만 선택적). 임베딩/재랭커만으로도 검색 품질 체감 개선 큼.

---

## 5. 검색 파이프라인(v2)

1. **Query Builder(LLM)**: “현재 티켓”에서 product/component/error_code/기간 등 **구조화 쿼리** 생성
2. **Candidate Gen (Hybrid)**

   * Dense: Qdrant 멀티벡터(증상/해결) Top-N
   * Sparse: BM25(OpenSearch 권장, 대안: Postgres pg_trgm)
   * Meta 필터: `tenant_id/product/component/version/기간`
   * **RRF(Late Fusion)** + time decay + error_code 부스팅
3. **Re-ranker**: Top-200 → 크로스인코더 Top-20
4. **Synthesis**: 유사사례 Top-5 + KB 절차 1~2개 결합 요약
5. **Action Draft**: 응답 초안 + 필드 업데이트 제안(카테고리/태그/우선순위 등)

> 팩트체크: Dense+Sparse 결합(RRF), 크로스인코더 재랭킹은 IR 표준 기법. Qdrant+BM25 조합은 일반적이며 운영 경험 다수.

---

## 6. 오케스트레이션( LangGraph )

### 필수 노드(MVP)

* `context_router`: 티켓/KB/일반대화 라우팅
* `retrieve_cases`: 유사사례 검색
* `retrieve_kb`: 관련 KB 검색
* `propose_solution`: 합성·제안
* `propose_field_updates`: 필드 제안
* `human_approve`: 승인/수정/거부 수집
* `execute_changes`: Freshdesk API 패치
* `log_feedback`: Supabase 로그 적재

> 팩트체크: LangGraph는 상태 기반 분기/루프/병렬 처리가 가능, FastAPI와 궁합 양호. PoC→프로덕션 전환에 적합.

---

## 7. 다중 에이전트(역할 분리, 단계적 도입)

### MVP(Phase 1, 권장 4 Agents)

* **Orchestrator Agent**(그래프 제어)
* **Retriever Agent**(유사사례/KB 검색)
* **Resolution Agent**(제안·초안)
* **Human Agent**(승인 인터페이스)

### 확장(Phase 2~3)

* Analyzer(의도/감정/원인), Compliance(PII/DLP), KB-Agent(신규 문서 제안), Metrics(지표 집계)

> 팩트체크: LangGraph에서 노드 확장으로 자연스럽게 증가 가능. 병렬 실행로 응답속도 개선 여지.

---

## 8. 상담원 UX (FDK App – 티켓 사이드바)

### 패널 구성(고정 1패널)

* **요약/상태**: AI 요약, 감정, 긴급도
* **유사사례 Top-5**: 근거 링크·요약
* **KB 절차 1~2**: 단계 요약·주의점
* **AI 제안**: 응답 초안 + 필드 업데이트
* **버튼**: `[승인 후 전송] [수정하기] [필드만 업데이트] [무시]`

> 팩트체크: FDK iframe에서 구현 가능(티켓 컨텍스트 접근, 외부 API 호출, Freshdesk API 연계).

---

## 9. 보안·거버넌스

* **RLS(행 레벨 보안)**: `tenant_id` 기반 접근 분리
* **비식별화**: LLM 호출 전 PII 마스킹(이메일/전화/계좌/주민번호 등)
* **감사 로깅**: 제안/승인/거부/패치 이력(Postgres)
* **모델 버전/프롬프트 버전 관리**: LangGraph 메타 + CI/CD 변수
* **오프라인 온프렘 경로**: LLM 호출 없이도 검색/재랭킹/필드 업데이트는 동작(추출기만 대체 필요)

---

## 10. 지표·품질 관리(KPI)

* **검색 품질**: Recall@10, nDCG@10
* **도입효과**: 상담원 **승인률(Adoption Rate)**, 응답 시간 단축, 1차 해결률(FTR)
* **정확도**: 승인 대비 수정율(수정 적을수록 양호)
* **운영**: 에러율, 평균 지연, LLM 비용/건

> 팩트체크: 모든 지표는 Supabase 로그+간단 대시보드로 측정 가능. 초기엔 최소 세트로 시작.

---

## 11. 구현 순서(8주 플랜)

**W1**: Repo 초기화, FastAPI+LangGraph 스캐폴드, FDK 샘플 앱
**W2**: 인제스트(티켓 수집) + 추출기(LLM) + Issue Block 저장
**W3**: 임베딩/인덱싱(Qdrant) + 하이브리드 Candidate Gen
**W4**: 재랭커 + 합성 + 제안(유사사례+KB)
**W5**: 필드 업데이트 제안/승인/패치, 피드백 로깅
**W6**: 라우터(티켓/KB/일반대화) + 타임디케이/부스팅
**W7**: 성능 튜닝(가중치/재랭커) + 지표 대시보드
**W8**: 파일럿/테넌트 1사례 적용, 베타 운영 가이드

---

## 12. 리스크 & 완화

* **LLM 비용/지연**: 배치추출·캐싱·경량 모델 전환(Phase 2)
* **데이터 품질**: 규칙+LLM 혼합 추출기, 하드네거티브로 임베딩 점진 티닝
* **테넌트 격리**: RLS + 벡터 페이로드 필터 + 컬렉션 분리(대형 테넌트)
* **확장성**: 재랭킹 Top-K 조정, 비동기 워커, 캐시 도입
* **FDK 제약**: 전역 브라우저 제어는 배제(기획상 제외), API 기반 자동화 중심

---

## 13. 최소 API 계약(예시)

* `POST /api/tickets/:id/context` → 현재 티켓 컨텍스트 수신
* `POST /api/assist/:id/suggest` → 유사사례+KB+제안
* `POST /api/assist/:id/approve` → 승인/수정/거부 기록
* `PATCH /api/tickets/:id/fields` → 필드 업데이트 실행
* `GET /api/metrics` → KPI & 로그 요약

---

### 최종 결론

* 제안 내용은 **모두 현 시점에서 구현 가능**하며, **MVP 범위로 현실화**했습니다.
* 핵심은 **“현재 티켓 맥락”**을 기준으로 **유사사례+KB**를 **한 번에** 제안하고, **승인 기반 자동화**까지 닫는 **짧은 루프**입니다.
* 구조적 선택(멀티벡터·하이브리드·재랭킹·LangGraph)은 **IR/오케스트레이션의 표준적이고 보수적인 조합**이며, 과장 없음입니다.
