"""
프로바이더 관련 모델들
"""

from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from .base import LLMProvider


class ProviderConfig(BaseModel):
    """프로바이더 설정"""
    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    default_model: str
    available_models: List[str] = Field(default_factory=list)
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    retry_attempts: int = 3
    enabled: bool = True


class ProviderStats(BaseModel):
    """프로바이더 통계"""
    provider: LLMProvider
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_latency_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """성공률 계산"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests


class ProviderWeights(BaseModel):
    """프로바이더 가중치 설정"""
    provider: LLMProvider
    base_weight: float = 1.0
    performance_multiplier: float = 1.0
    cost_efficiency: float = 1.0
    latency_threshold_ms: float = 5000.0
    max_consecutive_failures: int = 5
