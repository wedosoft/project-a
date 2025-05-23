"""
LLM Router 모듈

이 모듈은 여러 LLM 모델 간의 라우팅 로직을 제공합니다.
Anthropic Claude와 OpenAI GPT-4o 모델 간의 자동 선택 및 fallback 기능을 구현합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import os
import time
import logging
import asyncio
import httpx
from typing import Dict, Any, List, Optional, Union
import anthropic  # 최신 Anthropic 라이브러리 사용
import openai
import google.generativeai as genai # Gemini SDK 임포트
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge

# 로깅 설정
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # main.py에서 이미 설정하므로 중복 제거 또는 레벨 조정

# API 키 설정
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Gemini API 키 추가

# 환경 변수 확인
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
if not GEMINI_API_KEY: # Gemini API 키 확인 추가
    logger.warning("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. GeminiProvider를 사용할 수 없습니다.")


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
    total_tokens_used: int = 0
    total_latency_ms: float = 0.0  # 평균 계산을 위한 총 지연 시간
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
        else:
            self.failed_requests += 1
            if error_info:
                self.error_details.append(error_info)

    @property
    def success_rate(self) -> float:
        """성공률을 계산합니다."""
        if self.total_requests == 0:
            return 1.0  # 요청이 없으면 100% 성공으로 간주 (또는 0.0으로 할 수도 있음)
        return self.successful_requests / self.total_requests


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
    
    def __init__(self, api_key: str = None, timeout: float = 10.0):
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
    
    def __init__(self, api_key: str = None, timeout: float = 15.0):
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
    
    def __init__(self, api_key: str = None, timeout: float = 20.0):
        super().__init__(name="gemini", timeout=timeout) # 부모 클래스 생성자 호출
        self.api_key = api_key or GEMINI_API_KEY
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
        # 초기 우선순위: Anthropic > OpenAI > Gemini (API 키 유효성 및 상태에 따라 동적 조정)
        self.providers_priority = ["anthropic", "openai", "gemini"]
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
            name for name in self.providers_priority 
            if self.provider_instances[name].api_key and self.provider_instances[name].is_healthy()
        ]
        
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

        ordered_list = available_providers + unavailable_providers
        if not ordered_list: # 모든 제공자가 사용 불가능한 극단적인 경우
             logger.error("사용 가능한 LLM 제공자가 없습니다 (API 키 부재 또는 모두 비정상 상태).")
             return [] # 빈 리스트 반환 또는 기본 제공자 이름 반환
        
        logger.info(f"시도할 제공자 순서: {ordered_list}")
        return ordered_list

    # choose_provider 메소드는 _get_ordered_providers로 통합되거나, 더 복잡한 선택 로직을 위해 남겨둘 수 있음.
    # 현재 generate 메소드에서 _get_ordered_providers를 직접 사용하므로 choose_provider는 제거 또는 리팩토링.
    # def choose_provider(self, prompt: str, estimated_tokens: int, has_images: bool) -> LLMProvider:
    # ... 기존 choose_provider 로직 ... (필요시 _get_ordered_providers 내부 로직으로 흡수)


# 싱글톤 인스턴스 제공
# 타임아웃 값은 환경변수나 설정 파일에서 읽어오는 것이 좋음
llm_router = LLMRouter(timeout=15.0, gemini_timeout=25.0) # 타임아웃 값 조정

async def generate_text(prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
    """텍스트 생성 편의 함수"""
    return await llm_router.generate(prompt, system_prompt, max_tokens, temperature)

async def generate_ticket_summary(ticket_data: Dict[str, Any], max_tokens: int = 500) -> str:
    """
    티켓 데이터를 기반으로 LLM을 사용하여 요약문을 생성합니다.
    """
    # 컨텍스트 빌더를 사용하여 LLM 프롬프트에 적합한 형태로 티켓 정보 구성
    # 예시: 티켓 제목, 설명, 최신 대화 몇 개 등
    # 실제 구현에서는 context_builder.py의 함수를 활용하여 더 정교하게 구성해야 함
    
    subject = ticket_data.get("subject", "제목 없음")
    description = ticket_data.get("description_text", "설명 없음") # Freshdesk는 description_text 필드 사용
    conversations = ticket_data.get("conversations", [])
    
    # 간단한 프롬프트 구성 예시
    prompt_context = f"티켓 제목: {subject}\
티켓 설명: {description}\
"
    
    if conversations:
        prompt_context += "\\n최근 대화 내용:\n"
        # 마지막 3개의 사용자 및 상담원 메시지만 포함 (간단히)
        for conv in sorted(conversations, key=lambda c: c.get("created_at"), reverse=True)[:3]:
            sender = "사용자" if conv.get("user_id") else "상담원"
            body = conv.get("body_text", "내용 없음") # Freshdesk는 body_text 필드 사용
            prompt_context += f"- {sender}: {body[:200]}...\n" # 메시지 길이 제한
            
    system_prompt = (
        "당신은 AI 지원 에이전트입니다. 제공된 티켓 정보를 바탕으로 티켓의 핵심 내용을 간결하게 요약해주세요. "
        "요약은 주요 문제점, 고객의 요청, 현재 상태를 포함해야 합니다. "
        "한국어로 답변해주세요."
    )
    
    prompt = f"다음 티켓 정보를 요약해주세요:\n\n{prompt_context}"
    
    logger.info(f"티켓 요약 생성 요청 (ticket_id: {ticket_data.get('id')}, prompt_length: {len(prompt)} chars)")
    
    try:
        # llm_router를 사용하여 텍스트 생성
        response = await llm_router.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens, # 요약문 최대 토큰 수
            temperature=0.3 # 약간 더 창의적인 요약 (0.0 ~ 1.0)
        )
        logger.info(f"티켓 요약 생성 완료 (ticket_id: {ticket_data.get('id')}, model: {response.model_used}, duration: {response.duration_ms}ms)")
        return response.text
    except Exception as e:
        logger.error(f"티켓 요약 생성 중 오류 발생 (ticket_id: {ticket_data.get('id')}): {e}")
        # 오류 발생 시 기본 메시지 또는 예외를 다시 발생시킬 수 있음
        return "티켓 요약 생성에 실패했습니다."
