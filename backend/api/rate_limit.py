"""
Rate Limiting 미들웨어 및 유틸리티
"""

import time
import asyncio
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Rate limit 저장소 (실제 운영에서는 Redis 사용 권장)
_rate_limit_storage: Dict[str, Dict[str, any]] = {}
_cleanup_lock = asyncio.Lock()


class RateLimitExceeded(HTTPException):
    """Rate limit 초과 예외"""
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


class RateLimiter:
    """
    Rate Limiter 클래스
    
    토큰 버킷 알고리즘 사용
    """
    
    def __init__(
        self,
        rate: int = 100,  # 분당 요청 수
        burst: int = 10,   # 버스트 허용량
        per: int = 60,     # 시간 윈도우 (초)
        key_func: Optional[callable] = None
    ):
        """
        Args:
            rate: 시간 윈도우당 허용 요청 수
            burst: 순간적으로 허용되는 추가 요청 수
            per: 시간 윈도우 (초)
            key_func: 요청에서 키를 추출하는 함수
        """
        self.rate = rate
        self.burst = burst
        self.per = per
        self.key_func = key_func or self._default_key_func
        self.tokens_per_second = rate / per
        self.max_tokens = rate + burst
    
    @staticmethod
    def _default_key_func(request: Request) -> str:
        """기본 키 생성 함수 (IP + Tenant ID)"""
        client_ip = request.client.host if request.client else "unknown"
        tenant_id = request.headers.get("X-Tenant-ID", "unknown")
        return f"{client_ip}:{tenant_id}"
    
    async def _get_bucket(self, key: str) -> Tuple[float, float]:
        """토큰 버킷 가져오기"""
        current_time = time.time()
        
        if key not in _rate_limit_storage:
            _rate_limit_storage[key] = {
                "tokens": self.max_tokens,
                "last_update": current_time
            }
        
        bucket = _rate_limit_storage[key]
        
        # 토큰 리필
        time_passed = current_time - bucket["last_update"]
        bucket["tokens"] = min(
            self.max_tokens,
            bucket["tokens"] + time_passed * self.tokens_per_second
        )
        bucket["last_update"] = current_time
        
        return bucket["tokens"], current_time
    
    async def _consume_token(self, key: str) -> Tuple[bool, float]:
        """토큰 소비"""
        tokens, current_time = await self._get_bucket(key)
        
        if tokens >= 1:
            _rate_limit_storage[key]["tokens"] = tokens - 1
            return True, 0
        else:
            # 다음 토큰까지 대기 시간 계산
            wait_time = (1 - tokens) / self.tokens_per_second
            return False, wait_time
    
    async def check_rate_limit(self, request: Request) -> None:
        """Rate limit 확인"""
        key = self.key_func(request)
        
        allowed, wait_time = await self._consume_token(key)
        
        if not allowed:
            retry_after = int(wait_time) + 1
            logger.warning(f"Rate limit exceeded for {key}, retry after {retry_after}s")
            raise RateLimitExceeded(retry_after)
        
        # 주기적으로 오래된 항목 정리
        if len(_rate_limit_storage) > 10000:  # 메모리 보호
            await self._cleanup_old_entries()
    
    async def _cleanup_old_entries(self):
        """오래된 항목 정리"""
        async with _cleanup_lock:
            current_time = time.time()
            cutoff_time = current_time - self.per * 2
            
            keys_to_remove = [
                key for key, bucket in _rate_limit_storage.items()
                if bucket["last_update"] < cutoff_time
            ]
            
            for key in keys_to_remove:
                del _rate_limit_storage[key]
            
            if keys_to_remove:
                logger.info(f"Cleaned up {len(keys_to_remove)} old rate limit entries")


# 사전 정의된 Rate Limiter 인스턴스들

# 글로벌 Rate Limiter (모든 요청)
global_limiter = RateLimiter(
    rate=1000,    # 분당 1000개 요청
    burst=50,     # 버스트 50개
    per=60
)

# API 엔드포인트별 Rate Limiter
api_limiter = RateLimiter(
    rate=100,     # 분당 100개 요청
    burst=10,     # 버스트 10개
    per=60
)

# 무거운 작업용 Rate Limiter (예: 요약, 임베딩)
heavy_limiter = RateLimiter(
    rate=20,      # 분당 20개 요청
    burst=5,      # 버스트 5개
    per=60
)

# 인증 실패용 Rate Limiter
auth_limiter = RateLimiter(
    rate=5,       # 분당 5회 시도
    burst=2,      # 버스트 2개
    per=60,
    key_func=lambda req: req.headers.get("X-Tenant-ID", "unknown")
)


class RateLimitMiddleware:
    """Rate Limit 미들웨어"""
    
    def __init__(self, app, limiter: RateLimiter = None):
        self.app = app
        self.limiter = limiter or global_limiter
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # health check 등 제외
            if request.url.path in ["/health", "/metrics", "/"]:
                await self.app(scope, receive, send)
                return
            
            try:
                await self.limiter.check_rate_limit(request)
                await self.app(scope, receive, send)
            except RateLimitExceeded as e:
                response = JSONResponse(
                    status_code=e.status_code,
                    content={"detail": e.detail},
                    headers=e.headers
                )
                await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)


def create_endpoint_limiter(
    rate: int = 60,
    burst: int = 10,
    per: int = 60
) -> RateLimiter:
    """
    엔드포인트별 커스텀 Rate Limiter 생성
    
    사용 예:
    ```python
    from fastapi import Depends
    
    custom_limiter = create_endpoint_limiter(rate=30, burst=5)
    
    @app.get("/api/heavy-operation")
    async def heavy_operation(
        request: Request,
        _: None = Depends(custom_limiter.check_rate_limit)
    ):
        ...
    ```
    """
    return RateLimiter(rate=rate, burst=burst, per=per)


# Rate limit 상태 확인 함수
async def get_rate_limit_status(key: str) -> Dict[str, any]:
    """현재 rate limit 상태 확인"""
    if key not in _rate_limit_storage:
        return {
            "tokens": global_limiter.max_tokens,
            "max_tokens": global_limiter.max_tokens,
            "rate": global_limiter.rate,
            "per": global_limiter.per
        }
    
    bucket = _rate_limit_storage[key]
    current_time = time.time()
    time_passed = current_time - bucket["last_update"]
    current_tokens = min(
        global_limiter.max_tokens,
        bucket["tokens"] + time_passed * global_limiter.tokens_per_second
    )
    
    return {
        "tokens": current_tokens,
        "max_tokens": global_limiter.max_tokens,
        "rate": global_limiter.rate,
        "per": global_limiter.per
    }