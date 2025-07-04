"""
테스트 환경 설정
"""

from .base import DEFAULT_SETTINGS

TESTING_SETTINGS = {
    **DEFAULT_SETTINGS,
    "debug": True,
    "log_level": "WARNING",  # 테스트 시 로그 최소화
    
    # 테스트용 LLM 설정 (모킹 등)
    "llm": {
        **DEFAULT_SETTINGS["llm"],
        "timeout": 5,  # 빠른 테스트
        "mock_responses": True,  # 모킹 활성화
        "preferred_provider": "mock"
    },
    
    # 테스트용 데이터베이스 설정
    "database": {
        **DEFAULT_SETTINGS["database"],
        "use_memory": True,  # 메모리 DB 사용
        "pool_size": 2
    },
    
    # 테스트용 검색 설정
    "search": {
        **DEFAULT_SETTINGS["search"],
        "top_k": 3,  # 최소한의 결과
        "score_threshold": 0.5,
        "enable_caching": False
    }
}
