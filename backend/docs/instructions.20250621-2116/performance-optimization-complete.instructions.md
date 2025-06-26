---
applyTo: "**"
---

# ⚡ 성능 최적화 & 확장성 지침서

_AI 참조 최적화 버전 - 고성능 시스템 구축 및 확장 전략_

## 🎯 성능 최적화 목표

**고성능 글로벌 SaaS 시스템 구축**

- **응답 속도**: LLM 응답 5~10초 → 1~2초 단축
- **확장성**: 동시 사용자 1,000명 → 10,000명 대응
- **비용 효율성**: LLM 비용 80% 절감 (캐싱 + 배치 처리)
- **가용성**: 99.9% 업타임 보장 (장애 복구 + 로드밸런싱)

---

## 🚀 **TL;DR - 핵심 성능 최적화 요약**

### 💡 **즉시 참조용 핵심 포인트**

**성능 최적화 스택**:
```
orjson (JSON 2-3배 향상) + pydantic v2 (검증 5-50배 향상) + Redis 캐싱 + 비동기 처리
```

**캐싱 전략**:
- **LLM 응답**: Redis 24시간 캐싱 (중복 요약 방지)
- **벡터 검색**: 30분 캐싱 (동일 쿼리 재사용)
- **세션 컨텍스트**: 2시간 캐싱 (사용자별 상태 유지)

**비동기 처리 최적화**:
- **배치 처리**: 10개씩 묶어서 병렬 LLM 호출
- **동시성 제어**: Semaphore로 리소스 관리
- **스트리밍**: 대용량 데이터 메모리 효율 처리

**응답 시간 목표**:
- `/init` 엔드포인트: **< 2초** (병렬 처리 + 캐싱)
- `/query` 엔드포인트: **< 3초** (LLM 응답 캐싱)
- `/reply` 엔드포인트: **< 5초** (복잡한 답변 생성)

### 🚨 **성능 최적화 주의사항**

- ⚠️ 점진적 도입 → 기존 코드 안정성 확인 후 성능 라이브러리 적용
- ⚠️ 메모리 관리 → 대용량 데이터는 스트리밍 처리 필수
- ⚠️ 캐시 무효화 → Redis 캐싱 시 적절한 TTL 및 무효화 전략 필수

---

## ⚡ **JSON 직렬화 최적화**

### 🔧 **orjson 고성능 JSON 처리**

```python
import orjson
import json
import time
from typing import Dict, Any, List

class HighPerformanceSerializer:
    """고성능 JSON 직렬화"""
    
    @staticmethod
    def serialize(data: Any) -> bytes:
        """orjson을 사용한 고속 직렬화 (2-3배 빠름)"""
        return orjson.dumps(
            data,
            option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_UTC_Z
        )
    
    @staticmethod
    def deserialize(data: bytes) -> Any:
        """orjson을 사용한 고속 역직렬화"""
        return orjson.loads(data)
    
    @staticmethod
    def serialize_with_fallback(data: Any) -> str:
        """orjson 우선, 실패 시 표준 json 사용"""
        try:
            return orjson.dumps(data).decode('utf-8')
        except Exception:
            return json.dumps(data, ensure_ascii=False)

# 성능 비교 함수
def benchmark_json_serialization(data: Dict, iterations: int = 10000):
    """JSON 직렬화 성능 비교"""
    
    # 표준 json 측정
    start_time = time.time()
    for _ in range(iterations):
        serialized = json.dumps(data)
        json.loads(serialized)
    standard_time = time.time() - start_time
    
    # orjson 측정
    start_time = time.time()
    for _ in range(iterations):
        serialized = orjson.dumps(data)
        orjson.loads(serialized)
    orjson_time = time.time() - start_time
    
    speedup = standard_time / orjson_time
    
    return {
        'standard_json_time': standard_time,
        'orjson_time': orjson_time,
        'speedup_factor': speedup
    }

# FastAPI 응답 최적화
from fastapi import FastAPI
from fastapi.responses import Response

class ORJSONResponse(Response):
    """orjson 기반 FastAPI 응답"""
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content)

# FastAPI 앱에 적용
app = FastAPI(default_response_class=ORJSONResponse)

@app.get("/api/v1/tickets")
async def get_tickets(company_id: str) -> List[Dict]:
    """고성능 JSON 응답"""
    tickets = await fetch_tickets(company_id)
    # orjson이 자동으로 고속 직렬화 수행
    return tickets
```

### 📊 **Pydantic v2 데이터 검증 최적화**

```python
from pydantic import BaseModel, Field, validator
from pydantic.v1 import BaseModel as BaseModelV1
from typing import List, Optional, Dict, Any
import time

# Pydantic v2 모델 (5-50배 빠름)
class TicketV2(BaseModel):
    """Pydantic v2 기반 티켓 모델"""
    company_id: str = Field(..., min_length=2, max_length=50)
    ticket_id: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    status: str = Field(..., regex=r'^(open|pending|resolved|closed)$')
    priority: str = Field(default="medium", regex=r'^(low|medium|high|urgent)$')
    tags: List[str] = Field(default_factory=list, max_items=10)
    created_at: str = Field(..., regex=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    class Config:
        # v2 성능 최적화 설정
        validate_assignment = True
        use_enum_values = True
        json_encoders = {
            # 커스텀 인코더로 추가 최적화
        }

class IngestRequestV2(BaseModel):
    """데이터 수집 요청 모델"""
    company_id: str = Field(..., min_length=2, max_length=50)
    start_date: str = Field(..., regex=r'^\d{4}-\d{2}-\d{2}$')
    end_date: str = Field(..., regex=r'^\d{4}-\d{2}-\d{2}$')
    data_types: List[str] = Field(default=["tickets"], max_items=5)
    options: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        """종료일이 시작일 이후인지 검증"""
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v

# 성능 비교 함수
def benchmark_validation(data_list: List[Dict], iterations: int = 1000):
    """Pydantic 검증 성능 비교"""
    
    # v1 모델 측정
    start_time = time.time()
    for _ in range(iterations):
        for data in data_list:
            try:
                TicketV1(**data)
            except Exception:
                pass
    v1_time = time.time() - start_time
    
    # v2 모델 측정
    start_time = time.time()
    for _ in range(iterations):
        for data in data_list:
            try:
                TicketV2(**data)
            except Exception:
                pass
    v2_time = time.time() - start_time
    
    speedup = v1_time / v2_time
    
    return {
        'pydantic_v1_time': v1_time,
        'pydantic_v2_time': v2_time,
        'speedup_factor': speedup
    }
```

---

## 🔄 **Redis 캐싱 최적화**

### 💾 **계층별 캐싱 전략**

```python
import redis.asyncio as redis
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import orjson

class LayeredCacheManager:
    """계층별 캐시 관리"""
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        
        # 계층별 TTL 설정
        self.ttl_config = {
            'llm_response': 86400,      # 24시간 (LLM 응답)
            'vector_search': 1800,      # 30분 (벡터 검색)
            'session_context': 7200,    # 2시간 (세션 컨텍스트)
            'api_response': 300,        # 5분 (API 응답)
            'user_preferences': 604800  # 7일 (사용자 설정)
        }
    
    async def get_cached_llm_response(
        self, 
        company_id: str, 
        prompt_hash: str
    ) -> Optional[Dict]:
        """LLM 응답 캐시 조회"""
        cache_key = f"llm:{company_id}:{prompt_hash}"
        
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return orjson.loads(cached_data)
        return None
    
    async def cache_llm_response(
        self, 
        company_id: str, 
        prompt_hash: str, 
        response: Dict
    ):
        """LLM 응답 캐싱"""
        cache_key = f"llm:{company_id}:{prompt_hash}"
        
        # 응답에 캐시 메타데이터 추가
        cached_response = {
            **response,
            'cached_at': datetime.utcnow().isoformat(),
            'cache_key': cache_key
        }
        
        await self.redis.setex(
            cache_key,
            self.ttl_config['llm_response'],
            orjson.dumps(cached_response)
        )
    
    async def get_cached_vector_search(
        self, 
        company_id: str, 
        query_hash: str
    ) -> Optional[List[Dict]]:
        """벡터 검색 결과 캐시 조회"""
        cache_key = f"vector:{company_id}:{query_hash}"
        
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return orjson.loads(cached_data)
        return None
    
    async def cache_vector_search(
        self, 
        company_id: str, 
        query_hash: str, 
        results: List[Dict]
    ):
        """벡터 검색 결과 캐싱"""
        cache_key = f"vector:{company_id}:{query_hash}"
        
        await self.redis.setex(
            cache_key,
            self.ttl_config['vector_search'],
            orjson.dumps(results)
        )
    
    async def get_session_context(
        self, 
        company_id: str, 
        session_id: str
    ) -> Optional[Dict]:
        """세션 컨텍스트 조회"""
        cache_key = f"session:{company_id}:{session_id}"
        
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            context = orjson.loads(cached_data)
            
            # 세션 활성 시간 업데이트
            context['last_accessed'] = datetime.utcnow().isoformat()
            await self.cache_session_context(company_id, session_id, context)
            
            return context
        return None
    
    async def cache_session_context(
        self, 
        company_id: str, 
        session_id: str, 
        context: Dict
    ):
        """세션 컨텍스트 캐싱"""
        cache_key = f"session:{company_id}:{session_id}"
        
        await self.redis.setex(
            cache_key,
            self.ttl_config['session_context'],
            orjson.dumps(context)
        )
    
    async def invalidate_company_cache(self, company_id: str):
        """특정 회사의 모든 캐시 무효화"""
        patterns = [
            f"llm:{company_id}:*",
            f"vector:{company_id}:*",
            f"session:{company_id}:*",
            f"api:{company_id}:*"
        ]
        
        for pattern in patterns:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
        
        logger.info(f"Invalidated cache for company: {company_id}")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회"""
        info = await self.redis.info()
        
        # 키 개수 조회
        all_keys = await self.redis.keys("*")
        
        key_types = {}
        for key in all_keys:
            key_type = key.decode().split(':')[0]
            key_types[key_type] = key_types.get(key_type, 0) + 1
        
        return {
            'total_keys': len(all_keys),
            'memory_usage_mb': info.get('used_memory', 0) / 1024 / 1024,
            'hit_ratio': info.get('keyspace_hits', 0) / max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1),
            'key_distribution': key_types,
            'connected_clients': info.get('connected_clients', 0)
        }

# 전역 캐시 관리자
cache_manager = LayeredCacheManager(os.getenv("REDIS_URL"))

# 캐시 데코레이터
def smart_cache(cache_type: str, ttl: int = None):
    """스마트 캐싱 데코레이터"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            company_id = kwargs.get('company_id') or args[0]
            cache_key_data = str(args) + str(sorted(kwargs.items()))
            cache_hash = hashlib.md5(cache_key_data.encode()).hexdigest()[:8]
            
            # 캐시 조회
            if cache_type == 'llm':
                cached_result = await cache_manager.get_cached_llm_response(company_id, cache_hash)
            elif cache_type == 'vector':
                cached_result = await cache_manager.get_cached_vector_search(company_id, cache_hash)
            else:
                cached_result = None
            
            if cached_result:
                return cached_result
            
            # 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱
            if cache_type == 'llm':
                await cache_manager.cache_llm_response(company_id, cache_hash, result)
            elif cache_type == 'vector':
                await cache_manager.cache_vector_search(company_id, cache_hash, result)
            
            return result
        
        return wrapper
    return decorator
```

### 🔄 **캐시 워밍 및 프리로딩**

```python
class CacheWarmer:
    """캐시 워밍 시스템"""
    
    def __init__(self, cache_manager: LayeredCacheManager):
        self.cache_manager = cache_manager
    
    async def warm_popular_queries(self, company_id: str):
        """인기 쿼리 캐시 사전 로딩"""
        
        # 인기 검색 쿼리 목록
        popular_queries = [
            "로그인 문제",
            "비밀번호 재설정",
            "결제 문제",
            "계정 삭제",
            "기능 문의",
            "버그 신고",
            "환불 요청",
            "API 사용법"
        ]
        
        for query in popular_queries:
            try:
                # 벡터 검색 실행 및 캐싱
                query_vector = await generate_embedding(query)
                results = await search_similar_documents(
                    company_id=company_id,
                    query_vector=query_vector,
                    limit=10
                )
                
                # 캐시에 저장
                query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
                await self.cache_manager.cache_vector_search(
                    company_id, query_hash, results
                )
                
                logger.info(f"Warmed cache for query: {query}")
                
            except Exception as e:
                logger.error(f"Failed to warm cache for query '{query}': {e}")
    
    async def warm_llm_responses(self, company_id: str):
        """일반적인 LLM 응답 사전 캐싱"""
        
        common_prompts = [
            "안녕하세요. 어떻게 도와드릴까요?",
            "문제를 좀 더 자세히 설명해 주실 수 있나요?",
            "해결 방법을 찾았습니다. 다음 단계를 따라해 보세요:",
            "추가로 궁금한 점이 있으시면 언제든 말씀해 주세요.",
            "문제가 해결되지 않으면 다음 정보를 확인해 주세요:"
        ]
        
        for prompt in common_prompts:
            try:
                # LLM 응답 생성
                response = await generate_llm_response(
                    prompt=prompt,
                    company_id=company_id
                )
                
                # 캐시에 저장
                prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
                await self.cache_manager.cache_llm_response(
                    company_id, prompt_hash, response
                )
                
                logger.info(f"Warmed LLM cache for prompt: {prompt[:30]}...")
                
            except Exception as e:
                logger.error(f"Failed to warm LLM cache: {e}")
    
    async def schedule_cache_warming(self, company_id: str):
        """캐시 워밍 스케줄링"""
        
        # 매일 새벽 2시에 캐시 워밍
        import asyncio
        
        while True:
            now = datetime.now()
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            
            if next_run <= now:
                next_run += timedelta(days=1)
            
            sleep_seconds = (next_run - now).total_seconds()
            await asyncio.sleep(sleep_seconds)
            
            try:
                logger.info(f"Starting cache warming for {company_id}")
                
                await self.warm_popular_queries(company_id)
                await self.warm_llm_responses(company_id)
                
                logger.info(f"Cache warming completed for {company_id}")
                
            except Exception as e:
                logger.error(f"Cache warming failed for {company_id}: {e}")

# 캐시 워머 인스턴스
cache_warmer = CacheWarmer(cache_manager)
```

---

## 🔄 **비동기 처리 최적화**

### ⚡ **배치 처리 및 동시성 제어**

```python
import asyncio
from typing import List, Callable, TypeVar, Generic
from dataclasses import dataclass
import time

T = TypeVar('T')
R = TypeVar('R')

@dataclass
class BatchProcessingConfig:
    """배치 처리 설정"""
    batch_size: int = 10
    max_concurrent: int = 5
    delay_between_batches: float = 0.1
    retry_attempts: int = 3
    retry_delay: float = 1.0

class AsyncBatchProcessor(Generic[T, R]):
    """고성능 비동기 배치 처리기"""
    
    def __init__(self, config: BatchProcessingConfig = None):
        self.config = config or BatchProcessingConfig()
        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self.processing_stats = {
            'total_items': 0,
            'processed_items': 0,
            'failed_items': 0,
            'processing_time': 0.0,
            'average_batch_time': 0.0
        }
    
    async def process_items(
        self, 
        items: List[T], 
        processor_func: Callable[[T], R],
        progress_callback: Callable[[int, int], None] = None
    ) -> List[R]:
        """아이템 배치 처리"""
        
        start_time = time.time()
        self.processing_stats['total_items'] = len(items)
        
        # 배치 단위로 분할
        batches = [
            items[i:i + self.config.batch_size]
            for i in range(0, len(items), self.config.batch_size)
        ]
        
        all_results = []
        batch_times = []
        
        for batch_index, batch in enumerate(batches):
            batch_start_time = time.time()
            
            # 동시성 제어된 배치 처리
            async with self.semaphore:
                batch_results = await self._process_batch(
                    batch, processor_func, batch_index
                )
            
            all_results.extend(batch_results)
            
            # 배치 처리 시간 기록
            batch_time = time.time() - batch_start_time
            batch_times.append(batch_time)
            
            # 진행 상황 콜백
            if progress_callback:
                processed_count = len(all_results)
                progress_callback(processed_count, len(items))
            
            # 배치 간 지연 (Rate Limit 방지)
            if batch_index < len(batches) - 1:
                await asyncio.sleep(self.config.delay_between_batches)
        
        # 통계 업데이트
        total_time = time.time() - start_time
        self.processing_stats.update({
            'processed_items': len(all_results),
            'processing_time': total_time,
            'average_batch_time': sum(batch_times) / len(batch_times) if batch_times else 0.0
        })
        
        return all_results
    
    async def _process_batch(
        self, 
        batch: List[T], 
        processor_func: Callable[[T], R],
        batch_index: int
    ) -> List[R]:
        """단일 배치 처리"""
        
        # 병렬 태스크 생성
        tasks = [
            self._process_single_item(item, processor_func, item_index)
            for item_index, item in enumerate(batch)
        ]
        
        # 배치 내 병렬 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리 및 결과 수집
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch {batch_index}, Item {i} failed: {result}")
                self.processing_stats['failed_items'] += 1
            else:
                valid_results.append(result)
        
        return valid_results
    
    async def _process_single_item(
        self, 
        item: T, 
        processor_func: Callable[[T], R],
        item_index: int
    ) -> R:
        """단일 아이템 처리 (재시도 포함)"""
        
        for attempt in range(self.config.retry_attempts):
            try:
                result = await processor_func(item)
                return result
                
            except Exception as e:
                if attempt == self.config.retry_attempts - 1:
                    # 마지막 시도 실패
                    raise e
                
                # 재시도 지연
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
        
        raise Exception("All retry attempts failed")
    
    def get_processing_stats(self) -> dict:
        """처리 통계 조회"""
        return self.processing_stats.copy()

# 사용 예시
async def process_tickets_with_llm(tickets: List[Dict]) -> List[Dict]:
    """티켓 배치 LLM 처리"""
    
    config = BatchProcessingConfig(
        batch_size=10,
        max_concurrent=5,
        delay_between_batches=0.2,
        retry_attempts=3
    )
    
    processor = AsyncBatchProcessor[Dict, Dict](config)
    
    async def llm_processor(ticket: Dict) -> Dict:
        """단일 티켓 LLM 처리"""
        summary = await generate_ticket_summary(ticket)
        return {
            'ticket_id': ticket['id'],
            'summary': summary,
            'processed_at': datetime.utcnow().isoformat()
        }
    
    def progress_callback(processed: int, total: int):
        """진행 상황 로깅"""
        percentage = (processed / total) * 100
        logger.info(f"LLM processing progress: {processed}/{total} ({percentage:.1f}%)")
    
    results = await processor.process_items(
        items=tickets,
        processor_func=llm_processor,
        progress_callback=progress_callback
    )
    
    # 처리 통계 로깅
    stats = processor.get_processing_stats()
    logger.info(f"LLM processing completed: {stats}")
    
    return results
```

### 🌊 **스트리밍 데이터 처리**

```python
from typing import AsyncGenerator, AsyncIterator
import aiofiles
import asyncio

class StreamingDataProcessor:
    """대용량 데이터 스트리밍 처리"""
    
    def __init__(self, chunk_size: int = 1000):
        self.chunk_size = chunk_size
        self.processed_count = 0
        self.error_count = 0
    
    async def process_streaming_data(
        self,
        data_source: AsyncIterator[Dict],
        processor_func: Callable[[List[Dict]], List[Dict]],
        output_handler: Callable[[List[Dict]], None] = None
    ) -> Dict[str, int]:
        """스트리밍 데이터 처리"""
        
        chunk_buffer = []
        
        async for data_item in data_source:
            chunk_buffer.append(data_item)
            
            # 청크 크기에 도달하면 처리
            if len(chunk_buffer) >= self.chunk_size:
                await self._process_chunk(
                    chunk_buffer, processor_func, output_handler
                )
                chunk_buffer.clear()
        
        # 남은 데이터 처리
        if chunk_buffer:
            await self._process_chunk(
                chunk_buffer, processor_func, output_handler
            )
        
        return {
            'processed_count': self.processed_count,
            'error_count': self.error_count
        }
    
    async def _process_chunk(
        self,
        chunk: List[Dict],
        processor_func: Callable[[List[Dict]], List[Dict]],
        output_handler: Callable[[List[Dict]], None] = None
    ):
        """청크 처리"""
        try:
            processed_chunk = await processor_func(chunk)
            self.processed_count += len(processed_chunk)
            
            # 결과 출력 처리
            if output_handler and processed_chunk:
                await output_handler(processed_chunk)
                
        except Exception as e:
            logger.error(f"Chunk processing failed: {e}")
            self.error_count += len(chunk)
    
    async def stream_from_database(
        self,
        company_id: str,
        query: str,
        params: dict = None
    ) -> AsyncGenerator[Dict, None]:
        """데이터베이스에서 스트리밍 조회"""
        
        # 커서 기반 스트리밍 쿼리
        async with database.get_connection() as conn:
            async with conn.transaction():
                cursor = await conn.cursor(query, *(params or {}))
                
                async for row in cursor:
                    yield dict(row)
    
    async def stream_to_file(
        self,
        data_stream: AsyncIterator[Dict],
        output_file: str
    ):
        """스트리밍 데이터를 파일로 저장"""
        
        async with aiofiles.open(output_file, 'w') as f:
            async for data_item in data_stream:
                json_line = orjson.dumps(data_item).decode() + '\n'
                await f.write(json_line)

# 사용 예시
async def process_large_dataset(company_id: str):
    """대용량 데이터셋 스트리밍 처리"""
    
    processor = StreamingDataProcessor(chunk_size=100)
    
    # 데이터베이스에서 스트리밍 조회
    query = """
        SELECT * FROM tickets 
        WHERE company_id = $1 
        ORDER BY created_at 
    """
    
    data_stream = processor.stream_from_database(
        company_id=company_id,
        query=query,
        params={'company_id': company_id}
    )
    
    async def chunk_processor(chunk: List[Dict]) -> List[Dict]:
        """청크 처리 함수"""
        # LLM 요약 생성
        summaries = await process_tickets_with_llm(chunk)
        
        # 벡터 임베딩 생성
        embeddings = await generate_embeddings_batch([s['summary'] for s in summaries])
        
        # 결과 조합
        for i, summary in enumerate(summaries):
            summary['embedding'] = embeddings[i]
        
        return summaries
    
    async def output_handler(processed_chunk: List[Dict]):
        """처리 결과 출력"""
        # Qdrant에 벡터 저장
        await store_embeddings_batch(company_id, processed_chunk)
        
        # 진행 상황 로깅
        logger.info(f"Processed and stored {len(processed_chunk)} items")
    
    # 스트리밍 처리 실행
    result = await processor.process_streaming_data(
        data_source=data_stream,
        processor_func=chunk_processor,
        output_handler=output_handler
    )
    
    logger.info(f"Streaming processing completed: {result}")
    return result
```

---

## 📊 **성능 모니터링 & 메트릭**

### 📈 **Prometheus 메트릭 수집**

```python
from prometheus_client import (
    Histogram, Counter, Gauge, Summary, 
    start_http_server, CollectorRegistry
)
import time
from functools import wraps
from typing import Dict, Any

class PerformanceMetrics:
    """성능 메트릭 수집기"""
    
    def __init__(self):
        # HTTP 요청 메트릭
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint', 'company_id', 'status_code']
        )
        
        # LLM 요청 메트릭
        self.llm_request_duration = Histogram(
            'llm_request_duration_seconds',
            'LLM request duration',
            ['provider', 'model', 'company_id']
        )
        
        self.llm_request_count = Counter(
            'llm_requests_total',
            'Total LLM requests',
            ['provider', 'model', 'company_id', 'status']
        )
        
        self.llm_token_usage = Counter(
            'llm_token_usage_total',
            'Total LLM tokens used',
            ['provider', 'model', 'company_id', 'token_type']
        )
        
        # 벡터 검색 메트릭
        self.vector_search_duration = Histogram(
            'vector_search_duration_seconds',
            'Vector search duration',
            ['company_id', 'collection']
        )
        
        self.vector_search_results = Histogram(
            'vector_search_results_count',
            'Number of vector search results',
            ['company_id', 'collection']
        )
        
        # 캐시 메트릭
        self.cache_operations = Counter(
            'cache_operations_total',
            'Cache operations',
            ['operation', 'result', 'cache_type']
        )
        
        self.cache_hit_rate = Gauge(
            'cache_hit_rate_percent',
            'Cache hit rate percentage',
            ['cache_type', 'company_id']
        )
        
        # 데이터베이스 메트릭
        self.db_query_duration = Histogram(
            'db_query_duration_seconds',
            'Database query duration',
            ['query_type', 'company_id']
        )
        
        # 시스템 리소스 메트릭
        self.active_sessions = Gauge(
            'active_sessions_current',
            'Current active sessions',
            ['company_id']
        )
        
        self.memory_usage = Gauge(
            'memory_usage_bytes',
            'Memory usage in bytes',
            ['component']
        )
    
    def monitor_http_request(self, endpoint: str):
        """HTTP 요청 모니터링 데코레이터"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                company_id = kwargs.get('company_id', 'unknown')
                status_code = 200
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                    
                except Exception as e:
                    status_code = 500
                    raise e
                    
                finally:
                    duration = time.time() - start_time
                    self.http_request_duration.labels(
                        method='POST',
                        endpoint=endpoint,
                        company_id=company_id,
                        status_code=status_code
                    ).observe(duration)
            
            return wrapper
        return decorator
    
    def monitor_llm_request(self, provider: str, model: str):
        """LLM 요청 모니터링 데코레이터"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                company_id = kwargs.get('company_id', 'unknown')
                status = 'success'
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # 토큰 사용량 기록
                    if hasattr(result, 'usage'):
                        usage = result.usage
                        self.llm_token_usage.labels(
                            provider=provider,
                            model=model,
                            company_id=company_id,
                            token_type='prompt'
                        ).inc(usage.prompt_tokens)
                        
                        self.llm_token_usage.labels(
                            provider=provider,
                            model=model,
                            company_id=company_id,
                            token_type='completion'
                        ).inc(usage.completion_tokens)
                    
                    return result
                    
                except Exception as e:
                    status = 'error'
                    raise e
                    
                finally:
                    duration = time.time() - start_time
                    
                    self.llm_request_duration.labels(
                        provider=provider,
                        model=model,
                        company_id=company_id
                    ).observe(duration)
                    
                    self.llm_request_count.labels(
                        provider=provider,
                        model=model,
                        company_id=company_id,
                        status=status
                    ).inc()
            
            return wrapper
        return decorator
    
    def monitor_vector_search(self):
        """벡터 검색 모니터링 데코레이터"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                company_id = kwargs.get('company_id', 'unknown')
                collection = kwargs.get('collection_name', 'unknown')
                
                try:
                    results = await func(*args, **kwargs)
                    
                    # 검색 결과 수 기록
                    self.vector_search_results.labels(
                        company_id=company_id,
                        collection=collection
                    ).observe(len(results) if results else 0)
                    
                    return results
                    
                finally:
                    duration = time.time() - start_time
                    self.vector_search_duration.labels(
                        company_id=company_id,
                        collection=collection
                    ).observe(duration)
            
            return wrapper
        return decorator
    
    def track_cache_operation(
        self, 
        operation: str, 
        result: str, 
        cache_type: str
    ):
        """캐시 작업 추적"""
        self.cache_operations.labels(
            operation=operation,
            result=result,
            cache_type=cache_type
        ).inc()
    
    def update_cache_hit_rate(
        self, 
        cache_type: str, 
        company_id: str, 
        hit_rate: float
    ):
        """캐시 적중률 업데이트"""
        self.cache_hit_rate.labels(
            cache_type=cache_type,
            company_id=company_id
        ).set(hit_rate * 100)  # 퍼센트로 변환
    
    def track_active_session(self, company_id: str, increment: bool = True):
        """활성 세션 추적"""
        if increment:
            self.active_sessions.labels(company_id=company_id).inc()
        else:
            self.active_sessions.labels(company_id=company_id).dec()
    
    def update_memory_usage(self, component: str, usage_bytes: int):
        """메모리 사용량 업데이트"""
        self.memory_usage.labels(component=component).set(usage_bytes)

# 전역 메트릭 인스턴스
performance_metrics = PerformanceMetrics()

# Prometheus 서버 시작
def start_metrics_server(port: int = 8090):
    """메트릭 서버 시작"""
    start_http_server(port)
    logger.info(f"Prometheus metrics server started on port {port}")

# 사용 예시
@performance_metrics.monitor_http_request('ingest')
async def monitored_ingest_endpoint(
    company_id: str,
    request_data: IngestRequest
):
    """모니터링이 적용된 수집 엔드포인트"""
    return await ingest_service.process_request(company_id, request_data)

@performance_metrics.monitor_llm_request('openai', 'gpt-3.5-turbo')
async def monitored_llm_call(company_id: str, prompt: str):
    """모니터링이 적용된 LLM 호출"""
    return await llm_client.chat_completion(prompt, company_id=company_id)
```

---

## 📚 **관련 참조 지침서**

- **system-architecture.instructions.md** - 전체 시스템 아키텍처
- **data-processing-llm.instructions.md** - LLM 처리 최적화
- **vector-storage-search.instructions.md** - 벡터 검색 성능
- **backend-implementation-patterns.instructions.md** - 백엔드 최적화 패턴
- **quick-reference.instructions.md** - 핵심 성능 체크리스트

---

## 🔗 **크로스 참조**

이 지침서는 다음과 연계됩니다:
- **캐싱**: Redis 기반 계층별 캐싱 전략
- **비동기**: 배치 처리 및 동시성 제어
- **모니터링**: Prometheus 메트릭 및 성능 추적
- **최적화**: JSON 직렬화 및 데이터 검증 성능

**세션 간 일관성**: 이 성능 최적화 패턴들은 AI 세션이 바뀌어도 동일하게 적용되어야 합니다.
