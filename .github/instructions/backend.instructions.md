---
applyTo: "**"
---

# 🧠 자연어 기반 상담사 지원 시스템 - 코파일럿 백엔드 지침서

## 🎯 목적

Freshdesk Custom App에서 상담사를 위한 자연어 기반 AI 응답 지원 시스템을 개발합니다. 백엔드는 LLM과 Vector DB 기반으로 상담사의 자연어 요청을 처리하여 유사 티켓·추천 솔루션·이미지·첨부파일 데이터를 제공하고 프론트가 바로 사용할 수 있는 JSON을 반환합니다.

---

## 📌 백엔드 아키텍처 핵심

### 1. 전체 구조 분리 원칙

- `API Layer`: 프론트로부터 요청을 받고 분기
- `Context Builder`: 티켓 요약, 관련 문서, 유사 티켓 등 컨텍스트 구성
- `Retriever`: Vector DB에서 유사 문서/티켓 검색
- `LLM Orchestrator`: 프롬프트 구성 및 LLM 호출
- `Response Assembler`: LLM 응답 후 최종 포맷 구성

> 모든 서비스는 **함수형 모듈로 분리**하고, 고객/세션 정보는 메타데이터로 포함

---

### 2. ⚡️ 주요 엔드포인트 (최종 유지 목록)

| 엔드포인트                          | 용도                                            | 호출 위치               |
| ----------------------------------- | ----------------------------------------------- | ----------------------- |
| **`/init`** (GET)                   | 티켓 요약, 유사 티켓, 추천 솔루션 (초기 데이터) | ✅ 프론트 (1회 자동)    |
| **`/query`** (POST)                 | AI 채팅에 사용 (자연어 요청 처리)               | ✅ 프론트 (채팅 요청시) |
| **`/generate_reply`** (POST)        | 추천 답변 호출시 사용                           | ✅ 프론트 (답변 생성시) |
| **`/ingest`** (POST)                | 관리자가 데이터 수집 시작할 때 사용             | ✅ 프론트 (관리자 패널) |
| **`/health`** (GET)                 | 헬스체크 (시스템 상태 확인)                     | ✅ 프론트 (모니터링)    |
| **`/metrics`** (GET)                | 메트릭 모니터링 (성능 및 사용량 확인)           | ✅ 프론트 (관리자 패널) |
| **`/query/stream`** (POST)          | 채팅에서 스트리밍 응답 사용                     | ✅ 프론트 (실시간 채팅) |
| **`/generate_reply/stream`** (POST) | 답변 생성시 스트리밍 응답 사용                  | ✅ 프론트 (실시간 답변) |
| **`/attachments/*`**                | 첨부파일 열 때 사용 (파일 다운로드/미리보기)    | ✅ 프론트 (파일 접근)   |

**설계 원칙:**

- 모든 API는 `ticket_id`를 기본으로 하며 자연어 요청 텍스트를 함께 처리
- 스트리밍 엔드포인트는 실시간 응답 제공을 위한 Server-Sent Events (SSE) 지원
- 캐싱 전략 필요 (자주 요청되는 패턴 인식 및 응답 최적화)
- 첨부파일 엔드포인트는 보안을 위한 인증 및 권한 검증 필수

---

## 🟢 주요 엔드포인트 상세

### 1. 🟢 /init

✅ **기능**

- 프론트 최초 로딩 시 호출 (상담원이 티켓을 열 때 자동 트리거)
- **동적 Freshdesk 설정 지원**: 요청 헤더에서 `domain`, `api_key` 추출하여 동적 연결
- `/similar_tickets`, `/related_docs`를 내부적으로 호출 → 모든 초기 데이터를 단일 응답으로 구성
- 티켓 메타 정보 추출 및 LLM으로 요약 생성 (1회만 생성)
- 현재 상담사가 조회하고 있는 티켓을 parameter로 처리
- 기존 /init/{{ticket_id}} 그대로 사용하면 될 것 같음

✅ **처리 흐름**

1. **동적 설정 처리**:
   - 요청 헤더에서 `X-Freshdesk-Domain`, `X-Freshdesk-API-Key` 추출
   - 해당 도메인/API 키로 Freshdesk API 클라이언트 동적 생성
   - company_id는 도메인에서 추출하여 벡터 DB 네임스페이스로 활용
2. **요약 생성**: LLM으로 `에이전트용 요약` 생성
3. **벡터 검색**:
   - 유사 티켓: `similar_tickets` 내부 호출 (company_id 필터 적용)
   - 관련 솔루션: `related_docs` 내부 호출 (company_id 필터 적용)
4. **응답 구성**:
   - 요약 + 유사 티켓 + 추천 솔루션 통합 JSON 반환

### 2. 🟢 /query (POST)

✅ **기능**

- "OO와 대화하기" 탭에서 자연어 입력 + 콘텐츠 타입 선택 시 호출
- **AI 채팅 시스템의 핵심 엔드포인트**: 사용자의 자연어 요청을 분석하고 적절한 응답 제공
- **동적 Freshdesk 설정 지원**: 각 요청마다 헤더에서 도메인/API 키 추출하여 해당 고객사 데이터 처리
- 자연어 요청 의도 분석 및 검색 콘텐츠 타입에 따른 응답 생성
- 티켓 컨텍스트를 기반으로 관련 정보 검색 및 응답 구성 (company_id 필터링)

✅ **입력 예시**

```json
{
  "intent": "search",
  "type": ["tickets", "solutions", "images", "attachments"],
  "query": "이 문제 관련 자료를 찾아줘",
  "ticket_id": "12345"
}
```

✅ **요청 헤더**

```
X-Freshdesk-Domain: customer-domain.freshdesk.com
X-Freshdesk-API-Key: customer-api-key
```

✅ **처리 흐름**

- **동적 설정 처리**: 헤더에서 도메인/API 키 추출 및 클라이언트 생성
- `intent_classification`: 상담사 요청의 의도 분류 및 적절한 작업 선택
- **company_id 기반 필터링**: 해당 고객사 데이터만 검색하도록 벡터 DB 쿼리 제한
- 선택된 콘텐츠 타입에 따라 내부 검색 모듈 호출
- 결과를 타입별로 정리하여 JSON 응답 구성

### 3. 🟢 /generate_reply (POST)

✅ **기능**

- **추천 답변 생성 전용 엔드포인트**: 상담사가 고객에게 보낼 답변을 AI가 생성
- 티켓 내용과 관련 컨텍스트를 기반으로 적절한 답변 초안 제공
- **동적 Freshdesk 설정 지원**: 헤더에서 도메인/API 키 추출하여 해당 고객사 스타일 적용
- 답변 톤 및 스타일 조정 (공식적/친근한/기술적 등)

✅ **입력 예시**

```json
{
  "ticket_id": "12345",
  "context": "고객이 로그인 문제를 신고함",
  "tone": "professional",
  "include_solution_steps": true
}
```

✅ **처리 흐름**

- 티켓 정보 및 관련 컨텍스트 수집
- 고객사별 답변 스타일 가이드라인 적용
- LLM을 통한 적절한 답변 생성
- 답변 품질 검증 및 포맷 조정

### 4. 🟢 /ingest (POST)

✅ **기능**

- **관리자 전용 데이터 수집 엔드포인트**: Freshdesk에서 티켓, 지식베이스 등을 벡터 DB로 수집
- 대용량 데이터 처리 및 진행상황 모니터링 지원
- **동적 Freshdesk 설정 지원**: 각 고객사별 독립적인 데이터 수집 및 저장

✅ **입력 예시**

```json
{
  "data_types": ["tickets", "knowledge_base", "attachments"],
  "date_range": {
    "start": "2023-01-01",
    "end": "2024-01-01"
  },
  "batch_size": 1000
}
```

✅ **처리 흐름**

- Freshdesk API를 통한 데이터 수집
- 청크 단위 처리 및 진행률 리포팅
- 벡터 임베딩 생성 및 Qdrant 저장

### 5. 🟢 /health (GET)

✅ **기능**

- **시스템 헬스체크**: 백엔드 서비스, 벡터 DB, LLM API 상태 확인
- 프론트엔드에서 시스템 상태 모니터링에 사용

### 6. 🟢 /metrics (GET)

✅ **기능**

- **성능 메트릭 제공**: API 응답시간, 사용량, 에러율 등
- 관리자 패널에서 시스템 성능 모니터링에 사용

### 7. 🟢 /query/stream (POST)

✅ **기능**

- **실시간 스트리밍 채팅**: `/query` 엔드포인트의 스트리밍 버전
- Server-Sent Events (SSE)를 통한 실시간 응답 제공
- 긴 응답에 대한 사용자 경험 개선

### 8. 🟢 /generate_reply/stream (POST)

✅ **기능**

- **실시간 스트리밍 답변 생성**: `/generate_reply` 엔드포인트의 스트리밍 버전
- 답변 생성 과정을 실시간으로 표시하여 대기시간 체감 단축

### 9. 🟢 /attachments/\* (GET)

✅ **기능**

- **첨부파일 접근**: 티켓 첨부파일 다운로드 및 미리보기 제공
- 보안을 위한 인증 및 권한 검증
- 이미지, 문서 등 다양한 파일 타입 지원

### 제거된 엔드포인트들 (더 이상 필요 없음)

- `/similar_tickets` → `/init` 및 `/query` 내부에서 처리
- `/related_docs` → `/init` 및 `/query` 내부에서 처리
- `/summarize` → `/init` 에서 자동 처리
- `/documents/search` → `/query` 로 통합

### 3. 🔍 프론트와의 연동 흐름

### 페이지 최초 로드 (상담원이 티켓 열 때)

- **자동 트리거**: 상담원이 Freshdesk에서 티켓을 열면 Custom App이 자동으로 로드
- **동적 초기화**: 프론트에서 현재 Freshdesk 도메인과 API 키를 헤더에 포함하여 `/init` 호출
- **멀티테넌트 처리**: 백엔드에서 헤더 정보를 통해 해당 고객사의 데이터만 로드
- 티켓 요약, 유사 티켓, 추천 솔루션 한 번에 제공
- 초기 데이터는 프론트에서 로컬 캐싱하여 사용

### AI 채팅 요청 처리

- **자연어 요청**: "대화하기" 탭에서 검색 콘텐츠 선택 및 자연어 입력 후 `/query` 호출
- **스트리밍 채팅**: 실시간 응답이 필요한 경우 `/query/stream` 사용
- **동적 설정 전달**: 각 요청마다 Freshdesk 도메인/API 키 헤더 포함
- **고객사별 데이터 격리**: 백엔드에서 company_id 기반으로 해당 고객사 데이터만 검색
- 요청마다 새로운 검색 및 LLM 처리 수행
- 결과는 타입별(티켓/솔루션/이미지/첨부파일)로 구분하여 반환

### 추천 답변 생성

- **답변 생성**: 상담사가 답변 작성 지원을 요청할 때 `/generate_reply` 호출
- **스트리밍 답변**: 긴 답변의 경우 `/generate_reply/stream`으로 실시간 생성 과정 표시
- 티켓 컨텍스트와 고객사별 스타일 가이드를 반영한 답변 제공

### 관리자 기능

- **데이터 수집**: 관리자가 새로운 데이터 수집을 시작할 때 `/ingest` 호출
- **시스템 모니터링**: `/health`, `/metrics` 엔드포인트로 시스템 상태 및 성능 확인

### 첨부파일 처리

- **파일 접근**: 티켓 관련 첨부파일에 접근할 때 `/attachments/*` 경로 사용
- 보안 인증 및 권한 검증을 통한 안전한 파일 접근

---

## ⚙️ 관리자 설정 항목 (iparams.html용)

| 항목                    | 설명                                       |
| ----------------------- | ------------------------------------------ |
| **Freshdesk 연동 설정** | **도메인, API 키 (각 고객사별 개별 설정)** |
| 자연어 명령 인식 범위   | 지원할 자연어 명령 패턴 설정               |
| 스타일 지침             | 공식/친근/기술적 등                        |
| 금지 표현 목록          | 예: "죄송합니다" → "안내드립니다"          |
| 데이터 검색 기간 설정   | 1개월, 3개월, 6개월, 전체 등               |
| **멀티테넌트 옵션**     | **고객사별 데이터 격리 및 접근 제어**      |
| 향후 옵션 (로드맵)      | 자동화 수준 세분화, 상담사별 맞춤 설정     |

---

## 🛠️ 백엔드 개발 핵심 지침

### 동적 설정 및 멀티테넌트 지원

- **헤더 기반 동적 연결**: 모든 API 요청에서 `X-Freshdesk-Domain`, `X-Freshdesk-API-Key` 헤더 처리
- **company_id 추출**: 도메인에서 고유 식별자 생성하여 벡터 DB 네임스페이스로 활용
- **데이터 격리**: 각 고객사의 데이터가 섞이지 않도록 철저한 필터링 적용
- **보안**: API 키 검증 및 권한 확인 로직 필수

### 기존 지침 유지

- LLM 호출은 사용자의 **명시적 요청**이 있어야만 수행
- 자연어 요청의 의도 파악 정확성 향상을 위한 컨텍스트 최적화
- 모든 응답은 프론트가 바로 사용 가능한 구조로 JSON 포맷
- **9개 엔드포인트만 유지**: `/init`, `/query`, `/generate_reply`, `/ingest`, `/health`, `/metrics`, `/query/stream`, `/generate_reply/stream`, `/attachments/*`
- 티켓 ID를 기준으로 모든 요청 처리
- 자연어 명령 대표 패턴:
  - "이 문제 관련 자료 찾아줘"
  - "비슷한 문제 해결 사례 찾아줘"
  - "이 이슈의 해결책 제안해줘"
  - "이 문제에 대한 대응 방법은?"

## 소통원칙

- 모든 소통은 한국어로만 합니다.

## 💻 동적 Freshdesk 설정 구현 가이드

### 헤더 추출 및 검증

```python
from fastapi import Header, HTTPException
from typing import Optional

async def extract_freshdesk_config(
    x_freshdesk_domain: Optional[str] = Header(None),
    x_freshdesk_api_key: Optional[str] = Header(None)
) -> Tuple[str, str]:
    """
    요청 헤더에서 Freshdesk 설정을 추출하고 검증합니다.

    Args:
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 추출)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 추출)

    Returns:
        검증된 도메인과 API 키 튜플

    Raises:
        HTTPException: 필수 헤더가 누락되었거나 유효하지 않은 경우
    """
    if not x_freshdesk_domain or not x_freshdesk_api_key:
        raise HTTPException(
            status_code=400,
            detail="Freshdesk 도메인과 API 키 헤더가 필요합니다."
        )

    # 도메인 형식 검증
    if not x_freshdesk_domain.endswith('.freshdesk.com'):
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 Freshdesk 도메인 형식입니다."
        )

    return x_freshdesk_domain, x_freshdesk_api_key

def extract_company_id(domain: str) -> str:
    """
    Freshdesk 도메인에서 company_id를 추출합니다.

    Args:
        domain: Freshdesk 도메인 (예: customer.freshdesk.com)

    Returns:
        company_id (예: customer)
    """
    return domain.split('.')[0]
```

### API 엔드포인트 업데이트

```python
from fastapi import FastAPI, Depends

@app.get("/init/{ticket_id}")
async def init_ticket_data(
    ticket_id: str,
    freshdesk_config: Tuple[str, str] = Depends(extract_freshdesk_config)
):
    """
    티켓 초기 데이터를 로드합니다. (동적 Freshdesk 설정 지원)
    """
    domain, api_key = freshdesk_config
    company_id = extract_company_id(domain)

    # 동적 Freshdesk 클라이언트 생성
    freshdesk_client = FreshdeskAPI(domain=domain, api_key=api_key)

    # company_id 기반 벡터 DB 검색
    similar_tickets = await search_similar_tickets(ticket_id, company_id)
    related_docs = await search_related_docs(ticket_id, company_id)

    return {
        "company_id": company_id,
        "ticket_summary": await generate_ticket_summary(ticket_id, freshdesk_client),
        "similar_tickets": similar_tickets,
        "related_docs": related_docs
    }

@app.post("/query")
async def query_natural_language(
    request: QueryRequest,
    freshdesk_config: Tuple[str, str] = Depends(extract_freshdesk_config)
):
    """
    자연어 쿼리를 처리합니다. (동적 Freshdesk 설정 지원)
    """
    domain, api_key = freshdesk_config
    company_id = extract_company_id(domain)

    # company_id 필터링으로 해당 고객사 데이터만 검색
    search_results = await vector_search_with_filter(
        query=request.query,
        content_types=request.type,
        company_id=company_id
    )

    return {
        "company_id": company_id,
        "results": search_results
    }
```

### 벡터 DB 검색 시 company_id 필터링

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

async def search_with_company_filter(
    query_vector: List[float],
    company_id: str,
    collection_name: str,
    limit: int = 10
):
    """
    company_id 필터를 적용한 벡터 검색을 수행합니다.

    Args:
        query_vector: 검색할 벡터
        company_id: 고객사 ID (데이터 격리를 위한 필터)
        collection_name: 검색할 컬렉션명
        limit: 반환할 결과 수

    Returns:
        해당 고객사의 데이터만 포함된 검색 결과
    """
    # company_id 기반 필터 생성
    company_filter = Filter(
        must=[
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            )
        ]
    )

    # 필터링된 벡터 검색 실행
    search_results = await vector_db.client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=company_filter,
        limit=limit,
        with_payload=True
    )

    return search_results
```

---
