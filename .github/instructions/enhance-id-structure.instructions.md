## 🧠 Project A: ID 체계 개선 및 Qdrant 연동 표준화 GitHub Copilot 지침

다음은 Project A 시스템의 ID 체계 개선 및 Qdrant 벡터 DB 연동 표준화를 위한 GitHub Copilot 작업 지침입니다. 제공해주신 내용을 바탕으로 현재 저장소 구조에 맞게 각 파일별 수정 및 검토 사항을 구체적으로 명시했습니다.

### 🎯 목표
Project A 시스템의 ID 체계를 명확히 하고 Qdrant 벡터 DB와의 연동을 표준화하여, 코드의 가독성, 유지보수성 및 검색 정확도를 향상시킵니다.

---

### 🔑 핵심 원칙

1.  **`original_id` (Qdrant payload 내):**
    * Freshdesk의 원본 숫자 ID (예: 티켓 ID 12345, KB 문서 ID 67890)를 의미합니다.
    * Qdrant payload에 저장 시, **문자열 형태**로 변환하여 **접두어 없이** 저장합니다. (예: `{"original_id": "12345"}`)
    * 티켓, 지식베이스(KB) 문서 모두 이 규칙을 따릅니다.

2.  **컨버세이션 데이터:**
    * 별도의 Qdrant 문서로 저장되지 않고, 해당 티켓 문서의 payload 내 일부 (예: `conversations` 필드)로 포함됩니다.
    * 따라서 컨버세이션은 해당 티켓의 `original_id`로 식별됩니다.

3.  **API 경로 파라미터 (예: `{ticket_id}`):**
    * API 엔드포인트에서 사용되는 ID는 Freshdesk 원본 숫자 ID를 **문자열 형태**로 전달받는 것을 원칙으로 합니다. (예: API 호출 시 `/init/12345`)

4.  **Qdrant 포인트 ID (내부용):**
    * Qdrant 내부에서 각 벡터 문서를 식별하기 위해 사용하는 고유 ID입니다.
    * 일반적으로 UUID 형식을 사용하며, 이는 `original_id`와는 별개로 시스템 내부에서만 관리됩니다.
    * Qdrant 포인트 ID 생성 시, "ticket-" 또는 "kb-"와 같은 접두어를 붙인 문자열 (예: "ticket-12345")을 기반으로 UUID를 생성할 수 있으나, **이 접두어 붙은 ID 자체를 `original_id`로 사용하지 않습니다.**

5.  **`doc_type` (Qdrant payload 내):**
    * Qdrant payload에 문서의 유형을 명시적으로 저장합니다. (예: `{"doc_type": "ticket"}`, `{"doc_type": "kb"}`)
    * 이는 검색 시 특정 유형의 문서만 필터링하는 데 활용됩니다.

---

### 🛠️ 주요 수정 대상 및 검토 사항

#### 1. 데이터 수집 및 저장 (`backend/api/ingest.py`)

* **`process_batch` 함수 (또는 유사한 데이터 처리/저장 로직):**
    * Qdrant에 문서를 저장하기 위해 `QdrantAdapter.add_documents`를 호출할 때, `metadatas` 리스트의 각 요소(딕셔너리)에 다음 필드가 **정확히 포함**되도록 구성하십시오.
        * `original_id`: Freshdesk 원본 숫자 ID (**문자열 형태, 접두어 없음**).
            * 예: `ticket_data['id']`가 숫자 12345라면, `metadata['original_id'] = str(ticket_data['id'])` (즉, `"12345"`)
        * `doc_type`: 문서 유형 (**"ticket" 또는 "kb"**).
            * 예: `metadata['doc_type'] = "ticket"`
        * 기타 필요한 Freshdesk 원본 메타데이터.
    * **검토 포인트:** 현재 로직에서 `original_id`가 접두어를 포함하거나 숫자 형태로 전달되고 있지 않은지 확인하고 수정합니다.

```python
# 예시: backend/api/ingest.py 내의 데이터 처리 부분
# 실제 코드는 다를 수 있으므로, 해당 로직을 찾아 아래 원칙을 적용해야 합니다.

# documents = [] # Qdrant에 저장할 PointStruct 목록 또는 텍스트 목록
# metadatas = [] # 각 document에 대한 payload 정보

# for ticket_data in freshdesk_tickets:
#     # ... (텍스트 데이터 생성 로직) ...
#     current_metadata = {
#         "original_id": str(ticket_data['id']), # Freshdesk 원본 ID를 문자열로, 접두어 없이
#         "doc_type": "ticket", # 또는 "kb"
#         "title": ticket_data.get('subject'),
#         # ... 기타 필요한 메타데이터 ...
#     }
#     metadatas.append(current_metadata)

# # QdrantAdapter의 add_documents 호출 시 ids는 Qdrant 포인트 ID 생성용,
# # metadatas는 payload에 저장될 내용입니다.
# qdrant_adapter.add_documents(
#     documents=[...],
#     ids=[...], # 예: [f"ticket-{ticket_data['id']}" for ticket_data in freshdesk_tickets] 또는 UUID 기반
#     metadatas=metadatas
# )
```

#### 2. Qdrant 어댑터 (`backend/core/vectordb.py` - `QdrantAdapter` 클래스)

* **`add_documents` 함수:**
    * `ingest.py` (또는 다른 데이터 소스)로부터 전달받는 `metadatas` (위에서 정의한 `original_id`, `doc_type` 포함)를 각 Qdrant 포인트의 `payload`에 **올바르게 반영**해야 합니다.
    * **주의:** `payload` 구성 시, `ingest.py`에서 전달된 `metadatas`의 `original_id`를 Qdrant 포인트 ID 생성용 ID (예: `ids` 매개변수로 전달될 수 있는 "ticket-12345")로 **덮어쓰지 않도록** 주의하십시오. `payload` 내의 `original_id`는 항상 Freshdesk 원본 ID의 문자열 형태여야 합니다.

* **`get_by_id` 함수 (신규 또는 수정):**
    * 함수 시그니처 예시: `def get_by_id(self, original_id_value: str, doc_type: str = None, company_id: str = None) -> Optional[Dict]:`
    * 입력 파라미터 `original_id_value: str`는 **Freshdesk 원본 숫자 ID의 문자열 형태**를 받도록 합니다.
    * 내부적으로 Qdrant 클라이언트의 `scroll` API와 `Filter`를 사용하여 `payload.original_id`가 입력된 `original_id_value`와 일치하는 문서를 검색하도록 구현합니다.
    * 선택적으로 `doc_type` 및 `company_id` (존재한다면) 필터를 함께 사용하여 검색 결과를 좁힐 수 있도록 합니다.

```python
# 예시: backend/core/vectordb.py - QdrantAdapter 클래스 내
# from qdrant_client.http.models import Filter, FieldCondition, MatchValue

# class QdrantAdapter:
#     # ... (기존 코드) ...

#     def add_documents(self, collection_name: str, documents: List[str], ids: List[Any], metadatas: List[dict]):
#         # ... (기존 코드) ...
#         # points 생성 시 payload가 metadatas의 각 요소를 그대로 사용하는지 확인
#         # 예: PointStruct(id=point_id, vector=vector, payload=metadata)
#         # 여기서 metadata는 metadatas 리스트의 요소여야 하며,
#         # metadata['original_id']가 Freshdesk 원본 ID (문자열, 접두어 없음)인지 확인
#         pass

#     def get_by_id(self, collection_name: str, original_id_value: str, doc_type: Optional[str] = None, company_id: Optional[str] = None) -> Optional[Dict]:
#         filters = [
#             FieldCondition(key="payload.original_id", match=MatchValue(value=original_id_value))
#         ]
#         if doc_type:
#             filters.append(FieldCondition(key="payload.doc_type", match=MatchValue(value=doc_type)))
#         if company_id: # company_id 필드가 payload에 존재한다고 가정
#             filters.append(FieldCondition(key="payload.company_id", match=MatchValue(value=company_id)))

#         scroll_filter = Filter(must=filters)

#         try:
#             # 검색 결과는 여러 개일 수 있으나, original_id는 고유해야 하므로 첫 번째 결과를 반환하거나,
#             # 고유하지 않을 경우에 대한 처리 방안을 고려해야 합니다.
#             # 여기서는 첫 번째 결과만 가져온다고 가정합니다.
#             points, _next_page_offset = self.client.scroll(
#                 collection_name=collection_name,
#                 scroll_filter=scroll_filter,
#                 limit=1,
#                 with_payload=True,
#                 with_vectors=False # 필요에 따라 True
#             )
#             if points:
#                 return points[0].payload # payload 전체 또는 필요한 부분 반환
#             return None
#         except Exception as e:
#             # 로깅 및 예외 처리
#             print(f"Error fetching document by original_id {original_id_value}: {e}")
#             return None

```

#### 3. API 엔드포인트 로직 (`backend/api/main.py`)

* **경로 파라미터:**
    * 예시: `@app.get("/init/{ticket_id}")` 에서 `ticket_id`는 **Freshdesk 원본 숫자 ID를 문자열 형태**로 받습니다. (FastAPI가 자동으로 타입 변환을 시도할 수 있으나, 명시적으로 `str`로 받는 것이 좋습니다.)
    * **검토:** 현재 엔드포인트들이 `ticket_id`를 어떤 타입으로 받고 있는지 확인하고, 필요시 `str`로 통일합니다.

* **내부 모듈/함수 호출 시 ID 타입 일관성 유지:**
    * `freshdesk.fetcher.fetch_ticket_details(ticket_id: int, ...)` (또는 유사 함수) 호출 시:
        * API로 받은 문자열 `ticket_id`를 `int(ticket_id)`로 **명시적 형변환** 후 전달합니다.
    * `core.vectordb.QdrantAdapter.get_by_id(original_id_value: str, ...)` 호출 시:
        * API로 받은 문자열 `ticket_id`를 **그대로 전달**합니다.
    * **검토:** 각 함수 호출 시 전달되는 ID의 타입이 올바른지 확인하고 수정합니다.

```python
# 예시: backend/api/main.py

# from backend.core.dependencies import get_qdrant_adapter, get_settings
# from backend.freshdesk.fetcher import fetch_ticket_details # 가상의 함수, 실제 경로 확인 필요
# from backend.core.schemas import TicketSummary # 실제 스키마 경로 확인 필요

# @app.get("/init/{ticket_id}", response_model=TicketSummary) # 또는 다른 응답 모델
# async def get_initial_data(
#     ticket_id: str, # Freshdesk 원본 ID를 문자열로 받음
#     qdrant_adapter: QdrantAdapter = Depends(get_qdrant_adapter),
#     settings: Settings = Depends(get_settings)
# ):
#     # 1. Freshdesk에서 티켓 상세 정보 가져오기 (필요한 경우)
#     # fetch_ticket_details는 int형 ID를 받는다고 가정
#     try:
#         freshdesk_ticket_id_int = int(ticket_id)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid ticket_id format. Must be a number.")

#     # ticket_details = await fetch_ticket_details(settings.FRESHDESK_DOMAIN, settings.FRESHDESK_API_KEY, freshdesk_ticket_id_int) # 실제 함수 사용
#     # if not ticket_details:
#     #     raise HTTPException(status_code=404, detail="Ticket not found in Freshdesk")

#     # 2. Qdrant에서 정보 가져오기 (예: 티켓 요약 정보의 일부가 Qdrant에 있을 경우)
#     # QdrantAdapter.get_by_id는 문자열 ID를 받는다고 가정
#     # company_id는 요청 컨텍스트 또는 설정에서 가져올 수 있음 (예시)
#     # current_company_id = "some_company_id_from_context_or_config"
#     qdrant_payload = qdrant_adapter.get_by_id(
#         collection_name=settings.QDRANT_COLLECTION_TICKETS, # 설정 값 사용
#         original_id_value=ticket_id, # 문자열 ID 그대로 전달
#         doc_type="ticket"
#         # company_id=current_company_id # 필요한 경우
#     )
#     if not qdrant_payload:
#         raise HTTPException(status_code=404, detail="Ticket data not found in Vector DB")

#     # 3. 응답 모델 구성
#     # TicketSummary의 id 필드는 Freshdesk 원본 ID의 문자열 형태여야 함 (schemas.py 참조)
#     summary_data = {
#         "id": qdrant_payload.get("original_id"), # payload에서 original_id 사용
#         "title": qdrant_payload.get("title"),
#         # ... 기타 필드 ...
#         "problem": qdrant_payload.get("problem_description"), # 예시 필드명
#         # ...
#     }
#     # TicketSummary 모델로 변환하여 반환
#     return TicketSummary(**summary_data)
```

#### 4. API 응답 모델 (`backend/core/schemas.py`)

* `SimilarTicketItem`, `TicketSummary` 등 API 응답에 사용되는 Pydantic 모델에 포함되는 `id` 필드는 Qdrant `payload`에서 가져온 **`original_id` (Freshdesk 원본 ID의 문자열 형태)**를 사용하도록 합니다.
* **검토:** 각 스키마의 `id` 필드 타입과 해당 필드에 값이 할당되는 로직을 확인하여, `original_id` (문자열)가 사용되도록 보장합니다.

```python
# 예시: backend/core/schemas.py

# class TicketSummary(BaseModel):
#     id: str  # Freshdesk 원본 ID (문자열 형태)
#     title: Optional[str] = None
#     status: Optional[str] = None
#     priority: Optional[str] = None
#     # ... 기타 필드 정의 ...
#     problem: Optional[str] = None
#     cause: Optional[str] = None
#     # ...
#     # attachments: List[Attachment] = []

#     class Config:
#         orm_mode = True # 또는 from_attributes = True (Pydantic v2)

# class SimilarTicketItem(BaseModel):
#     id: str # Freshdesk 원본 ID (문자열 형태)
#     title: Optional[str] = None
#     excerpt: Optional[str] = None
#     # ...

#     class Config:
#         orm_mode = True # 또는 from_attributes = True (Pydantic v2)
```

---

### 📝 ID 종류별 명확한 정의 및 사용처 (재확인)

| ID 종류                 | 형식                                    | Qdrant payload 저장 값        | API 경로 파라미터 `{ticket_id}` | `freshdesk.fetcher.fetch_ticket_details` 인자 (예시) | `vectordb.QdrantAdapter.get_by_id` 인자 `original_id_value` | API 응답 모델 `id` 필드 |
| :---------------------- | :-------------------------------------- | :------------------------------ | :------------------------------ | :------------------------------------------------------- | :----------------------------------------------------------- | :------------------------ |
| Freshdesk 원본 ID       | 숫자 (예: 12345)                      | `original_id`: `"12345"` (문자열) | `"12345"` (문자열)              | `int(12345)`                                             | `"12345"` (문자열)                                       | `"12345"` (문자열)        |
| Qdrant 포인트 ID 생성용 | 문자열 (예: `"ticket-12345"`, UUID)   | (직접 저장 안 함)               | 해당 없음                       | 해당 없음                                                | 해당 없음                                                    | 해당 없음                 |
| Qdrant 포인트 ID (내부) | UUID 문자열 (예: `"xxxx-xxxx-..."`)     | (Qdrant 포인트 자체의 `id` 필드)  | 해당 없음                       | 해당 없음                                                | 해당 없음                                                    | 해당 없음                 |

---

이 지침들을 기준으로 코드 변경 및 검토 작업을 진행해주십시오. 각 파일과 함수에서 ID가 일관된 규칙에 따라 처리되고 저장되는지 확인하는 것이 중요합니다. 특히, `original_id`가 Qdrant payload에 **문자열 형태의 Freshdesk 원본 ID (접두어 없음)**로 저장되고, API와 내부 함수 간에 전달될 때 올바른 타입으로 변환/사용되는지 중점적으로 검토해주십시오.