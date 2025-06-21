---
applyTo: "**"
---

# 🚀 빠른 참조 지침서 (Quick Reference)

_AI 즉시 참조용 핵심 패턴 및 구현 가이드 - 최대 500라인 제한_

## 📂 **새로운 Instructions 구조** _(2024-06-21 최적화)_

### 🎯 **필수 참조 순서**
1. **[Quick Reference](../core/quick-reference.instructions.md)** ← 현재 파일
2. **[Global Instructions](../core/global.instructions.md)** ← 전역 규칙
3. **작업별 디렉터리** ← 해당 영역 참조

### 📁 **디렉터리 구조**
- **`/core/`** - 필수 참조 (아키텍처, 전역 규칙)
- **`/development/`** - 개발 패턴 (FDK, Backend, 디버깅)
- **`/data/`** - 데이터 처리 (수집, LLM, 벡터, 저장소)
- **`/specialized/`** - 특화 기능 (LLM 필터링, 플랫폼 어댑터)
- **`/legacy/`** - 참고용 (이전 버전)

---

## 🎯 **즉시 참조용 핵심 포인트**

### **📋 프로젝트 개요**

- **목적**: Freshdesk Custom App (RAG 기반 유사 티켓 추천)
- **스택**: Python FastAPI + FDK (JavaScript) + Qdrant + SQLite
- **아키텍처**: 멀티테넌트 SaaS (company_id 기반 격리)

### **🏗️ 핵심 아키텍처**

```
FDK Frontend → FastAPI Backend → [LLM + Qdrant + SQLite]
     ↓              ↓                    ↓
  iparams        API 엔드포인트        데이터 저장소
```

### **📊 데이터 흐름**

```
플랫폼 수집 → 데이터 검증 → 통합 객체 생성 → LLM 요약 → 임베딩 생성 → Vector DB 저장
```

### **🔐 보안 원칙**

- **멀티테넌트**: 모든 데이터에 company_id 필수
- **Row-level Security**: PostgreSQL + Qdrant 필터링
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

**3. 백엔드 API 호출**

```javascript
const apiUrl = `${iparam.backend_url}/api/v1/recommendations`;
const response = await fetch(apiUrl, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ company_id: companyId, ticket_data: ticketData }),
});
```

### **🐍 백엔드 필수 패턴**

**1. 멀티테넌트 보안**

```python
# 모든 데이터 처리에 company_id 필수
async def process_ticket(ticket_data: dict, company_id: str):
    if not company_id:
        raise ValueError("company_id is required")

    # 데이터에 company_id 태깅
    ticket_data["company_id"] = company_id
```

**2. 비동기 처리 패턴**

```python
import asyncio
from asyncio import Semaphore

# 동시성 제한
semaphore = Semaphore(max_concurrent=5)

async def process_with_limit(data):
    async with semaphore:
        return await process_data(data)
```

**3. 에러 처리 및 재시도**

```python
import asyncio
from functools import wraps

async def retry_on_failure(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 지수 백오프
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
