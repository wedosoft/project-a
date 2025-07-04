"""
개발 환경 설정
"""

from .base import DEFAULT_SETTINGS

DEVELOPMENT_SETTINGS = {
    **DEFAULT_SETTINGS,
    "debug": True,
    "log_level": "DEBUG",
    
    # 개발용 LLM 설정 (빠른 응답 우선)
    "llm": {
        **DEFAULT_SETTINGS["llm"],
        "timeout": 15,
        "temperature": 0.2,
        "preferred_provider": "gemini"  # 빠르고 저렴
    },
    
    # 개발용 검색 설정
    "search": {
        **DEFAULT_SETTINGS["search"],
        "top_k": 5,  # 적은 결과로 빠른 테스트
        "score_threshold": 0.6
    }
}
