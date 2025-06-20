"""
FastAPI 의존성 함수 정의

모든 엔드포인트에서 공통으로 사용하는 의존성 함수들을 정의합니다.
"""

from typing import Optional
from fastapi import Header

# 전역 변수들 (main.py에서 설정됨)
_vector_db = None
_fetcher = None
_llm_router = None
_ticket_context_cache = None
_ticket_summary_cache = None


def set_global_dependencies(
    vector_db,
    fetcher,
    llm_router,
    ticket_context_cache,
    ticket_summary_cache,
):
    """
    main.py에서 전역 의존성들을 설정하는 함수
    """
    global _vector_db, _fetcher, _llm_router, _ticket_context_cache, _ticket_summary_cache
    _vector_db = vector_db
    _fetcher = fetcher
    _llm_router = llm_router
    _ticket_context_cache = ticket_context_cache
    _ticket_summary_cache = ticket_summary_cache


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


def get_llm_router():
    """LLM 라우터 의존성"""
    if _llm_router is None:
        raise RuntimeError(
            "LLM Router가 초기화되지 않았습니다. main.py에서 set_global_dependencies를 호출해주세요."
        )
    return _llm_router


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


async def get_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID")
) -> str:
    """
    현재 사용자의 회사 ID를 반환합니다.
    X-Company-ID 헤더가 제공되지 않으면 "default" 값을 사용합니다.
    실제 환경에서는 인증 토큰에서 추출하는 방식으로 변경해야 합니다.
    """
    if not x_company_id:
        # X-Company-ID 헤더가 없으면 기본값 "default" 사용
        return "default"
    return x_company_id


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
