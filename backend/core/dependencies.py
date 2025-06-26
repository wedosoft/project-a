"""
의존성 함수 모듈

이 모듈은 FastAPI 경로 함수에서 사용할 수 있는 의존성 함수들을 제공합니다.
인증, 권한 검사, 공통 파라미터 처리 등에 사용됩니다.
"""

import time
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request, status

from core.utils import setup_logger
from core.database.tenant_context import TenantContext

# 로거 설정
logger = setup_logger(__name__)


async def get_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
) -> TenantContext:
    """
    HTTP 헤더에서 테넌트 컨텍스트 추출 및 검증
    
    Required Headers:
        X-Tenant-ID: 테넌트 식별자 (필수)
        X-Platform: 플랫폼 식별자 (선택, 기본값: freshdesk)
        
    Args:
        x_tenant_id: X-Tenant-ID 헤더 값
        x_platform: X-Platform 헤더 값
        
    Returns:
        TenantContext: 테넌트 컨텍스트 객체
        
    Raises:
        HTTPException: 테넌트 ID가 누락되거나 유효하지 않은 경우
    """
    # 1. tenant_id 검증
    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Tenant-ID header"
        )
    
    # 2. tenant_id 유효성 검증
    if not _validate_tenant_id(x_tenant_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tenant_id format: {x_tenant_id}"
        )
    
    # 3. 플랫폼 기본값 설정
    platform = x_platform or "freshdesk"
    
    # 4. 테넌트 컨텍스트 생성
    try:
        # tenant_id를 int로 변환 (현재는 string이지만 TenantContext는 int를 요구)
        # 간단한 해시 변환 사용
        tenant_id_int = hash(x_tenant_id) % (10**9)  # 임시 변환 로직
        
        return TenantContext(
            tenant_id=tenant_id_int,
            platform=platform
        )
    except Exception as e:
        logger.error(f"Failed to create tenant context for {x_tenant_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create tenant context"
        )


def _validate_tenant_id(tenant_id: str) -> bool:
    """tenant_id 유효성 검증"""
    if not tenant_id:
        return False
    
    # 기본 규칙: 2-50자, 영숫자 및 하이픈만 허용
    if not (2 <= len(tenant_id) <= 50):
        return False
    
    import re
    if not re.match(r'^[a-zA-Z0-9-]+$', tenant_id):
        return False
    
    # 예약어 확인
    reserved_words = {'admin', 'api', 'www', 'mail', 'ftp', 'localhost', 'test'}
    if tenant_id.lower() in reserved_words:
        return False
    
    return True


async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")
) -> str:
    """
    요청 헤더에서 테넌트 ID를 추출합니다.
    
    Args:
        x_tenant_id: X-Tenant-ID 헤더 값
        
    Returns:
        str: 테넌트 ID
        
    Raises:
        HTTPException: 테넌트 ID가 누락된 경우 400 오류 발생
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID 헤더가 필요합니다."
        )
    return x_tenant_id


async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """
    요청 헤더에서 API 키를 추출합니다.
    
    Args:
        x_api_key: X-API-Key 헤더 값
        
    Returns:
        str: API 키
        
    Raises:
        HTTPException: API 키가 누락된 경우 401 오류 발생
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key 헤더가 필요합니다."
        )
    
    # TODO: API 키 유효성 검증 로직 추가
    
    return x_api_key


async def validate_tenant_access(
    tenant_id: str = Depends(get_tenant_id),
    api_key: str = Depends(get_api_key)
) -> Dict[str, str]:
    """
    API 키가 특정 테넌트에 접근할 권한이 있는지 확인합니다.
    
    Args:
        tenant_id: 테넌트 ID
        api_key: API 키
        
    Returns:
        Dict[str, str]: 테넌트 ID와 API 키를 포함한 딕셔너리
        
    Raises:
        HTTPException: 접근 권한이 없는 경우 403 오류 발생
    """
    # TODO: API 키와 테넌트 ID의 매핑 확인 로직 구현
    
    # 현재는 간단한 검증만 수행 (실제로는 데이터베이스나 캐시에서 확인해야 함)
    auth_info = {
        "tenant_id": tenant_id,
        "api_key": api_key
    }
    
    return auth_info


async def get_request_id(request: Request) -> str:
    """
    요청 ID를 가져옵니다. 헤더에 요청 ID가 없으면 새로 생성합니다.
    
    Args:
        request: FastAPI 요청 객체
        
    Returns:
        str: 요청 ID
    """
    # 요청 객체에서 요청 ID 가져오기 (미들웨어에서 설정됨)
    request_id = request.headers.get("X-Request-ID")
    
    if not request_id:
        # 요청 ID가 없으면 새로 생성 (이 경우는 발생하지 않아야 함)
        import uuid
        request_id = str(uuid.uuid4())
        logger.warning(f"Missing X-Request-ID header, generated new one: {request_id}")
    
    return request_id


async def get_current_timestamp() -> int:
    """
    현재 Unix 타임스탬프를 반환합니다.
    
    Returns:
        int: Unix 타임스탬프 (초 단위)
    """
    return int(time.time())


# 공통 쿼리 파라미터
async def get_pagination_params(
    page: int = 1,
    per_page: int = 10,
    max_per_page: int = 100
) -> Dict[str, int]:
    """
    페이지네이션 파라미터를 처리하고 검증합니다.
    
    Args:
        page: 페이지 번호 (1부터 시작)
        per_page: 페이지당 항목 수
        max_per_page: 페이지당 최대 항목 수
        
    Returns:
        Dict[str, int]: 페이지네이션 파라미터
    """
    if page < 1:
        page = 1
        
    if per_page < 1:
        per_page = 10
        
    if per_page > max_per_page:
        per_page = max_per_page
        
    return {
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page
    }


async def get_ticket_permissions(
    auth_info: Dict[str, str] = Depends(validate_tenant_access),
    ticket_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    티켓에 대한 권한을 확인합니다.
    
    Args:
        auth_info: 인증 정보
        ticket_id: 티켓 ID (선택적)
        
    Returns:
        Dict[str, Any]: 권한 정보
    """
    # TODO: 티켓 권한 확인 로직 구현
    
    # 기본적으로 조회 권한만 제공
    permissions = {
        "can_view": True,
        "can_edit": False,
        "can_delete": False
    }
    
    # 실제 환경에서는 역할 기반 접근 제어 구현
    
    return permissions


# =================================================================
# 호환성 함수들 (레거시 코드 지원)
# =================================================================

async def get_company_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID")
) -> str:
    """
    레거시 호환성을 위한 company_id 함수
    내부적으로 get_tenant_id를 호출합니다.
    """
    # 새 헤더를 우선하고, 없으면 레거시 헤더 확인
    tenant_id = x_tenant_id or x_company_id
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID 또는 X-Company-ID 헤더가 필요합니다."
        )
    return tenant_id

async def validate_company_access(
    tenant_id: str = Depends(get_company_id),  # 내부적으로 새 로직 사용
    api_key: str = Depends(get_api_key)
) -> Dict[str, str]:
    """
    레거시 호환성을 위한 company 접근 검증 함수
    내부적으로 validate_tenant_access를 호출합니다.
    """
    # validate_tenant_access는 이미 async 함수이므로 직접 호출
    auth_info = {
        "tenant_id": tenant_id,
        "api_key": api_key
    }
    return auth_info
