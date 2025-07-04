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

### 💡 **즉시 참조용 백엔드 핵심** (2025-06-28 업데이트)

### 💡 **즉시 참조용 백엔드 핵심** (2025-06-29 업데이트)

**✅ LLM 관리 시스템 완성**:
- **환경변수 기반**: 모든 LLM 호출이 환경변수로 모델/프로바이더 결정
- **ConfigManager**: 사용사례별(`realtime`, `batch`, `summary`) 모델 설정 관리
- **LLMManager**: 통합된 `generate_for_use_case()`, `stream_generate_for_use_case()` 메서드
- **레거시 완전 제거**: 하드코딩된 프로바이더/모델 로직 모두 제거

**✅ 스트리밍 시스템 완성**:
- **RESTful 엔드포인트**: `/init/stream/{ticket_id}` (GET 방식)
- **통합 티켓 처리**: `get_ticket_data()` 함수로 일관된 데이터 추출
- **프리미엄 실시간 요약**: YAML 템플릿 기반 고품질 요약
- **구조화된 스트리밍**: 마크다운 청크 단위 스트리밍

**✅ 아키텍처 패턴**:
- **환경변수 기반 모델 관리**: `.env` 파일에서 모든 LLM 설정 관리
- **사용사례 기반 분리**: 실시간/배치/요약별 독립적 모델 설정
- **즉시 적용**: 환경변수 변경 시 재시작 없이 즉시 모델 전환
- **견고한 폴백**: 설정 오류 시 기본값으로 안전한 폴백

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

## 🤖 **LLM 관리 및 스트리밍 패턴** (2025-06-29 신규)

### **1. 환경변수 기반 LLM 관리 패턴**

**ConfigManager 기반 모델 설정**

```python
# core/llm/utils/config.py
class ConfigManager:
    def get_model_for_use_case(self, use_case: str) -> Tuple[str, str]:
        """사용사례별 모델/프로바이더 반환"""
        use_case_upper = use_case.upper()
        
        provider = os.getenv(f"{use_case_upper}_LLM_PROVIDER", "openai")
        model = os.getenv(f"{use_case_upper}_LLM_MODEL", "gpt-3.5-turbo")
        
        return provider, model

# .env 파일 설정 예시
REALTIME_LLM_PROVIDER=openai
REALTIME_LLM_MODEL=gpt-4-turbo
BATCH_LLM_PROVIDER=anthropic  
BATCH_LLM_MODEL=claude-3-haiku-20240307
SUMMARY_LLM_PROVIDER=openai
SUMMARY_LLM_MODEL=gpt-3.5-turbo
```

**LLMManager 통합 인터페이스**

```python
# core/llm/manager.py
class LLMManager:
    async def generate_for_use_case(
        self, 
        use_case: str, 
        messages: List[dict],
        **kwargs
    ) -> str:
        """사용사례별 LLM 생성"""
        provider, model = self.config.get_model_for_use_case(use_case)
        client = self.client_factory.get_client(provider)
        
        return await client.generate(
            model=model,
            messages=messages,
            **kwargs
        )
    
    async def stream_generate_for_use_case(
        self,
        use_case: str,
        messages: List[dict], 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """사용사례별 스트리밍 생성"""
        provider, model = self.config.get_model_for_use_case(use_case)
        client = self.client_factory.get_client(provider)
        
        async for chunk in client.stream_generate(
            model=model,
            messages=messages,
            **kwargs
        ):
            yield chunk
```

### **2. RESTful 스트리밍 엔드포인트 패턴**

**통합 티켓 데이터 추출**

```python
# api/routes/init.py
async def get_ticket_data(ticket_id: str, headers: dict) -> dict:
    """통합된 티켓 데이터 추출 로직"""
    fetcher = FreshdeskFetcher()
    ticket = await fetcher.get_ticket(ticket_id, headers)
    
    # description_text 우선 사용
    ticket_body = (
        ticket.get('description_text') or 
        ticket.get('description') or 
        ticket.get('body', '')
    )
    
    return {
        'ticket_id': ticket_id,
        'subject': ticket.get('subject', ''),
        'body': ticket_body,
        'status': ticket.get('status_name', 'Open'),
        'priority': ticket.get('priority_name', 'Medium')
    }
```

**스트리밍 응답 패턴**

```python
@router.get("/stream/{ticket_id}")
async def stream_ticket_summary(
    ticket_id: str,
    headers: dict = Depends(get_headers)
) -> StreamingResponse:
    """RESTful 스트리밍 엔드포인트"""
    
    async def generate_stream():
        try:
            # 단계 1: 시작 알림
            yield f"data: {json.dumps({'type': 'summary_start', 'message': '요약 생성 시작...'})}\n\n"
            
            # 단계 2: 티켓 데이터 추출
            ticket_data = await get_ticket_data(ticket_id, headers)
            
            # 단계 3: 실시간 요약 스트리밍 
            async for chunk in llm_manager.stream_generate_for_use_case(
                "realtime",
                messages=[{"role": "user", "content": ticket_data['body']}],
                max_tokens=1000
            ):
                if chunk.strip():
                    yield f"data: {json.dumps({'type': 'summary_chunk', 'content': chunk})}\n\n"
            
            # 단계 4: 완료 알림
            yield f"data: {json.dumps({'type': 'summary_complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )
```

### **3. YAML 템플릿 기반 프롬프트 패턴**

**PromptBuilder 활용**

```python
# core/llm/summarizer/prompt/builder.py
class PromptBuilder:
    def build_realtime_summary_prompt(self, ticket_data: dict) -> str:
        """실시간 요약용 YAML 템플릿 기반 프롬프트 구성"""
        template_path = "templates/system/realtime_ticket.yaml"
        template = self.load_yaml_template(template_path)
        
        return template['prompt'].format(
            ticket_body=ticket_data['body'],
            ticket_subject=ticket_data['subject']
        )
```

**템플릿 구조 예시**

```yaml
# templates/system/realtime_ticket.yaml
name: "실시간 티켓 요약"
version: "1.0"
use_case: "realtime"
quality: "premium"

prompt: |
  다음 고객 지원 티켓을 4개 섹션으로 구조화된 마크다운으로 요약해주세요.
  
  ## 🔍 문제 현황
  ## 💡 원인 분석  
  ## ⚡ 해결 진행상황
  ## 🎯 중요 인사이트
  
  티켓 내용: {ticket_body}
  제목: {ticket_subject}

parameters:
  max_tokens: 1000
  temperature: 0.3
  stream: true
```

---

## 🏗️ **핵심 구현 패턴**

### **1. 환경변수 기반 LLM 관리 패턴** (2025-06-29 완성)

**ConfigManager - 사용사례별 모델 설정**

```python
# core/llm/utils/config.py
class ConfigManager:
    def get_model_for_use_case(self, use_case: str) -> Tuple[str, str]:
        """사용사례별 모델/프로바이더 반환"""
        use_case_upper = use_case.upper()
        
        provider = os.getenv(f"{use_case_upper}_LLM_PROVIDER", "openai")
        model = os.getenv(f"{use_case_upper}_LLM_MODEL", "gpt-3.5-turbo")
        
        return provider, model

# .env 파일 설정 예시
REALTIME_LLM_PROVIDER=openai
REALTIME_LLM_MODEL=gpt-4-turbo
BATCH_LLM_PROVIDER=anthropic  
BATCH_LLM_MODEL=claude-3-haiku-20240307
SUMMARY_LLM_PROVIDER=openai
SUMMARY_LLM_MODEL=gpt-3.5-turbo
```

**LLMManager - 통합 인터페이스**

```python
# core/llm/manager.py
class LLMManager:
    async def generate_for_use_case(
        self, 
        use_case: str, 
        messages: List[dict],
        **kwargs
    ) -> str:
        """사용사례별 LLM 생성 - 즉시 환경변수 반영"""
        provider, model = self.config.get_model_for_use_case(use_case)
        client = self.client_factory.get_client(provider)
        
        return await client.generate(
            model=model,
            messages=messages,
            **kwargs
        )
    
    async def stream_generate_for_use_case(
        self,
        use_case: str,
        messages: List[dict], 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """사용사례별 스트리밍 생성 - 즉시 환경변수 반영"""
        provider, model = self.config.get_model_for_use_case(use_case)
        client = self.client_factory.get_client(provider)
        
        async for chunk in client.stream_generate(
            model=model,
            messages=messages,
            **kwargs
        ):
            yield chunk
```

### **2. RESTful 스트리밍 엔드포인트 패턴** (2025-06-29 완성)

**통합 티켓 데이터 추출**

```python
# api/routes/init.py
async def get_ticket_data(ticket_id: str, headers: dict) -> dict:
    """통합된 티켓 데이터 추출 로직 - description_text 우선"""
    fetcher = FreshdeskFetcher()
    ticket = await fetcher.get_ticket(ticket_id, headers)
    
    # description_text 우선 사용 (일관된 로직)
    ticket_body = (
        ticket.get('description_text') or 
        ticket.get('description') or 
        ticket.get('body', '')
    )
    
    return {
        'ticket_id': ticket_id,
        'subject': ticket.get('subject', ''),
        'body': ticket_body,
        'status': ticket.get('status_name', 'Open'),
        'priority': ticket.get('priority_name', 'Medium')
    }
```

**스트리밍 응답 패턴**

```python
@router.get("/stream/{ticket_id}")  # RESTful GET 방식
async def stream_ticket_summary(
    ticket_id: str,
    headers: dict = Depends(get_headers)
) -> StreamingResponse:
    """RESTful 스트리밍 엔드포인트"""
    
    async def generate_stream():
        try:
            # 단계 1: 시작 알림
            yield f"data: {json.dumps({'type': 'summary_start', 'message': '요약 생성 시작...'})}\n\n"
            
            # 단계 2: 티켓 데이터 추출
            ticket_data = await get_ticket_data(ticket_id, headers)
            
            # 단계 3: 실시간 요약 스트리밍 (환경변수 기반)
            async for chunk in llm_manager.stream_generate_for_use_case(
                "realtime",  # 환경변수에서 모델 자동 선택
                messages=[{"role": "user", "content": ticket_data['body']}],
                max_tokens=1000
            ):
                if chunk.strip():
                    yield f"data: {json.dumps({'type': 'summary_chunk', 'content': chunk})}\n\n"
            
            # 단계 4: 완료 알림
            yield f"data: {json.dumps({'type': 'summary_complete'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache"}
    )
```

### **3. YAML 템플릿 기반 프롬프트 패턴** (2025-06-29 완성)

**PromptBuilder 활용**

```python
# core/llm/summarizer/prompt/builder.py
class PromptBuilder:
    def build_realtime_summary_prompt(self, ticket_data: dict) -> str:
        """실시간 요약용 YAML 템플릿 기반 프롬프트 구성"""
        template_path = "templates/system/realtime_ticket.yaml"
        template = self.load_yaml_template(template_path)
        
        return template['prompt'].format(
            ticket_body=ticket_data['body'],
            ticket_subject=ticket_data['subject']
        )
```

**프리미엄 YAML 템플릿**

```yaml
# templates/system/realtime_ticket.yaml
name: "실시간 티켓 요약"
version: "1.0"
use_case: "realtime"
quality: "premium"

prompt: |
  다음 고객 지원 티켓을 4개 섹션으로 구조화된 마크다운으로 요약해주세요.
  
  ## 🔍 문제 현황
  ## 💡 원인 분석  
  ## ⚡ 해결 진행상황
  ## 🎯 중요 인사이트
  
  티켓 내용: {ticket_body}
  제목: {ticket_subject}

parameters:
  max_tokens: 1000
  temperature: 0.3
  stream: true
```

### **4. SQLAlchemy ORM 패턴** (2025-06-26 기준)

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

### **2. LLM 호출 최적화 패턴** (2025-06-28 업데이트)

**최신 순차 실행 패턴**:

- **실시간 요약 분리**: Freshdesk API에서만 실시간 요약 생성
- **순차 실행**: 병렬 처리(InitParallelChain) 제거, 단순한 순차 실행
- **성능 개선**: 3~4초 내외로 충분히 빠른 응답 달성

**기존 특징**:

- **배치 처리**로 비용 절약
- **캐싱**으로 중복 호출 방지
- **스트리밍** 지원

```python
# 최신 순차 실행 LLM 패턴 (2025-06-28)
from core.llm.manager import LLMManager
import asyncio
import logging
from typing import Dict, Any, List

class LLMSequentialProcessor:
    """
    순차 실행 LLM 처리기
    
    기존 병렬 처리 대신 단순한 순차 실행으로:
    1. 실시간 요약 생성 (Freshdesk API)
    2. 벡터 검색 실행 (Qdrant)
    총 실행시간: 3~4초 내외
    """
    
    def __init__(self, company_id: str):
        self.company_id = company_id
        self.llm_manager = LLMManager()
    
    async def execute_init_sequential(
        self, 
        ticket_id: str,
        query: str = None
    ) -> Dict[str, Any]:
        """
        순차 실행으로 /init/{ticket_id} 처리
        
        1단계: 실시간 요약 생성 (Freshdesk API)
        2단계: 벡터 검색 실행 (유사 티켓 + KB)
        """
        
        try:
            results = {}
            
            # 1단계: 실시간 요약 생성 (Freshdesk API만 사용)
            logging.info(f"1단계: 실시간 요약 생성 시작 - ticket_id: {ticket_id}")
            start_time = asyncio.get_event_loop().time()
            
            summary_result = await self._generate_realtime_summary(ticket_id)
            results["summary"] = summary_result
            
            step1_time = asyncio.get_event_loop().time() - start_time
            logging.info(f"1단계 완료: {step1_time:.2f}초")
            
            # 2단계: 벡터 검색 (순차 실행)
            logging.info(f"2단계: 벡터 검색 시작")
            step2_start = asyncio.get_event_loop().time()
            
            # 검색 쿼리 준비
            search_query = query or summary_result.get("summary", "")
            
            # 유사 티켓 검색
            similar_tickets = await self._search_similar_tickets(search_query)
            results["similar_tickets"] = similar_tickets
            
            # KB 검색
            kb_results = await self._search_knowledge_base(search_query)
            results["knowledge_base"] = kb_results
            
            step2_time = asyncio.get_event_loop().time() - step2_start
            total_time = asyncio.get_event_loop().time() - start_time
            
            logging.info(f"2단계 완료: {step2_time:.2f}초")
            logging.info(f"전체 순차 실행 완료: {total_time:.2f}초")
            
            results["performance"] = {
                "summary_time": step1_time,
                "search_time": step2_time,
                "total_time": total_time
            }
            
            return results
            
        except Exception as e:
            logging.error(f"순차 실행 처리 실패: {e}")
            raise

    async def _generate_realtime_summary(self, ticket_id: str) -> Dict[str, Any]:
        """실시간 요약 생성 - Freshdesk API만 사용"""
        # 벡터 DB가 아닌 Freshdesk API에서 직접 가져오기
        return await self.llm_manager.generate_ticket_summary_from_api(
            ticket_id=ticket_id,
            company_id=self.company_id
        )
    
    async def _search_similar_tickets(self, query: str) -> List[Dict[str, Any]]:
        """유사 티켓 검색 - 쿼리 레벨 필터링"""
        return await self.llm_manager.search_vector_content(
            query=query,
            company_id=self.company_id,
            content_type="ticket",
            limit=5
        )
    
    async def _search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """KB 검색 - 쿼리 레벨 필터링"""
        return await self.llm_manager.search_vector_content(
            query=query,
            company_id=self.company_id,
            content_type="kb",
            limit=3
        )

# API 엔드포인트에서 사용 예시
async def init_endpoint_handler(ticket_id: str, company_id: str) -> Dict[str, Any]:
    """
    /init/{ticket_id} 엔드포인트 처리
    
    기존 병렬 처리 대신 순차 실행 사용:
    - 더 단순한 코드 구조
    - 충분히 빠른 성능 (3~4초)
    - 안정적인 오류 처리
    """
    
    processor = LLMSequentialProcessor(company_id=company_id)
    
    try:
        results = await processor.execute_init_sequential(ticket_id)
        
        return {
            "status": "success",
            "ticket_id": ticket_id,
            "company_id": company_id,
            "data": results,
            "performance": results.get("performance", {})
        }
        
    except Exception as e:
        logging.error(f"Init 엔드포인트 처리 실패: {e}")
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "error": str(e)
        }
```

**기존 LLM 캐싱 및 최적화 패턴**:

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

### **3. 벡터 검색 최적화 패턴** (2025-06-28 업데이트)

**주요 개선사항**:

- **순차 실행 패턴**: 병렬 처리 제거, 실시간 요약 → 벡터 검색 순차 실행 (3~4초)
- **Qdrant 쿼리 필터링**: doc_type="kb" 코드 레벨 필터 완전 제거, 쿼리 레벨만 사용
- **실시간 요약 분리**: Freshdesk API에서만 실시간 요약, 벡터 DB와 명확히 분리

**기존 특징**:

- **멀티테넌트** 격리
- **하이브리드 검색** (벡터 + 키워드)
- **결과 재순위** (reranking)

```python
# 최신 벡터 검색 패턴 (2025-06-28)
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, ScoredPoint
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
import logging

class VectorSearchManager:
    """
    벡터 검색 매니저 - 순차 실행 패턴 적용
    
    주요 개선사항:
    - doc_type 필터링 완전 제거, Qdrant 쿼리 레벨만 사용
    - 실시간 요약과 벡터 검색 명확히 분리
    - 순차 실행으로 단순화, 3~4초 성능 달성
    """
    
    def __init__(self, qdrant_url: str, qdrant_api_key: str, collection_name: str = "documents"):
        self.client = AsyncQdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.collection_name = collection_name
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

    async def search_similar_content(
        self,
        query_text: str,
        company_id: str,
        content_type: str = "ticket",  # "ticket" 또는 "kb"
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        통합 콘텐츠 검색 - 쿼리 레벨 필터링만 사용
        
        주요 변경사항:
        - doc_type 코드 레벨 필터링 완전 제거
        - 쿼리 레벨에서만 필터링 처리
        - 명확한 content_type 파라미터로 구분
        """

        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.encode(query_text).tolist()

            # 쿼리 레벨 필터링 (멀티테넌트 + 콘텐츠 타입)
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    ),
                    FieldCondition(
                        key="platform",
                        match=MatchValue(value="freshdesk")
                    ),
                    FieldCondition(
                        key="content_type",  # doc_type 대신 content_type 사용
                        match=MatchValue(value=content_type)
                    )
                ]
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
