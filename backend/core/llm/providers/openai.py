"""
OpenAI Provider 구현체
"""

import asyncio
import logging
import time
from typing import List, Optional, AsyncGenerator

import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import BaseLLMProvider
from ..models.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API 제공자"""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self._available_models = None  # 레지스트리에서 동적으로 로드
    
    @property
    def provider_type(self) -> LLMProvider:
        return LLMProvider.OPENAI
    
    @property
    def available_models(self) -> List[str]:
        """레지스트리에서 사용 가능한 모델 목록 반환"""
        if self._available_models is None:
            try:
                from ..registry import get_model_registry
                registry = get_model_registry()
                models = registry.get_available_models(
                    provider="openai",
                    include_deprecated=False
                )
                self._available_models = [model.name for model in models]
            except Exception as e:
                logger.warning(f"Failed to load models from registry: {e}")
                # 폴백: 기본 모델 목록
                self._available_models = [
                    "gpt-3.5-turbo",
                    "gpt-4",
                    "gpt-4-turbo",
                    "gpt-4o-mini"
                ]
        return self._available_models
    
    @retry(
        retry=retry_if_exception_type((
            openai.RateLimitError, 
            openai.APIStatusError, 
            asyncio.TimeoutError
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """텍스트 생성"""
        start_time = time.time()
        
        try:
            response = await self.client.chat.completions.create(
                model=request.model or "gpt-3.5-turbo",
                messages=request.messages,
                max_tokens=request.max_tokens or 1024,
                temperature=request.temperature or 0.7,
                stream=False
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                provider=self.provider_type,
                model=response.model,
                content=response.choices[0].message.content,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                } if response.usage else None,
                latency_ms=latency_ms,
                success=True,
                metadata={"finish_reason": response.choices[0].finish_reason}
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"OpenAI API 오류: {e}")
            
            return LLMResponse(
                provider=self.provider_type,
                model=request.model or "gpt-3.5-turbo",
                content="",
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성"""
        try:
            stream = await self.client.chat.completions.create(
                model=request.model or "gpt-3.5-turbo",
                messages=request.messages,
                max_tokens=request.max_tokens or 1024,
                temperature=request.temperature or 0.7,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI 스트리밍 오류: {e}")
            yield f"Error: {str(e)}"
    
    async def get_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """임베딩 생성"""
        try:
            response = await self.client.embeddings.create(
                model=model or "text-embedding-3-large",
                input=texts
            )
            
            return [data.embedding for data in response.data]
            
        except Exception as e:
            logger.error(f"OpenAI 임베딩 오류: {e}")
            return []
    
    async def health_check(self) -> bool:
        """건강 상태 확인"""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
