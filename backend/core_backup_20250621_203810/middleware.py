"""
미들웨어 모듈

이 모듈은 FastAPI 애플리케이션에서 사용되는 미들웨어를 정의합니다.
요청 처리 전후에 공통 로직을 수행하는 컴포넌트들을 포함합니다.
"""

import json
import logging
import time
import uuid
from typing import Callable, Dict, Optional, Set

from cachetools import TTLCache
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.utils import setup_logger

# 로거 설정
logger = setup_logger(__name__)

# 요청 ID 헤더 이름
REQUEST_ID_HEADER = "X-Request-ID"

# 레이트 리미팅을 위한 인메모리 캐시
rate_limit_cache = TTLCache(maxsize=1000, ttl=60)  # 1분 TTL


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    요청과 응답에 대한 정보를 로깅하는 미들웨어입니다.
    각 요청에 고유한 요청 ID를 할당하고 실행 시간을 측정합니다.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 요청 ID 생성 또는 재사용
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        
        # 시작 시간 기록
        start_time = time.time()
        
        # 요청 로깅
        logger.info(
            f"요청 시작: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host,
                "query_params": str(request.query_params)
            }
        )
        
        # 응답 처리
        try:
            response = await call_next(request)
            
            # 실행 시간 계산 (밀리초)
            process_time = (time.time() - start_time) * 1000
            
            # 응답 로깅
            logger.info(
                f"요청 완료: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time_ms": process_time
                }
            )
            
            # 응답 헤더에 요청 ID와 처리 시간 추가
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # 예외 발생 시 로깅
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"요청 처리 중 오류 발생: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "process_time_ms": process_time
                },
                exc_info=True
            )
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    요청 속도를 제한하는 미들웨어입니다.
    설정된 기간 내에 허용된 요청 수를 초과하면 429 상태 코드를 반환합니다.
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        calls_per_minute: int = 60,
        exempt_paths: Optional[Set[str]] = None
    ):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.exempt_paths = exempt_paths or {"/health", "/metrics"}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 특정 경로는 속도 제한에서 제외
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # 클라이언트 식별자 (API 키 또는 IP 주소)
        client_id = (
            request.headers.get("X-API-Key") or 
            request.headers.get("Authorization") or 
            request.client.host
        )
        
        # 속도 제한 검사
        current_time = time.time()
        rate_limit_key = f"{client_id}:{request.url.path}"
        
        client_requests = rate_limit_cache.get(rate_limit_key, [])
        
        # 지난 1분 이내의 요청만 유지
        client_requests = [ts for ts in client_requests if current_time - ts < 60]
        
        # 요청 수 검사
        if len(client_requests) >= self.calls_per_minute:
            # 속도 제한 초과
            logger.warning(
                f"속도 제한 초과: {client_id}, {request.url.path}, {len(client_requests)}/{self.calls_per_minute}"
            )
            
            # 429 응답 반환
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "요청 속도 제한을 초과했습니다. 잠시 후 다시 시도해주세요.",
                    "error_code": "RATE_LIMIT_EXCEEDED"
                }),
                status_code=429,
                media_type="application/json"
            )
        
        # 현재 요청 시간 추가
        client_requests.append(current_time)
        rate_limit_cache[rate_limit_key] = client_requests
        
        # 요청 처리
        return await call_next(request)


class CompanyIdVerificationMiddleware(BaseHTTPMiddleware):
    """
    회사 ID의 유효성을 검증하고 격리를 보장하는 미들웨어입니다.
    API 키와 회사 ID의 매핑을 확인하여 올바른 접근을 보장합니다.
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        exempt_paths: Optional[Set[str]] = None
    ):
        super().__init__(app)
        self.exempt_paths = exempt_paths or {"/health", "/metrics", "/docs", "/redoc", "/openapi.json"}
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 특정 경로는 검증에서 제외
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # API 키와 회사 ID 확인
        api_key = request.headers.get("X-API-Key")
        company_id = request.headers.get("X-Company-ID")
        
        # TODO: API 키와 회사 ID 매핑 검증 로직 구현
        # 현재는 간단하게 존재 여부만 확인
        if not api_key or not company_id:
            # 필요한 헤더가 없음
            return Response(
                content=json.dumps({
                    "success": False,
                    "error": "인증 정보가 누락되었습니다. X-API-Key와 X-Company-ID 헤더가 필요합니다.",
                    "error_code": "MISSING_AUTH_INFO"
                }),
                status_code=401,
                media_type="application/json"
            )
        
        # 요청 본문에 포함된 회사 ID 확인 (POST 요청인 경우)
        if request.method == "POST":
            try:
                body = await request.json()
                body_company_id = body.get("company_id")
                
                if body_company_id and body_company_id != company_id:
                    # 헤더와 본문의 회사 ID가 일치하지 않음
                    return Response(
                        content=json.dumps({
                            "success": False,
                            "error": "회사 ID가 일치하지 않습니다. 헤더와 요청 본문의 company_id가 달라 권한이 없습니다.",
                            "error_code": "COMPANY_ID_MISMATCH"
                        }),
                        status_code=403,
                        media_type="application/json"
                    )
            except:
                # 요청 본문이 JSON이 아니거나 파싱 실패
                pass
        
        # 요청 처리
        return await call_next(request)


def setup_middlewares(app: FastAPI) -> None:
    """
    FastAPI 애플리케이션에 모든 미들웨어를 설정합니다.
    
    Args:
        app: FastAPI 애플리케이션 인스턴스
    """
    # CORS 미들웨어 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Gzip 압축 미들웨어 설정
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000  # 최소 1KB 이상인 응답만 압축
    )
    
    # 로깅 미들웨어 설정
    app.add_middleware(LoggingMiddleware)
    
    # 속도 제한 미들웨어 설정
    app.add_middleware(
        RateLimitMiddleware,
        calls_per_minute=60  # 분당 최대 60회 요청
    )
    
    # 회사 ID 검증 미들웨어 설정
    app.add_middleware(CompanyIdVerificationMiddleware)
