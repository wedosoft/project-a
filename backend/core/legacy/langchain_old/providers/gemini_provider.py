"""
Google Gemini API 제공자

기존 llm_manager.py의 GeminiProvider를 분리
"""

import asyncio
import os
import time
from typing import Optional

import google.generativeai as genai
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


class GeminiProvider(LLMProvider):
    """Google Gemini API 제공자 - 기존 코드 90% 재활용"""
    
    def __init__(self, api_key: str = None, timeout: float = 20.0):
        super().__init__(name="gemini", timeout=timeout)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.client = None
        
        if not self.api_key:
            logger.warning(f"GeminiProvider: {self.name} API 키가 없어 초기화되지 않았습니다.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel('gemini-1.5-flash-latest')
                logger.info(f"GeminiProvider ({self.name}) 초기화 완료 (모델: gemini-1.5-flash-latest).")
                self.available_models = {
                    "gemini-1.5-flash-latest": {"max_tokens": 8192, "priority": 1},
                    "gemini-pro": {"max_tokens": 30720, "priority": 2}, 
                }
            except Exception as e:
                logger.error(f"GeminiProvider ({self.name}) 초기화 실패: {e}")
                self.client = None

    @retry(
        retry=retry_if_exception_type((
            httpx.RequestError, 
            asyncio.TimeoutError, 
            genai.types.generation_types.BlockedPromptException,
            genai.types.generation_types.StopCandidateException,
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 2048, temperature: float = 0.2) -> LLMResponse:
        """기존 generate 메서드 90% 재활용"""
        if not self.client:
            self.stats.record_failure()
            if llm_requests_total:
                llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        model_name = 'gemini-1.5-flash-latest'

        contents = []
        if system_prompt:
            full_prompt = f"System Instructions: {system_prompt}\\n\\nUser Query: {prompt}"
        else:
            full_prompt = prompt
        
        contents.append({'role': 'user', 'parts': [full_prompt]})

        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        try:
            logger.info(f"{self.name} API ({model_name}) 호출 시작...")
            async_response = await asyncio.wait_for(
                self.client.generate_content_async(
                    contents=contents,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
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
            
            generated_text = ""
            if async_response.candidates:
                for candidate in async_response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                generated_text += part.text

            if not generated_text and async_response.prompt_feedback and async_response.prompt_feedback.block_reason:
                block_reason = async_response.prompt_feedback.block_reason
                logger.warning(f"{self.name} API: 프롬프트가 차단되었습니다. 이유: {block_reason}")
                raise genai.types.generation_types.BlockedPromptException(f"프롬프트가 차단되었습니다: {block_reason}")

            # 토큰 사용량 계산 (비동기) - 기존 로직 재활용
            input_tokens = 0
            output_tokens = 0
            try:
                count_response_input = await self.client.count_tokens_async(contents=contents)
                input_tokens = count_response_input.total_tokens
                if generated_text:
                    count_response_output = await self.client.count_tokens_async(contents=[{'role': 'model', 'parts': [generated_text]}])
                    output_tokens = count_response_output.total_tokens
            except Exception as e_count:
                logger.warning(f"{self.name} 토큰 계산 실패 ({e_count}), 근사치 사용.")
                input_tokens = self._approx_token_count(full_prompt)
                output_tokens = self._approx_token_count(generated_text)

            if output_tokens > 0 and llm_tokens_used_total:
                llm_tokens_used_total.labels(provider=self.name, model=model_name).inc(output_tokens)

            return LLMResponse(
                text=generated_text,
                model_used=model_name,
                duration_ms=duration,
                tokens_used=output_tokens,
                tokens_total=input_tokens + output_tokens,
                metadata={
                    "provider": self.name,
                    "tokens": {"input_tokens": input_tokens, "output_tokens": output_tokens},
                    "finish_reason": async_response.candidates[0].finish_reason.name if async_response.candidates and async_response.candidates[0].finish_reason else "UNKNOWN",
                    "safety_ratings": [rating.category.name for rating in async_response.candidates[0].safety_ratings] if async_response.candidates and async_response.candidates[0].safety_ratings else []
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

    def _approx_token_count(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산 (Gemini용 임시 방편) - 기존과 동일"""
        return int(len(text) / 2.5)

    def count_tokens(self, text: str) -> int:
        """Gemini 모델의 토큰 수를 계산합니다 - 기존과 동일"""
        if not self.client:
            logger.warning(f"{self.name}Provider가 초기화되지 않아 토큰 수를 정확히 계산할 수 없습니다. 근사치를 반환합니다.")
            return self._approx_token_count(text)
        
        logger.debug(f"{self.name}Provider.count_tokens는 현재 근사치를 반환합니다. 정확한 값은 generate 시 계산됩니다.")
        return self._approx_token_count(text)
