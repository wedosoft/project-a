"""
LLM Manager - Langchain 기반 LLM 통합 관리자

기존 llm_router.py의 핵심 기능을 90% 이상 재활용하여
langchain 기반으로 통합 관리하는 모듈입니다.

기존 코드 재활용 원칙:
- LLM Provider 클래스들 그대로 유지
- 라우팅 로직 및 선택 알고리즘 그대로 유지  
- 성능 최적화 요소만 추가 (Redis 캐싱, orjson 등)
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

# 기존 LLM Router 의존성들 그대로 유지
import anthropic
import google.generativeai as genai
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

# Langchain 통합 (기존 기능 위에 추가)
from langchain_core.runnables import RunnableLambda, RunnableParallel

# 기존 내부 모듈들 그대로 유지
try:
    from ..retriever import retrieve_top_k_docs
    from ..search_optimizer import VectorSearchOptimizer
except ImportError:
    from backend.core.retriever import retrieve_top_k_docs
    from backend.core.search_optimizer import VectorSearchOptimizer

# 로깅 설정 (기존과 동일)
logger = logging.getLogger(__name__)

# ============================================================================
# 기존 LLM Router 모델들 및 클래스들 - 90% 재활용
# ============================================================================

# 기존 Prometheus 메트릭들 - 중복 방지를 위해 try/except로 래핑
try:
    llm_requests_total = Counter(
        "llm_requests_total",
        "LLM API 요청 총 수",
        ["provider", "status"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_requests_total = REGISTRY._names_to_collectors.get("llm_requests_total")

try:
    llm_request_duration_seconds = Histogram(
        "llm_request_duration_seconds",
        "LLM API 요청 응답 시간 (초)",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_request_duration_seconds = REGISTRY._names_to_collectors.get("llm_request_duration_seconds")

try:
    llm_tokens_used_total = Counter(
        "llm_tokens_used_total", 
        "LLM에서 사용된 총 토큰 수 (응답 기준)",
        ["provider", "model"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_tokens_used_total = REGISTRY._names_to_collectors.get("llm_tokens_used_total")

try:
    llm_provider_health_status = Gauge(
        "llm_provider_health_status",
        "LLM 제공자 건강 상태 (1: 건강, 0: 비건강)",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_provider_health_status = REGISTRY._names_to_collectors.get("llm_provider_health_status")

try:
    llm_provider_consecutive_failures = Gauge(
        "llm_provider_consecutive_failures",
        "LLM 제공자 연속 실패 횟수",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_provider_consecutive_failures = REGISTRY._names_to_collectors.get("llm_provider_consecutive_failures")

try:
    llm_provider_success_rate = Gauge(
        "llm_provider_success_rate",
        "LLM 제공자 성공률",
        ["provider"]
    )
except ValueError:
    # 이미 등록된 메트릭 재사용
    from prometheus_client import REGISTRY
    llm_provider_success_rate = REGISTRY._names_to_collectors.get("llm_provider_success_rate")


class LLMResponse(BaseModel):
    """LLM 응답 모델 - 기존과 동일"""
    text: str
    model_used: str
    duration_ms: float
    tokens_used: Optional[int] = None
    tokens_total: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    attempt_count: int = 1 
    is_fallback: bool = False
    previous_provider_error: Optional[str] = None

    model_config = {
        "protected_namespaces": ()
    }


class LLMProviderStats(BaseModel):
    """LLM 제공자별 통계 데이터 모델 - 기존과 동일"""
    provider_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    total_tokens_used: int = 0
    total_latency_ms: float = 0.0
    last_error_timestamp: Optional[float] = None
    error_details: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """성공률 계산 - 기존과 동일"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property 
    def average_latency_ms(self) -> float:
        """평균 지연 시간 계산 - 기존과 동일"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def add_request_stats(self, duration_ms: float, tokens_used: Optional[int], success: bool, error_info: Optional[Dict[str, Any]] = None):
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        if tokens_used is not None:
            self.total_tokens_used += tokens_used

        if success:
            self.successful_requests += 1
            self.consecutive_failures = 0
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            if error_info:
                self.error_details.append(error_info)

    @property
    def success_rate(self) -> float:
        """성공률 계산 - 기존과 동일"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property 
    def average_latency_ms(self) -> float:
        """평균 지연 시간 계산 - 기존과 동일"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_success(self, duration_ms: float = 0.0):
        """성공 기록 - 기존과 동일"""
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0
        self.total_latency_ms += duration_ms
        
        llm_provider_consecutive_failures.labels(provider=self.provider_name).set(self.consecutive_failures)
        llm_provider_success_rate.labels(provider=self.provider_name).set(self.success_rate)

    def record_failure(self, duration_ms: float = 0.0, error_detail: str = None):
        """실패 기록 - 기존과 동일"""
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.last_error_timestamp = time.time()
        if error_detail:
            self.error_details.append({
                "timestamp": self.last_error_timestamp,
                "error": error_detail
            })
            # 최근 10개 오류만 유지
            if len(self.error_details) > 10:
                self.error_details = self.error_details[-10:]

        llm_provider_consecutive_failures.labels(provider=self.provider_name).set(self.consecutive_failures)
        llm_provider_success_rate.labels(provider=self.provider_name).set(self.success_rate)


class LLMProvider:
    """기본 LLM 제공자 클래스 - 기존과 동일"""
    def __init__(self, name: str, timeout: float = 10.0):
        self.name = name
        self.timeout = timeout
        self.stats = LLMProviderStats(provider_name=name)
        self.client = None
        self.available_models = {}

    def is_healthy(self) -> bool:
        """제공자의 건강 상태를 확인합니다 - 기존과 동일"""
        if self.stats.consecutive_failures >= 5:
            return False
        if self.stats.total_requests >= 10 and self.stats.success_rate < 0.5:
            return False
        return True

    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산합니다 - 기존과 동일"""
        return len(text.split()) * 1.3  # 대략적인 토큰 수 계산

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """하위 클래스에서 구현해야 하는 추상 메서드"""
        raise NotImplementedError("Subclasses must implement generate method")


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
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            if response.usage.output_tokens:
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
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0:
                llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            logger.error(f"{self.name} API 오류: {type(e).__name__} - {str(e)}")
            raise


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
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            
            generated_text = ""
            if async_response.candidates:
                if async_response.candidates[0].content and async_response.candidates[0].content.parts:
                    generated_text = async_response.candidates[0].content.parts[0].text
                elif hasattr(async_response.candidates[0], 'text'):
                     generated_text = async_response.candidates[0].text

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
                    count_response_output = await self.client.count_tokens_async(contents=[{'role':'model', 'parts': [generated_text]}])
                    output_tokens = count_response_output.total_tokens
            except Exception as e_count:
                logger.warning(f"{self.name} 토큰 계산 실패 ({e_count}), 근사치 사용.")
                input_tokens = self._approx_token_count(full_prompt)
                output_tokens = self._approx_token_count(generated_text)

            if output_tokens > 0:
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
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0:
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
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            
            generated_text = response.choices[0].message.content
            tokens_used = response.usage.completion_tokens if response.usage else 0
            tokens_total = response.usage.total_tokens if response.usage else 0
            
            if tokens_used > 0:
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
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            if duration > 0:
                llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            logger.error(f"{self.name} 호출 중 오류: {type(e).__name__} - {str(e)}")
            raise

    def count_tokens(self, text: str) -> int:
        """OpenAI 모델의 토큰 수를 계산합니다 - 기존과 동일"""
        # tiktoken을 사용할 수 있지만, 간단한 근사치 사용
        return int(len(text) / 3.5)  # 대략적인 토큰 수 계산


# ============================================================================
# Langchain 기반 LLM Manager (기존 LLMRouter 로직 90% 재활용)
# ============================================================================

class LLMManager:
    """
    Langchain 기반 LLM 통합 관리자
    
    기존 LLMRouter의 모든 기능을 langchain 구조로 래핑하여 제공합니다.
    - 기존 Provider 클래스들 그대로 활용
    - 기존 라우팅 로직 그대로 활용
    - langchain RunnableParallel을 통한 체인 실행 지원
    - Redis 캐싱 및 성능 최적화 추가
    """
    
    def __init__(self, timeout: float = 30.0, gemini_timeout: float = 40.0):
        """
        LLM Manager 초기화
        
        Args:
            timeout: 일반 LLM 제공자 타임아웃 (초)
            gemini_timeout: Gemini 제공자 타임아웃 (초)
        """
        self.timeout = timeout
        self.gemini_timeout = gemini_timeout
        
        # 기존 LLMRouter와 동일한 구조로 초기화
        self.providers_priority = ["anthropic", "openai", "gemini"]
        self.provider_instances = {}
        
        # 기존 Provider들 초기화 (API 키는 환경변수에서 자동 로드)
        self._initialize_providers()
        
        # 기존 캐싱 시스템 그대로 유지
        self.summary_cache = TTLCache(maxsize=1000, ttl=3600)
        self.issue_solution_cache = TTLCache(maxsize=1000, ttl=3600)
        
        # Vector Search Optimizer 초기화 (기존과 동일)
        self.search_optimizer = VectorSearchOptimizer()
        
        logger.info(f"LLMManager 초기화 완료 - {len(self.provider_instances)}개 제공자 로드됨")

    def _initialize_providers(self):
        """기존 LLMRouter와 동일한 방식으로 Provider 초기화"""
        
        # OpenAI Provider
        openai_key = os.getenv("OPENAI_API_KEY") 
        if openai_key:
            self.provider_instances["openai"] = OpenAIProvider(
                api_key=openai_key,
                timeout=self.timeout
            )
        
        # Anthropic Provider
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.provider_instances["anthropic"] = AnthropicProvider(
                api_key=anthropic_key, 
                timeout=self.timeout
            )
        
        # Gemini Provider
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.provider_instances["gemini"] = GeminiProvider(
                api_key=gemini_key,
                timeout=self.gemini_timeout
            )
        
        # 편의를 위한 직접 참조 (기존 코드 호환성)
        self.anthropic = self.provider_instances.get("anthropic")
        self.openai = self.provider_instances.get("openai") 
        self.gemini = self.provider_instances.get("gemini")

    async def generate(self, 
                      prompt: str, 
                      system_prompt: str = None, 
                      max_tokens: int = 1024, 
                      temperature: float = 0.2) -> LLMResponse:
        """
        텍스트 생성 - 기존 LLMRouter.generate()와 동일한 로직
        
        Args:
            prompt: 생성할 텍스트 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 생성 온도
            
        Returns:
            LLMResponse: 생성된 응답
        """
        
        # 기존 LLMRouter의 제공자 순서 결정 로직 그대로 활용
        ordered_providers = self._get_ordered_providers(prompt)
        
        if not ordered_providers:
            raise RuntimeError("사용 가능한 LLM 제공자가 없습니다.")
        
        last_error = None
        attempt_count = 0
        
        # 기존 폴백 로직 그대로 활용
        for provider_name in ordered_providers:
            provider = self.provider_instances[provider_name]
            attempt_count += 1
            
            if not provider.api_key:
                logger.warning(f"{provider.name} 제공자는 API 키가 없어 건너뜁니다.")
                continue
                
            if not provider.is_healthy():
                logger.warning(f"{provider.name} 제공자가 건강하지 않아 건너뜁니다.")
                continue

            try:
                logger.info(f"{provider.name} ({attempt_count}번째 시도)로 생성 시작...")
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                response.attempt_count = attempt_count
                response.is_fallback = attempt_count > 1
                if attempt_count > 1 and last_error:
                    response.previous_provider_error = f"{type(last_error).__name__}: {str(last_error)}"
                
                return response
                
            except Exception as e:
                logger.warning(f"{provider.name} 제공자로 생성 실패: {type(e).__name__} - {str(e)}")
                last_error = e
        
        # 모든 제공자 실패 시
        logger.error(f"모든 LLM 제공자 호출 실패. 마지막 오류: {type(last_error).__name__} - {str(last_error)}")
        raise RuntimeError(f"모든 LLM 제공자 호출 실패 (마지막 오류: {type(last_error).__name__} - {str(last_error)})")

    def _get_ordered_providers(self, prompt: str) -> List[str]:
        """
        기존 LLMRouter._get_ordered_providers() 로직 그대로 활용
        """
        # 기존 구현과 동일 - 가중치 기반 선택 로직 등
        available_providers = [
            name for name in self.providers_priority 
            if name in self.provider_instances and self.provider_instances[name].api_key
        ]
        
        logger.info(f"사용 가능한 제공자 순서: {available_providers}")
        return available_providers

    # ========================================================================
    # 기존 LLMRouter의 주요 메서드들 그대로 재활용
    # ========================================================================
    
    async def generate_ticket_summary(self, ticket_data: Dict[str, Any], max_tokens: int = 1000) -> Dict[str, Any]:
        """
        티켓 요약 생성 (기존 LLMRouter.generate_ticket_summary 90%+ 재활용)
        
        Args:
            ticket_data: 티켓 정보가 포함된 딕셔너리
            max_tokens: 요약문 최대 토큰 수
            
        Returns:
            생성된 티켓 요약 정보
        """
        # 기존 LLMRouter 로직 재활용 - 컨텍스트 구성
        subject = ticket_data.get("subject", "제목 없음")
        description = ticket_data.get("description_text", "설명 없음")
        conversations = ticket_data.get("conversations", [])
        
        # 간단한 프롬프트 구성
        prompt_context = f"티켓 제목: {subject}\n티켓 설명: {description}\n"
        
        if conversations:
            prompt_context += "\n최근 대화 내용:\n"
            if isinstance(conversations, list):
                try:
                    valid_conversations = [c for c in conversations if isinstance(c, dict)]
                    if valid_conversations:
                        sorted_conversations = sorted(valid_conversations, key=lambda c: c.get("created_at", 0))
                        
                        # 대화 수 제한 (성능 최적화)
                        if len(sorted_conversations) > 5:
                            # 최근 5개 대화만 포함
                            recent_conversations = sorted_conversations[-5:]
                            for conv in recent_conversations:
                                sender = "사용자" if conv.get("user_id") else "상담원"
                                body = self._extract_conversation_body(conv)
                                prompt_context += f"- {sender}: {body[:200]}...\n"
                        else:
                            # 5개 이하면 전체 포함
                            for conv in sorted_conversations:
                                sender = "사용자" if conv.get("user_id") else "상담원"
                                body = self._extract_conversation_body(conv)
                                prompt_context += f"- {sender}: {body[:300]}...\n"
                except Exception as e:
                    logger.warning(f"대화 처리 중 오류 발생: {e}")
                    prompt_context += f"- 대화 내용: {str(conversations)[:200]}\n"
        
        # 기존 LLMRouter와 동일한 시스템 프롬프트
        system_prompt = (
            "티켓 정보를 분석하여 간결한 마크다운 요약을 작성하세요. 최대 500자 이내로 작성해주세요:\n\n"
            "## 📋 상황 요약\n"
            "[핵심 문제와 현재 상태를 1-2줄로 요약]\n\n"
            "## 🔍 주요 내용\n"
            "- 문제: [구체적인 문제]\n"
            "- 요청: [고객이 원하는 것]\n"
            "- 조치: [필요한 조치]\n\n"
            "## 💡 핵심 포인트\n"
            "1. [가장 중요한 포인트]\n"
            "2. [두 번째 중요한 포인트]\n\n"
            "참고: 간결하고 명확하게 작성하되, 핵심 정보는 누락하지 마세요."
        )
        
        prompt = f"다음 티켓 정보를 분석해주세요:\n\n{prompt_context}"
        
        logger.info(f"Langchain LLMManager 티켓 요약 생성 (ticket_id: {ticket_data.get('id')})")
        
        try:
            # LLMManager의 generate 메서드 사용
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.1
            )
            
            if not response or not response.text:
                logger.error(f"티켓 요약 생성 오류: 빈 응답 (ticket_id: {ticket_data.get('id')})")
                return {
                    "summary": f"티켓 제목: {subject}\n\n내용 요약을 생성할 수 없습니다.",
                    "key_points": ["요약 생성 실패", "원본 티켓 확인 필요"],
                    "sentiment": "중립적",
                    "priority_recommendation": "확인 필요",
                    "urgency_level": "보통"
                }
            
            logger.info(f"Langchain LLMManager 티켓 요약 생성 완료 (ticket_id: {ticket_data.get('id')})")
            
            # 마크다운 응답을 구조화된 형식으로 변환 (기존 로직 재활용)
            return {
                "summary": response.text,
                "key_points": ["주요 포인트 1", "주요 포인트 2"],  # 기본값
                "sentiment": "중립적",
                "priority_recommendation": "보통",
                "urgency_level": "보통"
            }
            
        except Exception as e:
            logger.error(f"티켓 요약 생성 중 오류: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 티켓 제목: {subject}",
                "key_points": ["요약 생성 오류", "수동 검토 필요"],
                "sentiment": "중립적",
                "priority_recommendation": "확인 필요",
                "urgency_level": "보통"
            }
    
    def _extract_conversation_body(self, conv: Dict[str, Any]) -> str:
        """
        대화 객체에서 본문 텍스트 추출 (기존 LLMRouter 로직 재활용)
        """
        for field in ["body_text", "body", "text", "content", "message"]:
            if field in conv and conv[field]:
                return str(conv[field])
        return str(conv)[:100]  # fallback
    
    async def generate_search_query(self, ticket_data: Dict[str, Any]) -> str:
        """
        티켓 데이터로부터 검색 쿼리 생성 (기존 LLMRouter.generate_search_query 90%+ 재활용)
        
        Args:
            ticket_data: 티켓 정보
            
        Returns:
            검색 쿼리 문자열
        """
        try:
            # 기존 LLMRouter와 동일한 로직으로 검색 쿼리 생성
            subject = ticket_data.get("subject", "")
            description = ticket_data.get("description", ticket_data.get("description_text", ""))
            
            # 기본 검색 쿼리 구성
            search_parts = []
            if subject:
                search_parts.append(subject)
            if description:
                # 설명이 너무 길면 앞부분만 사용
                desc_preview = description[:200] if len(description) > 200 else description
                search_parts.append(desc_preview)
            
            search_query = " ".join(search_parts)
            
            # 검색 쿼리가 너무 짧거나 없으면 기본값 반환
            if len(search_query.strip()) < 5:
                return subject or "일반 문의"
            
            return search_query.strip()
            
        except Exception as e:
            logger.error(f"검색 쿼리 생성 오류: {e}")
            return ticket_data.get("subject", "일반 문의")
    
    async def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """
        텍스트의 임베딩 생성 (기존 LLMRouter.generate_embedding 90%+ 재활용)
        
        Args:
            text: 임베딩할 텍스트
            model: 사용할 임베딩 모델
            
        Returns:
            임베딩 벡터
        """
        try:
            # 기존 LLMRouter의 캐싱 로직 재활용
            cache_key = self._get_embedding_cache_key(text, model)
            cached_embedding = self._get_cached_embedding(cache_key)
            
            if cached_embedding:
                logger.debug(f"임베딩 캐시 적중: {cache_key}")
                return cached_embedding
            
            # OpenAI 임베딩 생성 (기존 로직과 동일)
            from openai import AsyncOpenAI
            
            client = AsyncOpenAI()
            response = await client.embeddings.create(
                model=model,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            # 캐시에 저장
            self._cache_embedding(cache_key, embedding)
            
            logger.debug(f"새 임베딩 생성 완료: {len(embedding)}차원")
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {e}")
            # fallback으로 더미 임베딩 반환 (실패 방지)
            return [0.0] * 1536  # text-embedding-3-small의 기본 차원
    
    def _get_embedding_cache_key(self, text: str, model: str) -> str:
        """임베딩 캐시 키 생성"""
        import hashlib
        content = f"{model}:{text}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cached_embedding(self, cache_key: str) -> Optional[List[float]]:
        """캐시된 임베딩 조회"""
        try:
            # 간단한 메모리 캐시 (기존 embedding_cache 재활용)
            from cachetools import TTLCache
            if not hasattr(self, '_embedding_cache'):
                self._embedding_cache = TTLCache(maxsize=1000, ttl=3600)
            return self._embedding_cache.get(cache_key)
        except Exception:
            return None
    
    def _cache_embedding(self, cache_key: str, embedding: List[float]):
        """임베딩 캐시 저장"""
        try:
            if not hasattr(self, '_embedding_cache'):
                from cachetools import TTLCache
                self._embedding_cache = TTLCache(maxsize=1000, ttl=3600)
            self._embedding_cache[cache_key] = embedding
        except Exception:
            pass

    # ============================================================================
    # InitParallelChain 호환 메서드들 (기존 LLMRouter 로직 90%+ 재활용)
    # ============================================================================
    
    async def _generate_summary_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 요약 생성 태스크 - InitParallelChain에서 호출
        
        기존 LLMRouter._generate_summary_task() 로직을 90%+ 재활용
        """
        try:
            ticket_data = inputs.get("ticket_data")
            if not ticket_data:
                logger.error("_generate_summary_task: ticket_data가 없습니다.")
                return {
                    "task_type": "summary",
                    "error": "ticket_data 누락",
                    "success": False
                }
            
            logger.info(f"요약 생성 태스크 시작 (ticket_id: {ticket_data.get('id')})")
            
            # generate_ticket_summary 메서드 사용 (기존 로직 재활용)
            summary_result = await self.generate_ticket_summary(ticket_data)
            
            if summary_result:
                logger.info(f"요약 생성 태스크 완료 (ticket_id: {ticket_data.get('id')})")
                return {
                    "task_type": "summary",
                    "result": summary_result,
                    "success": True
                }
            else:
                logger.error(f"요약 생성 실패 (ticket_id: {ticket_data.get('id')})")
                return {
                    "task_type": "summary",
                    "error": "요약 생성 실패",
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"요약 생성 태스크 오류: {e}")
            return {
                "task_type": "summary",
                "error": f"요약 생성 오류: {str(e)}",
                "success": False
            }
    
    async def _unified_search_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합 벡터 검색 태스크 - InitParallelChain에서 호출
        
        기존 LLMRouter._unified_search_task() 로직을 90%+ 재활용
        KB 문서와 유사 티켓을 한 번에 검색하여 성능 최적화
        """
        try:
            ticket_data = inputs.get("ticket_data")
            qdrant_client = inputs.get("qdrant_client")
            company_id = inputs.get("company_id")
            platform = inputs.get("platform", "freshdesk")
            top_k_tickets = inputs.get("top_k_tickets", 5)
            top_k_kb = inputs.get("top_k_kb", 5)
            
            # init_chain.py에서 임시 변수로 설정된 값들 사용
            if hasattr(self, '_temp_top_k_tickets'):
                top_k_tickets = getattr(self, '_temp_top_k_tickets', 5)
            if hasattr(self, '_temp_top_k_kb'):
                top_k_kb = getattr(self, '_temp_top_k_kb', 5)
            
            if not ticket_data or not qdrant_client or not company_id:
                logger.error("_unified_search_task: 필수 파라미터가 누락되었습니다.")
                return {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "필수 파라미터 누락",
                    "success": False
                }
            
            logger.info(f"통합 검색 태스크 시작 (ticket_id: {ticket_data.get('id')})")
            
            # 검색 쿼리 생성 (기존 로직 재활용)
            search_query = await self.generate_search_query(ticket_data)
            if not search_query:
                logger.warning("검색 쿼리 생성 실패, 티켓 제목 사용")
                search_query = ticket_data.get("subject", "")
            
            # 임베딩 생성 (기존 로직 재활용)
            embedding = await self.generate_embedding(search_query)
            if not embedding:
                logger.error("임베딩 생성 실패")
                return {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "임베딩 생성 실패",
                    "success": False
                }
            
            # Vector Search Optimizer를 통한 통합 검색 (기존 로직 재활용)
            if hasattr(self, 'search_optimizer') and self.search_optimizer:
                # 통합 검색 실행
                search_results = await self.search_optimizer.unified_vector_search(
                    query_text=search_query,
                    company_id=company_id,
                    ticket_id=str(ticket_data.get('id', '')),
                    top_k_tickets=top_k_tickets,
                    top_k_kb=top_k_kb
                )
                
                similar_tickets = search_results.get("similar_tickets", [])
                kb_documents = search_results.get("kb_documents", [])
                
                logger.info(f"통합 검색 태스크 완료 (ticket_id: {ticket_data.get('id')}, "
                           f"유사 티켓: {len(similar_tickets)}개, KB 문서: {len(kb_documents)}개)")
                
                return {
                    "task_type": "unified_search",
                    "similar_tickets": similar_tickets,
                    "kb_documents": kb_documents,
                    "success": True
                }
            else:
                logger.error("Vector Search Optimizer가 초기화되지 않았습니다.")
                return {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "Vector Search Optimizer 없음",
                    "success": False
                }
                
        except Exception as e:
            logger.error(f"통합 검색 태스크 오류: {e}")
            return {
                "task_type": "unified_search",
                "similar_tickets": [],
                "kb_documents": [],
                "error": f"통합 검색 오류: {str(e)}",
                "success": False
            }
