"""
OpenAI API 제공자

기존 llm_manager.py의 OpenAIProvider를 분리
"""

import asyncio
import os
import time
from typing import Optional

import httpx
import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..models.base_provider import LLMProvider
from ..models.llm_models import LLMResponse

# 메트릭 임포트 (안전하게 처리)
try:
    from prometheus_client import REGISTRY
    llm_requests_total = REGISTRY._names_to_collectors.get("llm_requests_total")
    llm_request_duration_seconds = REGISTRY._names_to_collectors.get("llm_request_duration_seconds")
    llm_tokens_used_total = REGISTRY._names_to_collectors.get("llm_tokens_used_total")
except (ImportError, AttributeError):
    llm_requests_total = None
    llm_request_duration_seconds = None
    llm_tokens_used_total = None

# 로깅
import logging
logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API 제공자 - 기존 코드 90% 재활용"""
    
    def __init__(self, api_key: str = None, timeout: float = 10.0):
        super().__init__(name="openai", timeout=timeout)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning(f"{self.name} API 키가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
        # 기존 available_models 그대로 유지
        self.available_models = {
            "gpt-3.5-turbo": {"max_tokens": 4096, "priority": 1},
            "gpt-4": {"max_tokens": 8192, "priority": 2},
            "gpt-4-turbo": {"max_tokens": 128000, "priority": 3},
        }
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIStatusError, asyncio.TimeoutError, httpx.RequestError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """기존 generate 메서드 90% 재활용"""
        if not self.client:
            logger.error(f"{self.name} 클라이언트가 초기화되지 않았습니다.")
            raise RuntimeError(f"{self.name} Provider가 사용할 수 없습니다.")

        start_time = time.time()
        model = "gpt-3.5-turbo"
        system = "당신은 친절한 고객 지원 AI입니다." if system_prompt is None else system_prompt
        
        try:
            # OpenAI API 호출 (기존 로직 재활용)
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=self.timeout
            )
            
            duration = (time.time() - start_time) * 1000
            self.stats.record_success(duration)
            
            # 메트릭 업데이트 (안전하게 처리)
            if llm_requests_total:
                llm_requests_total.labels(provider=self.name, status='success').inc()
            if llm_request_duration_seconds:
                llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            
            generated_text = response.choices[0].message.content
            tokens_used = response.usage.completion_tokens if response.usage else 0
            tokens_total = response.usage.total_tokens if response.usage else 0
            
            if tokens_used > 0 and llm_tokens_used_total:
                llm_tokens_used_total.labels(provider=self.name, model=model).inc(tokens_used)

            return LLMResponse(
                text=generated_text,
                model_used=model,
                duration_ms=duration,
                tokens_used=tokens_used,
                tokens_total=tokens_total,
                metadata={
                    "provider": self.name,
                    "tokens": {"prompt_tokens": response.usage.prompt_tokens if response.usage else 0, "completion_tokens": tokens_used},
                    "finish_reason": response.choices[0].finish_reason if response.choices else "unknown"
                }
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.stats.record_failure(duration)
            
            # 메트릭 업데이트 (안전하게 처리)
            if llm_requests_total:
                llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0 and llm_request_duration_seconds:
                llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            
            logger.error(f"{self.name} 호출 중 오류: {type(e).__name__} - {str(e)}")
            raise

    def count_tokens(self, text: str) -> int:
        """OpenAI 모델의 토큰 수를 계산합니다 - 기존과 동일"""
        # tiktoken을 사용할 수 있지만, 간단한 근사치 사용
        return int(len(text) / 3.5)  # 대략적인 토큰 수 계산
