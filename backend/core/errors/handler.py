"""
향상된 에러 핸들링 시스템

사용자 친화적 에러 메시지, 구조화된 에러 응답, 성능 모니터링을 제공합니다.
"""

import time
import logging
import traceback
from typing import Dict, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass, asdict
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """표준 에러 코드"""
    # 일반적인 에러
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # 서비스별 에러
    VECTOR_DB_ERROR = "VECTOR_DB_ERROR"
    LLM_SERVICE_ERROR = "LLM_SERVICE_ERROR"
    FRESHDESK_API_ERROR = "FRESHDESK_API_ERROR"
    CACHE_ERROR = "CACHE_ERROR"
    
    # 비즈니스 로직 에러
    TENANT_NOT_FOUND = "TENANT_NOT_FOUND"
    TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    SEARCH_FAILED = "SEARCH_FAILED"


@dataclass
class ErrorDetail:
    """에러 상세 정보"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: float = None
    request_id: Optional[str] = None
    user_message: Optional[str] = None  # 사용자에게 보여줄 친화적 메시지
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class BusinessError(Exception):
    """비즈니스 로직 에러"""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        status_code: int = 400
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.user_message = user_message or self._get_default_user_message(code)
        self.status_code = status_code
        super().__init__(message)
    
    def _get_default_user_message(self, code: ErrorCode) -> str:
        """기본 사용자 메시지 반환"""
        messages = {
            ErrorCode.TENANT_NOT_FOUND: "조직 정보를 찾을 수 없습니다. 관리자에게 문의해주세요.",
            ErrorCode.TICKET_NOT_FOUND: "요청하신 티켓을 찾을 수 없습니다.",
            ErrorCode.INSUFFICIENT_CONTEXT: "충분한 정보가 없어 답변을 생성할 수 없습니다.",
            ErrorCode.SEARCH_FAILED: "검색 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
            ErrorCode.LLM_SERVICE_ERROR: "AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요.",
            ErrorCode.FRESHDESK_API_ERROR: "Freshdesk 연동 중 오류가 발생했습니다.",
            ErrorCode.RATE_LIMIT_EXCEEDED: "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
        }
        return messages.get(code, "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
    
    def to_detail(self, request_id: Optional[str] = None) -> ErrorDetail:
        """ErrorDetail 객체로 변환"""
        return ErrorDetail(
            code=self.code.value,
            message=self.message,
            details=self.details,
            request_id=request_id,
            user_message=self.user_message
        )


class ErrorHandler:
    """중앙 에러 핸들러"""
    
    def __init__(self):
        self.error_stats = {
            "total_errors": 0,
            "errors_by_code": {},
            "errors_by_endpoint": {}
        }
    
    async def handle_error(
        self,
        error: Exception,
        request: Optional[Request] = None,
        request_id: Optional[str] = None
    ) -> JSONResponse:
        """에러 처리 및 응답 생성"""
        
        # 통계 업데이트
        self.error_stats["total_errors"] += 1
        
        if isinstance(error, BusinessError):
            # 비즈니스 에러 처리
            error_detail = error.to_detail(request_id)
            self._update_error_stats(error.code.value, request)
            
            logger.warning(
                f"비즈니스 에러 발생: {error.code.value} - {error.message}",
                extra={
                    "error_code": error.code.value,
                    "request_id": request_id,
                    "details": error.details
                }
            )
            
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": asdict(error_detail),
                    "success": False
                }
            )
        
        elif isinstance(error, HTTPException):
            # FastAPI HTTPException 처리
            error_detail = ErrorDetail(
                code="HTTP_ERROR",
                message=str(error.detail),
                request_id=request_id,
                user_message="요청을 처리할 수 없습니다."
            )
            self._update_error_stats("HTTP_ERROR", request)
            
            logger.warning(
                f"HTTP 에러 발생: {error.status_code} - {error.detail}",
                extra={"request_id": request_id}
            )
            
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error": asdict(error_detail),
                    "success": False
                }
            )
        
        else:
            # 예상치 못한 에러 처리
            error_detail = ErrorDetail(
                code=ErrorCode.UNKNOWN_ERROR.value,
                message="Internal server error",
                request_id=request_id,
                user_message="서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
            )
            self._update_error_stats(ErrorCode.UNKNOWN_ERROR.value, request)
            
            logger.error(
                f"예상치 못한 에러 발생: {type(error).__name__} - {str(error)}",
                extra={
                    "request_id": request_id,
                    "traceback": traceback.format_exc()
                }
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": asdict(error_detail),
                    "success": False
                }
            )
    
    def _update_error_stats(self, error_code: str, request: Optional[Request]):
        """에러 통계 업데이트"""
        # 에러 코드별 통계
        if error_code not in self.error_stats["errors_by_code"]:
            self.error_stats["errors_by_code"][error_code] = 0
        self.error_stats["errors_by_code"][error_code] += 1
        
        # 엔드포인트별 통계
        if request:
            endpoint = f"{request.method} {request.url.path}"
            if endpoint not in self.error_stats["errors_by_endpoint"]:
                self.error_stats["errors_by_endpoint"][endpoint] = 0
            self.error_stats["errors_by_endpoint"][endpoint] += 1
    
    def get_error_stats(self) -> Dict[str, Any]:
        """에러 통계 반환"""
        return self.error_stats.copy()
    
    def reset_stats(self):
        """에러 통계 초기화"""
        self.error_stats = {
            "total_errors": 0,
            "errors_by_code": {},
            "errors_by_endpoint": {}
        }


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """에러 핸들링 미들웨어"""
    
    def __init__(self, app, error_handler: ErrorHandler):
        super().__init__(app)
        self.error_handler = error_handler
    
    async def dispatch(self, request: Request, call_next):
        """요청 처리 및 에러 핸들링"""
        request_id = f"req_{int(time.time() * 1000000)}"  # 고유한 요청 ID 생성
        
        # 헬스체크는 로그에서 제외 (노이즈 방지)
        is_health_check = request.url.path == "/health"
        
        # 요청 정보 로깅 (헬스체크 제외)
        start_time = time.time()
        if not is_health_check:
            logger.info(
                f"요청 시작: {request.method} {request.url.path}",
                extra={"request_id": request_id}
            )
        
        try:
            # 요청 처리
            response = await call_next(request)
            
            # 성공 응답 로깅 (헬스체크 제외)
            process_time = time.time() - start_time
            if not is_health_check:
                logger.info(
                    f"요청 완료: {request.method} {request.url.path} - "
                    f"{response.status_code} ({process_time:.3f}s)",
                    extra={
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "process_time": process_time
                    }
                )
            
            return response
            
        except Exception as error:
            # 에러 처리
            process_time = time.time() - start_time
            logger.error(
                f"요청 실패: {request.method} {request.url.path} - "
                f"{type(error).__name__} ({process_time:.3f}s)",
                extra={
                    "request_id": request_id,
                    "error_type": type(error).__name__,
                    "process_time": process_time
                }
            )
            
            return await self.error_handler.handle_error(error, request, request_id)


# 전역 에러 핸들러 인스턴스
global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """전역 에러 핸들러 반환"""
    return global_error_handler
