"""
FastAPI 의존성 함수 정의

모든 엔드포인트에서 공통으로 사용하는 의존성 함수들을 정의합니다.
"""

from typing import Optional
from fastapi import Header, HTTPException
import logging

from core.utils import extract_company_id

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


async def get_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID"),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_zendesk_domain: Optional[str] = Header(None, alias="X-Zendesk-Domain")
) -> str:
    """
    멀티테넌트 보안을 위한 company_id 자동 추출
    
    지침서에 따른 우선순위:
    1. X-Company-ID 헤더 (명시적 지정)
    2. X-Freshdesk-Domain 헤더에서 자동 추출
    3. X-Zendesk-Domain 헤더에서 자동 추출
    4. 환경변수 FRESHDESK_DOMAIN에서 자동 추출 (fallback)
    
    Args:
        x_company_id: 명시적으로 지정된 company_id 헤더
        x_freshdesk_domain: Freshdesk 도메인 헤더
        x_zendesk_domain: Zendesk 도메인 헤더
        
    Returns:
        str: 추출된 company_id
        
    Raises:
        HTTPException: company_id를 추출할 수 없는 경우
    """
    # 1. 명시적 헤더 우선
    if x_company_id:
        logger.info(f"명시적 X-Company-ID 헤더 사용: {x_company_id}")
        return x_company_id
    
    # 2. 도메인 헤더에서 자동 추출
    domain_headers = [
        ("X-Freshdesk-Domain", x_freshdesk_domain),
        ("X-Zendesk-Domain", x_zendesk_domain),
    ]
    
    for header_name, domain in domain_headers:
        if domain:
            try:
                company_id = extract_company_id(domain)
                logger.info(f"{header_name} 헤더에서 company_id 자동 추출: {domain} → {company_id}")
                return company_id
            except ValueError as e:
                logger.warning(f"{header_name} 헤더 도메인 추출 실패 ({domain}): {e}")
                continue
    
    # 3. 환경변수 fallback (개발환경용)
    import os
    default_domain = os.getenv("FRESHDESK_DOMAIN")
    if default_domain:
        try:
            company_id = extract_company_id(default_domain)
            logger.info(f"환경변수 FRESHDESK_DOMAIN에서 company_id 추출: {default_domain} → {company_id}")
            return company_id
        except ValueError as e:
            logger.warning(f"환경변수 FRESHDESK_DOMAIN 추출 실패 ({default_domain}): {e}")
    
    # 4. 모든 방법 실패 시 에러
    raise HTTPException(
        status_code=400,
        detail="company_id를 추출할 수 없습니다. X-Company-ID 헤더 또는 유효한 플랫폼 도메인 헤더를 제공해주세요."
    )


async def get_platform(
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
    x_freshdesk_domain: Optional[str] = Header(
        None, alias="X-Freshdesk-Domain"
    ),
    x_zendesk_domain: Optional[str] = Header(None, alias="X-Zendesk-Domain")
) -> str:
    """
    현재 요청의 플랫폼을 반환합니다.
    우선순위: X-Platform > X-Freshdesk-Domain > X-Zendesk-Domain
    > "freshdesk" (기본값)
    하위 호환성을 위해 기존 Freshdesk 헤더도 지원합니다.
    """
    if x_platform:
        return x_platform.lower()
    elif x_freshdesk_domain:
        return "freshdesk"
    elif x_zendesk_domain:
        return "zendesk"
    else:
        # 기본값으로 freshdesk 사용 (하위 호환성)
        return "freshdesk"


# 하위 호환성을 위한 별칭
get_llm_router = get_llm_manager
