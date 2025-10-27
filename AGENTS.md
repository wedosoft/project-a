# Project-A Spinoff: Vertex AI Migration

**상태**: Phase 1 진행 중 (80% 완료)
**저장소**: https://github.com/wedosoft/project-a-spinoff
**목적**: 레거시(15K줄) → Vertex AI 기반 단순 시스템(800줄)
**마지막 업데이트**: 2025-10-27

## 현황

### ✅ 완료 (Phase 0)
- ✅ Git 저장소 초기화
- ✅ Backend 구조 생성 (routes/, services/, models/, utils/)
- ✅ 기본 파일 (main.py, requirements.txt, .env.example)
- ✅ Frontend 복사 (project-a에서)
- ✅ GitHub 연동 완료

### ✅ 완료 (Phase 1 - GCP 환경 셋업)
- ✅ GCP 프로젝트 생성 (project-a-spinoff, #715996531149)
- ✅ 빌링 연결 (01526A-E56CA7-1464C8)
- ✅ 필수 API 활성화 (Vertex AI, Discovery Engine, Logging, Monitoring, Storage)
- ✅ 서비스 계정 생성 및 키 발급
  - 계정: `vertex-ai-service@project-a-spinoff.iam.gserviceaccount.com`
  - 역할: Vertex AI User + Discovery Engine Admin
  - 키 위치: `backend/service-account-key.json` (2.3K)
- ✅ **과금 최적화 완료**
  - project-a-spinoff: 불필요한 API 14개 제거 (BigQuery, Datastore 등)
  - project-b-475522: 고비용 API 23개 제거 (Cloud Spanner 포함)
  - 기타 11개 프로젝트: 100개 이상 고비용 API 정리
  - **현재 과금: ₩0** (리소스 없음)

### ⏳ 진행 중 (Phase 1 - 남은 작업)
- ⏳ Vertex AI Datastore 생성 (asia-northeast3/서울)
- ⏳ 샘플 데이터 업로드 (티켓 50개 + KB 50개)
- ⏳ 검색 품질 테스트 (10개 쿼리)

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

### Phase 1: GCP 환경 셋업 (1주) - 80% 완료 ✅
- ✅ GCP 프로젝트 생성 (project-a-spinoff)
- ✅ Vertex AI API 활성화
- ✅ 서비스 계정 생성 및 권한 부여
- ✅ 과금 최적화 (100개 이상 불필요한 API 제거)
- ⏳ Datastore 생성 (asia-northeast3/서울) - **다음 단계**
- ⏳ 샘플 데이터 100개 업로드
- ⏳ 품질 검증 (10개 쿼리)

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
# backend/.env (실제 설정 완료)
GOOGLE_CLOUD_PROJECT=project-a-spinoff
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
VERTEX_AI_LOCATION=asia-northeast3  # 서울
VERTEX_AI_DATASTORE_ID=tenant_1_freshdesk  # 생성 예정
FRESHDESK_DOMAIN=your-domain  # 설정 필요
FRESHDESK_API_KEY=your-api-key  # 설정 필요
```

## GCP 리소스 정보

```bash
# 프로젝트 정보
프로젝트 ID: project-a-spinoff
프로젝트 번호: 715996531149
빌링 계정: 01526A-E56CA7-1464C8

# 서비스 계정
이메일: vertex-ai-service@project-a-spinoff.iam.gserviceaccount.com
역할: roles/aiplatform.user, roles/discoveryengine.admin
키 파일: backend/service-account-key.json (2.3K)

# 활성화된 API (8개만)
- aiplatform.googleapis.com
- discoveryengine.googleapis.com
- logging.googleapis.com
- monitoring.googleapis.com
- storage.googleapis.com (+ storage-api)
- servicemanagement.googleapis.com
- serviceusage.googleapis.com
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
**다음 단계**: Phase 1 - Vertex AI Datastore 생성 (서울)  
**상태**: Phase 1 진행 중 (80% 완료) ⏳

## 다음 작업자를 위한 인수인계

### 🎯 즉시 진행 가능한 작업

**1. Vertex AI Datastore 생성**
```bash
# 프로젝트 확인
gcloud config get-value project  # project-a-spinoff

# Datastore 생성 (Google Cloud Console 또는 gcloud CLI)
# 리전: asia-northeast3 (서울)
# 이름: tenant_1_freshdesk
# 타입: Search (Unstructured documents)
```

**2. 환경 변수 설정**
- `backend/.env` 파일에 Freshdesk 정보 입력 필요
- `FRESHDESK_DOMAIN`과 `FRESHDESK_API_KEY` 설정

**3. 샘플 데이터 준비**
- project-a에서 티켓 50개 추출
- KB 문서 50개 추출
- Datastore에 업로드

### ⚠️ 주의사항

**과금 관련:**
- 현재 과금: ₩0 (리소스 없음)
- Datastore 생성 시 과금 시작 (예상: ₩4,000-40,000/월)
- 고비용 API 모두 제거됨 (BigQuery, Cloud Spanner 등)

**인증 정보:**
- 서비스 계정 키: `backend/service-account-key.json` (Git 제외됨)
- 절대 커밋하지 말 것 (.gitignore에 포함됨)

**리전 정책:**
- 데이터 저장소: 반드시 서울(asia-northeast3)
- 백엔드: Fly.io nrt (도쿄) - 개인정보 일시 처리만

### 📚 참고 문서

**GCP 관련:**
- [Vertex AI Search 문서](https://cloud.google.com/generative-ai-app-builder/docs/introduction)
- [Discovery Engine API](https://cloud.google.com/discovery-engine/docs)

**레거시 참조:**
- project-a의 Freshdesk 연동 로직 참고
- 벡터 저장 구조는 완전히 다름 (Qdrant → Vertex AI Search)

