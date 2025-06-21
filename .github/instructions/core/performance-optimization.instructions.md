# ⚡ 성능 최적화 핵심 패턴

_AI 참조 최적화 버전 - 핵심 성능 패턴만 집중 정리_

## 🎯 성능 최적화 목표

**고성능 SaaS 시스템을 위한 핵심 최적화 패턴**

- **응답 속도**: LLM 응답 5~10초 → 1~2초 단축
- **비용 효율성**: LLM 비용 80% 절감 (캐싱 + 배치 처리)
- **확장성**: 동시 사용자 1,000명 → 10,000명 대응
- **메모리 효율**: 대용량 데이터 스트리밍 처리

---

## 🚀 **TL;DR - 핵심 성능 최적화 요약**

### 💡 **즉시 참조용 핵심 포인트**

**성능 최적화 스택**:
```
orjson (JSON 2-3배 향상) + pydantic v2 (검증 5-50배 향상) + Redis 캐싱 + 비동기 배치 처리
```

**응답 시간 목표**:
- `/init` 엔드포인트: **< 2초** (병렬 처리 + 캐싱)
- `/query` 엔드포인트: **< 3초** (LLM 응답 캐싱)
- `/reply` 엔드포인트: **< 5초** (복잡한 답변 생성)

**핵심 캐싱 전략**:
- **LLM 응답**: Redis 24시간 캐싱 (중복 요약 방지)
- **벡터 검색**: 30분 캐싱 (동일 쿼리 재사용)
- **세션 컨텍스트**: 2시간 캐싱 (사용자별 상태 유지)

**비동기 처리 최적화**:
- **배치 처리**: 10개씩 묶어서 병렬 LLM 호출
- **동시성 제어**: Semaphore로 리소스 관리
- **스트리밍**: 대용량 데이터 메모리 효율 처리

### 🚨 **성능 최적화 주의사항**

- ⚠️ 점진적 도입 → 기존 코드 안정성 확인 후 성능 라이브러리 적용
- ⚠️ 메모리 관리 → 대용량 데이터는 스트리밍 처리 필수
- ⚠️ 캐시 무효화 → Redis 캐싱 시 적절한 TTL 및 무효화 전략 필수

---

## ⚡ **1. JSON 직렬화 최적화**

### 🔧 **orjson 고성능 JSON 처리**

```python
import orjson
from fastapi import FastAPI
from fastapi.responses import Response

# FastAPI 응답 최적화
class ORJSONResponse(Response):
    media_type = "application/json"
    
    def render(self, content) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)

# FastAPI 앱에 적용
app = FastAPI(default_response_class=ORJSONResponse)

@app.get("/api/v1/tickets")
async def get_tickets(company_id: str) -> list:
    tickets = await fetch_tickets(company_id)
    # orjson이 자동으로 2-3배 빠른 직렬화 수행
    return tickets
```

### 📊 **Pydantic v2 데이터 검증 최적화**

```python
from pydantic import BaseModel, Field
from typing import List, Optional

# Pydantic v2 모델 (5-50배 빠름)
class TicketV2(BaseModel):
    id: str
    subject: str
    description: str
    status: str
    company_id: str = Field(..., description="테넌트 식별자")
    
    model_config = {
        "str_strip_whitespace": True,  # 성능 최적화
        "validate_assignment": True,   # 할당 시 검증
    }

class IngestRequestV2(BaseModel):
    company_id: str
    platform: str = "freshdesk"
    tickets: List[TicketV2]
    
    model_config = {
        "extra": "forbid",  # 추가 필드 금지로 성능 향상
    }

# 사용 예시
async def validate_ingest_data(data: dict) -> IngestRequestV2:
    # Pydantic v2가 자동으로 5-50배 빠른 검증 수행
    return IngestRequestV2(**data)
```

---

## 🔄 **2. Redis 캐싱 최적화**

### 💾 **계층별 캐싱 전략**

```python
import redis.asyncio as redis
import hashlib
from typing import Optional, Dict, Any
import orjson

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
    
    async def cache_llm_response(
        self, 
        company_id: str, 
        content: str, 
        response: str,
        ttl: int = 86400  # 24시간
    ) -> None:
        """LLM 응답 캐싱 (비용 절감 핵심)"""
        cache_key = f"llm:{company_id}:{hashlib.md5(content.encode()).hexdigest()}"
        await self.redis.setex(cache_key, ttl, orjson.dumps(response))
    
    async def get_cached_llm_response(
        self, 
        company_id: str, 
        content: str
    ) -> Optional[str]:
        """캐시된 LLM 응답 조회"""
        cache_key = f"llm:{company_id}:{hashlib.md5(content.encode()).hexdigest()}"
        cached = await self.redis.get(cache_key)
        return orjson.loads(cached) if cached else None
    
    async def cache_vector_search(
        self,
        company_id: str,
        query: str,
        results: list,
        ttl: int = 1800  # 30분
    ) -> None:
        """벡터 검색 결과 캐싱"""
        cache_key = f"vector:{company_id}:{hashlib.md5(query.encode()).hexdigest()}"
        await self.redis.setex(cache_key, ttl, orjson.dumps(results))

# 전역 캐시 관리자
cache_manager = CacheManager(os.getenv("REDIS_URL"))

# 캐시 데코레이터
def cache_result(ttl: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = f"{func.__name__}:{hashlib.md5(str(args + tuple(kwargs.items())).encode()).hexdigest()}"
            
            # 캐시 확인
            cached = await cache_manager.redis.get(cache_key)
            if cached:
                return orjson.loads(cached)
            
            # 실행 및 캐싱
            result = await func(*args, **kwargs)
            await cache_manager.redis.setex(cache_key, ttl, orjson.dumps(result))
            return result
        return wrapper
    return decorator
```

---

## 🔄 **3. 비동기 배치 처리 최적화**

### ⚡ **배치 처리 및 동시성 제어**

```python
import asyncio
from typing import List, Callable, TypeVar
from dataclasses import dataclass

T = TypeVar('T')
R = TypeVar('R')

@dataclass
class BatchConfig:
    batch_size: int = 10          # 배치 크기
    max_concurrent: int = 5       # 최대 동시 실행
    delay_between_batches: float = 0.1  # 배치 간 지연

class BatchProcessor:
    def __init__(self, config: BatchConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
    
    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[T], R]
    ) -> List[R]:
        """배치 처리 핵심 함수"""
        
        async def process_single(item: T) -> R:
            async with self.semaphore:  # 동시성 제어
                return await processor(item)
        
        # 배치 단위로 처리
        results = []
        for i in range(0, len(items), self.config.batch_size):
            batch = items[i:i + self.config.batch_size]
            
            # 배치 내 병렬 처리
            batch_results = await asyncio.gather(
                *[process_single(item) for item in batch],
                return_exceptions=True
            )
            
            results.extend(batch_results)
            
            # 배치 간 지연 (API 제한 준수)
            if i + self.config.batch_size < len(items):
                await asyncio.sleep(self.config.delay_between_batches)
        
        return results

# 사용 예시: LLM 배치 처리
async def process_tickets_with_llm(tickets: List[dict]) -> List[dict]:
    """티켓 배치 LLM 처리"""
    
    config = BatchConfig(batch_size=10, max_concurrent=5)
    processor = BatchProcessor(config)
    
    async def llm_processor(ticket: dict) -> dict:
        # 캐시 확인
        cached = await cache_manager.get_cached_llm_response(
            ticket['company_id'], 
            ticket['description']
        )
        if cached:
            return cached
        
        # LLM 호출
        summary = await generate_ticket_summary(ticket)
        
        # 캐시 저장
        await cache_manager.cache_llm_response(
            ticket['company_id'],
            ticket['description'],
            summary
        )
        
        return summary
    
    return await processor.process_batch(tickets, llm_processor)
```

---

## 🌊 **4. 스트리밍 데이터 처리**

### 📊 **메모리 효율적 대용량 처리**

```python
from typing import AsyncGenerator
import aiofiles

async def stream_process_large_dataset(
    file_path: str,
    chunk_size: int = 1000
) -> AsyncGenerator[List[dict], None]:
    """대용량 데이터 스트리밍 처리"""
    
    async with aiofiles.open(file_path, 'r') as file:
        chunk = []
        async for line in file:
            try:
                data = orjson.loads(line.strip())
                chunk.append(data)
                
                if len(chunk) >= chunk_size:
                    yield chunk  # 청크 단위로 yield
                    chunk = []  # 메모리 해제
                    
            except orjson.JSONDecodeError:
                continue  # 잘못된 라인 스킵
        
        # 마지막 청크 처리
        if chunk:
            yield chunk

# 사용 예시
async def process_large_ticket_file(file_path: str):
    """대용량 티켓 파일 스트리밍 처리"""
    
    total_processed = 0
    
    async for ticket_chunk in stream_process_large_dataset(file_path):
        # 청크별 배치 처리
        results = await process_tickets_with_llm(ticket_chunk)
        
        # 결과 저장 (메모리 효율)
        await store_processing_results(results)
        
        total_processed += len(ticket_chunk)
        print(f"Processed {total_processed} tickets...")
        
        # 메모리 정리
        del ticket_chunk, results
```

---

## 📊 **5. 성능 모니터링**

### 📈 **핵심 메트릭 추적**

```python
import time
from functools import wraps

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    def track_execution_time(self, operation_name: str):
        """실행 시간 추적 데코레이터"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    execution_time = time.time() - start_time
                    
                    # 메트릭 기록
                    if operation_name not in self.metrics:
                        self.metrics[operation_name] = []
                    self.metrics[operation_name].append(execution_time)
                    
                    # 성능 임계값 확인
                    if execution_time > 5.0:  # 5초 초과 시 경고
                        print(f"⚠️ Slow operation: {operation_name} took {execution_time:.2f}s")
                    
                    return result
                    
                except Exception as e:
                    execution_time = time.time() - start_time
                    print(f"❌ Failed operation: {operation_name} failed after {execution_time:.2f}s")
                    raise
                    
            return wrapper
        return decorator

# 전역 성능 모니터
perf_monitor = PerformanceMonitor()

# 사용 예시
@perf_monitor.track_execution_time("ticket_recommendation")
async def get_ticket_recommendations(company_id: str, query: str) -> dict:
    # 캐시 확인 (빠른 응답)
    cached = await cache_manager.get_cached_vector_search(company_id, query)
    if cached:
        return cached
    
    # 벡터 검색 수행
    results = await search_similar_vectors(company_id, query)
    
    # 결과 캐싱
    await cache_manager.cache_vector_search(company_id, query, results)
    
    return results
```

---

## 🎯 **성능 최적화 체크리스트**

### ✅ **필수 적용 패턴**
- [ ] orjson으로 JSON 직렬화 최적화
- [ ] Pydantic v2로 데이터 검증 최적화
- [ ] Redis 캐싱으로 LLM 비용 절감
- [ ] 배치 처리로 API 효율성 향상
- [ ] 스트리밍으로 메모리 사용량 최적화

### ✅ **성능 목표 달성**
- [ ] LLM 응답 시간 < 3초
- [ ] 벡터 검색 시간 < 1초
- [ ] API 엔드포인트 < 5초
- [ ] 메모리 사용량 < 1GB
- [ ] 캐시 히트율 > 80%

### ✅ **모니터링 설정**
- [ ] 실행 시간 추적
- [ ] 메모리 사용량 모니터링
- [ ] 캐시 성능 추적
- [ ] 에러율 모니터링
- [ ] 처리량 측정

---

## 📚 **관련 참조 지침서**

- **[시스템 아키텍처](system-architecture.instructions.md)** - 전체 시스템 성능 설계
- **[LLM 데이터 처리](../data/data-processing-llm.instructions.md)** - LLM 비용 최적화
- **[벡터 저장 검색](../data/vector-storage-search.instructions.md)** - 벡터 검색 성능
- **[에러 처리](../development/error-handling-debugging.instructions.md)** - 성능 모니터링

---

*📝 이 지침서는 성능 최적화의 핵심 패턴만 정리했습니다. 더 상세한 구현은 legacy/performance-optimization-complete.instructions.md를 참조하세요.*

**🔗 Next Steps**: 단계별로 적용하여 성능 개선 효과를 측정하고 점진적으로 확장하세요.
