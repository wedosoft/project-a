"""
인증 및 보안 관련 유틸리티
"""

import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import logging
from core.config import get_tenant_manager

logger = logging.getLogger(__name__)

# API 키 검증 실패 횟수 추적 (간단한 메모리 기반)
_failed_attempts: Dict[str, Dict[str, Any]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = 300  # 5분


class AuthenticationError(HTTPException):
    """인증 실패 예외"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class AuthorizationError(HTTPException):
    """권한 부족 예외"""
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


def validate_api_key(tenant_id: str, api_key: str, domain: str) -> bool:
    """
    API 키 유효성 검증
    
    Args:
        tenant_id: 테넌트 ID
        api_key: 제공된 API 키
        domain: 요청 도메인
        
    Returns:
        bool: 유효한 경우 True
        
    Raises:
        AuthenticationError: 인증 실패 시
    """
    # 실패 시도 확인
    key = f"{tenant_id}:{domain}"
    if key in _failed_attempts:
        attempts = _failed_attempts[key]
        if attempts['count'] >= MAX_FAILED_ATTEMPTS:
            if time.time() - attempts['last_attempt'] < LOCKOUT_DURATION:
                raise AuthenticationError(
                    f"Too many failed attempts. Try again after {LOCKOUT_DURATION//60} minutes."
                )
            else:
                # 잠금 해제
                del _failed_attempts[key]
    
    try:
        # 테넌트 매니저에서 설정 가져오기
        tenant_manager = get_tenant_manager()
        tenant_config = tenant_manager.get_config(tenant_id)
        
        if not tenant_config:
            raise AuthenticationError("Invalid tenant ID")
        
        # API 키 검증
        expected_api_key = tenant_config.freshdesk_api_key
        if not expected_api_key:
            raise AuthenticationError("API key not configured for tenant")
        
        # 타이밍 공격 방지를 위한 안전한 비교
        is_valid = hmac.compare_digest(api_key, expected_api_key)
        
        # 도메인 검증
        if domain and tenant_config.freshdesk_domain:
            expected_domain = tenant_config.freshdesk_domain.lower()
            provided_domain = domain.lower()
            if not provided_domain.endswith(expected_domain):
                is_valid = False
        
        if not is_valid:
            # 실패 시도 기록
            if key not in _failed_attempts:
                _failed_attempts[key] = {'count': 0, 'last_attempt': 0}
            _failed_attempts[key]['count'] += 1
            _failed_attempts[key]['last_attempt'] = time.time()
            
            raise AuthenticationError("Invalid API key or domain")
        
        # 성공 시 실패 기록 제거
        if key in _failed_attempts:
            del _failed_attempts[key]
        
        return True
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"API key validation error: {e}")
        raise AuthenticationError("Authentication service error")


def generate_request_signature(
    method: str,
    path: str,
    timestamp: int,
    body: Optional[str] = None,
    secret: Optional[str] = None
) -> str:
    """
    요청 서명 생성 (웹훅 검증 등에 사용)
    
    Args:
        method: HTTP 메서드
        path: 요청 경로
        timestamp: Unix 타임스탬프
        body: 요청 본문
        secret: 서명용 비밀 키
        
    Returns:
        str: 서명 문자열
    """
    if not secret:
        secret = secrets.token_urlsafe(32)
    
    # 서명할 문자열 생성
    parts = [
        method.upper(),
        path,
        str(timestamp),
        body or ""
    ]
    string_to_sign = "\n".join(parts)
    
    # HMAC-SHA256 서명
    signature = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def verify_webhook_signature(
    signature: str,
    method: str,
    path: str,
    timestamp: int,
    body: Optional[str] = None,
    secret: Optional[str] = None,
    max_age: int = 300  # 5분
) -> bool:
    """
    웹훅 서명 검증
    
    Args:
        signature: 제공된 서명
        method: HTTP 메서드
        path: 요청 경로
        timestamp: Unix 타임스탬프
        body: 요청 본문
        secret: 서명용 비밀 키
        max_age: 최대 허용 시간차 (초)
        
    Returns:
        bool: 유효한 경우 True
    """
    # 타임스탬프 검증
    current_time = int(time.time())
    if abs(current_time - timestamp) > max_age:
        logger.warning(f"Webhook signature expired: {abs(current_time - timestamp)} seconds old")
        return False
    
    # 서명 재생성
    expected_signature = generate_request_signature(
        method, path, timestamp, body, secret
    )
    
    # 타이밍 공격 방지를 위한 안전한 비교
    return hmac.compare_digest(signature, expected_signature)


def hash_api_key(api_key: str) -> str:
    """
    API 키 해싱 (로깅용)
    
    Args:
        api_key: 원본 API 키
        
    Returns:
        str: 해시된 키의 일부
    """
    if not api_key:
        return "NO_KEY"
    
    # SHA256 해시의 처음 8자만 반환
    hashed = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    return f"{api_key[:4]}...{hashed[:8]}"


def cleanup_failed_attempts():
    """
    오래된 실패 기록 정리
    """
    current_time = time.time()
    keys_to_remove = []
    
    for key, attempts in _failed_attempts.items():
        if current_time - attempts['last_attempt'] > LOCKOUT_DURATION:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del _failed_attempts[key]
    
    if keys_to_remove:
        logger.info(f"Cleaned up {len(keys_to_remove)} expired authentication failure records")