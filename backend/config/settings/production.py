"""
프로덕션 환경 설정
"""

from .base import DEFAULT_SETTINGS

PRODUCTION_SETTINGS = {
    **DEFAULT_SETTINGS,
    "debug": False,
    "log_level": "INFO",
    
    # 프로덕션용 LLM 설정 (안정성 우선)
    "llm": {
        **DEFAULT_SETTINGS["llm"],
        "timeout": 30,
        "temperature": 0.1,  # 더 안정적인 응답
        "preferred_provider": "openai",  # 안정성 우선
        "fallback_providers": ["anthropic", "gemini"]
    },
    
    # 프로덕션용 데이터베이스 설정
    "database": {
        **DEFAULT_SETTINGS["database"],
        "pool_size": 20,
        "max_overflow": 40
    },
    
    # 프로덕션용 검색 설정
    "search": {
        **DEFAULT_SETTINGS["search"],
        "top_k": 10,
        "score_threshold": 0.8,  # 더 엄격한 필터링
        "enable_caching": True
    }
}
