"""
SaaS 멀티테넌트 기본 설정
버전 관리되는 애플리케이션 기본값
"""

from typing import Dict, Any
from enum import Enum

class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GEMINI = "gemini"

class UseCaseType(str, Enum):
    REALTIME = "realtime"
    BATCH = "batch"
    SUMMARIZATION = "summarization"

# 애플리케이션 기본 모델 설정
DEFAULT_LLM_MODELS: Dict[str, Dict[str, Any]] = {
    "realtime": {
        "provider": ModelProvider.GEMINI,
        "model": "gemini-1.5-flash",
        "max_tokens": 1200,
        "temperature": 0.05,
        "timeout": 12.0
    },
    "batch": {
        "provider": ModelProvider.GEMINI,
        "model": "gemini-1.5-flash", 
        "max_tokens": 800,
        "temperature": 0.1,
        "timeout": 15.0
    },
    "summarization": {
        "provider": ModelProvider.GEMINI,
        "model": "gemini-1.5-flash",
        "max_tokens": 1000,
        "temperature": 0.1,
        "timeout": 15.0
    }
}

# 성능 티어별 기본값 (SaaS 플랜별)
PERFORMANCE_TIERS: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_requests_per_hour": 100,
        "max_tokens_per_request": 500,
        "allowed_models": [ModelProvider.GEMINI],
        "priority_level": 3
    },
    "pro": {
        "max_requests_per_hour": 1000,
        "max_tokens_per_request": 1500,
        "allowed_models": [ModelProvider.GEMINI, ModelProvider.OPENAI],
        "priority_level": 2
    },
    "enterprise": {
        "max_requests_per_hour": 10000,
        "max_tokens_per_request": 4000,
        "allowed_models": [ModelProvider.GEMINI, ModelProvider.OPENAI, ModelProvider.ANTHROPIC],
        "priority_level": 1,
        "custom_api_keys": True
    }
}

# 기능 플래그 기본값
DEFAULT_FEATURES: Dict[str, bool] = {
    "streaming_enabled": True,
    "vector_search_enabled": True,
    "conversation_filtering": True,
    "real_time_summaries": True,
    "custom_prompts": False,  # Enterprise only
    "api_access": False,      # Pro+ only
    "white_label": False      # Enterprise only
}

# 시스템 제한값
SYSTEM_LIMITS: Dict[str, Any] = {
    "max_tenants": 1000,
    "max_users_per_tenant": 500,
    "max_file_size_mb": 10,
    "session_timeout_hours": 24,
    "rate_limit_per_ip": 1000
}
