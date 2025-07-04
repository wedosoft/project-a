"""
통합된 LLM 관리 모듈

기존의 core/llm과 core/langchain을 통합하여 
명확한 책임 분리와 유지보수성을 개선한 구조입니다.

주요 구성:
- models/: 모든 데이터 모델과 스키마
- providers/: LLM 프로바이더 구현체들
- integrations/: 외부 통합 (Langchain 등)
- utils/: 유틸리티 함수들
- filters/: 필터링 및 전처리 로직
- manager.py: 메인 LLM 매니저
"""

from .manager import LLMManager
from .models.base import LLMResponse, LLMProvider
from .providers.base import BaseLLMProvider

__all__ = [
    "LLMManager",
    "LLMResponse", 
    "LLMProvider",
    "BaseLLMProvider"
]
