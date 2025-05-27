"""
예외 처리 모듈

이 모듈은 애플리케이션 전체에서 사용되는 커스텀 예외 클래스를 정의합니다.
표준화된 예외 처리를 통해 일관된 에러 응답을 제공하는 것이 목적입니다.
"""

from typing import Any, Dict, Optional

from fastapi import HTTPException, status


class BaseAppException(Exception):
    """
    애플리케이션의 기본 예외 클래스입니다.
    모든 커스텀 예외는 이 클래스를 상속받아야 합니다.
    """
    def __init__(
        self, 
        message: str = "내부 서버 오류가 발생했습니다.",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_http_exception(self) -> HTTPException:
        """
        현재 예외를 FastAPI HTTPException으로 변환합니다.
        
        Returns:
            HTTPException: HTTP 예외 객체
        """
        return HTTPException(
            status_code=self.status_code,
            detail={
                "message": self.message,
                "details": self.details
            }
        )


class ConfigurationError(BaseAppException):
    """
    설정 관련 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "설정 오류가 발생했습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class AuthenticationError(BaseAppException):
    """
    인증 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "인증에 실패했습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details
        )


class AuthorizationError(BaseAppException):
    """
    권한 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "이 작업을 수행할 권한이 없습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details
        )


class ResourceNotFoundError(BaseAppException):
    """
    요청한 리소스를 찾을 수 없을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "요청한 리소스를 찾을 수 없습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class ValidationError(BaseAppException):
    """
    입력 데이터 검증에 실패했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "입력 데이터 검증에 실패했습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )


class ExternalServiceError(BaseAppException):
    """
    외부 서비스(Freshdesk, OpenAI 등) 호출 시 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "외부 서비스 호출 중 오류가 발생했습니다.",
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            details=details
        )


class VectorDBError(BaseAppException):
    """
    벡터 데이터베이스 관련 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "벡터 데이터베이스 작업 중 오류가 발생했습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class LLMError(BaseAppException):
    """
    LLM 관련 오류가 발생했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "AI 모델 호출 중 오류가 발생했습니다.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details
        )


class RateLimitExceededError(BaseAppException):
    """
    요청 속도 제한을 초과했을 때 발생하는 예외입니다.
    """
    def __init__(
        self, 
        message: str = "요청 속도 제한을 초과했습니다. 잠시 후 다시 시도해주세요.",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details
        )
