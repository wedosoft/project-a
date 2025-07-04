"""
기본 LLM 프로바이더 인터페이스
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, AsyncGenerator
from ..models.base import LLMRequest, LLMResponse, LLMProvider


class BaseLLMProvider(ABC):
    """모든 LLM 프로바이더의 기본 인터페이스"""
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.config = kwargs
        
    @property
    @abstractmethod
    def provider_type(self) -> LLMProvider:
        """프로바이더 타입 반환"""
        pass
        
    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """사용 가능한 모델 목록 반환"""
        pass
        
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """텍스트 생성"""
        pass
        
    @abstractmethod
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성"""
        pass
        
    @abstractmethod
    async def get_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """임베딩 생성"""
        pass
        
    @abstractmethod
    async def health_check(self) -> bool:
        """건강 상태 확인"""
        pass
