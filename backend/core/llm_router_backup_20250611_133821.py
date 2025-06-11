# flake8: noqa
# isort: skip_file
# fmt: off
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

# Langchain imports for Phase 1: RunnableParallel
from langchain_core.runnables import RunnableLambda, RunnableParallel
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# 프로젝트 내부 모듈 import
try:
    from .retriever import retrieve_top_k_docs
except ImportError:
    # 상대 경로로 실행될 때 fallback
    from backend.core.retriever import retrieve_top_k_docs

# 로깅 설정
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # main.py에서 이미 설정하므로 중복 제거 또는 레벨 조정

# API 키 설정
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") # Google API 키 (호환성 유지)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")  # DeepSeek API 키 추가

# 환경 변수 확인
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
if not GOOGLE_API_KEY: # Google API 키 확인 추가
    logger.warning("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. GeminiProvider를 사용할 수 없습니다.")
if not DEEPSEEK_API_KEY:
    logger.warning("DEEPSEEK_API_KEY 환경 변수가 설정되지 않았습니다. DeepSeekProvider를 사용할 수 없습니다.")


# 임베딩 캐시 설정 (최대 1000개, 1시간 TTL)
embedding_cache = TTLCache(maxsize=1000, ttl=3600)

# Issue/Solution 캐시 (최대 500개, 6시간 TTL)
issue_solution_cache = TTLCache(maxsize=500, ttl=21600)

def _get_issue_solution_key(ticket_data: Dict[str, Any]) -> str:
    """Issue/Solution 캐시 키 생성"""
    key_fields = {
        "id": ticket_data.get("id"),
        "subject": ticket_data.get("subject"),
        "description": ticket_data.get("description_text", ticket_data.get("description", "")),
    }
    key_json = json.dumps(key_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(key_json.encode("utf-8")).hexdigest()

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

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """추상 메소드: 각 제공자 클래스에서 구현해야 함"""
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산 (기본 구현)"""
        return int(len(text.split()) * 1.3)

    def is_healthy(self) -> bool:
        """제공자가 현재 건강한 상태인지 판단 (복구 메커니즘 포함)"""
        current_time = time.time()
        
        # 🔄 복구 메커니즘: 5분 후 자동 복구 시도
        if self.stats.last_error_timestamp and (current_time - self.stats.last_error_timestamp > 300):  # 5분 후 복구
            logger.info(f"🔄 {self.name} 제공자 복구 시도 - 마지막 실패 후 5분 경과")
            self.stats.consecutive_failures = 0  # 연속 실패 카운트 리셋
            self.stats.last_error_timestamp = None  # 에러 타임스탬프 리셋
        
        healthy = True
        
        # 연속 실패 기준 체크
        if self.stats.consecutive_failures >= 3:  # 연속 실패 3회로 조정
            logger.warning(f"{self.name} 제공자 연속 실패 {self.stats.consecutive_failures}회 이상으로 비정상 상태 간주.")
            healthy = False
            
        # 최근 성공률 기준 체크 (복구 시간 고려)
        if self.stats.last_error_timestamp and (current_time - self.stats.last_error_timestamp < 180): # 최근 3분
            if self.stats.total_requests > 3 and self.stats.success_rate < 0.5: # 요청 3회 이상, 성공률 50% 미만
                 logger.warning(f"{self.name} 제공자 최근 3분 내 성공률 {self.stats.success_rate:.2f}로 비정상 상태 간주.")
                 healthy = False

        # Prometheus 메트릭 업데이트
        llm_provider_health_status.labels(provider=self.name).set(1 if healthy else 0)
        return healthy


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 제공자"""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 4.0):
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
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
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

            # Anthropic 응답에서 텍스트 추출 (타입 안전성 확보)
            text = ""
            if response.content and len(response.content) > 0:
                first_content = response.content[0]
                if hasattr(first_content, 'text'):
                    text = first_content.text
                else:
                    text = str(first_content)
            
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

    def __init__(self, api_key: Optional[str] = None, timeout: float = 4.0):
        super().__init__(name="openai", timeout=timeout) # 부모 클래스 생성자 호출
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            logger.warning(f"{self.name} API 키가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
        # ... 기존 available_models ...
        self.available_models = {
            "gpt-3.5-turbo": {"max_tokens": 16000, "priority": 1},  # 🚀 최고 우선순위 (최고 속도)
            "gpt-4o-mini": {"max_tokens": 128000, "priority": 2},   # 🏃‍♂️ 두 번째 우선순위 (빠르고 강력)
            "gpt-4o": {"max_tokens": 128000, "priority": 3},        # 폴백용으로 변경
        }

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError, asyncio.TimeoutError, httpx.RequestError)), # httpx.RequestError 추가
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.stats.record_failure() # 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        model = "gpt-3.5-turbo"  # 속도 우선으로 GPT-3.5 Turbo 사용
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
            if response.usage and response.usage.completion_tokens: # 토큰 정보가 있을 경우
                llm_tokens_used_total.labels(provider=self.name, model=model).inc(response.usage.completion_tokens)

            # OpenAI 응답에서 텍스트 추출 (null 안전성 확보)
            text = ""
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                text = content.strip() if content else ""
            
            tokens_used = {}
            if response.usage:
                tokens_used = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage.prompt_tokens else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage.completion_tokens else 0
                }

            return LLMResponse(
                text=text,
                model_used=model,
                duration_ms=duration,
                tokens_used=response.usage.completion_tokens if response.usage and response.usage.completion_tokens else 0,
                tokens_total=(response.usage.prompt_tokens if response.usage and response.usage.prompt_tokens else 0) + 
                             (response.usage.completion_tokens if response.usage and response.usage.completion_tokens else 0),
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

    def __init__(self, api_key: Optional[str] = None, timeout: float = 8.0):
        super().__init__(name="gemini", timeout=timeout) # 부모 클래스 생성자 호출
        self.api_key = api_key or GOOGLE_API_KEY
        self.client = None # genai.GenerativeModel 인스턴스
        self.model = "gemini-2.0-flash-exp"  # 기본 모델 설정 (동적 변경 가능)

        if not self.api_key:
            logger.warning(f"GeminiProvider: {self.name} API 키가 없어 초기화되지 않았습니다.")
        else:
            try:
                genai.configure(api_key=self.api_key)
                # 초기 클라이언트는 기본 모델로 설정
                self.client = genai.GenerativeModel(self.model)
                logger.info(f"GeminiProvider ({self.name}) 초기화 완료 (기본 모델: {self.model}).")
                self.available_models = {
                    # 속도 최우선 순서로 정렬 (speed 값은 tokens/second)
                    "gemini-2.0-flash-exp": {"max_tokens": 8192, "priority": 1, "speed": 350},  # 🥇 최고속 실험 모델
                    "gemini-1.5-flash": {"max_tokens": 8192, "priority": 2, "speed": 320},      # 🥈 안정적 고속 모델
                    "gemini-1.5-flash-latest": {"max_tokens": 8192, "priority": 3, "speed": 300}, # 🥉 최신 Flash 모델
                    "gemini-1.5-flash-8b": {"max_tokens": 8192, "priority": 4, "speed": 280},    # 경량화 고속 모델
                    "gemini-pro": {"max_tokens": 30720, "priority": 5, "speed": 150},            # 폴백용 (느리지만 안정적)
                }
            except Exception as e:
                logger.error(f"GeminiProvider ({self.name}) 초기화 실패: {e}")
                self.client = None # 실패 시 명시적으로 None 설정

    def set_model(self, model_name: str):
        """
        동적으로 사용할 모델을 변경합니다.
        
        Args:
            model_name: 변경할 모델명
        """
        if model_name in self.available_models:
            self.model = model_name
            if self.client and self.api_key:
                try:
                    self.client = genai.GenerativeModel(model_name)
                    logger.info(f"Gemini 모델 변경: {model_name}")
                except Exception as e:
                    logger.error(f"Gemini 모델 변경 실패 ({model_name}): {e}")
        else:
            logger.warning(f"지원하지 않는 Gemini 모델: {model_name}")

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
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 2048, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.stats.record_failure() # 통계 기록
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        # 현재 설정된 모델 사용 (동적 변경 가능)
        model_name = self.model

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
            
            # Gemini 성능 모니터링을 위한 상세 로깅
            response_time_seconds = duration / 1000
            if response_time_seconds > 5.0:
                logger.warning(f"🐌 {self.name} 응답 시간이 {response_time_seconds:.2f}초로 느립니다 (타임아웃: {self.timeout}초)")
            else:
                logger.info(f"⚡ {self.name} 응답 완료: {response_time_seconds:.2f}초")
            
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


class DeepSeekProvider(LLMProvider):
    """DeepSeek API 제공자 - 초고속 추론을 위한 R1 Distilled 모델"""

    def __init__(self, api_key: Optional[str] = None, timeout: Optional[float] = None):
        # 환경변수에서 DeepSeek 전용 타임아웃을 읽어오고, 없으면 기본값 10초 사용
        if timeout is None:
            timeout = float(os.getenv("LLM_DEEPSEEK_TIMEOUT", "10.0"))
        super().__init__(name="deepseek", timeout=timeout)
        self.api_key = api_key or DEEPSEEK_API_KEY
        if not self.api_key:
            logger.warning(f"{self.name} API 키가 설정되지 않았습니다.")
            self.client = None
        else:
            # DeepSeek는 OpenAI 호환 API를 제공
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
        
        # 속도 우선 모델 설정 (실제 DeepSeek API 지원 모델)
        self.available_models = {
            "deepseek-chat": {"max_tokens": 128000, "priority": 1, "speed": 350},      # 🚀 최고속 채팅 모델
            "deepseek-reasoner": {"max_tokens": 128000, "priority": 2, "speed": 300},  # ⚡ 추론 모델 (R1 기반)
        }

    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError, asyncio.TimeoutError, httpx.RequestError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.stats.record_failure()
            llm_requests_total.labels(provider=self.name, status='failure').inc()
            raise RuntimeError(f"{self.name} 제공자가 API 키 없이 초기화되었거나 클라이언트 설정에 실패했습니다.")

        start_time = time.time()
        model = "deepseek-chat"  # 가장 빠른 실제 지원 모델 사용
        system = "You are a helpful customer support AI assistant." if system_prompt is None else system_prompt

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
            self.stats.record_success(duration)
            llm_requests_total.labels(provider=self.name, status='success').inc()
            llm_request_duration_seconds.labels(provider=self.name).observe(duration / 1000)
            
            if response.usage and response.usage.completion_tokens:
                llm_tokens_used_total.labels(provider=self.name, model=model).inc(response.usage.completion_tokens)

            text = response.choices[0].message.content.strip()
            tokens_used = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0
            }

            return LLMResponse(
                text=text,
                model_used=model,
                duration_ms=duration,
                tokens_used=tokens_used["completion_tokens"],
                tokens_total=tokens_used["prompt_tokens"] + tokens_used["completion_tokens"],
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


class LLMProviderWeights(BaseModel):
    """LLM 제공자별 가중치 및 우선순위 관리"""
    provider_name: str
    base_weight: float = 1.0  # 기본 가중치 (1.0 = 100%)
    performance_multiplier: float = 1.0  # 성능 기반 배수
    cost_efficiency: float = 1.0  # 비용 효율성 점수
    latency_threshold_ms: float = 5000.0  # 지연 시간 임계값
    max_consecutive_failures: int = 5  # 최대 연속 실패 허용 횟수

    def calculate_dynamic_weight(self, stats: LLMProviderStats) -> float:
        """
        제공자의 통계 데이터를 기반으로 동적 가중치를 계산합니다.

        Args:
            stats: 제공자의 통계 데이터

        Returns:
            계산된 동적 가중치 (0.0 ~ 1.0)
        """
        if not stats or stats.total_requests == 0:
            return self.base_weight

        # 성공률 기반 가중치 (0.0 ~ 1.0)
        success_weight = stats.success_rate

        # 지연 시간 기반 가중치 계산
        avg_latency = stats.average_latency_ms
        if avg_latency <= self.latency_threshold_ms:
            latency_weight = 1.0
        else:
            # 임계값 초과 시 점진적으로 가중치 감소
            latency_weight = max(0.1, self.latency_threshold_ms / avg_latency)

        # 연속 실패 패널티 적용
        failure_penalty = 1.0
        if stats.consecutive_failures > 0:
            # 연속 실패가 늘어날수록 지수적으로 가중치 감소
            failure_penalty = max(0.1, 1.0 - (stats.consecutive_failures / self.max_consecutive_failures))

        # 최종 가중치 계산 (모든 요소의 가중 평균)
        dynamic_weight = (
            self.base_weight *
            success_weight *
            latency_weight *
            failure_penalty *
            self.performance_multiplier
        )

        return max(0.0, min(1.0, dynamic_weight))

    def should_exclude_provider(self, stats: LLMProviderStats) -> bool:
        """
        제공자를 일시적으로 제외해야 하는지 판단합니다.

        Args:
            stats: 제공자의 통계 데이터

        Returns:
            True면 제외, False면 포함
        """
        if not stats:
            return False

        # 연속 실패 횟수가 임계값을 초과하면 제외
        if stats.consecutive_failures >= self.max_consecutive_failures:
            return True

        # 최근 성공률이 매우 낮으면 제외 (최소 3회 요청 이후부터 적용 - 더 빠른 판단)
        if stats.total_requests >= 3 and stats.success_rate < 0.5:  # 5회->3회, 30%->50%로 강화
            return True

        # 평균 지연시간이 임계값의 2배를 초과하면 제외 (장애 상황 대응)
        if stats.total_requests >= 2 and stats.average_latency_ms > (self.latency_threshold_ms * 2):
            return True

        return False


class LLMProviderSelector:
    """LLM 제공자 선택 로직을 관리하는 클래스"""

    def __init__(self):
        # 🎯 Gemini Flash 2.0 최우선 가중치 설정 (사용자 요구사항 반영)
        self.provider_weights = {
            "gemini": LLMProviderWeights(
                provider_name="gemini",
                base_weight=4.0,  # 🥇 최고 우선순위 (Gemini Flash 2.0 - 사용자 요구사항)
                performance_multiplier=5.0,  # 성능 가중치 최대 강화 (350+ tokens/sec)
                cost_efficiency=3.0,  # 매우 높은 비용 효율성
                latency_threshold_ms=800.0,  # 0.8초 임계값 (초고속 응답 기대)
                max_consecutive_failures=1   # 연속 실패 허용 횟수 최소화 (빠른 폴백)
            ),
            "deepseek": LLMProviderWeights(
                provider_name="deepseek",
                base_weight=3.0,  # 🥈 두 번째 우선순위 (DeepSeek R1 Distilled)
                performance_multiplier=4.0,  # 성능 가중치 강화 (383 tokens/sec)
                cost_efficiency=2.5,  # 높은 비용 효율성
                latency_threshold_ms=1000.0,  # 1초 임계값 (초고속 응답 기대)
                max_consecutive_failures=2   # 연속 실패 허용 횟수 감소
            ),
            "openai": LLMProviderWeights(
                provider_name="openai",
                base_weight=2.0,  # 🥉 세 번째 우선순위 (GPT-3.5 Turbo)
                performance_multiplier=2.5,  # 성능 가중치 중간
                cost_efficiency=1.8,  # 비용 효율성 양호
                latency_threshold_ms=2000.0,  # 2초로 단축 (빠른 장애 감지)
                max_consecutive_failures=2   # 연속 실패 허용 횟수 감소
            ),
            "anthropic": LLMProviderWeights(
                provider_name="anthropic",
                base_weight=1.5,  # 🏃‍♂️ 폴백용 우선순위 (Claude 3 Haiku - 안정적)
                performance_multiplier=2.0,  # 기본 성능 가중치
                cost_efficiency=2.0,  # 비용 효율성 우수
                latency_threshold_ms=3000.0,  # 3초 (폴백용이므로 여유있게)
                max_consecutive_failures=3   # 폴백이므로 실패 허용도 높임
            )
        }

    def select_best_provider(self, providers: Dict[str, LLMProvider]) -> Optional[str]:
        """
        사용 가능한 제공자 중에서 가중치 기반으로 최적의 제공자를 선택합니다.

        Args:
            providers: 사용 가능한 제공자 딕셔너리

        Returns:
            선택된 제공자 이름 또는 None
        """
        if not providers:
            return None

        # 건강한 제공자만 필터링
        healthy_providers = {}
        provider_scores = {}

        for name, provider in providers.items():
            if not provider.is_healthy():
                logger.warning(f"제공자 {name}가 비건강 상태로 제외됩니다.")
                continue

            # 가중치 설정이 있는 제공자만 고려
            if name not in self.provider_weights:
                logger.warning(f"제공자 {name}에 대한 가중치 설정이 없습니다.")
                continue

            weights = self.provider_weights[name]

            # 제외 조건 확인
            if weights.should_exclude_provider(provider.stats):
                logger.warning(f"제공자 {name}가 제외 조건에 의해 제외됩니다.")
                continue

            # 동적 가중치 계산
            dynamic_weight = weights.calculate_dynamic_weight(provider.stats)

            healthy_providers[name] = provider
            provider_scores[name] = dynamic_weight

            logger.debug(f"제공자 {name} 점수: {dynamic_weight:.3f}")

        if not healthy_providers:
            logger.error("사용 가능한 건강한 제공자가 없습니다.")
            return None

        # 가장 높은 점수의 제공자 선택
        best_provider = max(provider_scores.items(), key=lambda x: x[1])
        selected_name = best_provider[0]
        selected_score = best_provider[1]

        logger.info(f"선택된 제공자: {selected_name} (점수: {selected_score:.3f})")
        return selected_name

    def get_fallback_order(self, providers: Dict[str, LLMProvider], exclude: Optional[str] = None) -> List[str]:
        """
        폴백 순서를 가중치 기반으로 결정합니다.

        Args:
            providers: 사용 가능한 제공자 딕셔너리
            exclude: 제외할 제공자 이름

        Returns:
            폴백 순서 리스트
        """
        if not providers:
            return []

        provider_scores = []

        for name, provider in providers.items():
            if exclude and name == exclude:
                continue

            if name not in self.provider_weights:
                continue

            weights = self.provider_weights[name]

            # 완전히 죽은 제공자가 아니라면 폴백 후보에 포함
            # (is_healthy()는 더 엄격한 기준이므로 폴백에는 더 관대한 기준 적용)
            if provider.stats.consecutive_failures >= 10:  # 10회 연속 실패 시에만 완전 제외
                continue

            # 가중치가 매우 낮더라도 폴백 후보에는 포함
            dynamic_weight = max(0.1, weights.calculate_dynamic_weight(provider.stats))
            provider_scores.append((name, dynamic_weight))

        # 점수 기준으로 내림차순 정렬
        provider_scores.sort(key=lambda x: x[1], reverse=True)

        fallback_order = [name for name, _ in provider_scores]
        logger.debug(f"폴백 순서: {fallback_order}")

        return fallback_order


class LLMRouter:
    """LLM 라우팅 및 Fallback 로직 구현"""

    def __init__(self, timeout: Optional[float] = None, gemini_timeout: Optional[float] = None): 
        # 🎯 글로벌 5초 타임아웃 설정 적용
        global_timeout = float(os.getenv("LLM_GLOBAL_TIMEOUT", "5.0"))
        self.timeout = timeout if timeout is not None else global_timeout
        
        # Gemini Flash 2.0 최우선 설정으로 타임아웃도 최적화
        self.gemini_timeout = gemini_timeout if gemini_timeout is not None else min(global_timeout, 3.0)  # Gemini는 더 빠르게
        
        # 🚀 Gemini Flash 2.0 최우선 - 가장 빠른 모델부터 초기화
        self.gemini = GeminiProvider(timeout=self.gemini_timeout)  # 🥇 Gemini Flash 2.0 최우선
        self.deepseek = DeepSeekProvider(timeout=min(global_timeout, 3.0))  # 🥈 DeepSeek R1 Distilled
        self.openai = OpenAIProvider(timeout=self.timeout)  # 🥉 OpenAI GPT
        self.anthropic = AnthropicProvider(timeout=self.timeout)  # 🏃‍♂️ Anthropic Claude
        
        # 🎯 Gemini Flash 2.0 최우선 순서로 재정렬
        # 사용자 요구사항: Gemini Flash 2.0을 최우선으로 설정
        self.providers_priority = ["gemini", "deepseek", "openai", "anthropic"]
        self.provider_instances: Dict[str, LLMProvider] = {
            "gemini": self.gemini,        # 🥇 Gemini Flash 2.0 (350+ tokens/sec, 최우선)
            "deepseek": self.deepseek,    # 🥈 DeepSeek R1 Distilled (383 tokens/sec)
            "openai": self.openai,        # 🥉 OpenAI GPT-3.5 Turbo
            "anthropic": self.anthropic   # 🏃‍♂️ Anthropic Claude 3 Haiku
        }

        # 가중치 기반 제공자 선택기 초기화
        self.provider_selector = LLMProviderSelector()
        
        # 🎯 작업별 모델 차등 적용 설정
        # 환경변수에서 작업별 모델 설정 로드
        self.light_model = os.getenv("LLM_LIGHT_MODEL", "gemini-1.5-flash")  # 소형: 요약, 분류
        self.heavy_model = os.getenv("LLM_HEAVY_MODEL", "gemini-2.0-flash-exp")  # 대형: 채팅, 복잡한 작업
        
        # 작업 타입별 모델 매핑
        self.task_model_mapping = {
            # 경량 작업 - 빠른 응답이 중요한 작업들
            "light": {
                "model": self.light_model,
                "max_tokens": 1024,
                "temperature": 0.1,
                "timeout": 3.0,
                "tasks": ["ticket_summary", "ticket_classification", "simple_analysis"]
            },
            # 중량 작업 - 품질이 중요한 작업들
            "heavy": {
                "model": self.heavy_model,
                "max_tokens": 4096,
                "temperature": 0.3,
                "timeout": 8.0,
                "tasks": ["agent_chat", "complex_analysis", "detailed_response", "conversation_analysis"]
            }
        }
        
        logger.info(f"🎯 작업별 모델 설정 완료 - 경량: {self.light_model}, 중량: {self.heavy_model}")

        def get_task_type_from_operation(self, operation: str) -> str:
        """
        작업명으로부터 작업 타입(light/heavy)을 결정합니다.
        
        Args:
            operation: 수행할 작업명
            
        Returns:
            작업 타입 ('light' 또는 'heavy')
        """
        # 경량 작업 키워드들
        light_keywords = [
            "summary", "요약", "classification", "분류", "category", 
            "simple", "간단", "quick", "빠른", "ticket_info", "basic"
        ]
        
        # 중량 작업 키워드들  
        heavy_keywords = [
            "chat", "채팅", "conversation", "대화", "analysis", "분석",
            "detailed", "상세", "complex", "복잡", "agent", "상담",
            "response", "응답", "solution", "해결"
        ]
        
        operation_lower = operation.lower()
        
        # 경량 작업 확인
        for keyword in light_keywords:
            if keyword in operation_lower:
                logger.info(f"🏃‍♂️ 경량 작업 감지: {operation} -> {self.light_model}")
                return "light"
        
        # 중량 작업 확인        
        for keyword in heavy_keywords:
            if keyword in operation_lower:
                logger.info(f"🚀 중량 작업 감지: {operation} -> {self.heavy_model}")
                return "heavy"
        
        # 기본값은 중량 작업으로 분류 (안전하게)
        logger.info(f"🔍 작업 타입 미지정, 중량 작업으로 분류: {operation} -> {self.heavy_model}")
        return "heavy"

    async def generate_with_task_type(self, prompt: str, task_type: str = "heavy", system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """
        작업 타입에 맞는 모델로 텍스트를 생성합니다.
        
        Args:
            prompt: 생성할 텍스트 프롬프트
            task_type: 작업 타입 ('light' 또는 'heavy')
            system_prompt: 시스템 프롬프트
            **kwargs: 추가 생성 옵션
            
        Returns:
            LLM 응답
        """
        # 작업별 설정 가져오기
        task_config = self.task_model_mapping.get(task_type, self.task_model_mapping["heavy"])
        
        # 작업별 설정으로 기본값 업데이트
        max_tokens = kwargs.get("max_tokens", task_config["max_tokens"])
        temperature = kwargs.get("temperature", task_config["temperature"])
        
        # Gemini 제공자의 모델을 작업별로 설정
        original_model = self.gemini.model
        self.gemini.set_model(task_config["model"])
        
        try:
            logger.info(f"🎯 {task_type} 작업 시작 - 모델: {task_config['model']}, 토큰: {max_tokens}")
            
            response = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            # 메타데이터에 작업 타입 정보 추가
            response.metadata["task_type"] = task_type
            response.metadata["model_used"] = task_config["model"]
            
            return response
            
        finally:
            # 원래 모델로 복원
            self.gemini.set_model(original_model)


# 싱글톤 인스턴스 제공
# 타임아웃 값은 환경변수나 설정 파일에서 읽어오는 것이 좋음
# 빠른 폴백을 위해 타임아웃을 단축하여 사용자 경험 개선
# 환경 변수로부터 타임아웃 설정 가져오기 (없으면 기본값 사용)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "4.0"))  # 사용자 경험을 위해 4초로 설정
LLM_GEMINI_TIMEOUT = float(os.getenv("LLM_GEMINI_TIMEOUT", "8.0"))  # Gemini는 8초

# 싱글톤 인스턴스 생성
llm_router = LLMRouter(timeout=LLM_TIMEOUT, gemini_timeout=LLM_GEMINI_TIMEOUT)

async def generate_text(prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
    """텍스트 생성 편의 함수"""
    return await llm_router.generate(prompt, system_prompt, max_tokens, temperature)

# 중복된 standalone 함수는 제거하고 LLMRouter 클래스의 메서드를 사용

# LLM 가중치 및 선택자 클래스들은 LLMRouter 클래스 앞으로 이동됩니다.
