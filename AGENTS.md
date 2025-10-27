# Project-A Spinoff: Vertex AI Migration

**상태**: Phase 0 완료, Phase 1 준비
**저장소**: https://github.com/wedosoft/project-a-spinoff
**목적**: 레거시(15K줄) → Vertex AI 기반 단순 시스템(800줄)

## 현황

### 완료 (Phase 0)
- ✅ Git 저장소 초기화
- ✅ Backend 구조 생성 (routes/, services/, models/, utils/)
- ✅ 기본 파일 (main.py, requirements.txt, .env.example)
- ✅ Frontend 복사 (project-a에서)
- ✅ GitHub 연동 완료

### 데이터
- 티켓: 4,800개
- KB 문서: 1,300개
- 증분 수집: 2시간마다

### 기술 스택 확정
- Backend: FastAPI + Fly.io (nrt/나리타)
- DB/Search: Vertex AI Search (asia-northeast3/서울)
- LLM: Gemini API
- Scheduler: Fly.io Machines API

## 아키텍처

```
Freshdesk App (Frontend)
       ↓
Fly.io Backend (nrt/도쿄) 🇯🇵
  - FastAPI
  - Stateless (임시 처리만)
  - 지연: ~30-50ms to 서울
       ↓
Vertex AI Search (asia-northeast3/서울) 🇰🇷
  - 모든 데이터 영구 저장
  - 자동 임베딩/파싱
  - Gemini 통합
       ↑
Fly.io Scheduled (2시간마다)
       ↑
Freshdesk API
```

### 컴플라이언스
- ✅ 데이터 영구 저장: 한국(서울)
- ✅ 백엔드 일시 처리: 일본(도쿄)
- ✅ 개인정보보호법 준수 (영구 저장소 기준)

## 프로젝트 구조

```
project-a-spinoff/
├── backend/           # 800줄 전체
│   ├── main.py                  # 50줄
│   ├── requirements.txt         # 7개 패키지
│   ├── routes/
│   │   ├── health.py           # 30줄
│   │   ├── init.py             # 80줄 - 티켓 로드
│   │   ├── query.py            # 150줄 - RAG 파이프라인
│   │   └── sync.py             # 100줄 - 데이터 동기화
│   ├── services/
│   │   ├── freshdesk.py        # 150줄
│   │   ├── vertex_search.py    # 100줄
│   │   ├── gemini.py           # 80줄
│   │   └── sync_service.py     # 150줄
│   ├── models/schemas.py       # 100줄
│   └── utils/tenant.py         # 40줄
└── frontend/          # project-a 복사
```

## 실행 계획

### Phase 1: GCP 환경 셋업 (1주)
- GCP 프로젝트 생성
- Vertex AI API 활성화
- Datastore 생성 (asia-northeast3/서울)
- 샘플 데이터 100개 업로드
- 품질 검증 (10개 쿼리)

### Phase 2: 백엔드 핵심 (1주)
- services/vertex_search.py
- services/gemini.py  
- services/freshdesk.py
- routes/query.py (RAG)
- services/sync_service.py

### Phase 3: 프론트엔드 연동 (3일)
- backend-config.js URL 변경
- 통합 테스트

### Phase 4: Fly.io 배포 (2일)
- fly.toml 작성 (nrt 리전)
- Dockerfile
- Secrets 설정
- 배포

### Phase 5: 스케줄링 (1일)
- Fly.io Machines API 또는 외부 cron

### Phase 6: 데이터 마이그레이션 (2일)
- 전체 동기화 (4,800 티켓 + 1,300 KB)
- 검증

## 핵심 구현 사항

### 1. 데이터 수집 (150줄)
```python
class FreshdeskSyncService:
    def fetch_tickets(updated_since=None)
    def fetch_ticket_conversations(ticket_id)
    def fetch_kb_articles(updated_since=None)
    def convert_to_vertex_document(data, doc_type)
    def upload_to_vertex(documents)
    def sync_all(incremental=False)
```

### 2. 증분 수집
- Freshdesk API: `?updated_since=2025-01-27T10:00:00Z`
- 마지막 동기화 시간: `backend/data/last_sync_tenant_1.json`
- Cloud Scheduler: 2시간마다 자동 실행

### 3. 첨부파일
- Vertex AI 자동 파싱 (PDF, DOCX, TXT)
- 별도 로직 불필요

## 환경변수

```bash
# backend/.env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
VERTEX_AI_LOCATION=asia-northeast3  # 서울
VERTEX_AI_DATASTORE_ID=tenant_1_freshdesk
FRESHDESK_DOMAIN=your-domain
FRESHDESK_API_KEY=your-api-key
```

## Fly.io 설정

```toml
# fly.toml
app = "copilot-vertex"
primary_region = "nrt"  # 나리타

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  min_machines_running = 0

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
```

## 예상 비용

```
Fly.io (nrt):        $0-5/월
Vertex AI (서울):    $70/월
─────────────────────────────
Total:               $70-75/월
```

## 참고 파일 (project-a)

**Freshdesk API**:
- `project-a/backend/core/platforms/freshdesk/fetcher.py`
- `project-a/backend/core/platforms/freshdesk/adapter.py`

**프롬프트**:
- `project-a/backend/config/prompts/*.yaml`

**프론트엔드**:
- `project-a/frontend/app/scripts/app.js`
- `project-a/frontend/app/config/backend-config.js`

---

**마지막 업데이트**: 2025-10-27  
**다음 단계**: Phase 1 - GCP 환경 셋업  
**상태**: Phase 0 완료 ✅

