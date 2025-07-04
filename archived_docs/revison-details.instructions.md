---
applyTo: "**"
---

네, 지금까지 논의한 내용을 종합하여 상세한 지침서를 작성하겠습니다.

```markdown
# 📚 Copilot RAG 시스템 최종 구현 지침서 v3

이 문서는 Freshdesk 기반 Copilot 시스템의 데이터 수집, 처리, 저장 및 추천 기능 구현을 위한 최종 지침서입니다.

---

## 📌 시스템 전체 아키텍처

### 🎯 목표

- Freshdesk 티켓 데이터를 수집하여 LLM 요약 생성
- 유사 티켓 추천 및 솔루션 제공
- 피드백 기반 추천 정확도 개선
- SaaS 확장성을 고려한 멀티테넌트 구조

### 🔄 전체 데이터 흐름
```

[Step 1] 데이터 수집 (티켓+대화+첨부파일) →
[Step 2] 하나의 문서로 병합 →
[Step 3] LLM 요약 (이슈/해결 요약) →
[Step 4] 임베딩 생성 →
[Step 5] Vector DB 저장 →
[Step 6] Copilot UI에서 추천 →
[Step 7] 피드백 수집 및 반영

```

---

## 1. 데이터 수집 및 병합 아키텍처

### 1.1 MVP 단계 (현재) - 파일 기반

#### 📂 디렉토리 구조
```

project-a/
├── data/
│ ├── raw/ # 원본 데이터
│ │ ├── tickets/ # 병합된 티켓 JSON
│ │ └── kb/ # 지식베이스 문서
│ ├── processed/ # LLM 요약된 데이터
│ │ ├── tickets/  
│ │ └── kb/
│ └── progress/ # 진행 상황 추적
│ └── progress.json

````

#### 🔧 데이터 병합 로직
```python
# backend/data/ingest.py
from typing import Dict, Any, List
import hashlib
import json
from pathlib import Path

class TicketMerger:
    """티켓 데이터 병합 클래스"""

    def merge_ticket_data(
        self,
        ticket: dict,
        conversations: list,
        attachments: list
    ) -> dict:
        """
        티켓 원본, 대화 내역, 첨부파일을 하나의 문서로 병합

        Args:
            ticket: 티켓 원본 데이터
            conversations: 대화 내역 리스트
            attachments: 첨부파일 메타데이터 리스트

        Returns:
            병합된 티켓 문서
        """
        # 대화 내용을 텍스트로 병합
        conversation_text = "\n\n".join([
            f"[{conv.get('created_at')}] {conv.get('body', '')}"
            for conv in conversations
        ])

        merged_document = {
            "original_id": str(ticket["id"]),
            "doc_type": "ticket",
            "subject": ticket.get("subject", ""),
            "description": ticket.get("description", ""),
            "merged_content": f"{ticket.get('description', '')}\n\n{conversation_text}",
            "conversations": conversations,
            "attachments": [
                {
                    "attachment_id": str(att["id"]),
                    "file_name": att["name"],
                    "content_type": att["content_type"],
                    "url": att["attachment_url"]
                } for att in attachments
            ],
            "metadata": {
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("updated_at"),
                "tags": ticket.get("tags", [])
            }
        }

        return merged_document

    def generate_document_hash(self, document: dict) -> str:
        """문서의 해시값 생성 (중복/변경 감지용)"""
        doc_str = json.dumps(document, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(doc_str.encode('utf-8')).hexdigest()
````

### 1.2 프로덕션 단계 - 클라우드 기반

#### 🗄️ 데이터베이스 설계

```sql
-- PostgreSQL 스키마 설계
-- 티켓 원본 및 처리 상태 관리
CREATE TABLE tickets (
    id BIGINT PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,           -- 원본 티켓+대화+첨부파일
    llm_summary JSONB,                 -- LLM 요약 결과
    processing_status VARCHAR(50) DEFAULT 'pending',
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hash VARCHAR(64) NOT NULL,         -- 중복/변경 감지용
    INDEX idx_company_status (company_id, processing_status),
    INDEX idx_hash (hash)
);

-- LLM 처리 큐
CREATE TABLE processing_queue (
    id SERIAL PRIMARY KEY,
    ticket_id BIGINT NOT NULL,
    company_id VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'queued',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_queue_status (status, created_at)
);

-- 피드백 데이터
CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    query_id VARCHAR(255),
    recommended_ticket_ids JSONB,
    feedback_type VARCHAR(20), -- 'positive' or 'negative'
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_company_feedback (company_id, timestamp)
);
```

---

## 2. LLM 요약 처리

### 2.1 요약 생성 로직

```python
# backend/core/llm_summarizer.py
from langchain.prompts import ChatPromptTemplate
from langchain.chat_models import ChatOpenAI
import asyncio
from typing import List, Dict, Any

class TicketSummarizer:
    """티켓 요약 생성 클래스"""

    def __init__(self, llm_client):
        self.llm = llm_client
        self.summary_prompt = ChatPromptTemplate.from_template("""
당신은 고객 지원 티켓을 분석하는 전문가입니다.
다음 티켓 내용을 분석하여 구조화된 요약을 생성해주세요.

티켓 내용:
{ticket_content}

다음 형식으로 요약해주세요:
1. 문제 (Problem): 고객이 겪고 있는 주요 문제
2. 원인 (Cause): 문제의 근본 원인
3. 해결방법 (Solution): 제시된 해결 방법
4. 결과 (Result): 최종 해결 여부 및 결과

JSON 형식으로 응답해주세요.
""")

    async def summarize_ticket(self, merged_document: Dict[str, Any]) -> Dict[str, Any]:
        """단일 티켓 요약 생성"""
        try:
            # 티켓 전체 텍스트 준비
            ticket_content = merged_document['merged_content']

            # 텍스트가 너무 긴 경우 청크로 분할
            if len(ticket_content) > 10000:  # 약 2500 토큰
                chunks = self.split_into_chunks(ticket_content)
                summaries = await asyncio.gather(*[
                    self._generate_chunk_summary(chunk)
                    for chunk in chunks
                ])
                # 청크 요약들을 통합
                final_summary = await self._merge_summaries(summaries)
            else:
                # 직접 요약 생성
                final_summary = await self._generate_summary(ticket_content)

            # 문서에 요약 추가
            merged_document['llm_summary'] = final_summary
            merged_document['summary_generated_at'] = datetime.utcnow().isoformat()

            return merged_document

        except Exception as e:
            print(f"요약 생성 실패: {e}")
            merged_document['llm_summary'] = {
                "problem": "요약 생성 실패",
                "cause": str(e),
                "solution": "수동 검토 필요",
                "result": "처리 실패"
            }
            return merged_document

    def split_into_chunks(self, text: str, max_chars: int = 8000) -> List[str]:
        """긴 텍스트를 청크로 분할"""
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = []
        current_length = 0

        for paragraph in paragraphs:
            if current_length + len(paragraph) > max_chars:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [paragraph]
                current_length = len(paragraph)
            else:
                current_chunk.append(paragraph)
                current_length += len(paragraph)

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks
```

### 2.2 배치 처리 및 비용 최적화

```python
# backend/data/batch_processor.py
class BatchProcessor:
    """배치 단위 LLM 처리"""

    def __init__(self, storage, llm_summarizer):
        self.storage = storage
        self.summarizer = llm_summarizer
        self.batch_size = 10
        self.max_concurrent = 5  # 동시 처리 수 제한

    async def process_pending_tickets(self, company_id: str):
        """대기 중인 티켓들을 배치로 처리"""
        while True:
            # 처리할 티켓 가져오기
            pending_tickets = await self.storage.get_pending_tickets(
                company_id=company_id,
                limit=self.batch_size
            )

            if not pending_tickets:
                break

            # 동시성 제한을 두고 병렬 처리
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def process_with_limit(ticket):
                async with semaphore:
                    return await self.process_single_ticket(ticket)

            # 배치 처리
            results = await asyncio.gather(*[
                process_with_limit(ticket)
                for ticket in pending_tickets
            ], return_exceptions=True)

            # 결과 저장
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    await self.handle_error(pending_tickets[i], result)
                else:
                    await self.storage.save_processed_ticket(result)

            # 진행 상황 업데이트
            await self.update_progress(company_id, len(results))
```

---

## 3. 벡터 저장 및 검색

### 3.1 임베딩 생성 및 저장

```python
# backend/core/embedding_manager.py
from langchain.embeddings import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import uuid

class EmbeddingManager:
    """임베딩 생성 및 벡터 DB 관리"""

    def __init__(self, qdrant_url: str, api_key: str):
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self.qdrant = QdrantClient(url=qdrant_url, api_key=api_key)

    async def store_ticket_embeddings(self, processed_ticket: Dict[str, Any], company_id: str):
        """처리된 티켓을 벡터 DB에 저장"""

        # 요약된 텍스트로 임베딩 생성
        summary_text = json.dumps(processed_ticket['llm_summary'], ensure_ascii=False)
        embedding = await self.embeddings.aembed_query(summary_text)

        # Qdrant 포인트 생성
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "original_id": processed_ticket["original_id"],
                "doc_type": "ticket",
                "company_id": company_id,
                "subject": processed_ticket["subject"],
                "summary": processed_ticket["llm_summary"],
                "metadata": processed_ticket["metadata"],
                "created_at": processed_ticket.get("created_at"),
                "processed_at": datetime.utcnow().isoformat()
            }
        )

        # 컬렉션에 저장
        collection_name = f"tickets_{company_id}"
        await self.ensure_collection_exists(collection_name)

        self.qdrant.upsert(
            collection_name=collection_name,
            points=[point]
        )

    async def search_similar_tickets(
        self,
        query: str,
        company_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """유사 티켓 검색"""

        # 쿼리 임베딩 생성
        query_embedding = await self.embeddings.aembed_query(query)

        # 벡터 검색
        collection_name = f"tickets_{company_id}"
        results = self.qdrant.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            limit=limit,
            with_payload=True
        )

        # 결과 포맷팅
        similar_tickets = []
        for result in results:
            similar_tickets.append({
                "ticket_id": result.payload["original_id"],
                "subject": result.payload["subject"],
                "summary": result.payload["summary"],
                "similarity_score": result.score,
                "metadata": result.payload.get("metadata", {})
            })

        return similar_tickets
```

---

## 4. 추상화 레이어 설계

### 4.1 스토리지 인터페이스

```python
# backend/core/storage_interface.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class StorageInterface(ABC):
    """스토리지 추상 인터페이스"""

    @abstractmethod
    async def save_ticket(self, ticket_data: Dict[str, Any]) -> None:
        """티켓 데이터 저장"""
        pass

    @abstractmethod
    async def get_ticket(self, ticket_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        """티켓 데이터 조회"""
        pass

    @abstractmethod
    async def get_pending_tickets(self, company_id: str, limit: int) -> List[Dict[str, Any]]:
        """처리 대기 중인 티켓 목록 조회"""
        pass

    @abstractmethod
    async def update_ticket_status(self, ticket_id: str, company_id: str, status: str) -> None:
        """티켓 처리 상태 업데이트"""
        pass

    @abstractmethod
    async def save_progress(self, company_id: str, progress_data: Dict[str, Any]) -> None:
        """진행 상황 저장"""
        pass
```

### 4.2 파일 기반 구현 (MVP)

```python
# backend/core/file_storage.py
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from .storage_interface import StorageInterface

class FileStorage(StorageInterface):
    """파일 기반 스토리지 구현"""

    def __init__(self, base_path: str = "./data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_ticket(self, ticket_data: Dict[str, Any]) -> None:
        company_id = ticket_data.get("company_id", "default")
        ticket_id = ticket_data["original_id"]

        # 디렉토리 생성
        ticket_dir = self.base_path / "raw" / "tickets" / company_id
        ticket_dir.mkdir(parents=True, exist_ok=True)

        # 파일 저장
        file_path = ticket_dir / f"{ticket_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(ticket_data, f, ensure_ascii=False, indent=2)

    async def get_ticket(self, ticket_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.base_path / "raw" / "tickets" / company_id / f"{ticket_id}.json"

        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    async def get_pending_tickets(self, company_id: str, limit: int) -> List[Dict[str, Any]]:
        raw_dir = self.base_path / "raw" / "tickets" / company_id
        processed_dir = self.base_path / "processed" / "tickets" / company_id

        if not raw_dir.exists():
            return []

        pending_tickets = []
        for file_path in raw_dir.glob("*.json"):
            ticket_id = file_path.stem
            processed_path = processed_dir / f"{ticket_id}.json"

            # 아직 처리되지 않은 티켓만 선택
            if not processed_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    ticket_data = json.load(f)
                    pending_tickets.append(ticket_data)

                if len(pending_tickets) >= limit:
                    break

        return pending_tickets
```

### 4.3 PostgreSQL 구현 (프로덕션)

```python
# backend/core/postgres_storage.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from .storage_interface import StorageInterface
from .models import Ticket, ProcessingQueue

class PostgresStorage(StorageInterface):
    """PostgreSQL 기반 스토리지 구현"""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save_ticket(self, ticket_data: Dict[str, Any]) -> None:
        async with self.async_session() as session:
            # 기존 티켓 확인
            existing = await session.get(Ticket, ticket_data["original_id"])

            if existing:
                # 해시 비교하여 변경된 경우만 업데이트
                new_hash = self._generate_hash(ticket_data)
                if existing.hash != new_hash:
                    existing.raw_data = ticket_data
                    existing.hash = new_hash
                    existing.processing_status = 'pending'
                    existing.updated_at = datetime.utcnow()
            else:
                # 새 티켓 생성
                ticket = Ticket(
                    id=int(ticket_data["original_id"]),
                    company_id=ticket_data["company_id"],
                    raw_data=ticket_data,
                    hash=self._generate_hash(ticket_data),
                    processing_status='pending'
                )
                session.add(ticket)

            await session.commit()

    async def get_pending_tickets(self, company_id: str, limit: int) -> List[Dict[str, Any]]:
        async with self.async_session() as session:
            query = select(Ticket).where(
                Ticket.company_id == company_id,
                Ticket.processing_status == 'pending'
            ).limit(limit)

            result = await session.execute(query)
            tickets = result.scalars().all()

            return [ticket.raw_data for ticket in tickets]
```

---

## 5. 멀티테넌트 및 멀티플랫폼 지원

### 5.1 플랫폼 어댑터 패턴

```python
# backend/adapters/base_adapter.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BasePlatformAdapter(ABC):
    """플랫폼 어댑터 기본 인터페이스"""

    @abstractmethod
    async def fetch_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """티켓 상세 정보 가져오기"""
        pass

    @abstractmethod
    async def fetch_conversations(self, ticket_id: str) -> List[Dict[str, Any]]:
        """티켓 대화 내역 가져오기"""
        pass

    @abstractmethod
    async def fetch_attachments(self, ticket_id: str) -> List[Dict[str, Any]]:
        """티켓 첨부파일 정보 가져오기"""
        pass

    @abstractmethod
    async def fetch_knowledge_base(self) -> List[Dict[str, Any]]:
        """지식베이스 문서 가져오기"""
        pass
```

### 5.2 Freshdesk 어댑터

```python
# backend/adapters/freshdesk_adapter.py
from .base_adapter import BasePlatformAdapter
from freshdesk.api import API

class FreshdeskAdapter(BasePlatformAdapter):
    """Freshdesk 플랫폼 어댑터"""

    def __init__(self, domain: str, api_key: str):
        self.client = API(domain, api_key)

    async def fetch_ticket(self, ticket_id: str) -> Dict[str, Any]:
        ticket = self.client.tickets.get_ticket(int(ticket_id))
        return self._normalize_ticket(ticket)

    async def fetch_conversations(self, ticket_id: str) -> List[Dict[str, Any]]:
        conversations = self.client.conversations.list_all_conversations(int(ticket_id))
        return [self._normalize_conversation(conv) for conv in conversations]

    def _normalize_ticket(self, ticket: dict) -> dict:
        """Freshdesk 티켓을 공통 형식으로 변환"""
        return {
            "id": str(ticket["id"]),
            "subject": ticket.get("subject", ""),
            "description": ticket.get("description", ""),
            "status": ticket.get("status"),
            "priority": ticket.get("priority"),
            "created_at": ticket.get("created_at"),
            "updated_at": ticket.get("updated_at"),
            "tags": ticket.get("tags", [])
        }
```

### 5.3 고객별 설정 관리

```python
# backend/core/customer_config.py
from typing import Dict, Any, Optional
import secrets

class CustomerConfigManager:
    """고객별 설정 관리"""

    def __init__(self, storage):
        self.storage = storage
        self._cache = {}

    async def get_customer_config(self, company_id: str) -> Dict[str, Any]:
        """고객사 설정 조회 (캐시 적용)"""
        if company_id in self._cache:
            return self._cache[company_id]

        config = await self.storage.get_customer_config(company_id)
        if not config:
            raise ValueError(f"고객사 설정을 찾을 수 없습니다: {company_id}")

        # 암호화된 API 키 복호화
        config['api_key'] = self._decrypt_api_key(config['encrypted_api_key'])

        self._cache[company_id] = config
        return config

    async def save_customer_config(self, company_id: str, config: Dict[str, Any]) -> None:
        """고객사 설정 저장"""
        # API 키 암호화
        if 'api_key' in config:
            config['encrypted_api_key'] = self._encrypt_api_key(config['api_key'])
            del config['api_key']

        await self.storage.save_customer_config(company_id, config)

        # 캐시 무효화
        if company_id in self._cache:
            del self._cache[company_id]

    def _encrypt_api_key(self, api_key: str) -> str:
        """API 키 암호화 (실제 구현에서는 적절한 암호화 라이브러리 사용)"""
        # 예시: Fernet 암호화 사용
        from cryptography.fernet import Fernet
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.encrypt(api_key.encode()).decode()

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """API 키 복호화"""
        from cryptography.fernet import Fernet
        key = self._get_encryption_key()
        f = Fernet(key)
        return f.decrypt(encrypted_key.encode()).decode()
```

---

## 6. 피드백 수집 및 추천 개선

### 6.1 피드백 API

```python
# backend/api/feedback.py
from fastapi import APIRouter, Depends
from ..core.schemas import FeedbackRequest, FeedbackResponse
from ..core.dependencies import get_storage

router = APIRouter()

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    storage = Depends(get_storage)
):
    """추천 결과에 대한 피드백 수집"""

    feedback_data = {
        "company_id": request.company_id,
        "query_id": request.query_id,
        "recommended_ticket_ids": request.recommended_tickets,
        "feedback_type": request.type,  # 'positive' or 'negative'
        "timestamp": datetime.utcnow().isoformat()
    }

    await storage.save_feedback(feedback_data)

    return FeedbackResponse(
        status="success",
        message="피드백이 저장되었습니다."
    )
```

### 6.2 추천 점수 재조정

```python
# backend/core/recommendation_optimizer.py
from typing import List, Dict, Any
import numpy as np

class RecommendationOptimizer:
    """피드백 기반 추천 최적화"""

    def __init__(self, storage):
        self.storage = storage
        self.boost_factor = 1.2
        self.penalty_factor = 0.8

    async def rerank_recommendations(
        self,
        candidates: List[Dict[str, Any]],
        company_id: str
    ) -> List[Dict[str, Any]]:
        """피드백 기반으로 추천 결과 재정렬"""

        # 최근 피드백 데이터 로드
        recent_feedback = await self.storage.get_recent_feedback(
            company_id=company_id,
            days=30
        )

        # 티켓별 피드백 점수 계산
        feedback_scores = self._calculate_feedback_scores(recent_feedback)

        # 후보 점수 조정
        for candidate in candidates:
            ticket_id = candidate['ticket_id']

            if ticket_id in feedback_scores:
                # 피드백 기반 점수 조정
                original_score = candidate['similarity_score']
                feedback_multiplier = feedback_scores[ticket_id]
                candidate['adjusted_score'] = original_score * feedback_multiplier
            else:
                # 피드백이 없는 경우 원본 점수 유지
                candidate['adjusted_score'] = candidate['similarity_score']

        # 조정된 점수로 재정렬
        return sorted(candidates, key=lambda x: x['adjusted_score'], reverse=True)

    def _calculate_feedback_scores(self, feedback_list: List[Dict]) -> Dict[str, float]:
        """티켓별 피드백 점수 계산"""
        scores = {}

        for feedback in feedback_list:
            for ticket_id in feedback['recommended_ticket_ids']:
                if ticket_id not in scores:
                    scores[ticket_id] = 1.0

                if feedback['feedback_type'] == 'positive':
                    scores[ticket_id] *= self.boost_factor
                else:
                    scores[ticket_id] *= self.penalty_factor

        return scores
```

---

## 7. API 엔드포인트 구현

### 7.1 초기화 엔드포인트

```python
# backend/api/main.py
from fastapi import FastAPI, Depends, Header
from typing import Optional

app = FastAPI()

@app.get("/init/{ticket_id}")
async def init_ticket_data(
    ticket_id: str,
    x_freshdesk_domain: Optional[str] = Header(None),
    x_freshdesk_api_key: Optional[str] = Header(None),
    storage = Depends(get_storage),
    vector_db = Depends(get_vector_db)
):
    """티켓 초기 데이터 로드"""

    # 동적 Freshdesk 설정 추출
    company_id = extract_company_id(x_freshdesk_domain)

    # 티켓 요약 생성 또는 조회
    ticket_summary = await get_or_generate_summary(
        ticket_id, company_id, storage
    )

    # 유사 티켓 검색
    similar_tickets = await vector_db.search_similar_tickets(
        query=ticket_summary['problem'],
        company_id=company_id,
        limit=5
    )

    # 관련 솔루션 검색
    related_solutions = await vector_db.search_solutions(
        query=ticket_summary['problem'],
        company_id=company_id,
        limit=5
    )

    return {
        "ticket_summary": ticket_summary,
        "similar_tickets": similar_tickets,
        "related_solutions": related_solutions
    }
```

### 7.2 자연어 쿼리 엔드포인트

```python
@app.post("/query")
async def process_natural_language_query(
    request: QueryRequest,
    x_freshdesk_domain: Optional[str] = Header(None),
    x_freshdesk_api_key: Optional[str] = Header(None),
    vector_db = Depends(get_vector_db),
    llm_client = Depends(get_llm_client)
):
    """자연어 쿼리 처리"""

    company_id = extract_company_id(x_freshdesk_domain)

    # 의도 분석
    intent = await analyze_intent(request.query, llm_client)

    results = {}

    # 선택된 콘텐츠 타입별 검색
    if "tickets" in request.type:
        results["tickets"] = await vector_db.search_similar_tickets(
            query=request.query,
            company_id=company_id,
            limit=10
        )

    if "solutions" in request.type:
        results["solutions"] = await vector_db.search_solutions(
            query=request.query,
            company_id=company_id,
            limit=10
        )

    if "attachments" in request.type:
        results["attachments"] = await search_attachments(
            query=request.query,
            company_id=company_id
        )

    # LLM 응답 생성
    llm_response = await generate_contextual_response(
        query=request.query,
        search_results=results,
        llm_client=llm_client
    )

    return {
        "intent": intent,
        "results": results,
        "llm_response": llm_response
    }
```

---

## 8. 모니터링 및 운영

### 8.1 성능 메트릭

```python
# backend/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# 메트릭 정의
ticket_processed_counter = Counter(
    'tickets_processed_total',
    'Total number of tickets processed',
    ['company_id', 'status']
)

llm_request_duration = Histogram(
    'llm_request_duration_seconds',
    'LLM API request duration',
    ['model', 'operation']
)

vector_search_duration = Histogram(
    'vector_search_duration_seconds',
    'Vector search duration',
    ['collection', 'company_id']
)

active_processing_gauge = Gauge(
    'active_processing_tasks',
    'Number of active processing tasks',
    ['company_id']
)

class MetricsCollector:
    """메트릭 수집 헬퍼"""

    @staticmethod
    def track_llm_request(model: str, operation: str):
        """LLM 요청 추적 데코레이터"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    llm_request_duration.labels(
                        model=model,
                        operation=operation
                    ).observe(duration)
            return wrapper
        return decorator
```

### 8.2 에러 처리 및 재시도

```python
# backend/core/error_handler.py
import asyncio
from typing import TypeVar, Callable
from functools import wraps

T = TypeVar('T')

class RetryConfig:
    """재시도 설정"""
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay

def with_retry(config: RetryConfig = RetryConfig()):
    """재시도 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        # 지수 백오프
                        delay = config.base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)

                    print(f"재시도 {attempt + 1}/{config.max_attempts}: {e}")

            raise last_exception

        return wrapper
    return decorator
```

---

## 9. 보안 및 규정 준수

### 9.1 데이터 보안

```python
# backend/core/security.py
from cryptography.fernet import Fernet
import hashlib
import hmac

class SecurityManager:
    """보안 관리자"""

    def __init__(self, encryption_key: bytes):
        self.cipher = Fernet(encryption_key)

    def encrypt_sensitive_data(self, data: str) -> str:
        """민감한 데이터 암호화"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """암호화된 데이터 복호화"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def generate_api_signature(self, api_key: str, timestamp: str) -> str:
        """API 요청 서명 생성"""
        message = f"{api_key}:{timestamp}".encode()
        signature = hmac.new(
            self.signing_key,
            message,
            hashlib.sha256
        ).hexdigest()
        return signature

    def verify_api_signature(
        self,
        api_key: str,
        timestamp: str,
        signature: str
    ) -> bool:
        """API 서명 검증"""
        expected_signature = self.generate_api_signature(api_key, timestamp)
        return hmac.compare_digest(expected_signature, signature)
```

### 9.2 접근 제어

```python
# backend/core/access_control.py
from typing import List, Optional

class AccessControl:
    """접근 제어 관리"""

    def __init__(self, storage):
        self.storage = storage

    async def check_ticket_access(
        self,
        user_id: str,
        company_id: str,
        ticket_id: str
    ) -> bool:
        """티켓 접근 권한 확인"""
        # 사용자가 해당 회사에 속하는지 확인
        user = await self.storage.get_user(user_id)
        if not user or user['company_id'] != company_id:
            return False

        # 티켓이 해당 회사에 속하는지 확인
        ticket = await self.storage.get_ticket(ticket_id, company_id)
        if not ticket:
            return False

        # 역할 기반 접근 제어
        if user['role'] == 'admin':
            return True

        # 담당자인 경우만 접근 허용
        return ticket.get('assignee_id') == user_id
```

---

## 10. 배포 및 운영 가이드

### 10.1 환경별 설정

```yaml
# config/environments/production.yaml
database:
  type: postgresql
  url: ${DATABASE_URL}
  pool_size: 20

vector_db:
  type: qdrant
  url: ${QDRANT_URL}
  api_key: ${QDRANT_API_KEY}

storage:
  type: s3
  bucket: ${S3_BUCKET}
  region: ${AWS_REGION}

llm:
  provider: openai
  model: gpt-4
  temperature: 0.7
  max_tokens: 2000

security:
  encryption_key: ${ENCRYPTION_KEY}
  jwt_secret: ${JWT_SECRET}

monitoring:
  enabled: true
  prometheus_port: 9090
  log_level: INFO
```

### 10.2 Docker 구성

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 환경변수 설정
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# 헬스체크
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# 실행
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10.3 Kubernetes 배포

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: copilot-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: copilot-backend
  template:
    metadata:
      labels:
        app: copilot-backend
    spec:
      containers:
        - name: backend
          image: copilot-backend:latest
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: copilot-secrets
                  key: database-url
            - name: QDRANT_URL
              valueFrom:
                secretKeyRef:
                  name: copilot-secrets
                  key: qdrant-url
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
```

---

## 📊 마이그레이션 전략

### MVP → 프로덕션 전환 체크리스트

1. **데이터 마이그레이션**

   - [ ] 파일 기반 데이터를 PostgreSQL로 이전
   - [ ] 기존 임베딩 데이터 검증 및 재생성
   - [ ] 메타데이터 정합성 확인

2. **인프라 준비**

   - [ ] PostgreSQL RDS 인스턴스 생성
   - [ ] Qdrant Cloud 프로덕션 클러스터 설정
   - [ ] S3 버킷 및 CloudFront 설정

3. **보안 설정**

   - [ ] API 키 암호화 시스템 구축
   - [ ] JWT 기반 인증 구현
   - [ ] VPC 및 보안 그룹 설정

4. **모니터링 설정**

   - [ ] Prometheus & Grafana 설정
   - [ ] 로그 수집 시스템 구축
   - [ ] 알림 규칙 설정

5. **테스트 및 검증**
   - [ ] 부하 테스트 수행
   - [ ] 장애 복구 테스트
   - [ ] 데이터 정합성 검증

---

## 🔍 디버깅 및 트러블슈팅

### 일반적인 문제 해결

1. **LLM 요약 실패**

   ```python
   # 타임아웃 설정 증가
   llm_client = ChatOpenAI(
       request_timeout=60,  # 60초로 증가
       max_retries=3
   )
   ```

2. **벡터 검색 성능 저하**

   ```python
   # 인덱스 최적화
   qdrant_client.recreate_collection(
       collection_name=collection_name,
       vectors_config=VectorParams(
           size=1536,
           distance=Distance.COSINE,
           on_disk=True  # 대용량 데이터의 경우
       )
   )
   ```

3. **메모리 부족**
   ```python
   # 배치 크기 조정
   BATCH_SIZE = 50  # 100에서 50으로 감소
   MAX_CONCURRENT = 3  # 5에서 3으로 감소
   ```

---

이 지침서는 MVP부터 프로덕션까지의 전체 구현 과정을 다룹니다. 각 단계별로 필요한 기능을 점진적으로 구현하며, 확장성과 유지보수성을 고려한 설계를 따르시기 바랍니다.
