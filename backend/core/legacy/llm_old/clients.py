"""
LLM 클라이언트 모듈

이 모듈은 다양한 LLM 제공업체(OpenAI, Anthropic, Google)의 클라이언트를 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import asyncio
import logging
import os
import time
from typing import List, AsyncGenerator

import anthropic
import google.generativeai as genai
import openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import LLMResponse, LLMProviderStats, EmbeddingResponse
from .utils import get_cache_key, embedding_cache
from .metrics import (
    llm_requests_total,
    llm_request_duration_seconds,
    llm_tokens_used_total,
    llm_provider_health_status,
    llm_provider_consecutive_failures,
    llm_provider_success_rate
)

# 로깅 설정
logger = logging.getLogger(__name__)

# API 키 설정
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# 환경 변수 확인
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. "
                   "GeminiProvider를 사용할 수 없습니다.")


class LLMProvider:
    """LLM 제공업체 추상 베이스 클래스"""
    
    def __init__(self, name: str):
        self.name = name
        self.stats = LLMProviderStats()
        self.api_key = None  # 서브클래스에서 설정
    
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """텍스트 생성 추상 메서드"""
        raise NotImplementedError("서브클래스에서 구현해야 합니다")
    
    async def generate_stream(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성 추상 메서드"""
        raise NotImplementedError("서브클래스에서 구현해야 합니다")
    
    def is_healthy(self) -> bool:
        """제공업체 건강 상태 확인"""
        # API 키가 없으면 건강하지 않음
        if not self.api_key:
            return False
        
        # 성공률이 50% 미만이면 건강하지 않음
        if self.stats.total_requests > 5 and self.stats.success_rate < 0.5:
            return False
        
        # 연속 실패가 5회 이상이면 건강하지 않음
        if self.stats.consecutive_failures >= 5:
            return False
        
        return True
    
    def get_stats(self) -> LLMProviderStats:
        """제공업체 통계 반환"""
        return self.stats


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 제공업체"""
    
    def __init__(self):
        super().__init__("anthropic")
        self.api_key = ANTHROPIC_API_KEY
        if ANTHROPIC_API_KEY:
            self.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        else:
            self.client = None
            logger.error("Anthropic API 키가 설정되지 않아 AnthropicProvider를 초기화할 수 없습니다.")
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """Claude로 텍스트 생성"""
        if not self.client:
            raise Exception("Anthropic 클라이언트가 초기화되지 않았습니다.")
        
        start_time = time.time()
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = await self.client.messages.create(**kwargs)
            
            # 응답 처리
            content = ""
            if response.content and len(response.content) > 0:
                # TextBlock에서 텍스트 추출
                content = response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
            
            duration = time.time() - start_time
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + duration) 
                / self.stats.successful_requests
            )
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="anthropic", status="success").inc()
            llm_request_duration_seconds.labels(provider="anthropic").observe(duration)
            
            return LLMResponse(
                content=content,
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                response_time=duration,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
                success=True
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Anthropic API 오류: {str(e)}"
            logger.error(error_msg)
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="anthropic", status="error").inc()
            
            return LLMResponse(
                content="",
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                response_time=duration,
                tokens_used=0,
                success=False,
                error=error_msg
            )
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate_stream(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """
        Anthropic Claude를 사용하여 스트리밍 방식으로 텍스트 생성
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 온도 설정
            
        Yields:
            str: 생성된 텍스트 청크들
        """
        start_time = time.time()
        
        try:
            kwargs = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": True
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            async with self.client.messages.stream(**kwargs) as stream:
                async for chunk in stream:
                    if chunk.type == "content_block_delta" and hasattr(chunk.delta, 'text'):
                        yield chunk.delta.text
            
            duration = time.time() - start_time
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + duration) 
                / self.stats.successful_requests
            )
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="anthropic", status="success").inc()
            llm_request_duration_seconds.labels(provider="anthropic").observe(duration)
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Anthropic 스트리밍 API 오류: {str(e)}"
            logger.error(error_msg)
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error_timestamp = time.time()
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="anthropic", status="error").inc()
            
            raise


class OpenAIProvider(LLMProvider):
    """OpenAI GPT API 제공업체"""
    
    def __init__(self):
        super().__init__("openai")
        self.api_key = OPENAI_API_KEY
        if OPENAI_API_KEY:
            self.client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        else:
            self.client = None
            logger.error("OpenAI API 키가 설정되지 않아 OpenAIProvider를 초기화할 수 없습니다.")
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """GPT로 텍스트 생성"""
        if not self.client:
            raise Exception("OpenAI 클라이언트가 초기화되지 않았습니다.")
        
        start_time = time.time()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            content = response.choices[0].message.content
            duration = time.time() - start_time
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + duration) 
                / self.stats.successful_requests
            )
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="openai", status="success").inc()
            llm_request_duration_seconds.labels(provider="openai").observe(duration)
            
            return LLMResponse(
                content=content,
                provider="openai",
                model="gpt-4o",
                response_time=duration,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                success=True
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"OpenAI API 오류: {str(e)}"
            logger.error(error_msg)
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="openai", status="error").inc()
            
            return LLMResponse(
                content="",
                provider="openai",
                model="gpt-4o",
                response_time=duration,
                tokens_used=0,
                success=False,
                error=error_msg
            )
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate_stream(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """
        OpenAI GPT를 사용하여 스트리밍 방식으로 텍스트 생성
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 온도 설정
            
        Yields:
            str: 생성된 텍스트 청크들
        """
        if not self.client:
            raise Exception("OpenAI 클라이언트가 초기화되지 않았습니다.")
        
        start_time = time.time()
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            stream = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            
            duration = time.time() - start_time
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + duration) 
                / self.stats.successful_requests
            )
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="openai", status="success").inc()
            llm_request_duration_seconds.labels(provider="openai").observe(duration)
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"OpenAI 스트리밍 API 오류: {str(e)}"
            logger.error(error_msg)
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error_timestamp = time.time()
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="openai", status="error").inc()
            
            raise


class GeminiProvider(LLMProvider):
    """Google Gemini API 제공업체"""
    
    def __init__(self):
        super().__init__("gemini")
        self.api_key = GOOGLE_API_KEY
        if GOOGLE_API_KEY:
            genai.configure(api_key=GOOGLE_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
            logger.error("Google API 키가 설정되지 않아 GeminiProvider를 초기화할 수 없습니다.")
    
    @retry(
        retry=retry_if_exception_type((Exception,)),  # Gemini 특정 예외가 없으므로 일반 Exception 사용
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 2048, temperature: float = 0.2) -> LLMResponse:
        """Gemini로 텍스트 생성"""
        if not self.model:
            raise Exception("Gemini 모델이 초기화되지 않았습니다.")
        
        start_time = time.time()
        try:
            # 시스템 프롬프트와 사용자 프롬프트 결합
            combined_prompt = prompt
            if system_prompt:
                combined_prompt = f"{system_prompt}\n\n{prompt}"
            
            # 생성 설정
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # 비동기 생성 (Gemini는 기본적으로 동기이므로 asyncio.to_thread 사용)
            response = await asyncio.to_thread(
                self.model.generate_content,
                combined_prompt,
                generation_config=generation_config
            )
            
            content = response.text if response.text else ""
            duration = time.time() - start_time
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + duration) 
                / self.stats.successful_requests
            )
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="gemini", status="success").inc()
            llm_request_duration_seconds.labels(provider="gemini").observe(duration)
            
            return LLMResponse(
                content=content,
                provider="gemini",
                model="gemini-1.5-flash",
                response_time=duration,
                tokens_used=0,  # Gemini에서 토큰 사용량 정보를 제공하지 않음
                success=True
            )
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Gemini API 오류: {str(e)}"
            logger.error(error_msg)
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="gemini", status="error").inc()
            
            return LLMResponse(
                content="",
                provider="gemini",
                model="gemini-1.5-flash",
                response_time=duration,
                tokens_used=0,
                success=False,
                error=error_msg
            )
    
    @retry(
        retry=retry_if_exception_type((Exception,)),  # Gemini 특정 예외가 없으므로 일반 Exception 사용
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def generate_stream(self, prompt: str, system_prompt: str = None, max_tokens: int = 2048, temperature: float = 0.2) -> AsyncGenerator[str, None]:
        """
        Google Gemini를 사용하여 스트리밍 방식으로 텍스트 생성
        
        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택사항)
            max_tokens: 최대 토큰 수
            temperature: 온도 설정
            
        Yields:
            str: 생성된 텍스트 청크들
        """
        if not self.model:
            raise Exception("Gemini 모델이 초기화되지 않았습니다.")
        
        start_time = time.time()
        try:
            # 시스템 프롬프트와 사용자 프롬프트 결합
            combined_prompt = prompt
            if system_prompt:
                combined_prompt = f"{system_prompt}\n\n{prompt}"
            
            # 생성 설정
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # 스트리밍 생성 (Gemini는 기본적으로 동기이므로 asyncio.to_thread 사용)
            response = await asyncio.to_thread(
                self.model.generate_content,
                combined_prompt,
                generation_config=generation_config,
                stream=True
            )
            
            # 스트리밍 응답 처리
            for chunk in response:
                if chunk.text:
                    yield chunk.text
            
            duration = time.time() - start_time
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.average_response_time = (
                (self.stats.average_response_time * (self.stats.successful_requests - 1) + duration) 
                / self.stats.successful_requests
            )
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="gemini", status="success").inc()
            llm_request_duration_seconds.labels(provider="gemini").observe(duration)
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Gemini 스트리밍 API 오류: {str(e)}"
            logger.error(error_msg)
            
            # 통계 업데이트
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error_timestamp = time.time()
            
            # 메트릭 업데이트
            llm_requests_total.labels(provider="gemini", status="error").inc()
            
            raise


# 임베딩 전용 클라이언트
class EmbeddingClient:
    """임베딩 생성 전용 클라이언트"""
    
    def __init__(self):
        if OPENAI_API_KEY:
            self.client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        else:
            self.client = None
            logger.error("OpenAI API 키가 설정되지 않아 EmbeddingClient를 초기화할 수 없습니다.")
    
    async def generate_embedding(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """텍스트 임베딩 생성"""
        if not self.client:
            raise Exception("OpenAI 클라이언트가 초기화되지 않았습니다.")
        
        # 캐시 확인
        cache_key = get_cache_key(text, model)
        if cache_key in embedding_cache:
            logger.debug(f"임베딩 캐시 히트: {cache_key[:8]}...")
            return embedding_cache[cache_key]
        
        try:
            # 텍스트 전처리 (길이 제한)
            if len(text) > 8000:
                text = text[:8000]
                logger.warning("임베딩 텍스트가 8000자로 잘렸습니다.")
            
            response = await self.client.embeddings.create(
                input=text,
                model=model
            )
            
            embedding = response.data[0].embedding
            
            # 캐시에 저장
            embedding_cache[cache_key] = embedding
            logger.debug(f"임베딩 생성 완료: {len(embedding)}차원")
            
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            raise


# 전역 클라이언트 인스턴스
anthropic_provider = AnthropicProvider()
openai_provider = OpenAIProvider()
gemini_provider = GeminiProvider()
embedding_client = EmbeddingClient()
