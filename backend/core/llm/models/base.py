"""
기본 모델 정의 모듈

LLM 관련 기본 데이터 모델들을 정의합니다.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    """지원되는 LLM 제공업체"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GEMINI = "gemini"


class LLMResponse(BaseModel):
    """LLM 응답 모델"""
    provider: LLMProvider
    model: str
    content: str
    usage: Optional[Dict[str, int]] = None
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMRequest(BaseModel):
    """LLM 요청 모델"""
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None


class ProviderHealthStatus(BaseModel):
    """프로바이더 건강 상태"""
    provider: LLMProvider
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
