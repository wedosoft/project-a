#!/usr/bin/env python3
"""
🚀 속도 최우선 LLM Router - Gemini Flash 2.0 최우선 버전

OpenAI API 장애 대응을 위한 속도 중심 라우터:
- 글로벌 5초 타임아웃
- Gemini Flash 2.0 최우선 (1순위)
- 작업별 모델 차등 적용 (소형/중형/대형)
- 빠른 폴백 및 복구 메커니즘
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

import anthropic
import google.generativeai as genai
import httpx
import openai
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# 프로젝트 내부 모듈 import
try:
    from .config import get_settings
except ImportError:
    from backend.core.config import get_settings

# 로깅 설정
logger = logging.getLogger(__name__)

# Settings 인스턴스 가져오기
settings = get_settings()

# API 키 설정 (환경변수 기반)
ANTHROPIC_API_KEY = settings.ANTHROPIC_API_KEY
OPENAI_API_KEY = settings.OPENAI_API_KEY
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
DEEPSEEK_API_KEY = settings.DEEPSEEK_API_KEY

# 글로벌 설정 (환경변수 기반)
GLOBAL_TIMEOUT = settings.LLM_GLOBAL_TIMEOUT
GEMINI_TIMEOUT = settings.LLM_GEMINI_TIMEOUT
DEEPSEEK_TIMEOUT = settings.LLM_DEEPSEEK_TIMEOUT
ANTHROPIC_TIMEOUT = settings.LLM_ANTHROPIC_TIMEOUT
OPENAI_TIMEOUT = settings.LLM_OPENAI_TIMEOUT
MAX_RETRIES = settings.LLM_MAX_RETRIES


class LLMResponse(BaseModel):
    """LLM 응답 모델"""
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


class LLMProvider:
    """LLM 제공자 기본 클래스"""
    
    def __init__(self, name: str, timeout: float = GLOBAL_TIMEOUT):
        self.name = name
        self.timeout = timeout
        self.api_key: Optional[str] = None
        self.client = None
        self.failure_count = 0
        self.last_success_time = time.time()
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                      max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """추상 메서드: 각 제공자에서 구현"""
        raise NotImplementedError
    
    def is_healthy(self) -> bool:
        """제공자 건강성 체크 - 더 엄격한 기준"""
        # 연속 실패 3회 이상이면 비건강 (기존 5회 → 3회)
        if self.failure_count >= 3:
            return False
        
        # 2분 이상 성공이 없으면 의심스러운 상태 (기존 5분 → 2분)
        if time.time() - self.last_success_time > 120:
            return False
            
        return True
    
    def record_success(self):
        """성공 기록"""
        self.failure_count = 0
        self.last_success_time = time.time()
    
    def record_failure(self):
        """실패 기록"""
        self.failure_count += 1


class GeminiProvider(LLMProvider):
    """🥇 Gemini Flash 2.0 제공자 - 최우선"""
    
    def __init__(self, timeout: Optional[float] = None):
        super().__init__("gemini", timeout or GEMINI_TIMEOUT)
        self.api_key = GOOGLE_API_KEY
        self.model = "gemini-2.0-flash-exp"  # 기본값 (동적 변경 가능)
        
        if self.api_key:
            try:
                # Gemini 클라이언트 초기화
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(self.model)
                logger.info(f"🥇 Gemini Flash 2.0 초기화 완료 (모델: {self.model})")
            except Exception as e:
                logger.error(f"Gemini 초기화 실패: {e}")
                self.client = None
        else:
            logger.warning("Gemini API 키가 설정되지 않았습니다")
    
    def set_model(self, model_name: str):
        """모델 동적 변경"""
        available_models = [
            "gemini-2.0-flash-exp",  # 중량 작업용
            "gemini-1.5-flash",      # 경량 작업용
            "gemini-1.5-flash-8b",   # 초경량 작업용
        ]
        
        if model_name in available_models and self.api_key:
            self.model = model_name
            try:
                # Gemini 클라이언트 초기화
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(model_name)
                logger.info(f"Gemini 모델 변경: {model_name}")
            except Exception as e:
                logger.error(f"Gemini 모델 변경 실패: {e}")
    
    @retry(
        retry=retry_if_exception_type((httpx.RequestError, asyncio.TimeoutError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                      max_tokens: int = 2048, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.record_failure()
            raise RuntimeError("Gemini 클라이언트가 초기화되지 않았습니다")
        
        start_time = time.time()
        
        # 프롬프트 구성
        if system_prompt:
            full_prompt = f"System Instructions: {system_prompt}\n\nUser Query: {prompt}"
        else:
            full_prompt = prompt
        
        # Gemini 생성 설정
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        
        try:
            # 실제 Gemini API 호출
            response = await asyncio.wait_for(
                self.client.generate_content_async(
                    contents=full_prompt,
                    generation_config=generation_config,
                ),
                timeout=self.timeout
            )
            
            duration = (time.time() - start_time) * 1000
            
            # 응답 텍스트 추출
            text = response.text if hasattr(response, 'text') else str(response)
            
            self.record_success()
            
            return LLMResponse(
                text=text,
                model_used=self.model,
                duration_ms=duration,
                tokens_used=len(text.split()),  # 간단한 토큰 추정
                metadata={"provider": self.name, "model": self.model}
            )
            
        except Exception as e:
            self.record_failure()
            error_msg = str(e)
            duration = (time.time() - start_time) * 1000
            
            # 상세한 에러 로깅
            logger.error(f"🚨 Gemini API 호출 실패 (timeout: {self.timeout}s, duration: {duration:.1f}ms)")
            logger.error(f"   ❌ 오류 타입: {type(e).__name__}")
            logger.error(f"   ❌ 오류 메시지: {error_msg}")
            logger.error(f"   ❌ 프롬프트 길이: {len(full_prompt)} chars")
            
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"   ⏰ Gemini 타임아웃 발생 - {self.timeout}초 초과")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                logger.error("   🚫 Gemini Rate Limit 도달")
            elif "quota" in error_msg.lower():
                logger.error("   💰 Gemini 할당량 초과")
            else:
                logger.error(f"   🔧 기타 Gemini 오류: {repr(e)}")
            
            raise RuntimeError(f"Gemini 호출 실패: {error_msg}")


class DeepSeekProvider(LLMProvider):
    """🥈 DeepSeek R1 제공자 - 2순위"""
    
    def __init__(self, timeout: Optional[float] = None):
        super().__init__("deepseek", timeout or DEEPSEEK_TIMEOUT)
        self.api_key = DEEPSEEK_API_KEY
        
        if self.api_key:
            self.client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
            logger.info("🥈 DeepSeek R1 초기화 완료")
        else:
            logger.warning("DeepSeek API 키가 설정되지 않았습니다")
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError, asyncio.TimeoutError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                      max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.record_failure()
            raise RuntimeError("DeepSeek 클라이언트가 초기화되지 않았습니다")
        
        start_time = time.time()
        system = system_prompt or "You are a helpful customer support AI assistant."
        
        # 타입 안전한 메시지 구성
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,  # type: ignore - 메시지 타입 문제 우회
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=self.timeout
            )
            
            duration = (time.time() - start_time) * 1000
            text = ""
            
            if response.choices and response.choices[0].message.content:
                text = response.choices[0].message.content.strip()
            
            if not text:
                raise ValueError("DeepSeek 응답이 비어있습니다")
            
            self.record_success()
            
            return LLMResponse(
                text=text,
                model_used="deepseek-chat",
                duration_ms=duration,
                tokens_used=response.usage.completion_tokens if response.usage else len(text.split()),
                metadata={"provider": self.name}
            )
            
        except Exception as e:
            self.record_failure()
            error_msg = str(e)
            duration = (time.time() - start_time) * 1000
            
            # 상세한 에러 로깅
            logger.error(f"🚨 DeepSeek API 호출 실패 (timeout: {self.timeout}s, duration: {duration:.1f}ms)")
            logger.error(f"   ❌ 오류 타입: {type(e).__name__}")
            logger.error(f"   ❌ 오류 메시지: {error_msg}")
            logger.error(f"   ❌ 프롬프트 길이: {len(prompt)} chars")
            
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"   ⏰ DeepSeek 타임아웃 발생 - {self.timeout}초 초과")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                logger.error("   🚫 DeepSeek Rate Limit 도달")
            elif "quota" in error_msg.lower():
                logger.error("   💰 DeepSeek 할당량 초과")
            else:
                logger.error(f"   🔧 기타 DeepSeek 오류: {repr(e)}")
            
            raise RuntimeError(f"DeepSeek 호출 실패: {error_msg}")
            
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"   ⏰ DeepSeek 타임아웃 발생 - {self.timeout}초 초과")
            elif hasattr(e, 'status_code'):
                status_code = getattr(e, 'status_code', None)
                logger.error(f"   🌐 HTTP 상태 코드: {status_code}")
                if status_code == 429:
                    logger.error("   🚫 DeepSeek Rate Limit 도달")
                elif status_code == 401:
                    logger.error("   🔑 DeepSeek 인증 실패")
                elif status_code and status_code >= 500:
                    logger.error("   🔧 DeepSeek 서버 오류")
            else:
                logger.error(f"   🔧 기타 DeepSeek 오류: {repr(e)}")
            
            raise RuntimeError(f"DeepSeek 호출 실패: {error_msg}")


class OpenAIProvider(LLMProvider):
    """🥉 OpenAI GPT 제공자 - 3순위"""
    
    def __init__(self, timeout: Optional[float] = None):
        super().__init__("openai", timeout or OPENAI_TIMEOUT)
        self.api_key = OPENAI_API_KEY
        
        if self.api_key:
            self.client = openai.AsyncOpenAI(api_key=self.api_key)
            logger.info("🥉 OpenAI GPT 초기화 완료")
        else:
            logger.warning("OpenAI API 키가 설정되지 않았습니다")
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError, asyncio.TimeoutError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                      max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.record_failure()
            raise RuntimeError("OpenAI 클라이언트가 초기화되지 않았습니다")
        
        start_time = time.time()
        system = system_prompt or "당신은 친절한 고객 지원 AI입니다."
        
        # 타입 안전한 메시지 구성
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model="gpt-4o-mini",  # 더 빠른 모델로 변경
                    messages=messages,  # type: ignore - 메시지 타입 문제 우회
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=self.timeout
            )
            
            duration = (time.time() - start_time) * 1000
            text = ""
            
            if response.choices and response.choices[0].message.content:
                text = response.choices[0].message.content.strip()
            
            if not text:
                raise ValueError("OpenAI 응답이 비어있습니다")
            
            self.record_success()
            
            return LLMResponse(
                text=text,
                model_used="gpt-4o-mini",  # 실제 사용 모델 반영
                duration_ms=duration,
                tokens_used=response.usage.completion_tokens if response.usage else len(text.split()),
                metadata={"provider": self.name}
            )
            
        except Exception as e:
            self.record_failure()
            error_msg = str(e)
            duration = (time.time() - start_time) * 1000
            
            # 상세한 에러 로깅 추가
            logger.error(f"🚨 OpenAI API 호출 실패 (timeout: {self.timeout}s, duration: {duration:.1f}ms)")
            logger.error(f"   ❌ 오류 타입: {type(e).__name__}")
            logger.error(f"   ❌ 오류 메시지: {error_msg}")
            logger.error(f"   ❌ 프롬프트 길이: {len(prompt)} chars")
            
            if isinstance(e, asyncio.TimeoutError):
                logger.error(f"   ⏰ OpenAI 타임아웃 발생 - {self.timeout}초 초과")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                logger.error("   🚫 OpenAI Rate Limit 도달")
            elif "quota" in error_msg.lower():
                logger.error("   💰 OpenAI 할당량 초과")
            else:
                logger.error(f"   🔧 기타 OpenAI 오류: {repr(e)}")
            
            raise RuntimeError(f"OpenAI 호출 실패: {error_msg}")


class AnthropicProvider(LLMProvider):
    """🏃‍♂️ Anthropic Claude 제공자 - 폴백용"""
    
    def __init__(self, timeout: Optional[float] = None):
        super().__init__("anthropic", timeout or ANTHROPIC_TIMEOUT)
        self.api_key = ANTHROPIC_API_KEY
        
        if self.api_key:
            self.client = anthropic.AsyncClient(api_key=self.api_key)
            logger.info("🏃‍♂️ Anthropic Claude 초기화 완료")
        else:
            logger.warning("Anthropic API 키가 설정되지 않았습니다")
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError, asyncio.TimeoutError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=2),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                      max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        if not self.client:
            self.record_failure()
            raise RuntimeError("Anthropic 클라이언트가 초기화되지 않았습니다")
        
        start_time = time.time()
        system = system_prompt or "당신은 친절한 고객 지원 AI입니다."
        
        try:
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=self.timeout
            )
            
            duration = (time.time() - start_time) * 1000
            text = ""
            
            if response.content and len(response.content) > 0:
                first_content = response.content[0]
                # 안전한 텍스트 접근
                if hasattr(first_content, 'text'):
                    text = getattr(first_content, 'text', '')
                else:
                    text = str(first_content)
            
            if not text:
                raise ValueError("Anthropic 응답이 비어있습니다")
            
            self.record_success()
            
            return LLMResponse(
                text=text,
                model_used="claude-3-haiku-20240307",
                duration_ms=duration,
                tokens_used=response.usage.output_tokens if response.usage else len(text.split()),
                metadata={"provider": self.name}
            )
            
        except Exception as e:
            self.record_failure()
            logger.error(f"Anthropic API 오류: {e}")
            raise


class SpeedOptimizedLLMRouter:
    """🚀 속도 최우선 LLM Router"""
    
    def __init__(self):
        logger.info("🚀 속도 최우선 LLM Router 초기화 중...")
        
        # 환경변수 기반 타임아웃 설정 (하드코딩 제거)
        self.gemini = GeminiProvider()      # 🥇 최우선 (환경변수 기반)
        self.openai = OpenAIProvider()       # 🥈 2순위 (환경변수 기반)
        self.anthropic = AnthropicProvider() # 🥉 3순위 (환경변수 기반)
        self.deepseek = DeepSeekProvider()   # 🏃‍♂️ 최하위 (환경변수 기반)
        
        logger.info("⏱️ 타임아웃 설정:")
        logger.info(f"   🥇 Gemini: {self.gemini.timeout}초")
        logger.info(f"   🥈 OpenAI: {self.openai.timeout}초")
        logger.info(f"   🥉 Anthropic: {self.anthropic.timeout}초")
        logger.info(f"   🏃‍♂️ DeepSeek: {self.deepseek.timeout}초")
        
        # 우선순위 순서 설정 (DeepSeek를 최하위로 이동)
        self.providers = [
            self.gemini,      # 🥇 Gemini Flash 2.0 최우선
            self.openai,      # 🥈 OpenAI GPT-4o-mini
            self.anthropic,   # 🥉 Anthropic Claude Haiku
            self.deepseek     # 🏃‍♂️ DeepSeek R1 최하위 (느림)
        ]
        
        # 🎯 작업별 모델 설정
        self.light_model = os.getenv("LLM_LIGHT_MODEL", "gemini-1.5-flash")
        self.heavy_model = os.getenv("LLM_HEAVY_MODEL", "gemini-2.0-flash-exp")
        
        logger.info(f"🎯 작업별 모델 설정 - 경량: {self.light_model}, 중량: {self.heavy_model}")
        logger.info("🚀 LLM Router 초기화 완료!")
    
    def _get_task_type(self, operation: str) -> str:
        """작업 타입 결정 (light/heavy)"""
        light_keywords = [
            "summary", "요약", "classification", "분류", "category",
            "simple", "간단", "quick", "빠른", "basic",
            "ticket", "티켓", "summarize", "정리", "extract", "추출"
        ]
        
        heavy_keywords = [
            "chat", "채팅", "conversation", "대화", "analysis", "분석",
            "detailed", "상세", "complex", "복잡", "agent", "상담",
            "response", "응답", "solution", "해결"
        ]
        
        operation_lower = operation.lower()
        
        for keyword in light_keywords:
            if keyword in operation_lower:
                logger.info(f"🏃‍♂️ 경량 작업 감지: {operation}")
                return "light"
        
        for keyword in heavy_keywords:
            if keyword in operation_lower:
                logger.info(f"🚀 중량 작업 감지: {operation}")
                return "heavy"
        
        # 기본값은 중량 작업
        logger.info(f"🔍 작업 타입 미지정, 중량 작업으로 분류: {operation}")
        return "heavy"
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                      max_tokens: int = 1024, temperature: float = 0.2,
                      operation: str = "general") -> LLMResponse:
        """
        메인 생성 메서드 - 속도 최우선 폴백 적용
        """
        # 작업 타입에 따른 모델 설정
        task_type = self._get_task_type(operation)
        target_model = self.light_model if task_type == "light" else self.heavy_model
        
        # Gemini 모델 설정 (다른 제공자는 고정 모델 사용)
        if self.gemini.client:
            self.gemini.set_model(target_model)
        
        logger.info(f"🎯 작업 시작 - 타입: {task_type}, 타겟 모델: {target_model}")
        
        # 건강한 제공자들만 필터링 - 더 적극적 필터링
        healthy_providers = []
        for p in self.providers:
            if p.api_key and p.is_healthy():
                # 최근 2분 내 실패가 3회 미만인 제공자만 사용
                if p.failure_count < 3:
                    healthy_providers.append(p)
        
        if not healthy_providers:
            # 긴급 모드: OpenAI만 사용 (가장 안정적)
            logger.warning("⚠️ 모든 제공자 불안정, OpenAI 긴급 모드 활성화")
            if self.openai.api_key:
                healthy_providers = [self.openai]
            else:
                # 최후 수단: 모든 제공자 리셋
                for provider in self.providers:
                    if provider.api_key:
                        provider.failure_count = 0
                        provider.last_success_time = time.time()
                healthy_providers = [p for p in self.providers if p.api_key]
        
        last_error = None
        attempt_count = 0
        
        # 🚀 병렬 시도 모드 확대 - 경량/중량 모두 적용
        if len(healthy_providers) >= 2:
            # 경량 작업: 상위 2개 제공자 병렬
            # 중량 작업: 상위 2개 제공자 병렬 (더 빠른 결과 우선)
            return await self._parallel_generation(
                healthy_providers[:2], prompt, system_prompt, max_tokens, temperature, target_model
            )
        
        # 기본 순차 모드
        for provider in healthy_providers:
            attempt_count += 1
            
            try:
                logger.info(f"🎯 시도 {attempt_count}: {provider.name} 호출")
                
                response = await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
                # 성공 시 메타데이터 추가
                response.attempt_count = attempt_count
                response.is_fallback = attempt_count > 1
                response.metadata.update({
                    "task_type": task_type,
                    "target_model": target_model,
                    "final_provider": provider.name
                })
                
                if attempt_count > 1:
                    response.previous_provider_error = str(last_error)
                
                logger.info(f"✅ 성공: {provider.name} ({response.duration_ms:.1f}ms)")
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"❌ {provider.name} 실패: {e}")
                
                # 빠른 실패: 첫 번째 제공자 실패 시 즉시 다음으로
                continue
        
        # 모든 제공자 실패
        error_msg = f"모든 LLM 제공자 실패. 마지막 오류: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    async def _parallel_generation(self, providers: List[LLMProvider], prompt: str, 
                                  system_prompt: Optional[str], max_tokens: int, 
                                  temperature: float, target_model: str) -> LLMResponse:
        """병렬 생성 - 첫 번째 성공한 응답 반환"""
        logger.info(f"🚀 병렬 모드 시작: {len(providers)}개 제공자")
        
        tasks = []
        for provider in providers:
            task = asyncio.create_task(
                provider.generate(prompt, system_prompt, max_tokens, temperature)
            )
            tasks.append((provider, task))
        
        # 첫 번째 성공한 결과 반환
        try:
            done, pending = await asyncio.wait(
                [task for _, task in tasks], 
                return_when=asyncio.FIRST_COMPLETED,
                timeout=4.0  # 병렬 모드 타임아웃 2초→4초로 증가
            )
            
            # 남은 태스크들 취소
            for task in pending:
                task.cancel()
            
            # 성공한 첫 번째 결과 반환
            for completed_task in done:
                try:
                    result = await completed_task
                    result.metadata["parallel_mode"] = True
                    result.metadata["target_model"] = target_model
                    logger.info(f"🚀 병렬 모드 성공: {result.model_used} ({result.duration_ms:.1f}ms)")
                    return result
                except Exception as e:
                    logger.warning(f"병렬 태스크 실패: {e}")
                    continue
            
            raise RuntimeError("모든 병렬 태스크 실패")
            
        except asyncio.TimeoutError:
            # 모든 태스크 취소
            for _, task in tasks:
                task.cancel()
            raise RuntimeError(f"병렬 생성 타임아웃 (4초)")
    
    async def generate_with_task_type(self, prompt: str, task_type: str = "heavy",
                                     system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """작업 타입을 직접 지정하여 생성"""
        # operation을 task_type으로 매핑하여 호출
        operation_mapping = {
            "light": "quick_summary",
            "heavy": "detailed_analysis"
        }
        
        operation = operation_mapping.get(task_type, "general")
        
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            operation=operation,
            **kwargs
        )
    
    async def generate_response(self, messages: List[Dict[str, str]], 
                              max_tokens: int = 1024, temperature: float = 0.2) -> Dict[str, Any]:
        """
        메시지 리스트를 받아서 LLM 응답을 생성합니다.
        
        Args:
            messages: 메시지 리스트 (role, content 포함)
            max_tokens: 최대 토큰 수
            temperature: 창의성 정도
            
        Returns:
            응답 딕셔너리 (content 키 포함)
        """
        try:
            # 메시지에서 프롬프트 추출
            prompt = ""
            system_prompt = None
            
            for message in messages:
                role = message.get("role", "")
                content = message.get("content", "")
                
                if role == "system":
                    system_prompt = content
                elif role == "user":
                    prompt += content + "\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            
            # LLM을 통한 응답 생성
            response = await self.generate(
                prompt=prompt.strip(),
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return {
                "content": response.text,
                "provider": response.metadata.get("final_provider", "unknown"),
                "duration_ms": response.duration_ms
            }
            
        except Exception as e:
            logger.error(f"generate_response 실패: {e}")
            return {
                "content": "응답 생성 중 오류가 발생했습니다.",
                "error": str(e)
            }
    
    async def analyze_ticket_issue_solution(self, ticket_data: Dict[str, Any]) -> Dict[str, str]:
        """
        티켓 데이터를 분석하여 Issue와 Solution을 추출합니다.
        
        Args:
            ticket_data: 티켓 데이터 (id, subject, description_text 등)
            
        Returns:
            {"issue": "문제 설명", "solution": "해결책"} 형태의 딕셔너리
        """
        try:
            # 티켓 분석을 위한 프롬프트 구성
            prompt = f"""
다음 티켓 정보를 분석하여 주요 문제(Issue)와 해결책(Solution)을 간결하게 요약해주세요.

티켓 정보:
- 제목: {ticket_data.get('subject', 'N/A')}
- 내용: {ticket_data.get('description_text', 'N/A')[:500]}
- 상태: {ticket_data.get('status', 'N/A')}
- 우선순위: {ticket_data.get('priority', 'N/A')}

응답 형식:
Issue: [고객이 경험한 주요 문제점을 1-2문장으로 설명]
Solution: [문제 해결을 위해 제공된 방법이나 답변을 1-2문장으로 설명]

한국어로 답변해주세요.
"""

            # LLM을 통한 분석 수행
            result = await self.generate(
                prompt=prompt,
                operation="ticket_analysis",  # 티켓 분석 작업으로 명시적 지정
                max_tokens=300,
                temperature=0.3
            )
            
            response_text = result.text
            
            # 응답에서 Issue와 Solution 추출
            issue = "문제 상황을 분석할 수 없습니다."
            solution = "해결책을 찾을 수 없습니다."
            
            if response_text:
                lines = response_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('Issue:') or line.startswith('문제:'):
                        issue = line.split(':', 1)[1].strip()
                    elif line.startswith('Solution:') or line.startswith('해결책:'):
                        solution = line.split(':', 1)[1].strip()
            
            return {
                "issue": issue,
                "solution": solution
            }
            
        except Exception as e:
            logger.error(f"티켓 Issue/Solution 분석 실패: {e}")
            return {
                "issue": "문제 상황 분석 실패",
                "solution": "해결책 분석 실패"
            }

    async def analyze_multiple_tickets_batch(self, tickets_data: List[dict]) -> List[dict]:
        """
        여러 티켓을 배치로 분석하여 각각의 issue/solution을 반환하는 메서드
        
        Args:
            tickets_data: 분석할 티켓 데이터 리스트
            
        Returns:
            각 티켓의 분석 결과 리스트 [{"issue": "...", "solution": "..."}, ...]
        """
        batch_start_time = time.time()
        
        try:
            if not tickets_data:
                return []
            
            logger.info(f"🚀 배치 분석 시작: {len(tickets_data)}개 티켓")
            
            # 배치 분석용 프롬프트 구성
            tickets_info = []
            for i, ticket in enumerate(tickets_data, 1):
                ticket_id = ticket.get("id", f"Unknown_{i}")
                subject = ticket.get("subject", "")
                description = ticket.get("description_text", "")
                status = ticket.get("status", "")
                priority = ticket.get("priority", "")
                
                tickets_info.append(f"""티켓 {i}:
- ID: {ticket_id}
- 제목: {subject}
- 상태: {status}
- 우선순위: {priority}
- 내용: {description[:500]}...""")
            
            prompt = f"""다음 {len(tickets_data)}개의 고객 지원 티켓을 각각 분석하여 핵심 문제 상황(issue)과 해결 방안(solution)을 상세하고 풍부하게 요약해 주세요.

{chr(10).join(tickets_info)}

**중요**: 응답은 반드시 아래 형식의 JSON 배열만 제공해 주세요. 다른 설명이나 텍스트는 포함하지 마세요.

```json
[
  {{
    "ticket_index": 1,
    "issue": "고객이 겪은 구체적인 문제상황과 배경을 포함한 상세한 설명 (2-3줄)",
    "solution": "문제 해결을 위한 구체적인 방법, 단계, 또는 제안사항을 포함한 실용적인 솔루션 (2-3줄)"
  }},
  {{
    "ticket_index": 2,
    "issue": "고객이 겪은 구체적인 문제상황과 배경을 포함한 상세한 설명 (2-3줄)",
    "solution": "문제 해결을 위한 구체적인 방법, 단계, 또는 제안사항을 포함한 실용적인 솔루션 (2-3줄)"
  }}
]
```

응답 규칙:
- 반드시 위 JSON 형식만 응답하세요
- ticket_index는 1부터 시작합니다
- issue는 고객의 구체적인 문제상황, 배경, 원인을 포함하여 2-3줄로 상세히 작성하세요
- solution은 문제 해결 방법, 구체적인 단계, 권장사항을 포함하여 2-3줄로 실용적으로 작성하세요
- 티켓 제목과 내용의 핵심 정보를 반영하여 구체적이고 유용한 정보를 제공하세요
- 총 {len(tickets_data)}개의 결과를 모두 포함해야 합니다"""

            # LLM 호출 (배치 분석은 heavy 작업으로 분류)
            llm_start_time = time.time()
            llm_response = await self.generate_with_task_type(prompt, task_type="heavy")
            llm_time = time.time() - llm_start_time
            
            logger.info(f"🔥 배치 LLM 호출 완료: {llm_time:.2f}초")
                        
            # LLMResponse 객체에서 텍스트 추출
            if hasattr(llm_response, 'text'):
                response_text = llm_response.text
            elif isinstance(llm_response, str):
                response_text = llm_response
            else:
                response_text = str(llm_response)
            
            # logger.info(f"🔍 LLM 응답 텍스트 타입: {type(llm_response)}, 텍스트 길이: {len(response_text)}")
            
            # JSON 파싱 시도
            import json
            try:
                #logger.info(f"🔍 배치 LLM 응답 원문 (처음 500자): {response_text[:500]}...")
                
                # JSON 추출 시도 (코드 블록이나 불필요한 텍스트 제거)
                json_text = response_text.strip()
                
                # JSON 코드 블록이 있는 경우 추출
                if "```json" in json_text:
                    start_idx = json_text.find("```json") + 7
                    end_idx = json_text.find("```", start_idx)
                    if end_idx != -1:
                        json_text = json_text[start_idx:end_idx].strip()
                elif json_text.startswith("```") and json_text.endswith("```"):
                    # 일반 코드 블록인 경우
                    json_text = json_text[3:-3].strip()
                
                # JSON 배열 추출 시도
                if json_text.startswith('[') and json_text.endswith(']'):
                    parsed_response = json.loads(json_text)
                elif '{' in json_text and '}' in json_text:
                    # JSON 객체가 중간에 있는 경우 추출
                    start_idx = json_text.find('[')
                    end_idx = json_text.rfind(']') + 1
                    if start_idx != -1 and end_idx > start_idx:
                        json_text = json_text[start_idx:end_idx]
                        parsed_response = json.loads(json_text)
                    else:
                        raise json.JSONDecodeError("No valid JSON array found", json_text, 0)
                else:
                    raise json.JSONDecodeError("No valid JSON structure found", json_text, 0)
                
                logger.info(f"🔍 JSON 파싱 성공: {len(parsed_response)}개 결과")
                # logger.info(f"🔍 파싱된 JSON 구조: {json.dumps(parsed_response[:1], ensure_ascii=False, indent=2)}")
                
                # 결과를 인덱스 순서대로 정렬하여 반환
                results = []
                for i in range(len(tickets_data)):
                    # 해당 인덱스의 결과 찾기
                    ticket_result = None
                    for result in parsed_response:
                        if result.get("ticket_index") == i + 1:
                            ticket_result = result
                            break
                    
                    if ticket_result:
                        issue = ticket_result.get("issue", "고객 문의사항 분석 중")
                        solution = ticket_result.get("solution", "해결 방안 검토 중")
                        logger.info(f"🔍 티켓 {i+1} 분석 결과: issue='{issue[:50]}...', solution='{solution[:50]}...'")
                        results.append({
                            "issue": issue,
                            "solution": solution
                        })
                    else:
                        # 해당 인덱스 결과가 없으면 기본값
                        logger.warning(f"⚠️ 티켓 {i+1} 결과 없음, 기본값 사용")
                        results.append({
                            "issue": "고객 문의사항 분석 중",
                            "solution": "해결 방안 검토 중"
                        })
                
                batch_time = time.time() - batch_start_time
                logger.info(f"✅ 배치 분석 성공: {len(tickets_data)}개 티켓 → {batch_time:.2f}초 (평균 {batch_time/len(tickets_data):.2f}초/건)")
                
                return results
                
            except json.JSONDecodeError as je:
                logger.error(f"⚠️ 배치 분석 JSON 파싱 실패: {je}")
                logger.error(f"⚠️ 파싱 실패한 응답 내용: {response_text[:1000]}...")
                # JSON 파싱 실패 시 개별 분석으로 폴백
                return await self._fallback_to_individual_analysis(tickets_data)
                
        except Exception as e:
            logger.error(f"❌ 배치 티켓 분석 실패: {e}, 개별 분석으로 폴백")
            # 배치 분석 실패 시 개별 분석으로 폴백
            return await self._fallback_to_individual_analysis(tickets_data)

    async def _fallback_to_individual_analysis(self, tickets_data: List[dict]) -> List[dict]:
        """
        배치 분석 실패 시 개별 분석으로 폴백하는 내부 메서드
        
        Args:
            tickets_data: 분석할 티켓 데이터 리스트
            
        Returns:
            각 티켓의 분석 결과 리스트
        """
        fallback_start_time = time.time()
        
        try:
            logger.info(f"🔄 개별 분석 폴백 시작: {len(tickets_data)}개 티켓")
            
            # 병렬 처리로 개별 분석 수행
            import asyncio
            
            async def analyze_single_ticket(ticket_data):
                return await self.analyze_ticket_issue_solution(ticket_data)
            
            # 최대 5개 티켓을 병렬로 처리
            tasks = [analyze_single_ticket(ticket) for ticket in tickets_data]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 예외 발생한 경우 기본값으로 대체
            final_results = []
            for result in results:
                if isinstance(result, Exception):
                    final_results.append({
                        "issue": "문제 상황 분석 중",
                        "solution": "해결 방안 검토 중"
                    })
                else:
                    final_results.append(result)
            
            fallback_time = time.time() - fallback_start_time
            logger.info(f"🔄 개별 분석 폴백 완료: {len(tickets_data)}개 티켓 → {fallback_time:.2f}초 (평균 {fallback_time/len(tickets_data):.2f}초/건)")
            
            return final_results
            
        except Exception as e:
            logger.error(f"❌ 개별 분석 폴백도 실패: {e}")
            # 모든 분석이 실패한 경우 기본값 반환
            return [{"issue": "문제 상황 분석 중", "solution": "해결 방안 검토 중"} for _ in tickets_data]

    async def generate_embedding(self, text: str) -> List[float]:
        """
        텍스트 임베딩 생성 메서드
        
        Args:
            text: 임베딩을 생성할 텍스트
            
        Returns:
            임베딩 벡터 (리스트)
        """
        try:
            # embedder 모듈을 사용하여 임베딩 생성
            from .embedder import generate_embedding
            return await generate_embedding(text)
        except ImportError:
            from backend.core.embedder import generate_embedding
            return await generate_embedding(text)
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            # 폴백: 더미 임베딩 반환
            return [0.1] * 1536

    async def generate_search_query(self, ticket_data: dict) -> str:
        """
        티켓 데이터를 기반으로 검색 쿼리 생성
        
        Args:
            ticket_data: 티켓 데이터 딕셔너리
            
        Returns:
            검색용 쿼리 문자열
        """
        try:
            # 티켓 데이터에서 주요 정보 추출
            subject = ticket_data.get("subject", "")
            description = ticket_data.get("description", ticket_data.get("description_text", ""))
            
            # 간단한 검색 쿼리 구성
            query_parts = []
            if subject:
                query_parts.append(subject)
            if description:
                # 설명은 처음 200자만 사용
                query_parts.append(description[:200])
            
            return " ".join(query_parts).strip()
            
        except Exception as e:
            logger.error(f"검색 쿼리 생성 실패: {e}")
            # 폴백: 기본 검색어 반환
            return ticket_data.get("subject", "고객 문의")
        

# 🚀 싱글톤 인스턴스 생성
llm_router = SpeedOptimizedLLMRouter()


async def generate_text(prompt: str, system_prompt: Optional[str] = None, 
                       max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
    """편의 함수: 기본 텍스트 생성"""
    return await llm_router.generate(
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature
    )


# 🎯 기존 호환성을 위한 alias
LLMRouter = SpeedOptimizedLLMRouter


if __name__ == "__main__":
    # 간단한 테스트
    async def test():
        logger.info("🧪 속도 최우선 LLM Router 테스트 시작")
        
        try:
            # 경량 작업 테스트
            response = await llm_router.generate(
                prompt="안녕하세요",
                operation="quick_summary"
            )
            print(f"✅ 테스트 성공: {response.text[:50]}...")
            print(f"📊 제공자: {response.metadata.get('final_provider')}")
            print(f"⏱️ 응답시간: {response.duration_ms:.1f}ms")
            
        except Exception as e:
            print(f"❌ 테스트 실패: {e}")
    
    asyncio.run(test())
