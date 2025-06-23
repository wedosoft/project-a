---
applyTo: "**"
---

# 🚀 빠른 참조 지침서 (Quick Reference)

_AI 즉시 참조용 핵심 패턴 - 2025-06-23 보안/데이터 삭제 기능 완성_

## 🎯 **2025-06-23 최신 업데이트** 🔥

### 🔐 **보안/데이터 삭제 기능 완성**
**GDPR 대응 완전한 데이터 초기화 구현**
- ✅ **SQLite 데이터**: 티켓, 지식베이스, 요약 등 완전 삭제
- ✅ **벡터 DB**: Qdrant 임베딩 및 메타데이터 삭제
- ✅ **캐시 데이터**: Redis, 메모리 캐시 정리
- ✅ **AWS Secrets Manager**: API 키, 인증 토큰 등 비밀키 삭제
- ✅ **백업 생성**: 삭제 전 자동 백업 (선택사항)
- ✅ **감사 로그**: 모든 삭제 작업 기록

### 🛡️ **작업 제어 & 모니터링 (완성)**
**사용자 데이터 민감성 고려한 완전한 제어**
- ✅ **즉시 실행** (/ingest): 제어 불가, 소량 테스트용
- ✅ **백그라운드 작업** (/ingest/jobs): pause/resume/cancel 지원
- ✅ **진행상황 추적**: 실시간 상태 모니터링
- ✅ **데이터 보안**: 토큰 기반 보안 검증

### 📋 **새로운 보안 API 엔드포인트**
```bash
# 보안 토큰 생성
POST /ingest/security/generate-token

# 완전한 데이터 삭제 (GDPR 대응)
POST /ingest/security/purge-data
```

### 🚨 **API 엔드포인트 핵심 교훈**
**가장 중요한 발견**: `/ingest`와 `/ingest/jobs`는 완전히 다른 용도!
- ✅ `/ingest` → **즉시 실행** (동기식, 테스트용, 소량 데이터)
- ✅ `/ingest/jobs` → **백그라운드 실행** (비동기식, 대량 데이터)

### 🔄 **표준 4개 헤더 체계 (완성)**
- ✅ **X-Company-ID**: 테넌트 식별자 (예: "your_company")
- ✅ **X-Platform**: 플랫폼 (항상 "freshdesk")  
- ✅ **X-Domain**: API 도메인 (예: "your_company.freshdesk.com")
- ✅ **X-API-Key**: 플랫폼 API 키

### 🔄 **주요 변경사항**
- ❌ **제거됨**: 레거시 환경변수 (FRESHDESK_DOMAIN, FRESHDESK_API_KEY)
- ❌ **제거됨**: Query 파라미터, 중복 헤더
- ✅ **구현됨**: 멀티테넌트 DB 정책 (회사별 SQLite 파일)
- ✅ **통합됨**: fetch_tickets 파라미터 일관성
- ✅ **검증됨**: 즉시 저장 로직 (store_immediately=True)

### 🧪 **즉시 테스트 가능 (검증됨)**
```bash
# 올바른 방법: /ingest로 즉시 실행
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: your_company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: your_company.freshdesk.com" \
  -H "X-API-Key: your_api_key" \
  -d '{"max_tickets": 100, "include_kb": true}'

# 잘못된 방법: 즉시 확인하려고 /ingest/jobs 사용
# 결과: 작업만 생성되고 완료를 기다려야 함!
```

---

### 📋 **API 엔드포인트 빠른 참조 (완성됨)**

| 엔드포인트 | 용도 | 언제 사용? | 응답 |
|------------|------|------------|------|
| **POST /ingest** | 즉시 실행 | 테스트, 소량 데이터, 즉시 확인 | 실행 결과 바로 반환 |
| **POST /ingest/jobs** | 작업 생성 | 대량 데이터, 스케줄링 | job_id 반환, 상태 추적 필요 |
| **GET /ingest/jobs/{job_id}** | 상태 확인 | 백그라운드 작업 모니터링 | 진행 상황 및 결과 |
| **POST /ingest/jobs/{job_id}/control** | 작업 제어 | pause/resume/cancel | 제어 결과 |
| **POST /ingest/security/generate-token** | 보안 토큰 | 데이터 삭제 전 토큰 생성 | 일일 보안 토큰 |
| **POST /ingest/security/purge-data** | 데이터 삭제 | GDPR/보안 사고 대응 | 삭제 결과 및 백업 정보 |

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
- **아키텍처**: 멀티테넌트 SaaS (company_id 기반 완전 격리)
- **스택**: Python FastAPI + FDK (JavaScript) + Qdrant + SQLite/PostgreSQL

### **🏗️ 데이터 흐름 (최신)**
```mermaid
표준 4개 헤더 → FastAPI 라우터 → 멀티테넌트 DB → 즉시 저장 → 벡터 저장 → 검색
```

1. **수집**: fetch_tickets(domain, api_key, max_tickets, store_immediately=True)
2. **저장**: {company_id}_{platform}.db (예: your_company_freshdesk.db)
3. **벡터화**: company_id 필터링으로 완전 격리
4. **검색**: 테넌트별 독립된 결과 반환

### **🔒 멀티테넌트 보안 (완성)**
- **DB 격리**: 개발환경 SQLite 파일별, 운영환경 PostgreSQL 스키마별
- **벡터 격리**: Qdrant company_id 필터링
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

**2. company_id 자동 추출**

```javascript
// iparams.html에서
const domain = window.location.hostname; // xxx.freshdesk.com
const companyId = domain.split(".")[0]; // "xxx"
```

**3. 백엔드 API 호출 (올바른 엔드포인트 사용)**

```javascript
---

## 🛠️ **핵심 구현 패턴 (2025-06-22 최신)**

### **🎨 FDK 패턴 (표준 헤더 기반)**

**1. company_id 자동 추출**
```javascript
// iparams.html에서 자동으로 추출
const domain = window.location.hostname; // xxx.freshdesk.com
const companyId = domain.split(".")[0];   // "xxx"
```

**2. 백엔드 API 호출 (표준 4개 헤더)**
```javascript
const response = await fetch(`${iparam.backend_url}/search`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Company-ID": companyId,
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
    company_id: str = Header(..., alias="X-Company-ID"),
    platform: str = Header(..., alias="X-Platform"),
    domain: str = Header(..., alias="X-Domain"), 
    api_key: str = Header(..., alias="X-API-Key")
):
    return {"company_id": company_id, "platform": platform, 
            "domain": domain, "api_key": api_key}
```

**2. 멀티테넌트 DB 접근**
```python
# 회사별 DB 파일 자동 생성
def get_database(company_id: str, platform: str):
    db_filename = f"{company_id}_{platform}.db"
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
    # company_id는 내부에서 domain에서 추출
    company_id = domain.split('.')[0]
    # 처리 로직...
```

### **🔍 벡터 검색 패턴**

**1. 테넌트별 검색**
```python
# Qdrant에서 company_id 필터링
search_results = await qdrant_client.search(
    collection_name="tickets",
    query_vector=embedding,
    query_filter=models.Filter(
        must=[models.FieldCondition(
            key="company_id",
            match=models.MatchValue(value=company_id)
        )]
    ),
    limit=10
)
```

**2. 하이브리드 검색 (Vector + BM25)**
```python
# 벡터 검색 + 키워드 검색 결합
vector_results = await vector_search(query, company_id)
keyword_results = await keyword_search(query, company_id) 
combined = await merge_results(vector_results, keyword_results)
```

### **🗄️ 데이터 저장 패턴**

**1. 통합 객체 생성**

```python
from core.langchain.integrated_objects import create_integrated_ticket_object

integrated_ticket = create_integrated_ticket_object(
    ticket_data=ticket_data,
    conversation_data=conversation_data,
    company_id=company_id,
    platform="freshdesk"
)
```

**2. Vector DB 저장**

```python
from core.qdrant.qdrant_manager import QdrantManager

async def store_ticket_vector(integrated_ticket, company_id):
    qdrant = QdrantManager()

    # 임베딩 생성
    embedding = await generate_embedding(integrated_ticket['content'])

    # Qdrant에 저장 (company_id 필터 포함)
    await qdrant.store_document(
        document_id=integrated_ticket['id'],
        embedding=embedding,
        metadata={
            "company_id": company_id,
            "platform": "freshdesk",
            "type": "ticket"
        },
        content=integrated_ticket['content']
    )
```

**3. 유사 티켓 검색**

```python
async def find_similar_tickets(query_text, company_id, limit=5):
    # 쿼리 임베딩 생성
    query_embedding = await generate_embedding(query_text)

    # company_id 필터로 검색
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
