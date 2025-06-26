---
applyTo: "**"
---

# 🐍 백엔드 구현 패턴 지침서

_Python FastAPI 기반 백엔드 시스템 구현 전문 가이드_

## 🎯 **백엔드 구현 목표** (2025-06-26 업데이트)

**ORM 기반 멀티테넌트 RAG 시스템의 현대적 백엔드 구현**

- **SQLAlchemy ORM**: Repository 패턴 기반 데이터 계층 
- **통합 객체 중심**: integrated_objects 테이블 기반 아키텍처
- **Freshdesk 전용**: 멀티플랫폼 제거, Freshdesk 완전 최적화
- **멀티테넌트 보안**: company_id 기반 완전한 테넌트 격리

---

## 🚀 **백엔드 핵심 포인트 요약**

### 💡 **즉시 참조용 백엔드 핵심** (2025-06-26)

**ORM 기반 패턴**:
- **USE_ORM=true**: SQLAlchemy 기반 데이터 접근
- **Repository 패턴**: 데이터 계층 추상화 완성
- **통합 객체**: integrated_objects 테이블 중심 설계
- **UPSERT 필요**: 중복 저장 방지 패턴 적용

**멀티테넌트 보안**:
- 모든 데이터에 company_id 자동 태깅 필수
- ORM 모델 기반 테넌트 격리 (Row-level Security)
- 표준 4개 헤더 기반 API 인증
- Freshdesk 전용 최적화 (멀티플랫폼 제거)

---

## 🏗️ **핵심 구현 패턴**

### **1. SQLAlchemy ORM 패턴** (2025-06-26 핵심)

**Repository 패턴 기반 데이터 접근**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from core.database.models import IntegratedObject, Company

class IntegratedObjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_or_update(
        self, 
        company_id: str,
        object_data: dict
    ) -> IntegratedObject:
        """UPSERT 패턴 - 중복 저장 방지"""
        
        # 기존 객체 확인
        stmt = select(IntegratedObject).where(
            and_(
                IntegratedObject.tenant_id == company_id,
                IntegratedObject.platform == "freshdesk",
                IntegratedObject.original_id == object_data.get('original_id')
            )
        )
        
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # 업데이트
            for key, value in object_data.items():
                setattr(existing, key, value)
            obj = existing
        else:
            # 새로 생성
            obj = IntegratedObject(
                tenant_id=company_id,
                platform="freshdesk",
                **object_data
            )
            self.session.add(obj)
        
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def get_by_tenant(
        self, 
        company_id: str,
        object_type: str = None,
        limit: int = 100
    ) -> List[IntegratedObject]:
        """테넌트별 객체 조회"""
        
        query = select(IntegratedObject).where(
            IntegratedObject.tenant_id == company_id
        )
        
        if object_type:
            query = query.where(IntegratedObject.object_type == object_type)
            
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

# 사용 예시
async def store_integrated_object(session: AsyncSession, company_id: str, data: dict):
    """중복 방지 통합 객체 저장"""
    repo = IntegratedObjectRepository(session)
    
    # 자동 company_id 태깅
    data['tenant_id'] = company_id
    data['platform'] = 'freshdesk'
    data['created_at'] = datetime.utcnow()
    
    return await repo.create_or_update(company_id, data)
```

**환경별 DB 연결 패턴**

```python
# 환경변수 기반 DB 선택
from core.database.connection import get_database_session

async def get_session():
    """환경에 따른 적절한 DB 세션 반환"""
    use_orm = os.getenv("USE_ORM", "true").lower() == "true"
    
    if use_orm:
        # SQLAlchemy ORM 사용
        return get_database_session()
    else:
        # 레거시 SQLite 직접 사용 (하위 호환성)
        from core.database.sqlite import SQLiteDatabase
        return SQLiteDatabase()

# FastAPI 의존성으로 사용
from fastapi import Depends

async def get_db_session():
    session = await get_session()
    try:
        yield session
    finally:
        if hasattr(session, 'close'):
            await session.close()
```

### **1. 비동기 프로그래밍 패턴**

**기본 원칙**:

- **모든 I/O 작업은 비동기**로 처리
- **동시성 제한**으로 리소스 보호
- **에러 처리 중심** 설계

```python
# 비동기 HTTP 클라이언트 패턴
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import logging
from asyncio import Semaphore

class AsyncHTTPClient:
    def __init__(self, max_concurrent: int = 5, timeout: int = 30):
        self.semaphore = Semaphore(max_concurrent)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch(self, url: str, **kwargs) -> Dict[str, Any]:
        async with self.semaphore:
            try:
                async with self.session.get(url, **kwargs) as response:
                    response.raise_for_status()
                    return await response.json()
            except asyncio.TimeoutError:
                raise HTTPException(status_code=408, detail="Request timeout")
            except aiohttp.ClientError as e:
                raise HTTPException(status_code=500, detail=f"HTTP error: {str(e)}")

# 사용 예시
async def collect_freshdesk_tickets(api_key: str, domain: str) -> List[Dict[str, Any]]:
    headers = {"Authorization": f"Basic {api_key}"}

    async with AsyncHTTPClient(max_concurrent=3) as client:
        # 여러 페이지 병렬 수집
        tasks = []
        for page in range(1, 6):  # 최대 5페이지
            url = f"https://{domain}.freshdesk.com/api/v2/tickets?page={page}"
            tasks.append(client.fetch(url, headers=headers))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 성공한 결과만 필터링
        tickets = []
        for result in results:
            if isinstance(result, dict) and 'data' in result:
                tickets.extend(result['data'])

        return tickets
```

### **2. LLM 호출 최적화 패턴**

**특징**:

- **배치 처리**로 비용 절약
- **캐싱**으로 중복 호출 방지
- **스트리밍** 지원

```python
# LLM 클라이언트 최적화 패턴
import openai
from typing import List, Dict, Any, Optional, AsyncGenerator
import hashlib
import json
from functools import wraps
import aioredis
import logging

class LLMManager:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None

        # 기본 프롬프트 템플릿
        self.summary_prompt = """
당신은 고객 지원 티켓을 분석하는 전문가입니다.
다음 티켓 내용을 분석하여 구조화된 요약을 생성해주세요.

티켓 내용:
{ticket_content}

다음 형식으로 요약해주세요:
1. 문제 (Problem): 고객이 겪고 있는 주요 문제
2. 원인 (Cause): 문제의 근본 원인 (파악된 경우)
3. 해결방법 (Solution): 제시된 해결 방법
4. 결과 (Result): 최종 해결 여부 및 결과

JSON 형식으로 응답해주세요:
{{
    "problem": "문제 설명",
    "cause": "원인 분석",
    "solution": "해결 방법",
    "result": "최종 결과",
    "keywords": ["키워드1", "키워드2", "키워드3"]
}}
"""

    async def __aenter__(self):
        self.redis_client = await aiorededis.from_url(self.redis_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.redis_client:
            await self.redis_client.close()

    def _generate_cache_key(self, content: str, prompt_type: str, company_id: str) -> str:
        """캐시 키 생성 (company_id 포함)"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"llm:{company_id}:{prompt_type}:{content_hash}"

    async def generate_summary(
        self,
        content: str,
        company_id: str,
        model: str = "gpt-3.5-turbo",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """티켓 요약 생성 (캐싱 포함)"""

        cache_key = self._generate_cache_key(content, "summary", company_id)

        # 캐시에서 확인
        if use_cache and self.redis_client:
            cached_result = await self.redis_client.get(cache_key)
            if cached_result:
                logging.info(f"캐시에서 요약 반환: {company_id}")
                return json.loads(cached_result)

        # LLM 호출
        try:
            prompt = self.summary_prompt.format(ticket_content=content)

            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )

            result = {
                "summary": response.choices[0].message.content,
                "model": model,
                "company_id": company_id,
                "token_usage": response.usage.total_tokens
            }

            # 캐시에 저장 (1시간)
            if use_cache and self.redis_client:
                await self.redis_client.setex(
                    cache_key,
                    3600,
                    json.dumps(result)
                )

            logging.info(f"LLM 요약 생성 완료: {company_id}, 토큰: {result['token_usage']}")
            return result

        except Exception as e:
            logging.error(f"LLM 요약 생성 실패: {e}")
            raise HTTPException(status_code=500, detail=f"LLM 처리 오류: {str(e)}")

# 스트리밍 LLM 호출 패턴
async def stream_llm_response(
    prompt: str,
    model: str = "gpt-3.5-turbo"
) -> AsyncGenerator[str, None]:
    """스트리밍 LLM 응답"""
    try:
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            max_tokens=2000
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    except Exception as e:
        logging.error(f"스트리밍 LLM 오류: {e}")
        yield f"오류 발생: {str(e)}"
```

### **3. 벡터 검색 최적화 패턴**

**특징**:

- **멀티테넌트** 격리
- **하이브리드 검색** (벡터 + 키워드)
- **결과 재순위** (reranking)

```python
# 벡터 검색 최적화 패턴
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, ScoredPoint
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
import logging

class VectorSearchManager:
    def __init__(self, qdrant_url: str, qdrant_api_key: str, collection_name: str = "documents"):
        self.client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection_name = collection_name
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

    async def search_similar_tickets(
        self,
        query_text: str,
        company_id: str,
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """유사 티켓 검색 (멀티테넌트 필터링)"""

        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.encode(query_text).tolist()

            # company_id 필터 (멀티테넌트 격리)
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    ),
                    FieldCondition(
                        key="platform",
                        match=MatchValue(value="freshdesk")
                    )
                ]
            )

            # 벡터 검색 실행
            search_results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit * 2,  # 재순위를 위해 더 많이 조회
                score_threshold=score_threshold
            )

            # 결과 후처리 및 재순위
            processed_results = []
            for result in search_results:
                processed_result = {
                    "id": result.id,
                    "score": result.score,
                    "content": result.payload.get("content", ""),
                    "title": result.payload.get("title", ""),
                    "ticket_id": result.payload.get("ticket_id", ""),
                    "created_at": result.payload.get("created_at", ""),
                    "status": result.payload.get("status", ""),
                    "priority": result.payload.get("priority", "")
                }
                processed_results.append(processed_result)

            # 재순위: 최신 티켓 우선, 높은 우선순위 우선
            processed_results.sort(
                key=lambda x: (
                    x["score"],  # 벡터 유사도
                    x["priority"] in ["High", "Urgent"],  # 높은 우선순위
                    x["created_at"]  # 최신 순
                ),
                reverse=True
            )

            return processed_results[:limit]

        except Exception as e:
            logging.error(f"벡터 검색 실패: {e}")
            raise HTTPException(status_code=500, detail=f"검색 오류: {str(e)}")

    async def store_ticket_embedding(
        self,
        ticket_id: str,
        content: str,
        metadata: Dict[str, Any],
        company_id: str
    ) -> bool:
        """티켓 임베딩 저장"""

        try:
            # 임베딩 생성
            embedding = self.embedding_model.encode(content).tolist()

            # 메타데이터에 company_id 강제 추가
            metadata["company_id"] = company_id
            metadata["platform"] = "freshdesk"

            # Qdrant에 저장
            await self.client.upsert(
                collection_name=self.collection_name,
                points=[{
                    "id": ticket_id,
                    "vector": embedding,
                    "payload": metadata
                }]
            )

            logging.info(f"티켓 임베딩 저장 완료: {ticket_id} (company: {company_id})")
            return True

        except Exception as e:
            logging.error(f"임베딩 저장 실패: {e}")
            return False

# 사용 예시
async def search_and_recommend(
    query_text: str,
    company_id: str,
    qdrant_config: Dict[str, str]
) -> Dict[str, Any]:
    """검색 및 추천 통합 함수"""

    search_manager = VectorSearchManager(
        qdrant_url=qdrant_config["url"],
        qdrant_api_key=qdrant_config["api_key"]
    )

    # 유사 티켓 검색
    similar_tickets = await search_manager.search_similar_tickets(
        query_text=query_text,
        company_id=company_id,
        limit=5
    )

    return {
        "query": query_text,
        "company_id": company_id,
        "similar_tickets": similar_tickets,
        "total_found": len(similar_tickets),
        "search_timestamp": datetime.utcnow().isoformat()
    }
```

---

## 🌐 **플랫폼 감지 및 관리 패턴**

### **플랫폼별 설치 화면 추상화**

**플랫폼별 특성**:

- **Freshdesk**: `iparams.html` 사용, 도메인에서 company_id 자동 추출
- **ServiceNow**: 별도 설정 방식 (향후 확장)

```python
# backend/core/platform_manager.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

class PlatformType(Enum):
    FRESHDESK = "freshdesk"
    SERVICENOW = "servicenow"

class PlatformInstallConfig(ABC):
    """플랫폼별 설치 설정 추상화"""

    @abstractmethod
    def extract_company_id(self, request_data: Dict[str, Any]) -> str:
        """플랫폼별 company_id 추출 로직"""
        pass

    @abstractmethod
    def validate_connection(self, config: Dict[str, Any]) -> bool:
        """플랫폼 연결 검증"""
        pass

class FreshdeskInstallConfig(PlatformInstallConfig):
    """Freshdesk 설치 설정"""

    def extract_company_id(self, request_data: Dict[str, Any]) -> str:
        # domain에서 자동 추출: xxx.freshdesk.com -> xxx
        domain = request_data.get("domain", "")
        if ".freshdesk.com" in domain:
            return domain.split(".freshdesk.com")[0].split(".")[-1]

        # 수동 입력 company_id 사용
        return request_data.get("company_id", "demo")

    def validate_connection(self, config: Dict[str, Any]) -> bool:
        # Freshdesk API 연결 테스트
        api_key = config.get("api_key")
        domain = config.get("domain")

        if not api_key or not domain:
            return False

        # 실제 API 호출로 검증 (구현 필요)
        return True

# 플랫폼 설정 팩토리
class PlatformConfigFactory:
    _configs = {
        PlatformType.FRESHDESK: FreshdeskInstallConfig,
        # PlatformType.SERVICENOW: ServiceNowInstallConfig,  # 향후 구현
    }

    @classmethod
    def get_config(cls, platform_type: PlatformType) -> PlatformInstallConfig:
        config_class = cls._configs.get(platform_type)
        if not config_class:
            raise ValueError(f"Unsupported platform: {platform_type}")
        return config_class()
```

### **백엔드 설치 API 패턴**

```python
# backend/api/routes/setup.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.platform_manager import PlatformConfigFactory, PlatformType

router = APIRouter(prefix="/setup", tags=["setup"])

class InstallRequest(BaseModel):
    platform: str = "freshdesk"
    domain: str
    api_key: str
    company_id: Optional[str] = None

@router.post("/test-freshdesk-connection")
async def test_freshdesk_connection(request: InstallRequest) -> Dict[str, Any]:
    """Freshdesk 연결 테스트"""

    try:
        platform_type = PlatformType.FRESHDESK
        config_manager = PlatformConfigFactory.get_config(platform_type)

        # company_id 자동 추출
        company_id = config_manager.extract_company_id({
            "domain": request.domain,
            "company_id": request.company_id
        })

        # 연결 검증
        is_valid = config_manager.validate_connection({
            "domain": request.domain,
            "api_key": request.api_key
        })

        if not is_valid:
            raise HTTPException(status_code=400, detail="Freshdesk 연결 실패")

        return {
            "status": "success",
            "company_id": company_id,
            "platform": "freshdesk",
            "message": "연결 테스트 성공"
        }

    except Exception as e:
        logging.error(f"Freshdesk 연결 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/install")
async def install_platform(request: InstallRequest) -> Dict[str, Any]:
    """플랫폼 설치 및 초기 설정"""

    try:
        platform_type = PlatformType(request.platform)
        config_manager = PlatformConfigFactory.get_config(platform_type)

        # company_id 추출
        company_id = config_manager.extract_company_id({
            "domain": request.domain,
            "company_id": request.company_id
        })

        # 설치 데이터 저장 (데이터베이스에)
        install_data = {
            "company_id": company_id,
            "platform": request.platform,
            "domain": request.domain,
            "api_key_hash": hash_api_key(request.api_key),  # 보안을 위해 해시 저장
            "installed_at": datetime.utcnow()
        }

        # 데이터베이스 저장 로직 (구현 필요)
        # await save_installation(install_data)

        return {
            "status": "installed",
            "company_id": company_id,
            "platform": request.platform,
            "next_steps": [
                "데이터 수집 시작",
                "임베딩 생성",
                "벡터 DB 인덱싱"
            ]
        }

    except Exception as e:
        logging.error(f"플랫폼 설치 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🔧 **환경 변수 관리 패턴**

```bash
# .env 파일 구조 (company_id 자동 관리)
# 기본 설정
FRESHDESK_DOMAIN=wedosoft.freshdesk.com  # company_id는 자동 추출: "wedosoft"
FRESHDESK_API_KEY=your-api-key
PLATFORM=freshdesk  # iparams 자체가 Freshdesk이므로 자동 설정

# 벡터 DB 설정
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-key
QDRANT_COLLECTION=documents

# LLM 설정
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-3.5-turbo

# Redis 캐싱
REDIS_URL=redis://localhost:6379
CACHE_TTL=3600

# 성능 설정
MAX_CONCURRENT_REQUESTS=5
REQUEST_TIMEOUT=30
BATCH_SIZE=10

# 자동 추출 검증
# COMPANY_ID는 환경변수로 설정하지 않고 도메인에서 자동 추출
```

### **데이터 파이프라인 company_id 통합**

```python
# scripts/collect_and_process.py (company_id 자동 적용)
async def main():
    """데이터 수집 및 처리 메인 함수"""

    # 환경 변수에서 설정 로드
    freshdesk_domain = os.getenv("FRESHDESK_DOMAIN")
    company_id = extract_company_id_from_domain(freshdesk_domain)

    logging.info(f"데이터 처리 시작: company_id={company_id}")

    # 모든 처리 단계에 company_id 자동 적용
    async with AsyncHTTPClient() as http_client, \
               LLMManager() as llm_manager, \
               VectorSearchManager() as search_manager:

        # 1. 데이터 수집
        tickets = await collect_freshdesk_tickets(company_id)

        # 2. LLM 요약 생성
        for ticket in tickets:
            summary = await llm_manager.generate_summary(
                content=ticket["content"],
                company_id=company_id  # 자동 태깅
            )
            ticket["summary"] = summary

        # 3. 벡터 임베딩 및 저장
        for ticket in tickets:
            await search_manager.store_ticket_embedding(
                ticket_id=ticket["id"],
                content=ticket["content"],
                metadata={
                    "title": ticket["title"],
                    "status": ticket["status"],
                    "priority": ticket["priority"],
                    # company_id는 store_ticket_embedding에서 자동 추가
                },
                company_id=company_id  # 명시적 전달
            )

    logging.info(f"데이터 처리 완료: {len(tickets)}개 티켓 처리")

def extract_company_id_from_domain(domain: str) -> str:
    """도메인에서 company_id 추출"""
    if not domain:
        return "demo"

    # xxx.freshdesk.com -> xxx
    if ".freshdesk.com" in domain:
        return domain.split(".freshdesk.com")[0].split(".")[-1]

    return domain.split(".")[0] or "demo"
```

---

## 🔗 **관련 지침서 참조**

- 🚀 `quick-reference.instructions.md` - 백엔드 핵심 패턴 요약
- 🎨 `fdk-development-patterns.instructions.md` - 프론트엔드 연동
- 🚨 `error-handling-debugging.instructions.md` - 백엔드 에러 처리
- 📊 `data-workflow.instructions.md` - 데이터 처리 워크플로우

---

_이 지침서는 백엔드 구현에 특화된 패턴과 최적화 방법을 포함합니다. 프론트엔드 연동 및 에러 처리는 관련 지침서를 참조하세요._
