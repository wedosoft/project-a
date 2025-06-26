---
applyTo: "**"
---

# 🏗️ 시스템 아키텍처 & 모듈화 설계 지침서

_AI 참조 최적화 버전 - 확장 가능한 아키텍처 및 모듈 구조_

## 🎯 시스템 아키텍처 목표

**확장 가능한 멀티플랫폼 AI 지원 시스템 구축**

- **모듈화 아키텍처**: 기능별 독립적 모듈로 유지보수성 향상
- **글로벌 스케일링**: 다국어 지원 및 지역별 배포
- **성능 최적화**: 비동기 처리 및 캐싱으로 응답 속도 향상

---

## 🚀 **TL;DR - 핵심 아키텍처 요약**

### 💡 **즉시 참조용 핵심 포인트**

**디렉터리 구조 (2025년 6월 21일 대규모 리팩토링 완료)**:
```
backend/
├── api/                    # FastAPI 라우터 & 엔드포인트
│   ├── main.py            # 메인 API 애플리케이션
│   └── main_legacy.py     # 레거시 API (호환성 유지)
├── core/                   # 핵심 비즈니스 로직 (완전 모듈화)
│   ├── database/          # 데이터베이스 관련
│   │   ├── vectordb.py    # Qdrant 벡터 DB
│   │   └── sqlite.py      # SQLite 관리
│   ├── data/              # 데이터 모델 및 스키마
│   │   ├── schemas.py     # Pydantic 모델
│   │   └── merger.py      # 데이터 병합 로직
│   ├── search/            # 검색 및 임베딩
│   │   ├── retriever.py   # 문서 검색
│   │   ├── hybrid.py      # 하이브리드 검색
│   │   └── embeddings/    # 임베딩 모델
│   ├── processing/        # 데이터 처리
│   │   └── context_builder.py
│   ├── llm/              # LLM 통합 관리 (완전 통합)
│   │   ├── router.py     # LLM 라우터
│   │   ├── clients.py    # LLM 클라이언트
│   │   └── models.py     # LLM 모델
│   ├── platforms/        # 플랫폼별 어댑터
│   │   ├── freshdesk/    # Freshdesk 통합
│   │   └── factory.py    # 플랫폼 팩토리
│   ├── ingest/           # 데이터 수집 파이프라인
│   │   └── processor.py  # 수집 처리기
│   └── legacy/           # 레거시 코드 보관
├── config/               # 환경 설정 (분리됨)
│   ├── settings/         # Python 설정 파일
│   └── data/            # JSON 설정 데이터
├── tests/               # 테스트 파일
└── legacy/              # 백업된 구조
    ├── backend_freshdesk_backup/
    └── backend_data_backup/
```

**핵심 기술 스택**:
- **Backend**: FastAPI + asyncio + langchain + Redis
- **Vector DB**: Qdrant Cloud (단일 `documents` 컬렉션)
- **Cache**: Redis (LLM 응답 캐싱)
- **DB**: SQLite (개발) → PostgreSQL (프로덕션)

**멀티테넌트 전략**:
- company_id 자동 추출: `domain.split('.')[0]`
- 모든 컴포넌트에 테넌트 격리 적용
- X-Company-ID 헤더 기반 API 보안

### 🚨 **아키텍처 주의사항**

- ⚠️ 기존 모듈 구조 변경 금지 → 점진적 개선만 허용
- ⚠️ company_id 없는 컴포넌트 절대 금지 → 멀티테넌트 필수
- ⚠️ 플랫폼별 하드코딩 금지 → 어댑터 패턴 적용

---

## 🔧 **모듈화 아키텍처 패턴**

### 📦 **통합 LLM 관리 모듈 (완전 통합 완료)**

**모듈 구조**: `core/llm/` (단일화된 구조)
- `router.py`: 통합 LLM 라우터 (모델 선택, 비용 최적화)
- `clients.py`: 모든 LLM 클라이언트 구현 (OpenAI, Anthropic, Azure, Gemini)
- `models.py`: LLM 모델 정의 (요청/응답 스키마)
- `providers.py`: 프로바이더별 구현체
- `utils.py`: LLM 유틸리티 (토큰 계산, 캐싱)

```python
# 통합 LLM 모듈 사용 예시
from core.llm import LLMRouter, LLMResponse

# 스마트 라우팅 LLM 호출
llm_router = LLMRouter()
response: LLMResponse = await llm_router.route_and_execute(
    prompt=user_query,
    quality_requirement='standard',
    cost_budget=0.01,
    company_id=company_id
)

# 특정 모델 직접 호출
response = await llm_router.execute_with_model(
    model_name='gpt-4',
    messages=[{"role": "user", "content": prompt}],
    company_id=company_id
)
```

### 📊 **데이터 수집 모듈 (완료)**

**모듈 구조**: `core/ingest/`
- `processor.py`: 핵심 ingest 함수 (메인 비즈니스 로직)
- `validator.py`: 데이터 검증 및 필터링
- `integrator.py`: 통합 객체 생성 및 병합
- `storage.py`: 저장소 관리 (Qdrant, SQLite)

```python
# 데이터 수집 모듈 사용 예시
from core.ingest import ingest, validate_data, integrate_data

# 통합 수집 함수 (모든 플랫폼 대응)
result = await ingest(
    company_id="wedosoft",
    platform="freshdesk",
    start_date="2024-01-01",
    end_date="2024-12-31",
    data_types=["tickets", "conversations", "kb_articles"]
)

# 데이터 검증
validated_data = await validate_data(raw_data, company_id, platform)

# 통합 객체 생성
integrated_objects = await integrate_data(validated_data, company_id)
```

### 🔄 **플랫폼 어댑터 패턴**

```python
from abc import ABC, abstractmethod
from typing import Dict, List, AsyncGenerator

class PlatformAdapter(ABC):
    """플랫폼별 어댑터 추상 클래스"""
    
    def __init__(self, company_id: str, credentials: Dict[str, Any]):
        self.company_id = company_id
        self.credentials = credentials
    
    @abstractmethod
    async def fetch_tickets(self, start_date: str, end_date: str) -> AsyncGenerator[List[Dict], None]:
        """티켓 데이터 수집"""
        pass
    
    @abstractmethod
    async def fetch_conversations(self, ticket_id: str) -> List[Dict]:
        """대화 데이터 수집"""
        pass
    
    @abstractmethod
    async def fetch_knowledge_base(self) -> List[Dict]:
        """지식베이스 수집"""
        pass
    
    @abstractmethod
    def get_rate_limits(self) -> Dict[str, int]:
        """플랫폼별 API 제한 정보"""
        pass

class FreshdeskAdapter(PlatformAdapter):
    """Freshdesk 플랫폼 어댑터"""
    
    async def fetch_tickets(self, start_date: str, end_date: str) -> AsyncGenerator[List[Dict], None]:
        """Freshdesk 티켓 수집 구현"""
        # Freshdesk API 특화 로직
        async for batch in self._fetch_tickets_batch(start_date, end_date):
            # company_id 자동 태깅
            for ticket in batch:
                ticket['company_id'] = self.company_id
                ticket['platform'] = 'freshdesk'
            yield batch
    
    def get_rate_limits(self) -> Dict[str, int]:
        return {
            'requests_per_minute': 1000,
            'requests_per_hour': 50000,
            'concurrent_requests': 50
        }

    
    async def fetch_tickets(self, start_date: str, end_date: str) -> AsyncGenerator[List[Dict], None]:
        pass
    
    def get_rate_limits(self) -> Dict[str, int]:
        return {
            'requests_per_minute': 700,
            'requests_per_hour': 40000,
            'concurrent_requests': 30
        }

# 어댑터 팩토리
class AdapterFactory:
    @staticmethod
    def create_adapter(platform: str, company_id: str, credentials: Dict) -> PlatformAdapter:
        adapters = {
            'freshdesk': FreshdeskAdapter,
            'servicenow': ServiceNowAdapter  # 미래 확장
        }
        
        adapter_class = adapters.get(platform.lower())
        if not adapter_class:
            raise ValueError(f"Unsupported platform: {platform}")
        
        return adapter_class(company_id, credentials)
```

---

## ⚡ **성능 최적화 아키텍처**

### 🚀 **비동기 처리 패턴**

```python
import asyncio
from typing import List, Dict, Coroutine
import orjson
from datetime import datetime

class AsyncProcessor:
    """비동기 처리 최적화"""
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results = []
    
    async def process_batch(
        self, 
        tasks: List[Coroutine],
        batch_size: int = 50
    ) -> List[Dict]:
        """배치 단위 비동기 처리"""
        
        all_results = []
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            
            # 동시성 제어
            async with self.semaphore:
                batch_results = await asyncio.gather(
                    *batch, 
                    return_exceptions=True
                )
            
            # 예외 처리
            valid_results = []
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing error: {result}")
                    continue
                valid_results.append(result)
            
            all_results.extend(valid_results)
            
            # 배치 간 지연 (Rate Limit 방지)
            await asyncio.sleep(0.1)
        
        return all_results

# 사용 예시
async def process_multiple_companies(companies: List[str]) -> Dict[str, Any]:
    """여러 테넌트 동시 처리"""
    
    processor = AsyncProcessor(max_concurrent=5)
    
    # 각 테넌트별 처리 태스크 생성
    tasks = []
    for company_id in companies:
        task = process_company_data(company_id)
        tasks.append(task)
    
    # 배치 처리 실행
    results = await processor.process_batch(tasks, batch_size=10)
    
    return {
        'processed_companies': len(companies),
        'successful_results': len(results),
        'processing_time': datetime.utcnow().isoformat()
    }
```

### 📈 **캐싱 전략 아키텍처**

```python
import redis.asyncio as redis
import hashlib
from functools import wraps
from typing import Callable, Any, Optional

class CacheManager:
    """통합 캐시 관리자"""
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = 3600  # 1시간
    
    def cache_result(
        self, 
        prefix: str, 
        ttl: int = None,
        company_aware: bool = True
    ):
        """결과 캐싱 데코레이터"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 캐시 키 생성
                cache_key = self._generate_cache_key(
                    prefix, func.__name__, args, kwargs, company_aware
                )
                
                # 캐시 확인
                cached_result = await self.redis.get(cache_key)
                if cached_result:
                    logger.info(f"Cache hit: {cache_key}")
                    return orjson.loads(cached_result)
                
                # 함수 실행
                result = await func(*args, **kwargs)
                
                # 결과 캐싱
                cache_ttl = ttl or self.default_ttl
                await self.redis.setex(
                    cache_key, 
                    cache_ttl, 
                    orjson.dumps(result)
                )
                
                logger.info(f"Cache set: {cache_key}")
                return result
            
            return wrapper
        return decorator
    
    def _generate_cache_key(
        self, 
        prefix: str, 
        func_name: str, 
        args: tuple, 
        kwargs: dict,
        company_aware: bool
    ) -> str:
        """캐시 키 생성"""
        
        # 회사별 격리가 필요한 경우
        if company_aware:
            company_id = kwargs.get('company_id') or (args[0] if args else 'unknown')
            key_base = f"{prefix}:{company_id}:{func_name}"
        else:
            key_base = f"{prefix}:{func_name}"
        
        # 매개변수 해시
        params_str = str(args) + str(sorted(kwargs.items()))
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        
        return f"{key_base}:{params_hash}"
    
    async def invalidate_pattern(self, pattern: str):
        """패턴 기반 캐시 무효화"""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching {pattern}")

# 전역 캐시 관리자
cache_manager = CacheManager(os.getenv("REDIS_URL"))

# 사용 예시
@cache_manager.cache_result(prefix="llm", ttl=3600, company_aware=True)
async def cached_llm_response(company_id: str, prompt: str) -> Dict:
    """LLM 응답 캐싱"""
    return await llm_client.chat_completion(prompt, company_id=company_id)

@cache_manager.cache_result(prefix="vector", ttl=1800, company_aware=True)
async def cached_vector_search(company_id: str, query_vector: List[float]) -> List[Dict]:
    """벡터 검색 결과 캐싱"""
    return await vector_db.search(company_id, query_vector)
```

### 📊 **성능 모니터링**

```python
from prometheus_client import Histogram, Counter, Gauge, start_http_server
import time
from functools import wraps

# Prometheus 메트릭 정의
REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'company_id']
)

LLM_REQUESTS = Counter(
    'llm_requests_total',
    'Total LLM requests',
    ['provider', 'model', 'company_id']
)

CACHE_OPERATIONS = Counter(
    'cache_operations_total',
    'Cache operations',
    ['operation', 'result']  # operation: get/set, result: hit/miss
)

ACTIVE_SESSIONS = Gauge(
    'active_sessions_current',
    'Current active sessions',
    ['company_id']
)

def monitor_performance(endpoint: str):
    """성능 모니터링 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            company_id = kwargs.get('company_id', 'unknown')
            
            try:
                result = await func(*args, **kwargs)
                
                # 성공 메트릭 기록
                duration = time.time() - start_time
                REQUEST_DURATION.labels(
                    method='POST',
                    endpoint=endpoint,
                    company_id=company_id
                ).observe(duration)
                
                return result
                
            except Exception as e:
                # 에러 메트릭 기록
                duration = time.time() - start_time
                REQUEST_DURATION.labels(
                    method='POST',
                    endpoint=f"{endpoint}_error",
                    company_id=company_id
                ).observe(duration)
                
                raise e
        
        return wrapper
    return decorator

# 사용 예시
@monitor_performance('ingest')
async def monitored_ingest(company_id: str, platform: str, **kwargs):
    """모니터링이 적용된 데이터 수집"""
    return await ingest(company_id, platform, **kwargs)

# Prometheus 서버 시작
def start_metrics_server(port: int = 8090):
    """메트릭 서버 시작"""
    start_http_server(port)
    logger.info(f"Metrics server started on port {port}")
```

---

## 🗄️ **데이터 계층 아키텍처**

### 📊 **데이터베이스 추상화**

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import sqlite3
import asyncpg
from contextlib import asynccontextmanager

class DatabaseInterface(ABC):
    """데이터베이스 추상화 인터페이스"""
    
    @abstractmethod
    async def connect(self):
        pass
    
    @abstractmethod
    async def disconnect(self):
        pass
    
    @abstractmethod
    async def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        pass
    
    @abstractmethod
    async def execute_transaction(self, queries: List[Dict]) -> bool:
        pass
    
    @abstractmethod
    async def get_tickets(self, company_id: str, **filters) -> List[Dict]:
        pass
    
    @abstractmethod
    async def insert_ticket(self, company_id: str, ticket_data: Dict) -> str:
        pass

class SQLiteDatabase(DatabaseInterface):
    """SQLite 데이터베이스 구현 (개발/테스트용)"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
    
    async def connect(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        await self._create_tables()
    
    async def disconnect(self):
        if self.connection:
            self.connection.close()
    
    async def _create_tables(self):
        """테이블 생성"""
        schema = """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            platform_ticket_id TEXT NOT NULL,
            subject TEXT,
            description TEXT,
            status TEXT,
            priority TEXT,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE(company_id, platform, platform_ticket_id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_tickets_company 
        ON tickets(company_id, platform);
        """
        
        self.connection.executescript(schema)
        self.connection.commit()
    
    async def get_tickets(self, company_id: str, **filters) -> List[Dict]:
        """테넌트별 티켓 조회"""
        query = "SELECT * FROM tickets WHERE company_id = ?"
        params = [company_id]
        
        # 추가 필터 적용
        if 'platform' in filters:
            query += " AND platform = ?"
            params.append(filters['platform'])
        
        if 'status' in filters:
            query += " AND status = ?"
            params.append(filters['status'])
        
        query += " ORDER BY created_at DESC"
        
        if 'limit' in filters:
            query += " LIMIT ?"
            params.append(filters['limit'])
        
        cursor = self.connection.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL 데이터베이스 구현 (프로덕션용)"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool = None
    
    async def connect(self):
        self.pool = await asyncpg.create_pool(self.connection_string)
    
    async def disconnect(self):
        if self.pool:
            await self.pool.close()
    
    @asynccontextmanager
    async def get_connection(self):
        async with self.pool.acquire() as connection:
            # Row-level Security 설정
            await connection.execute("SET row_security = on")
            yield connection
    
    async def get_tickets(self, company_id: str, **filters) -> List[Dict]:
        """Row-level Security가 적용된 티켓 조회"""
        async with self.get_connection() as conn:
            # 테넌트 컨텍스트 설정
            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, true)",
                company_id
            )
            
            query = "SELECT * FROM tickets WHERE company_id = $1"
            params = [company_id]
            
            # 추가 필터 적용
            param_index = 2
            if 'platform' in filters:
                query += f" AND platform = ${param_index}"
                params.append(filters['platform'])
                param_index += 1
            
            query += " ORDER BY created_at DESC"
            
            if 'limit' in filters:
                query += f" LIMIT ${param_index}"
                params.append(filters['limit'])
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

# 데이터베이스 팩토리
class DatabaseFactory:
    @staticmethod
    def create_database(db_type: str, **config) -> DatabaseInterface:
        if db_type.lower() == 'sqlite':
            return SQLiteDatabase(config['db_path'])
        elif db_type.lower() == 'postgresql':
            return PostgreSQLDatabase(config['connection_string'])
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

# 전역 데이터베이스 인스턴스
database = DatabaseFactory.create_database(
    db_type=os.getenv("DB_TYPE", "sqlite"),
    db_path=os.getenv("SQLITE_PATH", "freshdesk_data.db"),
    connection_string=os.getenv("DATABASE_URL")
)
```

---

## 🔧 **환경별 설정 관리**

### ⚙️ **설정 관리 패턴**

```python
from pydantic import BaseSettings, Field
from typing import Optional, Dict, List
import os

class DatabaseSettings(BaseSettings):
    """데이터베이스 설정"""
    type: str = Field(default="sqlite", env="DB_TYPE")
    sqlite_path: str = Field(default="data/freshdesk_data.db", env="SQLITE_PATH")
    postgresql_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    max_connections: int = Field(default=20, env="DB_MAX_CONNECTIONS")

class RedisSettings(BaseSettings):
    """Redis 캐시 설정"""
    url: str = Field(..., env="REDIS_URL")
    ttl_default: int = Field(default=3600, env="REDIS_TTL_DEFAULT")
    ttl_llm: int = Field(default=7200, env="REDIS_TTL_LLM")
    ttl_vector: int = Field(default=1800, env="REDIS_TTL_VECTOR")

class QdrantSettings(BaseSettings):
    """Qdrant 벡터 DB 설정"""
    url: str = Field(..., env="QDRANT_URL")
    api_key: str = Field(..., env="QDRANT_API_KEY")
    collection_name: str = Field(default="documents", env="QDRANT_COLLECTION")
    vector_size: int = Field(default=1536, env="QDRANT_VECTOR_SIZE")

class LLMSettings(BaseSettings):
    """LLM 제공자 설정"""
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    azure_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    default_model: str = Field(default="gpt-3.5-turbo", env="LLM_DEFAULT_MODEL")
    max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")
    temperature: float = Field(default=0.1, env="LLM_TEMPERATURE")

class AppSettings(BaseSettings):
    """애플리케이션 전체 설정"""
    app_name: str = Field(default="Freshdesk AI Assistant", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    max_concurrent_requests: int = Field(default=100, env="MAX_CONCURRENT_REQUESTS")
    
    # 서브 설정들
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    qdrant: QdrantSettings = QdrantSettings()
    llm: LLMSettings = LLMSettings()
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 전역 설정 인스턴스
settings = AppSettings()

# 환경별 설정 오버라이드
def get_environment_settings(env: str = None) -> AppSettings:
    """환경별 설정 로드"""
    env = env or os.getenv("ENVIRONMENT", "development")
    
    env_files = {
        "development": ".env.dev",
        "testing": ".env.test",
        "staging": ".env.staging",
        "production": ".env.prod"
    }
    
    env_file = env_files.get(env, ".env")
    
    return AppSettings(_env_file=env_file)
```

---

## 📚 **관련 참조 지침서**

- **data-collection-patterns.instructions.md** - 데이터 수집 아키텍처
- **data-processing-llm.instructions.md** - LLM 처리 아키텍처
- **vector-storage-search.instructions.md** - 벡터 DB 아키텍처
- **multitenant-security.instructions.md** - 보안 아키텍처
- **backend-implementation-patterns.instructions.md** - 백엔드 구현 패턴
- **quick-reference.instructions.md** - 핵심 아키텍처 요약

---

## 🔗 **크로스 참조**

이 지침서는 다음과 연계됩니다:
- **모듈화**: 각 기능별 독립적 모듈 설계
- **성능**: 비동기 처리 및 캐싱 아키텍처
- **확장성**: 플랫폼별 어댑터 패턴
- **보안**: 멀티테넌트 아키텍처 설계

**세션 간 일관성**: 이 아키텍처 패턴들은 AI 세션이 바뀌어도 동일하게 유지되어야 합니다.

---

## 🔍 **통합 검색 모듈 (완전 리팩토링 완료)**

**모듈 구조**: `core/search/`
- `retriever.py`: 문서 검색 및 관련성 평가
- `hybrid.py`: 하이브리드 검색 (키워드 + 벡터)
- `embeddings/`: 임베딩 모델 관리
  - `embedder.py`: GPU 최적화 임베딩 생성
  - `models.py`: 임베딩 모델 정의

```python
# 통합 검색 모듈 사용 예시
from core.search.retriever import retrieve_top_k_docs
from core.search.hybrid import hybrid_search
from core.search.embeddings.embedder import embed_documents_optimized

# 하이브리드 검색 수행
results = await hybrid_search(
    query="사용자 질문",
    company_id=company_id,
    top_k=10,
    search_types=["vector", "keyword", "semantic"]
)

# GPU 최적화 임베딩 생성
embeddings = await embed_documents_optimized(
    documents=document_list,
    batch_size=32,
    use_gpu=True
)
```

### 🔧 **플랫폼 통합 모듈 (Freshdesk 완전 통합)**

**모듈 구조**: `core/platforms/`
- `factory.py`: 플랫폼 팩토리 (자동 등록)
- `freshdesk/`: Freshdesk 플랫폼 구현
  - `fetcher.py`: 데이터 수집
  - `collector.py`: 통합 데이터 수집기
  - `optimized_fetcher.py`: 최적화된 페처
  - `adapter.py`: 플랫폼 어댑터

```python
# 플랫폼 팩토리 사용 예시
from core.platforms.factory import PlatformFactory

# 자동 플랫폼 감지 및 어댑터 생성
adapter = PlatformFactory.create_adapter(
    platform_type="freshdesk",
    company_id=company_id,
    credentials=credentials
)

# 데이터 수집 실행
tickets = await adapter.fetch_tickets(
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

### 💾 **데이터베이스 모듈 (벡터DB 통합)**

**모듈 구조**: `core/database/`
- `vectordb.py`: Qdrant 벡터 데이터베이스 관리
- `sqlite.py`: SQLite 로컬 데이터베이스
- `migrations/`: 데이터 마이그레이션 스크립트

```python
# 벡터 DB 사용 예시
from core.database.vectordb import vector_db

# 문서 저장
await vector_db.upsert_documents(
    documents=processed_docs,
    company_id=company_id
)

# 벡터 검색
results = await vector_db.search(
    query_vector=query_embedding,
    company_id=company_id,
    top_k=10
)
```
