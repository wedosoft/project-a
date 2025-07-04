---
applyTo: "**"
---

# 🚀 빠른 참조 지침서 (Quick Reference)

_AI 즉시 참조용 핵심 패턴 - 2025-06-29 강제 준수 시스템 적용_

## 🚨 **필수 체크리스트 (모든 응답 전 확인)**
```
□ MANDATORY_PROCESS.md 읽었는가?
□ 제안서 작성했는가?
□ 사용자 컨펀 요청했는가?
□ 파일 존재 여부 정확히 확인했는가?
□ 승인 없이 파일 편집하려 하지 않았는가?
```

## 🚫 **절대 금지 (NEVER)**
- ❌ replace_string_in_file, insert_edit_into_file 승인 없이 사용
- ❌ "없습니다", "존재하지 않습니다" 확인 없이 단정
- ❌ 제안 → 컨펌 → 실행 단계 건너뛰기

## ✅ **절대 필수 (MUST)**
- ✅ file_search, read_file, grep_search로 코드 확인
- ✅ 3단계 프로세스 강제 준수
- ✅ "이 방향으로 진행해도 괜찮으신가요?" 컨펌 요청

## 🎯 **2025-06-29 최신 업데이트** 🔥

### 🤖 **환경변수 기반 LLM 관리 시스템 완성** ✅
**완전한 설정 기반 모델 관리로 하드코딩 제거**
- ✅ **ConfigManager**: 사용사례별(`REALTIME_`, `BATCH_`, `SUMMARY_`) 환경변수 기반 모델 설정
- ✅ **LLMManager**: `generate_for_use_case()`, `stream_generate_for_use_case()` 통합 인터페이스
- ✅ **즉시 적용**: 환경변수 변경 시 재시작 없이 모델/프로바이더 전환
- ✅ **레거시 완전 제거**: 모든 하드코딩된 프로바이더/모델 로직 제거

### � **RESTful 스트리밍 시스템 완성** ✅
**프리미엄 실시간 요약 시스템 구현**
- ✅ **RESTful 엔드포인트**: `/init/stream/{ticket_id}` (GET 방식)
- ✅ **통합 티켓 처리**: `get_ticket_data()` 함수로 `description_text` 우선 추출
- ✅ **프리미엄 실시간 요약**: YAML 템플릿 기반 고품질 요약 (8-9초)
- ✅ **구조화된 스트리밍**: 이모지 섹션별 마크다운 청크 스트리밍

### 🏗️ **아키텍처 완성도**
**핵심 시스템 모두 안정화 완료**
- ✅ **Backend**: 100% 완성 (LLM 관리, 스트리밍, ORM)
- ✅ **Database**: 95% 완성 (ORM, 벡터DB, 메타데이터)  
- ✅ **Frontend**: 85% 완성 (스트리밍 연동 필요)
- 🎯 **다음 단계**: 성능 최적화 및 에러 핸들링 강화

### 🔄 **현재 우선순위 작업**
- **성능 최적화**: 실시간 요약 속도 개선 (목표: 3-5초)
- **유사 티켓 품질**: 중간 품질 요약 시스템 검증
- **에러 핸들링**: 누락/빈 티켓 필드 처리 강화  
- **자동화 테스트**: 스트리밍 엔드포인트 테스트 추가

### 🔄 **현재 기술 스택 (2025-06-29)**
- ✅ **Frontend**: FDK (Freshdesk 전용)
- ✅ **Backend**: FastAPI + SQLAlchemy ORM + 환경변수 기반 LLM
- ✅ **Database**: SQLite (ORM) + Qdrant (벡터) + Redis (캐시)
- ✅ **LLM**: 환경변수 기반 멀티 프로바이더 지원
- ✅ **Database**: SQLite(개발) → PostgreSQL(운영)
- 📋 **관리**: 문서 기반 (TaskMaster 종료)
- ✅ **Vector DB**: Qdrant (단일 documents 컬렉션)
- ✅ **Cache**: Redis (LLM 응답 캐싱)
- ✅ **테넌트 격리**: company_id 기반 완전 분리

### 🔄 **환경 설정 (현재)**
---

## 🚀 **핵심 사용 패턴 (2025-06-29 최신)**

### 🤖 **환경변수 기반 LLM 사용**

```python
# ✅ 올바른 방법: 환경변수 기반 사용사례별 호출
from core.llm.manager import LLMManager

llm_manager = LLMManager()

# 실시간 요약 (프리미엄 품질)
response = await llm_manager.generate_for_use_case(
    "realtime",  # 환경변수에서 자동 모델 선택
    messages=[{"role": "user", "content": ticket_content}]
)

# 스트리밍 실시간 요약
async for chunk in llm_manager.stream_generate_for_use_case(
    "realtime",
    messages=[{"role": "user", "content": ticket_content}]
):
    print(chunk, end="")

# ❌ 잘못된 방법: 하드코딩 (절대 사용 금지)
# client = OpenAI() 
# response = client.chat.completions.create(model="gpt-4", ...)
```

### 🔧 **환경변수 설정 패턴**

```bash
# LLM 사용사례별 모델 설정 (즉시 적용)
REALTIME_LLM_PROVIDER=openai
REALTIME_LLM_MODEL=gpt-4-turbo
BATCH_LLM_PROVIDER=anthropic  
BATCH_LLM_MODEL=claude-3-haiku-20240307
SUMMARY_LLM_PROVIDER=openai
SUMMARY_LLM_MODEL=gpt-3.5-turbo

# ORM 및 환경 설정
USE_ORM=true              # ORM 모드 활성화
LOG_LEVEL=ERROR           # 디버그 로그 제거  
DATABASE_TYPE=sqlite      # 개발 환경
ENVIRONMENT=development   # 개발 모드
```

### 🚀 **RESTful 스트리밍 엔드포인트**

```bash
# ✅ 올바른 방법: GET 방식 스트리밍
curl -X GET "http://localhost:8000/init/stream/12345" \
  -H "X-Company-ID: your_company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: your_company.freshdesk.com" \
  -H "X-API-Key: your_api_key"

# 응답: Server-Sent Events 형태
# data: {"type": "summary_start", "message": "요약 생성 시작..."}
# data: {"type": "summary_chunk", "content": "## 🔍 문제 현황\n"}
# data: {"type": "summary_chunk", "content": "- 고객사 정보..."}
# data: {"type": "summary_complete"}

# ❌ 잘못된 방법: POST 방식 (레거시)
# curl -X POST "http://localhost:8000/init/stream"
```

---

## 📋 **API 엔드포인트 빠른 참조 (최신)**

| 엔드포인트 | 용도 | 언제 사용? | 응답 |
|------------|------|------------|------|
| **GET /init/stream/{ticket_id}** | 실시간 요약 스트리밍 | 티켓 요약, 실시간 분석 | SSE 마크다운 스트림 |
| **POST /init** | 일반 초기 분석 | 배치 분석, 유사 티켓 검색 | JSON 응답 |
| **POST /ingest** | 즉시 데이터 수집 | 테스트, 소량 데이터 | 실행 결과 바로 반환 |
| **POST /ingest/jobs** | 백그라운드 수집 | 대량 데이터, 스케줄링 | job_id 반환 |
| **GET /ingest/jobs/{job_id}** | 작업 상태 확인 | 백그라운드 작업 모니터링 | 진행 상황 및 결과 |

---

## 📂 **필수 참조 구조**

### 🎯 **즉시 참조 순서**
1. **이 파일** (Quick Reference) - 5분
2. **[API 엔드포인트 가이드](../data/api-endpoints-data-ingestion-guide.instructions.md)** - 실전 API 사용법
3. **[Pipeline Updates 2025-06-22](../data/pipeline-updates-20250622.instructions.md)** - 최신 변경사항
4. **작업별 디렉터리** - 해당 영역 상세

### 📁 **디렉터리 맵**
- **`/core/`** ← 필수 참조 (아키텍처, 보안, 전역)
- **`/data/`** ← 데이터 파이프라인 (**최우선**: api-endpoints-data-ingestion-guide)
- **`/development/`** ← 개발 패턴 (FDK, Backend, 디버깅)
- **`/specialized/`** ← 특화 기능 (LLM, 어댑터, 모니터링)

---

## 🎯 **프로젝트 핵심**

### **📋 시스템 정의**
- **목적**: Freshdesk Custom App (RAG 기반 유사 티켓 추천)
- **아키텍처**: 멀티테넌트 SaaS (tenant_id 기반 완전 격리)
- **스택**: Python FastAPI + FDK (JavaScript) + Qdrant + SQLite/PostgreSQL

### **🏗️ 데이터 흐름 (최신)**
```mermaid
표준 4개 헤더 → FastAPI 라우터 → 멀티테넌트 DB → 즉시 저장 → 벡터 저장 → 검색
```

1. **수집**: fetch_tickets(domain, api_key, max_tickets, store_immediately=True)
2. **저장**: {tenant_id}_{platform}.db (예: your_company_freshdesk.db)
3. **벡터화**: tenant_id 필터링으로 완전 격리
4. **검색**: 테넌트별 독립된 결과 반환

### **🔒 멀티테넌트 보안 (완성)**
- **DB 격리**: 개발환경 SQLite 파일별, 운영환경 PostgreSQL 스키마별
- **벡터 격리**: Qdrant tenant_id 필터링
- **API 격리**: 모든 엔드포인트에서 헤더 기반 테넌트 검증
- **API 키**: secrets manager 참조만 저장

---

## 🛠️ **핵심 구현 패턴**

### **🎨 FDK 필수 패턴**

**1. 환경 및 제약사항**

```javascript
// Node.js v14-v18만 지원
// 플랫폼은 항상 "freshdesk" (FDK 전용)
// 디버깅: fdk validate --verbose
```

**2. tenant_id 자동 추출**

```javascript
// iparams.html에서
const domain = window.location.hostname; // xxx.freshdesk.com
const tenantId = domain.split(".")[0]; // "xxx"
```

**3. 백엔드 API 호출 (올바른 엔드포인트 사용)**

```javascript
---

## 🛠️ **핵심 구현 패턴 (2025-06-22 최신)**

### **🎨 FDK 패턴 (표준 헤더 기반)**

**1. tenant_id 자동 추출**
```javascript
// iparams.html에서 자동으로 추출
const domain = window.location.hostname; // xxx.freshdesk.com
const tenantId = domain.split(".")[0];   // "xxx"
```

**2. 백엔드 API 호출 (표준 4개 헤더)**
```javascript
const response = await fetch(`${iparam.backend_url}/search`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Tenant-ID": tenantId,
    "X-Platform": "freshdesk",
    "X-Domain": window.location.hostname,
    "X-API-Key": iparam.api_key
  },
  body: JSON.stringify({ query: ticketSubject })
});
```

### **🐍 Backend 패턴 (멀티테넌트 완성)**

**1. 표준 헤더 의존성**
```python
from fastapi import Header

async def get_tenant_info(
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    platform: str = Header(..., alias="X-Platform"),
    domain: str = Header(..., alias="X-Domain"), 
    api_key: str = Header(..., alias="X-API-Key")
):
    return {"tenant_id": tenant_id, "platform": platform, 
            "domain": domain, "api_key": api_key}
```

**2. 멀티테넌트 DB 접근**
```python
# 회사별 DB 파일 자동 생성
def get_database(tenant_id: str, platform: str):
    db_filename = f"{tenant_id}_{platform}.db"
    return SQLiteDatabase(db_filename)

# 사용 예시
db = get_database("your_company", "freshdesk")  # your_company_freshdesk.db
```

**3. fetch_tickets 최신 시그니처**
```python
async def fetch_tickets(
    domain: str,           # your_company.freshdesk.com
    api_key: str,          # API 키
    max_tickets: int = 100,
    include_description: bool = True
) -> List[Dict]:
    # tenant_id는 내부에서 domain에서 추출
    tenant_id = domain.split('.')[0]
    # 처리 로직...
```

### **🔍 벡터 검색 패턴**

**1. 테넌트별 검색**
```python
# Qdrant에서 tenant_id 필터링
search_results = await qdrant_client.search(
    collection_name="tickets",
    query_vector=embedding,
    query_filter=models.Filter(
        must=[models.FieldCondition(
            key="tenant_id",
            match=models.MatchValue(value=tenant_id)
        )]
    ),
    limit=10
)
```

**2. 하이브리드 검색 (Vector + BM25)**
```python
# 벡터 검색 + 키워드 검색 결합
vector_results = await vector_search(query, tenant_id)
keyword_results = await keyword_search(query, tenant_id) 
combined = await merge_results(vector_results, keyword_results)
```

### **🗄️ 데이터 저장 패턴**

**1. 통합 객체 생성**

```python
from core.langchain.integrated_objects import create_integrated_ticket_object

integrated_ticket = create_integrated_ticket_object(
    ticket_data=ticket_data,
    conversation_data=conversation_data,
    tenant_id=tenant_id,
    platform="freshdesk"
)
```

**2. Vector DB 저장**

```python
from core.qdrant.qdrant_manager import QdrantManager

async def store_ticket_vector(integrated_ticket, tenant_id):
    qdrant = QdrantManager()

    # 임베딩 생성
    embedding = await generate_embedding(integrated_ticket['content'])

    # Qdrant에 저장 (tenant_id 필터 포함)
    await qdrant.store_document(
        document_id=integrated_ticket['id'],
        embedding=embedding,
        metadata={
            "tenant_id": tenant_id,
            "platform": "freshdesk",
            "type": "ticket"
        },
        content=integrated_ticket['content']
    )
```

**3. 유사 티켓 검색**

```python
async def find_similar_tickets(query_text, tenant_id, limit=5):
    # 쿼리 임베딩 생성
    query_embedding = await generate_embedding(query_text)

    # tenant_id 필터로 검색
    results = await qdrant.search(
        query_vector=query_embedding,
        filter_conditions={"company_id": company_id, "platform": "freshdesk"},
        limit=limit
    )

    return results
```

---

## 🧠 **LLM 처리 패턴**

### **1. 대화 필터링 (최신)**

```python
from core.langchain.smart_conversation_filter import SmartConversationFilter

filter = SmartConversationFilter()
filtered_conversations = await filter.filter_conversations(
    conversations=raw_conversations,
    max_tokens=4000,
    language="auto"  # 자동 감지
)
```

### **2. 요약 생성**

```python
from core.langchain.llm_manager import LLMManager

llm_manager = LLMManager()
summary = await llm_manager.generate_summary(
    content=filtered_conversations,
    company_id=company_id,
    summary_type="ticket_summary"
)
```

### **3. 캐싱 (필수)**

```python
# Redis 캐싱으로 LLM 비용 절약
cache_key = f"summary:{company_id}:{content_hash}"
cached_summary = await redis_client.get(cache_key)

if not cached_summary:
    summary = await llm_manager.generate_summary(content)
    await redis_client.setex(cache_key, 3600, summary)
else:
    summary = cached_summary
```

---

## 🔧 **환경 설정**

### **필수 환경 변수**

```bash
# 백엔드 (.env)
OPENAI_API_KEY=sk-...
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-key
DATABASE_URL=sqlite:///./data/app.db

# LLM 대화 필터링
ENABLE_CONVERSATION_FILTERING=true
MIN_CONVERSATION_LENGTH_KO=10
MIN_CONVERSATION_LENGTH_EN=5
FILTERING_LOG_LEVEL=INFO

# 멀티테넌트
DEFAULT_COMPANY_ID=demo
```

### **FDK 설정 (manifest.json)**

```json
{
  "platform": {
    "name": "freshdesk"
  },
  "engines": {
    "node": "14.x"
  }
}
```

---

## ⚠️ **주의사항 체크리스트**

### **🚨 절대 금지 사항**

- [ ] company_id 없는 데이터 처리 ❌
- [ ] FDK에서 중괄호 매칭 오류 ❌
- [ ] LLM 응답 캐싱 없이 운영 ❌
- [ ] 플랫폼 값 하드코딩 ("freshdesk" 외) ❌

### **✅ 필수 체크 포인트**

- [ ] 모든 API 엔드포인트에 company_id 검증
- [ ] 비동기 처리 시 동시성 제한 (Semaphore)
- [ ] 에러 발생 시 재시도 로직 적용
- [ ] Vector DB 검색 시 company_id 필터 적용
- [ ] LLM 호출 전 토큰 수 확인
- [ ] 캐싱 키에 company_id 포함

---

## 🔍 **디버깅 명령어**

### **FDK 디버깅**

```bash
# 구문 검증
fdk validate --verbose

# 상세 로그
fdk run --verbose

# 브라우저 콘솔에서 확인 (중요!)
console.log("Debug info:", data);
```

### **백엔드 디버깅**

```bash
# 개발 서버 (자동 재로드)
cd backend && source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 로그 레벨 설정
export LOG_LEVEL=DEBUG
```

### **벡터 DB 연결 테스트**

```python
# Qdrant 연결 확인
from core.qdrant.qdrant_manager import QdrantManager
qdrant = QdrantManager()
collections = await qdrant.list_collections()
print(f"Collections: {collections}")
```

---

## 📋 **8개 핵심 API 엔드포인트**

1. **POST** `/api/v1/recommendations` - 유사 티켓 추천
2. **POST** `/api/v1/ingest` - 데이터 수집 및 처리
3. **POST** `/api/v1/feedback` - 사용자 피드백 수집
4. **GET** `/api/v1/health` - 서비스 상태 확인
5. **POST** `/api/v1/summarize` - LLM 요약 생성
6. **GET** `/api/v1/collections/{company_id}` - 컬렉션 상태
7. **POST** `/api/v1/search` - 직접 벡터 검색
8. **DELETE** `/api/v1/collections/{company_id}` - 데이터 삭제

---

## 🔗 **관련 지침서 참조**

### **상세 구현 가이드**

- 📖 `implementation-guide.instructions.md` - 전체 구현 패턴
- 📊 `data-workflow.instructions.md` - 데이터 처리 상세
- 🏗️ `core-architecture.instructions.md` - 아키텍처 전체

### **특화 기능**

- 🧠 `llm-conversation-filtering-strategy.instructions.md` - LLM 필터링 전략
- 🛠️ `llm-conversation-filtering-implementation.instructions.md` - LLM 필터링 구현
- 🗂️ `integrated-object-storage.instructions.md` - 통합 객체 저장

### **공통 원칙**

- 📚 `global.instructions.md` - 프로젝트 공통 지침
- 📋 `README.md` - 전체 지침서 구조 및 활용법

---

_이 지침서는 AI가 가장 자주 참조하는 핵심 패턴과 구현 방법만을 포함합니다. 상세한 내용은 관련 지침서를 참조하세요._
