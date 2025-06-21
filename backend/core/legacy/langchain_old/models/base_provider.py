"""
기본 LLM Provider 추상 클래스

모든 LLM Provider의 기본 인터페이스를 정의합니다.
"""

from typing import Optional
from .llm_models import LLMResponse, LLMProviderStats


class LLMProvider:
    """기본 LLM 제공자 클래스 - 기존과 동일"""
    
    def __init__(self, name: str, timeout: float = 10.0):
        self.name = name
        self.timeout = timeout
        self.stats = LLMProviderStats(provider_name=name)
        self.client = None
        self.available_models = {}
        self.api_key: Optional[str] = None

    def is_healthy(self) -> bool:
        """제공자의 건강 상태를 확인합니다 - 기존과 동일"""
        if self.stats.consecutive_failures >= 5:
            return False
        if self.stats.total_requests >= 10 and self.stats.success_rate < 0.5:
            return False
        return True

    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산합니다 - 기존과 동일"""
        return int(len(text.split()) * 1.3)  # 대략적인 토큰 수 계산

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """하위 클래스에서 구현해야 하는 추상 메서드"""
        raise NotImplementedError("Subclasses must implement generate method")
