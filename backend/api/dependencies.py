"""
FastAPI 의존성 함수 정의

모든 엔드포인트에서 공통으로 사용하는 의존성 함수들을 정의합니다.
"""

from typing import Optional
from fastapi import Header, HTTPException, Depends
import logging
from core.config import get_tenant_manager, TenantConfig

from core.utils import extract_tenant_id

# 로거 설정
logger = logging.getLogger(__name__)

# 전역 변수들 (main.py에서 설정됨)
_vector_db = None
_fetcher = None
_llm_manager = None
_ticket_context_cache = None
_ticket_summary_cache = None
_hybrid_search_manager = None


def set_global_dependencies(
    vector_db,
    fetcher,
    llm_manager,
    ticket_context_cache,
    ticket_summary_cache,
    hybrid_search_manager=None,
):
    """
    main.py에서 전역 의존성들을 설정하는 함수
    """
    global _vector_db, _fetcher, _llm_manager, _ticket_context_cache, _ticket_summary_cache, _hybrid_search_manager
    _vector_db = vector_db
    _fetcher = fetcher
    _llm_manager = llm_manager
    _ticket_context_cache = ticket_context_cache
    _ticket_summary_cache = ticket_summary_cache
    _hybrid_search_manager = hybrid_search_manager


def get_vector_db():
    """벡터 데이터베이스 의존성"""
    if _vector_db is None:
        raise RuntimeError(
            "Vector DB가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _vector_db


def get_fetcher():
    """Freshdesk fetcher 의존성"""
    if _fetcher is None:
        raise RuntimeError(
            "Fetcher가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _fetcher


def get_llm_manager():
    """LLM 매니저 의존성"""
    if _llm_manager is None:
        raise RuntimeError(
            "LLM Manager가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _llm_manager


def get_ticket_context_cache():
    """티켓 컨텍스트 캐시 의존성"""
    if _ticket_context_cache is None:
        raise RuntimeError(
            "Ticket context cache가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _ticket_context_cache


def get_ticket_summary_cache():
    """티켓 요약 캐시 의존성"""
    if _ticket_summary_cache is None:
        raise RuntimeError(
            "Ticket summary cache가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _ticket_summary_cache


def get_hybrid_search_manager():
    """하이브리드 검색 매니저 의존성"""
    if _hybrid_search_manager is None:
        raise RuntimeError(
            "Hybrid search manager가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _hybrid_search_manager


async def get_tenant_id(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", description="테넌트 ID (필수)")
) -> str:
    """
    멀티테넌트 보안을 위한 tenant_id
    
    Args:
        x_tenant_id: 테넌트 ID 헤더 (필수)
        
    Returns:
        str: 테넌트 ID
    """
    logger.info(f"X-Tenant-ID 헤더 사용: {x_tenant_id}")
    return x_tenant_id


async def get_platform(
    x_platform: str = Header(..., alias="X-Platform", description="플랫폼 식별자 (필수, freshdesk만 지원)")
) -> str:
    """
    현재 요청의 플랫폼을 반환합니다 (Freshdesk 전용)
    
    Args:
        x_platform: 플랫폼 식별자 헤더 (필수, "freshdesk"만 허용)
        
    Returns:
        str: 플랫폼 식별자 ("freshdesk"로 고정)
    """
    platform = x_platform.lower()
    if platform != "freshdesk":
        logger.warning(f"지원하지 않는 플랫폼 요청: {platform}, freshdesk로 설정")
        platform = "freshdesk"
    logger.info(f"X-Platform 헤더 사용: {platform} (Freshdesk 전용)")
    return platform


async def get_api_key(
    x_api_key: str = Header(..., alias="X-API-Key", description="API 키 (필수)")
) -> str:
    """
    API 키를 반환합니다
    
    Args:
        x_api_key: API 키 헤더 (필수)
        
    Returns:
        str: API 키
    """
    logger.info("X-API-Key 헤더 사용")
    return x_api_key


async def get_domain(
    x_domain: str = Header(..., alias="X-Domain", description="플랫폼 도메인 (필수, 예: wedosoft.freshdesk.com)")
) -> str:
    """
    도메인을 반환합니다
    
    Args:
        x_domain: 도메인 헤더 (필수)
        
    Returns:
        str: 도메인
    """
    logger.info(f"X-Domain 헤더 사용: {x_domain}")
    return x_domain


async def get_tenant_config(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform), 
    domain: str = Depends(get_domain),
    api_key: str = Depends(get_api_key)
) -> TenantConfig:
    """
    헤더에서 테넌트 정보를 받아 TenantConfig 객체를 생성합니다.
    
    멀티테넌트 환경에서 각 요청별로 테넌트 설정을 제공하는 핵심 함수입니다.
    
    Args:
        tenant_id: X-Tenant-ID 헤더
        platform: X-Platform 헤더
        domain: X-Domain 헤더
        api_key: X-API-Key 헤더
        
    Returns:
        TenantConfig: 테넌트별 설정 객체
    """
    tenant_manager = get_tenant_manager()
    
    # 헤더 기반 설정 생성 (멀티테넌트의 핵심)
    tenant_config = tenant_manager.get_config_from_headers(
        tenant_id=tenant_id,
        platform=platform,
        domain=domain,
        api_key=api_key
    )
    
    logger.info(f"테넌트 설정 로드 완료: {tenant_id} ({platform})")
    return tenant_config


# 하위 호환성을 위한 별칭
get_llm_router = get_llm_manager

# Freshdesk 전용 별칭 (하위 호환성)
async def get_freshdesk_config(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform), 
    domain: str = Depends(get_domain),
    api_key: str = Depends(get_api_key)
) -> TenantConfig:
    """
    Freshdesk 설정을 반환합니다 (get_tenant_config의 별칭)
    
    이 함수는 하위 호환성을 위해 제공되며, 
    내부적으로 get_tenant_config를 호출합니다.
    
    Args:
        tenant_id: X-Tenant-ID 헤더
        platform: X-Platform 헤더 (freshdesk로 고정)
        domain: X-Domain 헤더
        api_key: X-API-Key 헤더
        
    Returns:
        TenantConfig: 테넌트별 설정 객체
    """
    return await get_tenant_config(tenant_id, platform, domain, api_key)
