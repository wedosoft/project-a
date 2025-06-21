---
applyTo: "**"
---

# 🚨 에러 처리 및 디버깅 지침서

_견고한 에러 처리와 효과적인 디버깅 전문 가이드_

## 🎯 **에러 처리 목표**

**시스템 안정성과 디버깅 효율성 극대화**

- **견고한 에러 처리**: 재시도 로직, 회복 메커니즘, 사용자 친화적 메시지
- **체계적 디버깅**: 로깅, 모니터링, 성능 추적
- **운영 안정성**: 장애 대응, 알림, 자동 복구
- **개발 효율성**: 빠른 문제 진단 및 해결

---

## 🚀 **에러 처리 핵심 포인트 요약**

### 💡 **즉시 참조용 에러 처리 핵심**

**재시도 전략**:

- 지수 백오프: 1초 → 2초 → 4초 (최대 3회)
- 특정 에러만 재시도 (네트워크, 일시적 장애)
- 영구적 에러는 즉시 실패 (인증, 권한, 잘못된 요청)

**로깅 원칙**:

- 구조화된 로깅 (JSON 형태)
- company_id 포함 필수 (멀티테넌트 추적)
- 민감 정보 마스킹 (API 키, 개인정보)

**사용자 경험**:

- 기술적 에러는 숨기고 친화적 메시지 표시
- 진행 상태 표시 (로딩, 재시도 중)
- 명확한 해결 방안 제시

---

## 🛠️ **에러 처리 표준 패턴**

### **1. 재시도 로직 with 지수 백오프**

```python
import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, Type, Tuple
from enum import Enum

class ErrorCategory(Enum):
    """에러 카테고리 분류"""
    NETWORK = "network"           # 네트워크 관련 (재시도 가능)
    TEMPORARY = "temporary"       # 일시적 장애 (재시도 가능)
    PERMANENT = "permanent"       # 영구적 에러 (재시도 불가)
    AUTHENTICATION = "auth"       # 인증/권한 문제 (재시도 불가)
    VALIDATION = "validation"     # 데이터 검증 실패 (재시도 불가)

# 재시도 가능한 예외 분류
RETRYABLE_EXCEPTIONS = {
    # 네트워크 관련
    ConnectionError: ErrorCategory.NETWORK,
    TimeoutError: ErrorCategory.NETWORK,

    # HTTP 상태 코드 기반
    # 500, 502, 503, 504는 재시도 가능
}

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    company_id: Optional[str] = None
) -> Any:
    """지수 백오프를 사용한 재시도 로직"""

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = await func()

            if attempt > 0:
                logging.info(
                    f"재시도 성공: attempt={attempt}, company_id={company_id}"
                )

            return result

        except Exception as e:
            last_exception = e

            # 재시도 불가능한 에러 체크
            error_category = classify_error(e)
            if error_category in [ErrorCategory.PERMANENT, ErrorCategory.AUTHENTICATION, ErrorCategory.VALIDATION]:
                logging.error(
                    f"재시도 불가능한 에러: {error_category.value}, "
                    f"error={str(e)}, company_id={company_id}"
                )
                raise e

            # 마지막 시도인 경우 에러 발생
            if attempt >= max_retries:
                logging.error(
                    f"최대 재시도 횟수 초과: max_retries={max_retries}, "
                    f"error={str(e)}, company_id={company_id}"
                )
                break

            # 백오프 계산
            delay = min(base_delay * (2 ** attempt), max_delay)

            logging.warning(
                f"재시도 예정: attempt={attempt + 1}/{max_retries}, "
                f"delay={delay}s, error={str(e)}, company_id={company_id}"
            )

            await asyncio.sleep(delay)

    # 모든 재시도 실패
    raise last_exception

def classify_error(exception: Exception) -> ErrorCategory:
    """예외를 카테고리별로 분류"""

    # HTTP 상태 코드 기반 분류
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code

        if status_code in [401, 403]:
            return ErrorCategory.AUTHENTICATION
        elif status_code in [400, 404, 422]:
            return ErrorCategory.VALIDATION
        elif status_code in [500, 502, 503, 504]:
            return ErrorCategory.TEMPORARY
        else:
            return ErrorCategory.PERMANENT

    # 예외 타입 기반 분류
    exception_type = type(exception)
    if exception_type in RETRYABLE_EXCEPTIONS:
        return RETRYABLE_EXCEPTIONS[exception_type]

    # 기본값: 영구적 에러로 처리
    return ErrorCategory.PERMANENT

# 데코레이터 형태 재시도
def retry_on_failure(max_retries: int = 3, base_delay: float = 1.0):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # company_id 추출 (kwargs에서)
            company_id = kwargs.get('company_id', 'unknown')

            return await retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                base_delay=base_delay,
                company_id=company_id
            )
        return wrapper
    return decorator

# 사용 예시
@retry_on_failure(max_retries=3, base_delay=1.0)
async def fetch_freshdesk_data(company_id: str, endpoint: str) -> dict:
    """Freshdesk API 호출 (자동 재시도)"""
    async with aiohttp.ClientSession() as session:
        url = f"https://{company_id}.freshdesk.com{endpoint}"
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
```

### **2. 사용자 친화적 에러 메시지**

```python
from typing import Dict, Any
from enum import Enum

class UserErrorType(Enum):
    """사용자 친화적 에러 타입"""
    NETWORK_ERROR = "network_error"
    SERVER_ERROR = "server_error"
    DATA_ERROR = "data_error"
    AUTH_ERROR = "auth_error"
    RATE_LIMIT = "rate_limit"
    NOT_FOUND = "not_found"

class UserFriendlyError:
    """사용자 친화적 에러 메시지 생성"""

    ERROR_MESSAGES = {
        UserErrorType.NETWORK_ERROR: {
            "title": "연결 문제",
            "message": "인터넷 연결을 확인하고 다시 시도해주세요.",
            "action": "재시도",
            "retry_allowed": True
        },
        UserErrorType.SERVER_ERROR: {
            "title": "서버 오류",
            "message": "일시적인 서버 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "action": "재시도",
            "retry_allowed": True
        },
        UserErrorType.DATA_ERROR: {
            "title": "데이터 오류",
            "message": "입력하신 정보에 문제가 있습니다. 확인 후 다시 시도해주세요.",
            "action": "수정",
            "retry_allowed": False
        },
        UserErrorType.AUTH_ERROR: {
            "title": "인증 오류",
            "message": "API 키 또는 권한에 문제가 있습니다. 관리자에게 문의하세요.",
            "action": "문의",
            "retry_allowed": False
        },
        UserErrorType.RATE_LIMIT: {
            "title": "요청 제한",
            "message": "너무 많은 요청이 발생했습니다. 잠시 후 다시 시도해주세요.",
            "action": "대기",
            "retry_allowed": True
        },
        UserErrorType.NOT_FOUND: {
            "title": "데이터 없음",
            "message": "요청하신 데이터를 찾을 수 없습니다.",
            "action": "확인",
            "retry_allowed": False
        }
    }

    @classmethod
    def format_user_error(cls, exception: Exception, company_id: str = "unknown") -> Dict[str, Any]:
        """기술적 에러를 사용자 친화적 메시지로 변환"""

        # 에러 타입 결정
        error_type = cls._classify_user_error(exception)
        error_info = cls.ERROR_MESSAGES[error_type]

        # 기술적 정보는 로그에만 기록
        logging.error(
            f"User error occurred: type={error_type.value}, "
            f"original_error={str(exception)}, company_id={company_id}"
        )

        return {
            "error_type": error_type.value,
            "title": error_info["title"],
            "message": error_info["message"],
            "suggested_action": error_info["action"],
            "retry_allowed": error_info["retry_allowed"],
            "error_id": f"ERR_{int(time.time())}",  # 에러 추적용 ID
            "timestamp": datetime.utcnow().isoformat()
        }

    @classmethod
    def _classify_user_error(cls, exception: Exception) -> UserErrorType:
        """예외를 사용자 에러 타입으로 분류"""

        if isinstance(exception, (ConnectionError, TimeoutError)):
            return UserErrorType.NETWORK_ERROR

        if hasattr(exception, 'status_code'):
            status_code = exception.status_code

            if status_code in [401, 403]:
                return UserErrorType.AUTH_ERROR
            elif status_code == 404:
                return UserErrorType.NOT_FOUND
            elif status_code == 429:
                return UserErrorType.RATE_LIMIT
            elif status_code in [400, 422]:
                return UserErrorType.DATA_ERROR
            elif status_code >= 500:
                return UserErrorType.SERVER_ERROR

        # 기본값
        return UserErrorType.SERVER_ERROR

# FastAPI 에러 핸들러 예시
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """글로벌 예외 핸들러"""

    # company_id 추출 (요청에서)
    company_id = getattr(request.state, 'company_id', 'unknown')

    # 사용자 친화적 에러 메시지 생성
    user_error = UserFriendlyError.format_user_error(exc, company_id)

    # HTTP 상태 코드 결정
    status_code = 500
    if isinstance(exc, HTTPException):
        status_code = exc.status_code
    elif user_error["error_type"] in ["auth_error"]:
        status_code = 401
    elif user_error["error_type"] in ["data_error", "not_found"]:
        status_code = 400

    return JSONResponse(
        status_code=status_code,
        content=user_error
    )
```

### **3. 리소스 관리 패턴**

```python
import asyncio
import aiohttp
import aioredis
from contextlib import asynccontextmanager
from typing import AsyncGenerator

class ResourceManager:
    """리소스 관리 클래스"""

    def __init__(self):
        self.http_session = None
        self.redis_client = None
        self.db_connection = None

    @asynccontextmanager
    async def managed_http_session(self, max_concurrent: int = 5) -> AsyncGenerator[aiohttp.ClientSession, None]:
        """HTTP 세션 컨텍스트 매니저"""

        connector = aiohttp.TCPConnector(limit=max_concurrent)
        timeout = aiohttp.ClientTimeout(total=30)

        session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )

        try:
            logging.info("HTTP 세션 시작")
            yield session
        except Exception as e:
            logging.error(f"HTTP 세션 에러: {e}")
            raise
        finally:
            await session.close()
            logging.info("HTTP 세션 종료")

    @asynccontextmanager
    async def managed_redis_connection(self, redis_url: str) -> AsyncGenerator[aioredis.Redis, None]:
        """Redis 연결 컨텍스트 매니저"""

        redis_client = None
        try:
            redis_client = await aioredis.from_url(redis_url)

            # 연결 테스트
            await redis_client.ping()
            logging.info("Redis 연결 성공")

            yield redis_client

        except Exception as e:
            logging.error(f"Redis 연결 에러: {e}")
            raise
        finally:
            if redis_client:
                await redis_client.close()
                logging.info("Redis 연결 종료")

# 사용 예시 - 컨텍스트 매니저 사용 (리소스 정리 보장)
async def process_tickets_with_resources(company_id: str):
    """리소스 관리를 통한 안전한 티켓 처리"""

    resource_manager = ResourceManager()

    async with resource_manager.managed_http_session(max_concurrent=5) as session, \
               resource_manager.managed_redis_connection("redis://localhost") as redis:

        try:
            # HTTP 요청
            async with session.get(f"https://{company_id}.freshdesk.com/api/v2/tickets") as response:
                tickets = await response.json()

            # Redis 캐싱
            cache_key = f"tickets:{company_id}"
            await redis.setex(cache_key, 3600, json.dumps(tickets))

            logging.info(f"티켓 처리 완료: company_id={company_id}, count={len(tickets)}")
            return tickets

        except Exception as e:
            logging.error(f"티켓 처리 실패: company_id={company_id}, error={e}")
            raise
```

---

## 📊 **로깅 및 모니터링 패턴**

### **1. 구조화된 로깅**

```python
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

class StructuredLogger:
    """구조화된 로깅 클래스"""

    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # JSON 포맷터 설정
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _create_log_entry(
        self,
        level: str,
        message: str,
        company_id: Optional[str] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
        duration_ms: Optional[float] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """구조화된 로그 엔트리 생성"""

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "company_id": company_id or "unknown",
            "user_id": user_id,
            "operation": operation,
            "duration_ms": duration_ms
        }

        # 추가 데이터 병합
        if extra_data:
            # 민감 정보 마스킹
            safe_extra_data = self._mask_sensitive_data(extra_data)
            log_entry.update(safe_extra_data)

        return json.dumps(log_entry, ensure_ascii=False)

    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """민감 정보 마스킹"""
        sensitive_keys = ['api_key', 'password', 'token', 'secret', 'authorization']

        masked_data = {}
        for key, value in data.items():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                masked_data[key] = "*" * 8
            else:
                masked_data[key] = value

        return masked_data

    def info(self, message: str, **kwargs):
        """정보 레벨 로깅"""
        log_entry = self._create_log_entry("INFO", message, **kwargs)
        self.logger.info(log_entry)

    def warning(self, message: str, **kwargs):
        """경고 레벨 로깅"""
        log_entry = self._create_log_entry("WARNING", message, **kwargs)
        self.logger.warning(log_entry)

    def error(self, message: str, **kwargs):
        """에러 레벨 로깅"""
        log_entry = self._create_log_entry("ERROR", message, **kwargs)
        self.logger.error(log_entry)

# 전역 로거 인스턴스
app_logger = StructuredLogger("ai_assistant")

# 사용 예시
def log_api_call(company_id: str, endpoint: str, duration_ms: float, status_code: int):
    """API 호출 로깅"""
    app_logger.info(
        f"API 호출 완료: {endpoint}",
        company_id=company_id,
        operation="api_call",
        duration_ms=duration_ms,
        extra_data={
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_category": "fast" if duration_ms < 1000 else "slow"
        }
    )
```

### **2. 성능 모니터링**

```python
import time
from functools import wraps
from typing import Callable
import asyncio

class PerformanceMonitor:
    """성능 모니터링 클래스"""

    def __init__(self):
        self.metrics = {}

    def track_execution_time(self, operation_name: str, company_id: str = "unknown"):
        """실행 시간 추적 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)

                    duration_ms = (time.time() - start_time) * 1000

                    # 성능 로깅
                    app_logger.info(
                        f"작업 완료: {operation_name}",
                        company_id=company_id,
                        operation=operation_name,
                        duration_ms=duration_ms,
                        extra_data={"status": "success"}
                    )

                    # 성능 임계값 체크
                    if duration_ms > 5000:  # 5초 이상
                        app_logger.warning(
                            f"느린 작업 감지: {operation_name}",
                            company_id=company_id,
                            duration_ms=duration_ms,
                            extra_data={"performance_issue": True}
                        )

                    return result

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000

                    app_logger.error(
                        f"작업 실패: {operation_name}",
                        company_id=company_id,
                        operation=operation_name,
                        duration_ms=duration_ms,
                        extra_data={
                            "status": "failed",
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )

                    raise

            return wrapper
        return decorator

# 전역 성능 모니터
perf_monitor = PerformanceMonitor()

# 사용 예시
@perf_monitor.track_execution_time("ticket_recommendation", company_id="wedosoft")
async def get_ticket_recommendations(company_id: str, query: str) -> dict:
    """티켓 추천 (성능 모니터링 포함)"""

    # 실제 추천 로직
    await asyncio.sleep(2)  # 시뮬레이션

    return {
        "recommendations": [],
        "query": query,
        "company_id": company_id
    }
```

---

## 🔍 **디버깅 도구 및 명령어**

### **FDK 디버깅**

```bash
# 1. FDK 상세 검증
fdk validate --verbose

# 2. 개발 서버 디버그 모드
fdk run --log-level debug --verbose

# 3. 네트워크 요청 로깅
fdk run --enable-network-logs

# 4. 빌드 디버깅
fdk build --verbose

# 5. 패키징 검증
fdk package --verbose
```

### **백엔드 디버깅**

```bash
# 1. 개발 서버 (자동 재로드)
cd backend && source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 2. 로그 레벨 설정
export LOG_LEVEL=DEBUG
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 3. 프로파일링 모드
python -m cProfile -o profile_output.prof api/main.py

# 4. 메모리 사용량 모니터링
python -m tracemalloc api/main.py

# 5. API 엔드포인트 테스트
curl -X POST http://localhost:8000/api/v1/health \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: demo"
```

### **데이터베이스 디버깅**

```python
# Qdrant 연결 테스트
from core.qdrant.qdrant_manager import QdrantManager

async def debug_qdrant_connection():
    """Qdrant 연결 디버깅"""
    try:
        qdrant = QdrantManager()

        # 연결 테스트
        collections = await qdrant.list_collections()
        print(f"연결 성공: 컬렉션 수 = {len(collections)}")

        # 컬렉션 정보
        for collection in collections:
            info = await qdrant.get_collection_info(collection.name)
            print(f"컬렉션: {collection.name}, 점수: {info.points_count}")

        return True

    except Exception as e:
        print(f"Qdrant 연결 실패: {e}")
        return False

# SQLite 연결 테스트
import sqlite3

def debug_sqlite_connection(db_path: str = "data/app.db"):
    """SQLite 연결 디버깅"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 테이블 목록
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"SQLite 테이블: {[table[0] for table in tables]}")

        # 각 테이블 레코드 수
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"테이블 {table_name}: {count}개 레코드")

        conn.close()
        return True

    except Exception as e:
        print(f"SQLite 연결 실패: {e}")
        return False
```

---

## 🔗 **관련 지침서 참조**

- 🚀 `quick-reference.instructions.md` - 에러 처리 핵심 패턴 요약
- 🎨 `fdk-development-patterns.instructions.md` - FDK 특수 에러 처리
- 🐍 `backend-implementation-patterns.instructions.md` - 백엔드 에러 처리
- 📋 `coding-principles-checklist.instructions.md` - 에러 처리 체크리스트

---

_이 지침서는 에러 처리와 디버깅에 특화된 패턴과 도구를 포함합니다. 구체적인 구현 방법은 관련 지침서를 참조하세요._
