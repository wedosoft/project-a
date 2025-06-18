---
applyTo: "**"
---

물론입니다. Phase 1과 Phase 2의 구체적인 코드 수정 내용을 포함하고, Phase 3 (`langchain-qdrant` 도입)와 Phase 4 (안정성 강화)까지 모두 반영한 최종 통합 버전을 마크다운 파일로 만들어 드립니다.

이 문서는 그대로 팀의 작업 지침서로 사용하실 수 있습니다.

---

# **Langchain 아키텍처 개선을 위한 단계별 리팩토링 가이드 (v2 - 통합본)**

## 🎯 **목표**

본 리팩토링의 목표는 현재 프로젝트의 LLM 활용 아키텍처를 개선하여 다음을 달성하는 것입니다.

1.  **성능 최적화**: LLM 동시 요청을 통해 API 응답 시간을 단축합니다.
2.  **유지보수성 향상**: 비즈니스 로직과 데이터 접근 로직을 Langchain 네이티브 방식으로 추상화하여 코드의 가독성과 재사용성을 높입니다.
3.  **확장성 확보**: 향후 캐싱, 폴백(Fallback), 고급 에이전트(Agent) 기능 등을 쉽게 추가할 수 있는 견고한 기반을 마련합니다.

---

## **Phase 1: 즉각적인 성능 개선 (`asyncio.gather`를 이용한 병렬 처리)**

가장 시급한 `/init/{ticket_id}` 엔드포인트의 성능 문제를 최소한의 코드로 즉시 해결합니다.

- **변경 대상**: `backend/api/main.py`
- **핵심 작업**: 순차적으로 실행되던 3개의 LLM 체인 호출을 `asyncio.gather`를 사용하여 동시에 실행하도록 변경합니다.

### **수정 가이드**

`backend/api/main.py` 파일의 `init_ticket` 함수를 아래와 같이 수정합니다.

```python
# backend/api/main.py

import asyncio  # asyncio 임포트 추가
from fastapi import APIRouter, Depends, HTTPException, status
from ..core.dependencies import get_llm_router, get_settings
from ..core.llm_router import LLM_ROUTER
from ..core import schemas
from ..core.logger import logger
from ..core.settings import Settings


router = APIRouter()

@router.post("/init/{ticket_id}",
             status_code=status.HTTP_200_OK,
             response_model=schemas.InitResponse)
async def init_ticket(
    ticket_id: int,
    data: schemas.InitRequest,
    llm_router: LLM_ROUTER = Depends(get_llm_router),
    settings: Settings = Depends(get_settings),
):
    """
    Initializes a ticket by processing its data, generating a title, summary, and category.
    """
    logger.info(f"Initializing ticket {ticket_id} with email body.")

    try:
        # --- 기존 코드 (Before) ---
        # # Step 1: Generate Title
        # title_chain = llm_router.get_title_generation_chain()
        # title = await title_chain.ainvoke({"email_body": data.email_body})
        #
        # # Step 2: Generate Summary
        # summary_chain = llm_router.get_summary_generation_chain()
        # summary = await summary_chain.ainvoke({"email_body": data.email_body})
        #
        # # Step 3: Classify Category
        # category_chain = llm_router.get_category_classification_chain()
        # category = await category_chain.ainvoke({"email_body": data.email_body})

        # --- 수정 코드 (After) ---
        title_chain = llm_router.get_title_generation_chain()
        summary_chain = llm_router.get_summary_generation_chain()
        category_chain = llm_router.get_category_classification_chain()

        # 3개의 작업을 병렬로 동시에 실행
        results = await asyncio.gather(
            title_chain.ainvoke({"email_body": data.email_body}),
            summary_chain.ainvoke({"email_body": data.email_body}),
            category_chain.ainvoke({"email_body": data.email_body})
        )

        # 병렬 실행 결과 할당
        title, summary, category = results[0], results[1], results[2]
        # --- 수정 완료 ---

        logger.info(f"Successfully generated title, summary, and category for ticket {ticket_id}.")

        response = schemas.InitResponse(
            title=title.content,
            summary=summary.content,
            category=category.content
        )
        return response

    except Exception as e:
        logger.error(f"Error initializing ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while initializing the ticket: {e}",
        )
```

---

## **Phase 2: Langchain 네이티브 리팩토링 (`RunnableParallel` 적용)**

`asyncio`를 직접 사용하는 대신, Langchain Expression Language (LCEL)가 제공하는 `RunnableParallel`을 사용하여 비즈니스 로직을 하나의 체인으로 캡슐화합니다.

- **변경 대상 1**: `backend/core/llm_router.py`
- **변경 대상 2**: `backend/api/main.py`

### **수정 가이드 1: `llm_router.py`에 통합 체인 생성**

`LLM_ROUTER` 클래스에 병렬 처리를 위한 새로운 통합 체인 생성 메서드를 추가합니다.

```python
# backend/core/llm_router.py

from langchain_core.runnables import RunnableParallel, RunnableSequence
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from .settings import Settings

class LLM_ROUTER:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = ChatOpenAI(temperature=0, openai_api_key=self.settings.openai_api_key.get_secret_value())

    def get_title_generation_chain(self):
        # ... (기존 로직)
        prompt = ChatPromptTemplate.from_template("Generate a concise title for the following email body:\n\n{email_body}")
        return RunnableSequence(prompt | self.llm)

    def get_summary_generation_chain(self):
        # ... (기존 로직)
        prompt = ChatPromptTemplate.from_template("Summarize the following email body:\n\n{email_body}")
        return RunnableSequence(prompt | self.llm)

    def get_category_classification_chain(self):
        # ... (기존 로직)
        prompt = ChatPromptTemplate.from_template("Classify the category of the following email body:\n\n{email_body}")
        return RunnableSequence(prompt | self.llm)

    def get_ticket_initialization_chain(self) -> RunnableParallel:
        """
        티켓 초기화(제목, 요약, 분류)를 위한 병렬 처리 체인을 반환합니다.
        """
        return RunnableParallel(
            title=self.get_title_generation_chain(),
            summary=self.get_summary_generation_chain(),
            category=self.get_category_classification_chain(),
        )
```

### **수정 가이드 2: `main.py`에서 통합 체인 사용**

`init_ticket` 함수에서 `asyncio.gather` 대신 새로 만든 통합 체인을 호출하도록 수정합니다.

```python
# backend/api/main.py

# asyncio 임포트는 더 이상 필요 없으므로 제거 가능
from fastapi import APIRouter, Depends, HTTPException, status
from ..core.dependencies import get_llm_router, get_settings
from ..core.llm_router import LLM_ROUTER
from ..core import schemas
from ..core.logger import logger
from ..core.settings import Settings

router = APIRouter()

@router.post("/init/{ticket_id}",
             #...
             )
async def init_ticket(
    ticket_id: int,
    data: schemas.InitRequest,
    llm_router: LLM_ROUTER = Depends(get_llm_router),
    settings: Settings = Depends(get_settings),
):
    # ...
    try:
        # Phase 1에서 수정했던 asyncio.gather 로직을 아래 코드로 대체
        initialization_chain = llm_router.get_ticket_initialization_chain()

        # 통합 체인을 한 번만 호출
        result_dict = await initialization_chain.ainvoke({"email_body": data.email_body})

        response = schemas.InitResponse(
            title=result_dict.get('title').content,
            summary=result_dict.get('summary').content,
            category=result_dict.get('category').content
        )
        return response

    except Exception as e:
        logger.error(f"Error initializing ticket {ticket_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while initializing the ticket: {e}",
        )
```

---

## **Phase 3: Vector Store 추상화 (`langchain-qdrant` 도입)**

현재 `qdrant-client`를 직접 사용하여 구현된 `VectorDB` 클래스와 `CustomRetriever`를 `langchain-qdrant` 라이브러리로 대체하여 아키텍처를 대폭 개선합니다.

### **수정 가이드**

#### **1. 의존성 추가**

`backend/requirements.txt` 파일에 `langchain-qdrant`를 추가합니다.

```text
# backend/requirements.txt
...
langchain==0.1.16
langchain-community==0.0.34
langchain-core==0.1.45
langchain-openai==0.1.3
langchain-qdrant  # <-- 이 라인 추가
qdrant-client==1.8.2
...
```

#### **2. `core/vectordb.py` 와 `core/retriever.py` 리팩토링**

현재 두 파일에 나뉘어 있는 복잡한 로직을 Langchain의 `Qdrant` 클래스를 사용하여 대폭 단순화합니다.

**개선 코드 예시 (`backend/core/retriever.py`):**

기존 `CustomRetriever` 클래스와 `get_retriever` 함수를 아래의 새 함수로 대체합니다. (`core/vectordb.py` 파일은 더 이상 필요 없게 되어 삭제 가능합니다.)

```python
# backend/core/retriever.py

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import Qdrant
from qdrant_client import QdrantClient

from .settings import Settings

# VectorDB 클래스와 CustomRetriever 클래스는 더 이상 필요 없으므로 삭제합니다.

def get_qdrant_retriever(
    settings: Settings,
    embeddings: Embeddings,
    collection_name: str
) -> VectorStoreRetriever:
    """
    langchain-qdrant를 사용하여 Qdrant DB에 연결하고
    표준 VectorStoreRetriever를 반환합니다.
    """
    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        grpc_port=settings.qdrant_grpc_port,
        prefer_grpc=settings.qdrant_prefer_grpc,
        api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
    )

    # langchain-qdrant의 Qdrant 클래스를 사용하여 vector_store 인스턴스 생성
    vector_store = Qdrant(
        client=client,
        collection_name=collection_name,
        embeddings=embeddings,
    )

    # .as_retriever() 메서드를 호출하기만 하면 표준 리트리버가 생성됩니다.
    return vector_store.as_retriever(
        search_type="similarity", # 또는 "mmr"
        search_kwargs={"k": 5}
    )
```

---

## **Phase 4: 프로덕션 안정성 강화 (캐싱 & 폴백)**

시스템의 안정성과 비용 효율성을 위해 Langchain의 고급 기능을 도입합니다.

### **1. LLM 응답 캐싱 (Caching)**

동일한 요청에 대해 LLM API를 반복 호출하는 것을 방지하여 비용을 절감하고 응답 속도를 향상시킵니다.

**구현 가이드 (예시):**
애플리케이션 시작 지점 (예: `backend/api/main.py` 최상단)에 다음 코드를 추가합니다.

```python
# backend/api/main.py 최상단

import langchain
from langchain.cache import InMemoryCache

# 애플리케이션 시작 시 Langchain 전역 캐시 설정
# 프로덕션 환경에서는 RedisCache 등을 고려
langchain.llm_cache = InMemoryCache()

# ... (기존 FastAPI 애플리케이션 코드)
```

### **2. LLM 폴백 (Fallbacks)**

주력 모델에 장애 발생 시, 대체 모델로 자동 전환하여 서비스 안정성을 높입니다.

**구현 가이드 (예시 - `backend/core/llm_router.py`):**

```python
# backend/core/llm_router.py
from langchain_openai import ChatOpenAI
# ... (다른 import)

class LLM_ROUTER:
    def __init__(self, settings: Settings):
        self.settings = settings
        # 주력 LLM
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=self.settings.openai_api_key.get_secret_value())
        # 폴백 LLM
        self.fallback_llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=self.settings.openai_api_key.get_secret_value())

    def get_title_generation_chain(self):
        prompt = ChatPromptTemplate.from_template("Generate a concise title for the following email body:\n\n{email_body}")

        # 주력 LLM 체인에 .with_fallbacks()를 사용하여 폴백 로직 추가
        primary_chain = prompt | self.llm
        chain_with_fallback = primary_chain.with_fallbacks(
            fallbacks=[self.fallback_llm],
        )
        return chain_with_fallback

    # ... (get_summary_generation_chain 등 다른 체인에도 동일하게 폴백 적용 가능)
```
