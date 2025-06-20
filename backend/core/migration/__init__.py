"""
기존 코드 마이그레이션 모듈

기존 LLM Router 및 main.py 코드와의 호환성을 유지하기 위한 어댑터들입니다.
"""

from .llm_router_adapter import LLMRouterAdapter
from .legacy_wrapper import LegacyWrapper

__all__ = [
    "LLMRouterAdapter",
    "LegacyWrapper"
]
