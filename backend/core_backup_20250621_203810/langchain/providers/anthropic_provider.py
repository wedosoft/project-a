"""
Anthropic Claude API 제공자

기존 llm_manager.py의 AnthropicProvider를 분리
"""

import asyncio
import os
import time
from typing import Optional

import anthropic
import httpx
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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 제공자 - 기존 코드 90% 재활용"""
    
    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        super().__init__(name="anthropic", timeout=timeout)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning(f"{self.name} API 키가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = anthropic.AsyncClient(api_key=self.api_key)
        # 기존 available_models 그대로 유지
        self.available_models = {
            "claude-3-haiku-20240307": {"max_tokens": 200000, "priority": 1},
            "claude-3-sonnet-20240229": {"max_tokens": 200000, "priority": 2},
        }
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError, asyncio.TimeoutError, httpx.RequestError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """기존 generate 메서드 90% 재활용"""
        if not self.client:
            self.stats.record_failure()
            if llm_requests_total:
                llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        model = "claude-3-haiku-20240307"
        system = "당신은 친절한 고객 지원 AI입니다." if system_prompt is None else system_prompt
        
        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=self.timeout
            )
            duration = (time.time() - start_time) * 1000
            self.stats.record_success(duration)
            
            # 메트릭 업데이트 (안전하게 처리)
            if llm_requests_total:
                llm_requests_total.labels(provider=self.name, status='success').inc()
            if llm_request_duration_seconds:
                llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            if response.usage.output_tokens and llm_tokens_used_total:
                llm_tokens_used_total.labels(provider=self.name, model=model).inc(response.usage.output_tokens)
            
            text = response.content[0].text
            tokens_used = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
            
            return LLMResponse(
                text=text,
                model_used=model,
                duration_ms=duration,
                tokens_used=response.usage.output_tokens,
                tokens_total=response.usage.input_tokens + response.usage.output_tokens,
                metadata={
                    "provider": self.name,
                    "tokens": tokens_used,
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
            
            logger.error(f"{self.name} API 오류: {type(e).__name__} - {str(e)}")
            raise
