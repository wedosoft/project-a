"""
기본 설정

모든 환경에서 공통으로 사용되는 기본 설정들입니다.
"""

import os
from pathlib import Path

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 데이터 설정 파일 경로
CONFIG_DATA_DIR = BASE_DIR / "config" / "data"

# 기본 설정들
DEFAULT_SETTINGS = {
    "debug": False,
    "log_level": "INFO",
    "max_workers": 4,
    "timeout": 30,
    
    # LLM 설정
    "llm": {
        "max_retries": 3,
        "timeout": 30,
        "temperature": 0.7,
        "max_tokens": 4096
    },
    
    # 데이터베이스 설정
    "database": {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30
    },
    
    # 벡터DB 설정
    "vectordb": {
        "collection_name": "documents",
        "vector_size": 1536,
        "distance": "cosine"
    },
    
    # 검색 설정
    "search": {
        "top_k": 10,
        "score_threshold": 0.7,
        "enable_hybrid": True
    }
}

# 환경별 설정 파일 매핑
ENV_SETTINGS_MAP = {
    "development": "development",
    "production": "production", 
    "testing": "testing",
    "local": "development"
}
