"""
Anthropic Provider 구현체
"""

import asyncio
import logging
import time
from typing import List, Optional, AsyncGenerator

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import BaseLLMProvider
from ..models.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API 제공자"""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self._available_models = [
            "claude-3-haiku-20240307",
            "claude-3-sonnet-20240229",
            "claude-3-opus-20240229"
        ]
    
    @property
    def provider_type(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC
    
    @property
    def available_models(self) -> List[str]:
        return self._available_models
    
    @retry(
        retry=retry_if_exception_type((
            anthropic.RateLimitError,
            anthropic.APIStatusError,
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
            # 시스템 메시지와 사용자 메시지 분리
            system_message = ""
            user_messages = []
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)
            
            response = await self.client.messages.create(
                model=request.model or "claude-3-haiku-20240307",
                max_tokens=request.max_tokens or 1024,
                temperature=request.temperature or 0.7,
                system=system_message,
                messages=user_messages
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                provider=self.provider_type,
                model=response.model,
                content=response.content[0].text,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                } if response.usage else None,
                latency_ms=latency_ms,
                success=True,
                metadata={"stop_reason": response.stop_reason}
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Anthropic API 오류: {e}")
            
            return LLMResponse(
                provider=self.provider_type,
                model=request.model or "claude-3-haiku-20240307",
                content="",
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성"""
        try:
            # 시스템 메시지와 사용자 메시지 분리
            system_message = ""
            user_messages = []
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)
            
            async with self.client.messages.stream(
                model=request.model or "claude-3-haiku-20240307",
                max_tokens=request.max_tokens or 1024,
                temperature=request.temperature or 0.7,
                system=system_message,
                messages=user_messages
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                    
        except Exception as e:
            logger.error(f"Anthropic 스트리밍 오류: {e}")
            yield f"Error: {str(e)}"
    
    async def get_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """임베딩 생성 (Anthropic은 임베딩 API가 없음)"""
        logger.warning("Anthropic은 임베딩 API를 제공하지 않습니다.")
        return []
    
    async def health_check(self) -> bool:
        """건강 상태 확인"""
        try:
            # 간단한 테스트 메시지로 건강 상태 확인
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            response = await self.generate(test_request)
            return response.success
        except Exception:
            return False
