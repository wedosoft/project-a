"""
LLM Router 모듈

이 모듈은 여러 LLM 모델 간의 라우팅 로직을 제공합니다.
Anthropic Claude와 OpenAI GPT-4o 모델 간의 자동 선택 및 fallback 기능을 구현합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Union

import anthropic  # 최신 Anthropic 라이브러리 사용
import google.generativeai as genai  # Gemini SDK 임포트
import httpx
import openai
from cachetools import TTLCache
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# 로깅 설정
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # main.py에서 이미 설정하므로 중복 제거 또는 레벨 조정

# API 키 설정
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") # Google API 키 (호환성 유지)

# 환경 변수 확인
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
if not GOOGLE_API_KEY: # Google API 키 확인 추가
    logger.warning("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. GeminiProvider를 사용할 수 없습니다.")


# 임베딩 캐시 설정 (최대 1000개, 1시간 TTL)
embedding_cache = TTLCache(maxsize=1000, ttl=3600)

def _get_cache_key(text: str, model: str) -> str:
    """임베딩 캐시 키 생성"""
    # 텍스트와 모델명을 조합하여 해시 생성
    content = f"{model}:{text}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


# Prometheus 메트릭 정의 (LLM Router 전용)
llm_requests_total = Counter(
    "llm_requests_total",
    "LLM 요청 총 수",
    ["provider", "status"] # 레이블: 제공자 이름, 성공/실패 상태
)
llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM 요청 처리 시간 (초)",
    ["provider"] # 레이블: 제공자 이름
)
llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "LLM에서 사용된 총 토큰 수 (응답 기준)",
    ["provider", "model"] # 레이블: 제공자 이름, 사용된 모델
)
llm_provider_health_status = Gauge(
    "llm_provider_health_status",
    "LLM 제공자 건강 상태 (1: 건강, 0: 비건강)",
    ["provider"]
)
llm_provider_consecutive_failures = Gauge(
    "llm_provider_consecutive_failures",
    "LLM 제공자 연속 실패 횟수",
    ["provider"]
)
llm_provider_success_rate = Gauge(
    "llm_provider_success_rate",
    "LLM 제공자 성공률",
    ["provider"]
)


class LLMResponse(BaseModel):
    """LLM 응답 모델"""
    text: str
    model_used: str
    duration_ms: float
    tokens_used: Optional[int] = None
    tokens_total: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # 새로운 필드 추가
    attempt_count: int = 1 
    is_fallback: bool = False
    previous_provider_error: Optional[str] = None

    model_config = {
        "protected_namespaces": ()
    }


class LLMProviderStats(BaseModel):
    """LLM 제공자별 통계 데이터 모델"""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0  # 연속 실패 횟수 추가
    total_tokens_used: int = 0
    total_latency_ms: float = 0.0  # 평균 계산을 위한 총 지연 시간
    last_error_timestamp: Optional[float] = None  # 마지막 오류 발생 시간 (타임스탬프)
    error_details: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def average_latency_ms(self) -> float:
        """요청당 평균 지연 시간 (밀리초)"""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    def add_request_stats(self, duration_ms: float, tokens_used: Optional[int], success: bool, error_info: Optional[Dict[str, Any]] = None):
        """개별 요청 통계를 집계합니다."""
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        if tokens_used is not None:
            self.total_tokens_used += tokens_used

        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0  # 성공 시 연속 실패 횟수 리셋
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1  # 실패 시 연속 실패 횟수 증가
            if error_info:
                self.error_details.append(error_info)

    @property
    def success_rate(self) -> float:
        """성공률을 계산합니다."""
        if self.total_requests == 0:
            return 1.0  # 요청이 없으면 100% 성공으로 간주 (또는 0.0으로 할 수도 있음)
        return self.successful_requests / self.total_requests

    def record_success(self, duration_ms: float, tokens_used: Optional[int] = None):
        """성공한 요청 통계를 기록합니다."""
        self.add_request_stats(duration_ms, tokens_used, success=True)
        
        # Prometheus 메트릭 업데이트
        llm_provider_consecutive_failures.labels(provider=self.provider_name).set(self.consecutive_failures)
        llm_provider_success_rate.labels(provider=self.provider_name).set(self.success_rate)

    def record_failure(self, duration_ms: float = 0, error_info: Optional[Dict[str, Any]] = None):
        """실패한 요청 통계를 기록합니다."""
        import time
        self.last_error_timestamp = time.time()  # 마지막 오류 시간 기록
        self.add_request_stats(duration_ms, None, success=False, error_info=error_info)
        
        # Prometheus 메트릭 업데이트
        llm_provider_consecutive_failures.labels(provider=self.provider_name).set(self.consecutive_failures)
        llm_provider_success_rate.labels(provider=self.provider_name).set(self.success_rate)


class LLMProvider:
    """LLM 제공자의 기본 추상 클래스"""
    def __init__(self, name: str, timeout: float): # name과 timeout을 생성자에서 받도록 변경
        self.name = name
        self.timeout = timeout
        self.stats = LLMProviderStats(provider_name=name) # 통계 객체 초기화
        self.api_key: Optional[str] = None # API 키는 하위 클래스에서 설정
        # 초기 건강 상태 메트릭 설정
        llm_provider_health_status.labels(provider=self.name).set(1) # 초기에는 건강하다고 가정
        llm_provider_consecutive_failures.labels(provider=self.name).set(0)
        llm_provider_success_rate.labels(provider=self.name).set(1.0)

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """추상 메소드: 각 제공자 클래스에서 구현해야 함"""
        raise NotImplementedError
    
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산 (기본 구현)"""
        return int(len(text.split()) * 1.3)

    def is_healthy(self) -> bool:
        """제공자가 현재 건강한 상태인지 판단 (기본은 항상 True)"""
        healthy = True
        if self.stats.consecutive_failures >= 3:
            logger.warning(f"{self.name} 제공자 연속 실패 3회 이상으로 비정상 상태 간주.")
            healthy = False
        if self.stats.last_error_timestamp and (time.time() - self.stats.last_error_timestamp < 300): # 최근 5분
            if self.stats.total_requests > 5 and self.stats.success_rate < 0.5: # 요청 5회 이상, 성공률 50% 미만
                 logger.warning(f"{self.name} 제공자 최근 5분 내 성공률 {self.stats.success_rate:.2f}로 비정상 상태 간주.")
                 healthy = False
        
        # Prometheus 메트릭 업데이트
        llm_provider_health_status.labels(provider=self.name).set(1 if healthy else 0)
        return healthy


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 제공자"""
    
    def __init__(self, api_key: str = None, timeout: float = 8.0):
        super().__init__(name="anthropic", timeout=timeout) # 부모 클래스 생성자 호출
        self.api_key = api_key or ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning(f"{self.name} API 키가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = anthropic.AsyncClient(api_key=self.api_key)
        # ... 기존 available_models ...
        self.available_models = {
            "claude-3-haiku-20240307": {"max_tokens": 200000, "priority": 1},
            "claude-3-sonnet-20240229": {"max_tokens": 200000, "priority": 2},
        }
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError, asyncio.TimeoutError, httpx.RequestError)), # httpx.RequestError 추가
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.stats.record_failure() # 통계 기록
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
            self.stats.record_success(duration) # 성공 통계 기록
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            if response.usage.output_tokens: # 토큰 정보가 있을 경우
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
            self.stats.record_failure(duration) # 실패 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0: # 타임아웃 등의 경우 duration이 있을 수 있음
                 llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            logger.error(f"{self.name} API 오류: {type(e).__name__} - {str(e)}")
            raise


class OpenAIProvider(LLMProvider):
    """OpenAI API 제공자"""
    
    def __init__(self, api_key: str = None, timeout: float = 12.0):
        super().__init__(name="openai", timeout=timeout) # 부모 클래스 생성자 호출
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            logger.warning(f"{self.name} API 키가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
        # ... 기존 available_models ...
        self.available_models = {
            "gpt-4o": {"max_tokens": 128000, "priority": 1},
            "gpt-3.5-turbo": {"max_tokens": 16000, "priority": 2},
        }

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError, asyncio.TimeoutError, httpx.RequestError)), # httpx.RequestError 추가
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.stats.record_failure() # 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        model = "gpt-4o"
        system = "당신은 친절한 고객 지원 AI입니다." if system_prompt is None else system_prompt
        
        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=self.timeout
            )
            duration = (time.time() - start_time) * 1000
            self.stats.record_success(duration) # 성공 통계 기록
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            if response.usage.completion_tokens: # 토큰 정보가 있을 경우
                llm_tokens_used_total.labels(provider=self.name, model=model).inc(response.usage.completion_tokens)
            
            text = response.choices[0].message.content.strip()
            tokens_used = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            }
            
            return LLMResponse(
                text=text,
                model_used=model,
                duration_ms=duration,
                tokens_used=response.usage.completion_tokens,
                tokens_total=response.usage.prompt_tokens + response.usage.completion_tokens,
                metadata={
                    "provider": self.name,
                    "tokens": tokens_used,
                }
            )
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            self.stats.record_failure(duration) # 실패 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0:
                 llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            logger.error(f"{self.name} API 오류: {type(e).__name__} - {str(e)}")
            raise


class GeminiProvider(LLMProvider):
    """Google Gemini API 제공자"""
    
    def __init__(self, api_key: str = None, timeout: float = 18.0):
        super().__init__(name="gemini", timeout=timeout) # 부모 클래스 생성자 호출
        self.api_key = api_key or GOOGLE_API_KEY
        self.client = None # genai.GenerativeModel 인스턴스
        
        if not self.api_key:
            logger.warning(f"GeminiProvider: {self.name} API 키가 없어 초기화되지 않았습니다.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                # 모델명은 최신 안정화 버전 또는 특정 요구사항에 맞는 모델로 설정
                self.client = genai.GenerativeModel('gemini-1.5-flash-latest') # 예시: 최신 Flash 모델
                logger.info(f"GeminiProvider ({self.name}) 초기화 완료 (모델: gemini-1.5-flash-latest).")
                self.available_models = {
                    "gemini-1.5-flash-latest": {"max_tokens": 8192, "priority": 1}, # Flash 모델은 컨텍스트 윈도우가 더 클 수 있음, 확인 필요
                    "gemini-pro": {"max_tokens": 30720, "priority": 2}, 
                }
            except Exception as e:
                logger.error(f"GeminiProvider ({self.name}) 초기화 실패: {e}")
                self.client = None # 실패 시 명시적으로 None 설정

    @retry(
        retry=retry_if_exception_type((
            httpx.RequestError, 
            asyncio.TimeoutError, 
            genai.types.generation_types.BlockedPromptException,
            genai.types.generation_types.StopCandidateException,
            # google.api_core.exceptions.GoogleAPIError, # 좀 더 포괄적인 Google API 오류
            # google.api_core.exceptions.RetryError,
            # google.api_core.exceptions.ServiceUnavailable,
            # google.api_core.exceptions.DeadlineExceeded,
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 2048, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.stats.record_failure() # 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        model_name = 'gemini-1.5-flash-latest' # 초기화 시 설정된 모델 사용 또는 동적 선택

        contents = []
        if system_prompt:
            # Gemini는 system_prompt를 contents의 첫 번째 메시지로 구성하여 전달 가능
            # 또는 모델에 따라 `system_instruction` 파라미터 사용 가능 (gemini-1.5-pro 등)
            # 여기서는 contents에 포함하는 방식 사용
            # contents.append({'role': 'system', 'parts': [system_prompt]}) # 역할 'system' 지원 여부 확인 필요
            # 일반적으로는 user/model 턴으로 구성. 시스템 프롬프트는 첫 user 메시지에 포함.
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
            self.stats.record_success(duration) # 성공 통계 기록
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            # Gemini 응답에서 output_tokens 가져오기 (이전에 계산된 값 사용)
            # response_obj는 LLMResponse 객체가 아님. async_response로부터 토큰 계산.
            # 아래 LLMResponse 생성 시 output_tokens 사용.
            
            generated_text = ""
            # ... (기존 텍스트 추출 및 차단 로직) ...
            if async_response.candidates:
                if async_response.candidates[0].content and async_response.candidates[0].content.parts:
                    generated_text = async_response.candidates[0].content.parts[0].text
                elif hasattr(async_response.candidates[0], 'text'):
                     generated_text = async_response.candidates[0].text

            if not generated_text and async_response.prompt_feedback and async_response.prompt_feedback.block_reason:
                block_reason = async_response.prompt_feedback.block_reason
                logger.warning(f"{self.name} API: 프롬프트가 차단되었습니다. 이유: {block_reason}")
                raise genai.types.generation_types.BlockedPromptException(f"프롬프트가 차단되었습니다: {block_reason}")

            # 토큰 사용량 계산 (비동기)
            input_tokens = 0
            output_tokens = 0
            try:
                count_response_input = await self.client.count_tokens_async(contents=contents)
                input_tokens = count_response_input.total_tokens
                if generated_text:
                    count_response_output = await self.client.count_tokens_async(contents=[{'role':'model', 'parts': [generated_text]}])
                    output_tokens = count_response_output.total_tokens
            except Exception as e_count: # 토큰 계산 실패 시 근사치 사용
                logger.warning(f"{self.name} 토큰 계산 실패 ({e_count}), 근사치 사용.")
                input_tokens = self._approx_token_count(full_prompt)
                output_tokens = self._approx_token_count(generated_text)

            if output_tokens > 0:
                llm_tokens_used_total.labels(provider=self.name, model=model_name).inc(output_tokens)

            return LLMResponse(
                text=generated_text,
                model_used=model_name,
                duration_ms=duration,
                tokens_used=output_tokens, # 계산된 output_tokens
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
            self.stats.record_failure(duration) # 실패 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0:
                llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            logger.error(f"{self.name} 호출 중 오류: {type(e).__name__} - {str(e)}")
            raise

    def _approx_token_count(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산 (Gemini용 임시 방편)"""
        # Gemini는 BPE 기반 토크나이저를 사용. 정확한 계산은 SDK의 count_tokens 사용.
        # 여기서는 단순 근사치 제공 (영어 기준 단어 1개는 약 1.3 ~ 1.5 토큰, 한글은 더 많음)
        return int(len(text) / 2.5) # 글자 수 기반으로 더 단순화 (경험적 조정 필요)

    def count_tokens(self, text: str) -> int:
        """Gemini 모델의 토큰 수를 계산합니다. (동기 컨텍스트용 - 근사치 사용)"""
        if not self.client:
            logger.warning(f"{self.name}Provider가 초기화되지 않아 토큰 수를 정확히 계산할 수 없습니다. 근사치를 반환합니다.")
            return self._approx_token_count(text)
        
        # 동기적 count_tokens가 필요하다면, Gemini SDK가 동기 버전을 제공하는지 확인하거나,
        # asyncio.run()을 사용하여 비동기 호출을 실행해야 하지만, 라이브러리 내에서는 권장되지 않음.
        # LLMRouter.choose_provider (동기)에서는 이 근사치를 사용하고,
        # 실제 generate (비동기)에서는 count_tokens_async를 사용.
        logger.debug(f"{self.name}Provider.count_tokens는 현재 근사치를 반환합니다. 정확한 값은 generate 시 계산됩니다.")
        return self._approx_token_count(text)


class LLMRouter:
    """LLM 라우팅 및 Fallback 로직 구현"""
    
    def __init__(self, timeout: float = 10.0, gemini_timeout: float = 20.0): # Gemini 타임아웃 분리
        self.timeout = timeout # Anthropic, OpenAI용 기본 타임아웃
        self.anthropic = AnthropicProvider(timeout=timeout)
        self.openai = OpenAIProvider(timeout=timeout) 
        self.gemini = GeminiProvider(timeout=gemini_timeout) # Gemini는 별도 타임아웃 적용
        
        # 제공자 우선순위 및 상태 관리 (Prometheus 연동 시 메트릭으로 활용 가능)
        # 성능 기반 우선순위: OpenAI > Anthropic > Gemini (응답 속도 최적화)
        self.providers_priority = ["openai", "anthropic", "gemini"]
        self.provider_instances: Dict[str, LLMProvider] = {
            "anthropic": self.anthropic,
            "openai": self.openai,
            "gemini": self.gemini
        }

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """최적의 LLM 제공자를 선택하고, 실패 시 순차적으로 Fallback하여 텍스트 생성"""
        
        # TODO: 이미지 포함 여부, 예상 토큰 수 등은 choose_provider 내부 또는 외부에서 결정
        # has_images = False 
        # estimated_tokens = self.provider_instances[self.providers_priority[0]].count_tokens(prompt) 
        
        # 동적으로 시도할 제공자 목록 생성 (건강 상태, API 키 유무 등 고려)
        # choose_provider 메소드가 선택한 우선순위에 따라 정렬
        ordered_providers = self._get_ordered_providers(prompt)

        last_error: Optional[Exception] = None
        attempt_count = 0
        
        for provider_name in ordered_providers:
            provider = self.provider_instances[provider_name]
            attempt_count += 1
            
            if not provider.api_key:
                logger.warning(f"{provider.name} 제공자는 API 키가 없어 건너뜁니다.")
                continue
            if not provider.is_healthy(): # 건강 상태 체크 추가
                logger.warning(f"{provider.name} 제공자가 건강하지 않아 건너뜁니다 (성공률: {provider.stats.success_rate:.2f}, 연속실패: {provider.stats.consecutive_failures}).")
                continue

            try:
                logger.info(f"{provider.name} ({attempt_count}번째 시도)로 생성 시작...")
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                # 성공 시 메타데이터에 시도 정보 추가
                response.attempt_count = attempt_count
                response.is_fallback = attempt_count > 1
                if attempt_count > 1 and last_error:
                    response.previous_provider_error = f"{type(last_error).__name__}: {str(last_error)}"
                
                return response
            except Exception as e:
                logger.warning(f"{provider.name} 제공자로 생성 실패: {type(e).__name__} - {str(e)}. 다음 제공자로 Fallback 시도합니다.")
                last_error = e
        
        logger.error(f"모든 LLM 제공자 호출 실패. 마지막 오류: {type(last_error).__name__} - {str(last_error)} (총 {attempt_count}번 시도)")
        # 모든 시도 실패 시, LLMResponse 대신 에러를 발생시켜 상위 호출자가 처리하도록 함
        raise RuntimeError(f"모든 LLM 제공자 호출 실패 (마지막 오류: {type(last_error).__name__} - {str(last_error)})")


    def _get_ordered_providers(self, prompt: str) -> List[str]:
        """
        요청 특성 및 제공자 상태를 기반으로 시도할 제공자 이름 목록을 우선순위대로 반환합니다.
        (현재는 단순 우선순위 + 건강상태만 고려, 향후 확장 가능)
        """
        # 1. API 키가 있고 건강한 제공자만 필터링
        available_providers = [
            name
            for name in self.providers_priority
            if self.provider_instances[name].api_key
            and self.provider_instances[name].is_healthy()
        ]

        # 평균 지연 시간 기준 정렬 (데이터가 없으면 기본 우선순위 사용)
        available_providers.sort(
            key=lambda name: (
                self.provider_instances[name].stats.average_latency_ms
                if self.provider_instances[name].stats.total_requests > 0
                else float("inf"),
                self.providers_priority.index(name),
            )
        )
        
        # 2. (선택적) 요청 특성에 따른 우선순위 동적 조정 로직 (예시)
        # estimated_tokens = self.provider_instances[self.providers_priority[0]].count_tokens(prompt) # 가장 우선순위 높은 제공자로 토큰 계산
        # if estimated_tokens > 7000: # 긴 컨텍스트는 Gemini나 OpenAI GPT-4o가 유리할 수 있음
        #     if "gemini" in available_providers and "openai" in available_providers:
        #         # Gemini와 OpenAI를 앞으로 당기는 로직 (순서 변경)
        #         pass 
        
        # 3. API 키가 없거나 건강하지 않은 제공자들을 목록 뒤로 배치 (fallback용)
        unavailable_providers = [
            name for name in self.providers_priority if name not in available_providers
        ]

        latency_info = {
            name: round(self.provider_instances[name].stats.average_latency_ms, 2)
            for name in available_providers
        }
        logger.info(f"동적 라우팅 - 평균 지연 시간(ms): {latency_info}")

        ordered_list = available_providers + unavailable_providers
        if not ordered_list:  # 모든 제공자가 사용 불가능한 극단적인 경우
             logger.error("사용 가능한 LLM 제공자가 없습니다 (API 키 부재 또는 모두 비정상 상태).")
             return [] # 빈 리스트 반환 또는 기본 제공자 이름 반환
        
        logger.info(f"시도할 제공자 순서: {ordered_list}")
        return ordered_list

    def _extract_conversation_body(self, conv: Dict[str, Any]) -> str:
        """
        대화 딕셔너리에서 본문 텍스트를 안전하게 추출합니다.
        여러 가능한 필드를 순서대로 시도합니다.
        
        Args:
            conv: 대화 항목 딕셔너리
            
        Returns:
            추출된 본문 텍스트
        """
        if not isinstance(conv, dict):
            return str(conv)[:300]
            
        # 가능한 필드들을 우선순위대로 시도
        for field in ["body_text", "body", "text", "content", "message"]:
            if field in conv and conv[field]:
                content = conv[field]
                # HTML 태그 제거 시도
                if isinstance(content, str) and "<" in content and ">" in content:
                    try:
                        # 간단한 HTML 태그 제거 (실패하면 원본 사용)
                        content = re.sub(r'<[^>]+>', ' ', content)
                    except:
                        pass
                return str(content)
        
        # 필드를 찾지 못한 경우 전체 딕셔너리를 문자열로 변환
        try:
            # 너무 길면 잘라내기
            return str(conv)[:300]
        except:
            return "내용을 추출할 수 없음"
    
    async def generate_ticket_summary(self, ticket_data: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
        """
        티켓 데이터를 기반으로 LLM을 사용하여 요약문과 주요 정보를 생성합니다.
        
        Args:
            ticket_data: 티켓 정보가 포함된 딕셔너리
            max_tokens: 요약문 최대 토큰 수
            
        Returns:
            생성된 티켓 요약 정보를 포함하는 딕셔너리
            {
                'summary': '요약문',
                'key_points': ['핵심 포인트 1', '핵심 포인트 2', ...],
                'sentiment': '감정 상태',
                'urgency_level': '긴급도',
                'priority_recommendation': '우선순위 추천'
            }
            
        Raises:
            RuntimeError: 모든 LLM 제공자 호출이 실패한 경우
        """
        # 컨텍스트 빌더를 사용하여 LLM 프롬프트에 적합한 형태로 티켓 정보 구성
        subject = ticket_data.get("subject", "제목 없음")
        description = ticket_data.get("description_text", "설명 없음")
        conversations = ticket_data.get("conversations", [])
        
        # 간단한 프롬프트 구성
        prompt_context = f"티켓 제목: {subject}\n티켓 설명: {description}\n"
        
        if conversations:
            prompt_context += "\n최근 대화 내용:\n"
            # conversations의 타입에 따라 적절히 처리
            if isinstance(conversations, list):
                try:
                    # 대화 항목들을 필터링하고 시간 순서대로 정렬
                    # 정렬하기 전에 리스트 내 항목이 모두 딕셔너리인지 확인
                    valid_conversations = [c for c in conversations if isinstance(c, dict)]
                    
                    if valid_conversations:
                        # 시간순으로 정렬 (오래된 순 -> 최신순)
                        sorted_conversations = sorted(valid_conversations, key=lambda c: c.get("created_at", 0))
                        
                        # 대화의 양이 많은 경우(10개 초과)에는 더 많은 컨텍스트를 포함하고 중요 대화에 집중
                        if len(sorted_conversations) > 10:
                            # 처음 30%의 대화 포함 (초기 상황 파악 개선)
                            early_conv_count = max(3, int(len(sorted_conversations) * 0.3))
                            early_conversations = sorted_conversations[:early_conv_count]
                            
                            # 마지막 70%의 대화 (최근 상황 집중)
                            # 중간 대화도 일부 포함하여 맥락 유지
                            late_start_idx = max(early_conv_count, len(sorted_conversations) - 20)
                            late_conversations = sorted_conversations[late_start_idx:]
                            
                            # 처음 대화 추가 (문제 상황 파악)
                            prompt_context += "초기 대화 내용:\n"
                            for conv in early_conversations:
                                sender = "사용자" if conv.get("user_id") else "상담원"
                                body = self._extract_conversation_body(conv)
                                # 초기 대화는 더 많은 내용 포함 (300자)
                                prompt_context += f"- {sender}: {body[:300]}...\n"
                            
                            # 중간 생략 표시
                            if late_start_idx > early_conv_count:
                                skipped = late_start_idx - early_conv_count
                                prompt_context += f"\n... (중간 {skipped}개 대화 생략) ...\n\n"
                            
                            # 최근 대화 추가 (더 자세한 내용 포함)
                            prompt_context += "최근 대화 내용:\n"
                            for conv in late_conversations:
                                sender = "사용자" if conv.get("user_id") else "상담원"
                                body = self._extract_conversation_body(conv)
                                # 최근 대화는 더 많은 내용 포함 (500자)
                                prompt_context += f"- {sender}: {body[:500]}...\n"
                        else:
                            # 대화가 적은 경우 전체 내용 포함 (10개 이하)
                            prompt_context += "대화 내용:\n"
                            for conv in sorted_conversations:
                                sender = "사용자" if conv.get("user_id") else "상담원"
                                body = self._extract_conversation_body(conv)
                                # 적은 대화일 경우 대화당 최대 1000자까지 포함
                                prompt_context += f"- {sender}: {body[:1000]}...\n"
                    else:
                        # 유효한 대화 항목이 없는 경우
                        prompt_context += f"- 대화 내용: {str(conversations)[:200]}\n"
                except Exception as e:
                    logger.warning(f"대화 처리 중 오류 발생: {e}")
                    prompt_context += f"- 대화 내용: {str(conversations)[:200]}\n"
            elif isinstance(conversations, str):
                # 문자열인 경우 직접 포함
                prompt_context += f"- 대화 내용: {conversations[:200]}\n"
            else:
                # 기타 타입인 경우 문자열로 변환하여 포함
                prompt_context += f"- 대화 내용: {str(conversations)[:200]}\n"
                
        system_prompt = (
            "당신은 AI 지원 에이전트입니다. 제공된 티켓 정보를 바탕으로 다음 정보를 추출하세요:\n"
            "1. 티켓의 핵심 내용 요약 (주요 문제점, 고객의 요청, 현재 상태, 해결 과정 포함)\n"
            "   - 초기 대화와 최근 대화의 맥락을 모두 고려하여 전체 상황을 포괄적으로 요약\n"
            "   - 대화 흐름에 따른 문제 진행 상황과 해결 과정을 상세히 포함\n"
            "   - 문제의 원인, 조치 사항, 결과를 명확하게 언급\n"
            "   - 티켓이 해결되었다면 최종 해결책과 결과를 반드시 포함\n"
            "2. 3-5개의 핵심 포인트 (반드시 배열로 제공)\n"
            "   - 초기 및 최근 대화에서 나타난 중요한 정보 모두 포함\n"
            "   - 기술적 문제점, 해결 방법, 고객 요구사항을 균형있게 포함\n"
            "3. 티켓의 전반적인 감정 상태 (긍정적, 중립적, 부정적)\n"
            "4. 추천 우선순위 (높음, 보통, 낮음)\n"
            "5. 긴급도 수준 (높음, 보통, 낮음)\n\n"
            "반드시 아래 형식의 유효한 JSON으로만 응답해주세요:\n"
            "{\n"
            "  \"summary\": \"티켓 요약 텍스트 - 가능한 상세하게 작성\",\n"
            "  \"key_points\": [\"핵심 포인트 1\", \"핵심 포인트 2\", \"핵심 포인트 3\"],\n"
            "  \"sentiment\": \"감정 상태\",\n"
            "  \"priority_recommendation\": \"우선순위\",\n"
            "  \"urgency_level\": \"긴급도\"\n"
            "}\n\n"
            "주의: key_points는 반드시 배열 형태로 제공해야 합니다. 문자열이나 다른 형식은 허용되지 않습니다.\n"
            "요약은 가능한 자세하게 작성하고, 대화의 전체 맥락을 포함해야 합니다.\n"
            "한국어로 답변해주세요."
        )
        
        prompt = f"다음 티켓 정보를 분석해주세요:\n\n{prompt_context}"
        
        # 로깅 개선 - 대화 수와 처리된 정보량 기록
        conv_count = 0
        if isinstance(conversations, list):
            conv_count = len(conversations)
        
        logger.info(f"티켓 요약 생성 요청 (ticket_id: {ticket_data.get('id')}, 대화 수: {conv_count}, prompt_length: {len(prompt)} chars)")
        
        # 프롬프트가 너무 길어질 경우 경고 로그
        if len(prompt) > 15000:
            logger.warning(f"티켓 {ticket_data.get('id')}의 프롬프트가 매우 깁니다 ({len(prompt)} chars). 일부 정보가 생략될 수 있습니다.")
        
        try:
            # self.generate를 사용하여 텍스트 생성
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            if not response or not hasattr(response, 'text') or not response.text:
                # 응답이 비어있거나 유효하지 않은 경우
                logger.error(f"티켓 요약 생성 오류: LLM에서 유효한 응답을 받지 못했습니다 (ticket_id: {ticket_data.get('id')})")
                return {
                    "summary": f"티켓 제목: {subject}\n\n내용 요약을 생성할 수 없습니다.",
                    "key_points": ["요약 생성 실패", "원본 티켓 확인 필요"],
                    "sentiment": "중립적",
                    "priority_recommendation": "확인 필요",
                    "urgency_level": "보통"
                }
                
            logger.info(f"티켓 요약 생성 완료 (ticket_id: {ticket_data.get('id')}, model: {response.model_used}, duration: {response.duration_ms}ms)")
            
            # LLM 응답을 파싱하여 구조화된 형식으로 변환
            try:
                # 원본 응답 로깅 (디버깅용)
                logger.info(f"LLM 원본 응답 (ticket_id: {ticket_data.get('id')}): {response.text[:500]}...")
                
                # 응답에서 JSON 부분만 추출하는 시도 (여러 줄 텍스트에서 JSON만 찾기)
                json_text = response.text
                # JSON 객체 시작과 끝을 찾아서 추출
                json_match = re.search(r'(\{.*\})', json_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1)
                    logger.info(f"JSON 추출 성공: {json_text[:200]}...")
                
                # JSON 형식으로 응답을 파싱
                result = json.loads(json_text)
                
                # 필수 필드가 없는 경우 기본값 설정
                if not isinstance(result, dict):
                    result = {"summary": json_text}
                
                # 요약(summary) 필드 처리
                if "summary" not in result:
                    result["summary"] = "요약 정보가 제공되지 않았습니다."
                
                # key_points 처리 강화
                if "key_points" not in result:
                    logger.warning(f"티켓 요약에 key_points가 없습니다. 자동 생성을 시도합니다. (ticket_id: {ticket_data.get('id')})")
                    result["key_points"] = []
                
                # key_points 타입 확인 및 처리
                if not isinstance(result["key_points"], list):
                    logger.warning(f"key_points가 리스트가 아닙니다. 변환을 시도합니다: {type(result['key_points'])}")
                    
                    # 문자열인 경우, 여러 가지 구분자로 분리 시도
                    if isinstance(result["key_points"], str):
                        # 1. 줄바꿈으로 구분된 경우
                        if '\n' in result["key_points"]:
                            points = [p.strip() for p in result["key_points"].split('\n') if p.strip()]
                        # 2. 쉼표로 구분된 경우
                        elif ',' in result["key_points"]:
                            points = [p.strip() for p in result["key_points"].split(',') if p.strip()]
                        # 3. 세미콜론으로 구분된 경우
                        elif ';' in result["key_points"]:
                            points = [p.strip() for p in result["key_points"].split(';') if p.strip()]
                        # 4. 마침표로 구분된 경우
                        else:
                            points = [p.strip() for p in re.split(r'[.!?]\s+', result["key_points"]) if p.strip()]
                        
                        result["key_points"] = points if points else ["자동 변환 실패"]
                    else:
                        # 다른 타입인 경우 빈 배열로 설정
                        result["key_points"] = []
                
                # key_points가 비어있는 경우 요약에서 추출
                if not result["key_points"]:
                    if "summary" in result and result["summary"]:
                        summary_text = result["summary"]
                        # 요약에서 문장을 추출하여 핵심 포인트로 사용
                        sentences = [s.strip() for s in re.split(r'[.!?]\s+', summary_text) if s.strip() and len(s.strip()) > 10]
                        # 너무 많은 문장이 있다면 처음 3-5개만 사용
                        result["key_points"] = sentences[:min(len(sentences), 5)]
                
                # 여전히 key_points가 없다면 기본값 설정
                if not result["key_points"]:
                    result["key_points"] = ["주요 내용 파악 필요", "상세 정보 확인 요망", "추가 정보 요청 고려"]
                
                # 나머지 필드 처리
                if "sentiment" not in result:
                    result["sentiment"] = "중립적"
                if "priority_recommendation" not in result:
                    result["priority_recommendation"] = "보통"
                if "urgency_level" not in result:
                    result["urgency_level"] = "보통"
                
                return result
            except json.JSONDecodeError as e:
                # JSON 파싱 실패 시 텍스트 전체를 요약으로 처리
                logger.warning(f"JSON 파싱 실패, 텍스트 분석으로 전환 (ticket_id: {ticket_data.get('id')}): {str(e)}")
                
                try:
                    # 응답에서 JSON 형식과 유사한 부분 추출 시도
                    summary_match = re.search(r'"summary"\s*:\s*"([^"]+)"', response.text)
                    summary = summary_match.group(1) if summary_match else response.text
                    
                    # key_points 추출 시도
                    key_points_matches = re.findall(r'"([^"]+)"', re.search(r'"key_points"\s*:\s*\[(.*?)\]', response.text).group(1) if re.search(r'"key_points"\s*:\s*\[(.*?)\]', response.text) else "")
                    key_points = key_points_matches if key_points_matches else []
                    
                    # 텍스트에서 문장을 추출하여 핵심 포인트로 활용 (key_points가 비어있는 경우)
                    if not key_points:
                        sentences = [s.strip() for s in re.split(r'[.!?]\s+', summary) if s.strip() and len(s.strip()) > 10]
                        key_points = sentences[:min(len(sentences), 5)] if sentences else ["자동 생성 실패"]
                    
                    # 감정, 우선순위, 긴급도 추출 시도
                    sentiment_match = re.search(r'"sentiment"\s*:\s*"([^"]+)"', response.text)
                    sentiment = sentiment_match.group(1) if sentiment_match else "중립적"
                    
                    priority_match = re.search(r'"priority_recommendation"\s*:\s*"([^"]+)"', response.text)
                    priority = priority_match.group(1) if priority_match else "보통"
                    
                    urgency_match = re.search(r'"urgency_level"\s*:\s*"([^"]+)"', response.text)
                    urgency = urgency_match.group(1) if urgency_match else "보통"
                    
                    return {
                        "summary": summary,
                        "key_points": key_points,
                        "sentiment": sentiment,
                        "priority_recommendation": priority,
                        "urgency_level": urgency
                    }
                except Exception as regex_error:
                    logger.error(f"정규식 추출 실패: {str(regex_error)}")
                    # 가장 기본적인 형태로 처리
                    summary = response.text
                    # 문장 분리로 핵심 포인트 생성
                    sentences = [s.strip() for s in re.split(r'[.!?]\s+', summary) if s.strip() and len(s.strip()) > 10]
                    key_points = sentences[:min(len(sentences), 5)] if sentences else ["자동 생성 실패"]
                    
                    return {
                        "summary": summary[:1000] if len(summary) > 1000 else summary,  # 요약이 너무 길면 잘라내기
                        "key_points": key_points,
                        "sentiment": "중립적",
                        "priority_recommendation": "보통",
                        "urgency_level": "보통"
                    }
        except Exception as e:
            logger.error(f"티켓 요약 생성 중 오류 발생 (ticket_id: {ticket_data.get('id')}): {e}")
            # 오류 발생 시 기본 메시지 반환
            return {
                "summary": "티켓 요약 생성에 실패했습니다.",
                "key_points": ["요약 생성 오류"],
                "sentiment": "중립적",
                "priority_recommendation": "보통",
                "urgency_level": "보통"
            }

    async def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        OpenAI API를 사용하여 텍스트 임베딩을 생성합니다.
        캐싱을 통해 동일한 텍스트에 대한 중복 요청을 방지합니다.
        
        Args:
            text: 임베딩을 생성할 텍스트
            model: 사용할 임베딩 모델 (기본값: text-embedding-3-small)
            
        Returns:
            텍스트 임베딩 벡터 (리스트)
            
        Raises:
            RuntimeError: OpenAI API 호출이 실패한 경우
        """
        if not OPENAI_API_KEY:
            logger.error("임베딩 생성을 위한 OpenAI API 키가 설정되지 않았습니다.")
            raise RuntimeError("OpenAI API 키가 설정되지 않아 임베딩을 생성할 수 없습니다.")
            
        # 텍스트가 너무 길면 잘라내기 (임베딩 모델 토큰 제한 고려)
        max_length = 8000  # 대략적인 토큰 제한 (모델에 따라 조정 필요)
        original_text = text
        if len(text) > max_length:
            text = text[:max_length]
            logger.warning(f"임베딩 생성을 위해 텍스트를 {max_length}자로 잘랐습니다.")
        
        # 캐시 키 생성
        cache_key = _get_cache_key(text, model)
        
        # 캐시에서 확인
        if cache_key in embedding_cache:
            logger.info(f"캐시에서 임베딩 반환 (cache_key: {cache_key[:8]}..., vector_size: {len(embedding_cache[cache_key])})")
            return embedding_cache[cache_key]
        
        try:
            client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
            logger.info(f"임베딩 생성 시작 (model: {model}, text_length: {len(text)} chars)")
            
            start_time = time.time()
            response = await client.embeddings.create(
                model=model,
                input=text
            )
            duration = (time.time() - start_time) * 1000
            
            embedding = response.data[0].embedding
            
            # 캐시에 저장
            embedding_cache[cache_key] = embedding
            
            logger.info(f"임베딩 생성 완료 (duration: {duration:.2f}ms, vector_size: {len(embedding)}, cached: True)")
            
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {type(e).__name__} - {str(e)}")
            raise RuntimeError(f"임베딩 생성 실패: {str(e)}")

    async def generate_search_query(self, ticket_data: Dict[str, Any]) -> str:
        """
        티켓 데이터를 기반으로 검색에 최적화된 쿼리 텍스트를 생성합니다.
        
        Args:
            ticket_data: 티켓 정보가 포함된 딕셔너리
            
        Returns:
            검색용 쿼리 텍스트
        """
        subject = ticket_data.get("subject", "").strip()
        description = ticket_data.get("description_text", "").strip()
        
        # 기본적으로 제목과 설명을 결합
        query_parts = []
        if subject:
            query_parts.append(subject)
        if description:
            # 설명이 너무 길면 앞부분만 사용
            description_preview = description[:500] if len(description) > 500 else description
            query_parts.append(description_preview)
        
        # 대화 내용이 있다면 최근 메시지도 포함
        conversations = ticket_data.get("conversations", [])
        if conversations:
            # 최근 2개의 대화만 포함 (너무 길어지지 않도록)
            recent_conversations = sorted(conversations, key=lambda c: c.get("created_at", ""), reverse=True)[:2]
            for conv in recent_conversations:
                body = conv.get("body_text", "").strip()
                if body:
                    # 대화 내용도 길면 잘라내기
                    body_preview = body[:200] if len(body) > 200 else body
                    query_parts.append(body_preview)
        
        # 모든 부분을 공백으로 연결
        search_query = " ".join(query_parts).strip()
        
        # 너무 길면 최대 길이로 제한
        max_query_length = 1000
        if len(search_query) > max_query_length:
            search_query = search_query[:max_query_length]
            logger.warning(f"검색 쿼리가 너무 길어 {max_query_length}자로 잘랐습니다.")
        
        logger.info(f"검색 쿼리 생성 완료 (ticket_id: {ticket_data.get('id')}, query_length: {len(search_query)} chars)")
        return search_query

    async def analyze_ticket_issue_solution(self, ticket_data: Dict[str, Any], max_tokens: int = 800) -> Dict[str, str]:
        """
        티켓 데이터를 Issue/Solution 형태로 분석합니다.
        
        Args:
            ticket_data: 티켓 정보가 포함된 딕셔너리
            max_tokens: 분석 결과 최대 토큰 수
            
        Returns:
            {"issue": "문제 상황", "solution": "해결책"} 형태의 딕셔너리
            
        Raises:
            RuntimeError: 모든 LLM 제공자 호출이 실패한 경우
        """
        # 티켓 정보 추출 및 최적화
        subject = ticket_data.get("subject", "제목 없음")
        
        # 설명 텍스트 최적화 (너무 긴 경우 잘라내기)
        description = ticket_data.get("description_text", "설명 없음")
        if len(description) > 1500:  # 너무 긴 설명은 앞뒤 부분만 사용
            description = description[:1000] + "...[중략]..." + description[-300:]
            
        status = ticket_data.get("status", "")
        priority = ticket_data.get("priority", "")
        
        # 대화 내용 최적화 (필수 정보만 포함)
        conversations = ticket_data.get("conversations", [])
        conversation_text = ""
        if conversations:
            # 최대 2개의 최근 대화만 포함
            conversation_text = "\n대화 내용:\n"
            conv_count = 0
            for conv in sorted(conversations, key=lambda c: c.get("created_at", ""), reverse=True):
                if conv_count >= 2:
                    break
                    
                sender = "고객" if conv.get("user_id") else "상담원"
                body = conv.get("body_text", "내용 없음")
                
                # 대화 내용도 적절히 잘라내기
                body_preview = body[:100] + "..." if len(body) > 100 else body
                conversation_text += f"- {sender}: {body_preview}\n"
                conv_count += 1
        
        # 보다 명확한 시스템 프롬프트로 정확한 형식 지정
        system_prompt = (
            "당신은 고객 지원 티켓을 분석하는 AI입니다. "
            "제공된 티켓 정보를 바탕으로 문제 상황(Issue)과 해결책(Solution)을 구분해서 분석해주세요. "
            "정확히 다음 JSON 형식으로만 응답하세요:\n\n"
            '{"issue": "구체적인 문제 상황", "solution": "해결책 또는 조치사항"}\n\n'
            "다른 설명이나 텍스트를 추가하지 말고 오직 위의 JSON 형식만 반환하세요."
        )
        
        # 간결한 프롬프트 구성
        prompt = f"""다음 티켓 정보를 분석하여 문제 상황(Issue)과 해결책(Solution)을 JSON 형식으로 제공해주세요:

제목: {subject}
설명: {description}
상태: {status}
우선순위: {priority}{conversation_text}"""
        
        logger.info(f"티켓 Issue/Solution 분석 요청 (ticket_id: {ticket_data.get('id')}, 제목: '{subject[:30]}...')")
        
        try:
            # LLM을 사용하여 분석 수행
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.2  # 일관성을 위해 낮은 temperature 사용
            )
            
            # JSON 파싱 시도
            import json
            import re
            try:
                # 응답 전처리: 제어 문자 제거 및 이스케이프
                cleaned_text = response.text.strip()
                
                # JSON 추출 시도 (다양한 패턴 지원)
                # 1. 중괄호로 둘러싸인 JSON 객체 (가장 일반적인 패턴)
                json_match = re.search(r'(\{.*\})', cleaned_text, re.DOTALL)
                if json_match:
                    json_text = json_match.group(1)
                    logger.info(f"JSON 추출 성공 (중괄호 패턴): {json_text[:50]}...")
                else:
                    # 2. 전체 텍스트가 중괄호로 둘러싸여 있는지 확인
                    if cleaned_text.strip().startswith('{') and cleaned_text.strip().endswith('}'):
                        json_text = cleaned_text
                        logger.info(f"JSON 추출 성공 (전체 텍스트): {json_text[:50]}...")
                    else:
                        # 3. 코드 블록 내 JSON 검색 시도 (```json {...} ``` 패턴)
                        json_match = re.search(r'```(?:json)?(.*?)```', cleaned_text, re.DOTALL)
                        if json_match:
                            json_text = json_match.group(1).strip()
                            logger.info(f"JSON 추출 성공 (코드 블록): {json_text[:50]}...")
                        else:
                            # 4. 더 공격적으로 중괄호 내용만 추출 시도
                            json_match = re.search(r'\{[^{]*"issue"[^}]*"solution"[^}]*\}', cleaned_text, re.DOTALL)
                            if json_match:
                                json_text = json_match.group(0)
                                logger.info(f"JSON 추출 성공 (패턴 매칭): {json_text[:50]}...")
                            else:
                                # 5. 마지막 시도: 전체 텍스트 사용
                                json_text = cleaned_text
                                logger.info(f"JSON 구조 찾지 못함, 전체 텍스트 사용: {json_text[:50]}...")
                
                # 제어 문자 포괄적 처리
                # 1. 줄바꿈, 탭 등을 공백으로 변환 (JSON 구조 내부 제외)
                json_text = re.sub(r'[\n\r\t\f\v]', ' ', json_text)
                
                # 2. JSON 문자열 내에서 이미 이스케이프된 제어 문자는 이중 이스케이프 처리
                json_text = re.sub(r'(?<=")\\n(?=")', '\\\\n', json_text)
                json_text = re.sub(r'(?<=")\\r(?=")', '\\\\r', json_text)
                json_text = re.sub(r'(?<=")\\t(?=")', '\\\\t', json_text)
                
                # 3. 불필요한 백슬래시 제거 (JSON 형식을 깨뜨릴 수 있는 경우)
                json_text = re.sub(r'\\([^"\\/bfnrtu])', r'\1', json_text)
                
                # 4. 닫히지 않은 따옴표 처리 시도
                # 문자열 마지막이 백슬래시로 끝나는 경우 제거
                json_text = re.sub(r'\\+(?=")', '', json_text)
                
                # 5. 추가 정리: 불필요한 공백 제거
                json_text = re.sub(r'\s+(?=[:,])', '', json_text)
                json_text = re.sub(r'(?<=[:,])\s+', ' ', json_text)
                                
                result = json.loads(json_text)
                if "issue" in result and "solution" in result:
                    logger.info(f"티켓 Issue/Solution 분석 완료 (ticket_id: {ticket_data.get('id')}, model: {response.model_used})")
                    return result
                else:
                    logger.warning(f"LLM 응답에 필수 필드가 없음: {json_text}")
                    raise ValueError("Invalid response format")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"LLM 응답 JSON 파싱 실패: {e}, 응답: {response.text[:200]}...")
                # 파싱 실패 시 텍스트에서 Issue/Solution 추출 시도
                text = response.text.strip()
                
                # 정규식을 사용하여 issue와 solution 부분 추출
                issue = self._extract_section_from_text(text, "issue", "문제 상황을 분석할 수 없습니다.")
                solution = self._extract_section_from_text(text, "solution", "해결책을 찾을 수 없습니다.")
                
                logger.info(f"정규식 추출 결과 - issue: {issue[:50]}..., solution: {solution[:50]}...")
                return {
                    "issue": issue,
                    "solution": solution
                }
                
        except Exception as e:
            logger.error(f"티켓 Issue/Solution 분석 중 오류 발생 (ticket_id: {ticket_data.get('id')}): {e}")
            # 오류 발생 시 기본 메시지 반환
            return {
                "issue": "문제 상황 분석에 실패했습니다.",
                "solution": "해결책 분석에 실패했습니다."
            }
    
    def _extract_section_from_text(self, text: str, section: str, default: str) -> str:
        """
        텍스트에서 특정 섹션을 추출하는 헬퍼 함수 (확장 버전)
        다양한 형식의 응답에서 문제(issue)와 해결책(solution) 섹션을 정확히 추출합니다.
        """
        import re
        
        # 섹션명을 표준화 (대소문자 무시)
        section_lower = section.lower()
        text_lower = text.lower()
        
        # 한국어/영어 섹션명 매핑
        section_names = {
            'issue': ['issue', '문제', '이슈', '상황', 'problem', '질문'],
            'solution': ['solution', '해결책', '솔루션', '해결 방법', '조치', '대응', '답변', '해결']
        }

        # 현재 섹션에 해당하는 이름들
        current_section_names = section_names.get(section_lower, [section_lower])
        
        # 1. 마크다운 스타일 섹션 찾기 시도 (## Issue, ## Solution 등)
        for name in current_section_names:
            markdown_pattern = rf'(?:#+\s*{name}[\s:]*)|((?<=\n){name}[\s:]+)|(^{name}[\s:]+)'
            section_matches = list(re.finditer(markdown_pattern, text_lower, re.IGNORECASE | re.MULTILINE))
            
            if section_matches:
                start_pos = section_matches[0].end()
                
                # 다음 섹션 찾기 (현재 섹션이 아닌 다른 섹션) - 종료 위치 결정
                end_pos = len(text)
                for next_section in section_names.get('solution' if section_lower == 'issue' else 'issue', []):
                    next_section_pattern = rf'(?:#+\s*{next_section}[\s:]*)|((?<=\n){next_section}[\s:]+)|(^{next_section}[\s:]+)'
                    next_matches = list(re.finditer(next_section_pattern, text_lower[start_pos:], re.IGNORECASE | re.MULTILINE))
                    if next_matches:
                        end_pos = start_pos + next_matches[0].start()
                        break
                
                extracted = text[start_pos:end_pos].strip()
                if extracted:
                    return extracted[:500] if len(extracted) > 500 else extracted
        
        # 2. JSON 형식 패턴 (다양한 따옴표 스타일 처리) - 강화된 버전
        json_patterns = []
        for name in current_section_names:
            # 큰 따옴표로 둘러싸인 JSON 키-값
            json_patterns.append(rf'"{name}"[\s:]*"(.*?)(?:"|\n)')
            # 작은 따옴표로 둘러싸인 JSON 키-값
            json_patterns.append(rf"'{name}'[\s:]*'(.*?)(?:'|\n)")
            # 따옴표 혼합 버전
            json_patterns.append(rf'"{name}"[\s:]*\'(.*?)(?:\'|\n)')
            json_patterns.append(rf"'{name}'[\s:]*\"(.*?)(?:\"|\n)")
            # 큰 따옴표 키, 값은 없음
            json_patterns.append(rf'"{name}"[\s:]*([^",\}}\]]+)')
            # 작은 따옴표 키, 값은 없음
            json_patterns.append(rf"'{name}'[\s:]*([^',\}}\]]+)")
            # 따옴표 없는 JSON 스타일
            json_patterns.append(rf"{name}[\s:]*([^,\}}\]]+)")
        
        for pattern in json_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                if extracted:
                    # 따옴표 제거 (시작/끝에 있는 경우)
                    extracted = re.sub(r'^["\']+|["\']+$', '', extracted)
                    return extracted[:500] if len(extracted) > 500 else extracted
        
        # 3. 콜론 형식 (다양한 변형) - 강화된 버전
        colon_patterns = []
        for name in current_section_names:
            # 기본 콜론 형식 (다음 섹션까지)
            colon_patterns.append(rf'{name}[\s:]+([^\n].*?)(?=\n\s*\w+:|\Z)')
            # 대문자 섹션명
            colon_patterns.append(rf'{name.upper()}[\s:]+([^\n].*?)(?=\n\s*\w+:|\Z)')
            # 콜론+대시 형식
            colon_patterns.append(rf'{name}[\s:]+-\s*([^\n].*?)(?=\n\s*\w+:|\Z)')
            # 섹션명 다음에 줄바꿈이 있는 경우
            colon_patterns.append(rf'{name}[\s:]*\n+\s*([^\n].*?)(?=\n\s*\w+:|\Z)')
            # 번호형 목록 항목
            colon_patterns.append(rf'\d+[\s.]*{name}[\s:]*([^\n].*?)(?=\n\s*\d+[\s.]*\w+:|\Z)')
        
        for pattern in colon_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                if extracted:
                    return extracted[:500] if len(extracted) > 500 else extracted
        
        # 4. 단락 기반 키워드 검색 - 강화된 버전
        if section_lower in section_names:
            keywords = '|'.join(current_section_names)
            other_keywords = '|'.join(section_names.get('solution' if section_lower == 'issue' else 'issue', []))
            
            # 키워드로 시작하는 단락 찾기
            keyword_paragraph_pattern = rf'(?:^|\n|\s)(?:{keywords})[\s:]+(.*?)(?=(?:^|\n|\s)(?:{other_keywords})[\s:]|$)'
            match = re.search(keyword_paragraph_pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                if extracted:
                    return extracted[:500] if len(extracted) > 500 else extracted
                    
            # 키워드 기반 세분화된 검색
            if section_lower == 'issue':
                issue_indicators = ['고객이', '문제는', '상황은', '이슈는', '오류', 'error', 'problem is']
                for indicator in issue_indicators:
                    indicator_match = re.search(rf'{indicator}[^\n]*', text, re.IGNORECASE)
                    if indicator_match:
                        return indicator_match.group(0)[:500]
            elif section_lower == 'solution':
                solution_indicators = ['해결 방법', '해결하려면', '권장', '제안', '다음과 같이', '조치', '대응']
                for indicator in solution_indicators:
                    indicator_match = re.search(rf'{indicator}[^\n]*', text, re.IGNORECASE)
                    if indicator_match:
                        # 해당 문장부터 이후 200자 추출
                        start = indicator_match.start()
                        return text[start:start+300].strip()[:500]
        
        # 5. 위치 기반 추출 (강화된 휴리스틱) - 텍스트 분석 기반 추출
        if section_lower == "issue":
            # issue는 주로 앞쪽에 나타남
            # 텍스트 길이에 따라 적응적으로 추출 비율 조정
            if len(text) < 200:
                return text[:len(text)].strip() if text else default
            elif len(text) < 500:
                return text[:len(text)//2].strip() if text else default
            else:
                # 첫 문단이나 처음 25% 텍스트 반환
                first_paragraph_match = re.search(r'^.*?\n\s*\n', text, re.DOTALL)
                if first_paragraph_match and len(first_paragraph_match.group(0)) > 20:
                    return first_paragraph_match.group(0).strip()
                return text[:len(text)//4].strip()[:500]
                
        elif section_lower == "solution":
            # solution은 주로 뒤쪽에 나타남
            if len(text) < 200:
                return text.strip() if text else default
                
            # 텍스트 길이에 따라 적응적으로 추출 비율 조정
            if len(text) < 500:
                return text[len(text)//2:].strip()
            else:
                # 마지막 문단이나 마지막 30% 텍스트 반환
                last_paragraphs = text[int(len(text)*0.7):].strip()
                if last_paragraphs:
                    return last_paragraphs[:500]
                    
                # 마지막 두 문단 찾기 시도
                paragraphs = re.split(r'\n\s*\n', text)
                if len(paragraphs) >= 2:
                    return '\n\n'.join(paragraphs[-2:])[:500]
            
        return default


# 싱글톤 인스턴스 제공
# 타임아웃 값은 환경변수나 설정 파일에서 읽어오는 것이 좋음
# 복잡한 응답 생성을 위해 충분한 시간 제공 (특히 issue/solution 분석)
# 환경 변수로부터 타임아웃 설정 가져오기 (없으면 기본값 사용)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30.0"))  # 기본 30초
LLM_GEMINI_TIMEOUT = float(os.getenv("LLM_GEMINI_TIMEOUT", "40.0"))  # 기본 40초 (Gemini는 더 긴 타임아웃 필요)

# 싱글톤 인스턴스 생성
llm_router = LLMRouter(timeout=LLM_TIMEOUT, gemini_timeout=LLM_GEMINI_TIMEOUT)

async def generate_text(prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
    """텍스트 생성 편의 함수"""
    return await llm_router.generate(prompt, system_prompt, max_tokens, temperature)

# 중복된 standalone 함수는 제거하고 LLMRouter 클래스의 메서드를 사용
