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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel, Field

# 로깅 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# API 키 설정
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 환경 변수 확인
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")


class LLMResponse(BaseModel):
    """LLM 응답 모델"""
    text: str
    model_used: str
    duration_ms: float
    tokens_used: Optional[int] = None
    tokens_total: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMProvider:
    """LLM 제공자의 기본 추상 클래스"""
    
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """추상 메소드: 각 제공자 클래스에서 구현해야 함"""
        raise NotImplementedError
    
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수를 대략적으로 계산 (기본 구현)"""
        # 단순 근사: 영어 기준으로 단어 1개는 약 1.3 토큰
        return int(len(text.split()) * 1.3)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 제공자"""
    
    def __init__(self, api_key: str = None, timeout: float = 10.0):
        self.api_key = api_key or ANTHROPIC_API_KEY
        self.client = anthropic.AsyncClient(api_key=self.api_key)  # 최신 버전 API 클라이언트
        self.timeout = timeout
        self.available_models = {
            "claude-3-haiku-20240307": {"max_tokens": 200000, "priority": 1},  # 가장 빠름
            "claude-3-sonnet-20240229": {"max_tokens": 200000, "priority": 2},  # 더 고품질
        }
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """Claude API를 사용하여 텍스트 생성"""
        start_time = time.time()
        model = "claude-3-haiku-20240307"  # 기본 모델
        
        system = "당신은 친절한 고객 지원 AI입니다." if system_prompt is None else system_prompt
        
        try:
            # Timeout 설정
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
            
            duration = (time.time() - start_time) * 1000  # ms로 변환
            
            # 응답 텍스트 추출 - 최신 API에 맞춤
            text = response.content[0].text
            
            # 토큰 사용량 추출
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
                    "provider": "anthropic",
                    "tokens": tokens_used,
                }
            )
            
        except (anthropic.APIError, anthropic.RateLimitError) as e:
            logger.error(f"Claude API 오류: {str(e)}")
            raise
        except asyncio.TimeoutError:
            logger.error(f"Claude API 호출 타임아웃 ({self.timeout}초)")
            raise
        except Exception as e:
            logger.error(f"Claude 호출 중 예상치 못한 오류: {str(e)}")
            raise


class OpenAIProvider(LLMProvider):
    """OpenAI API 제공자"""
    
    def __init__(self, api_key: str = None, timeout: float = 15.0):
        self.api_key = api_key or OPENAI_API_KEY
        self.client = openai.AsyncOpenAI(api_key=self.api_key)
        self.timeout = timeout
        self.available_models = {
            "gpt-4o": {"max_tokens": 128000, "priority": 1},  # 기본
            "gpt-3.5-turbo": {"max_tokens": 16000, "priority": 2},  # 백업
        }
    
    @retry(
        retry=retry_if_exception_type((openai.RateLimitError, openai.APIError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """OpenAI API를 사용하여 텍스트 생성"""
        start_time = time.time()
        model = "gpt-4o"  # 기본 모델
        
        system = "당신은 친절한 고객 지원 AI입니다." if system_prompt is None else system_prompt
        
        try:
            # Timeout 설정
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
            
            duration = (time.time() - start_time) * 1000  # ms로 변환
            
            # 응답 텍스트 추출
            text = response.choices[0].message.content.strip()
            
            # 토큰 사용량 추출
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
                    "provider": "openai",
                    "tokens": tokens_used,
                }
            )
            
        except (openai.RateLimitError, openai.APIError) as e:
            logger.error(f"OpenAI API 오류: {str(e)}")
            raise
        except asyncio.TimeoutError:
            logger.error(f"OpenAI API 호출 타임아웃 ({self.timeout}초)")
            raise
        except Exception as e:
            logger.error(f"OpenAI 호출 중 예상치 못한 오류: {str(e)}")
            raise


class LLMRouter:
    """LLM 라우팅 및 Fallback 로직 구현"""
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.anthropic = AnthropicProvider(timeout=timeout)
        self.openai = OpenAIProvider(timeout=timeout)
        
        # 기본 라우팅 전략: Anthropic을 주 모델, OpenAI를 fallback으로 사용
        self.primary_provider = self.anthropic
        self.fallback_provider = self.openai
    
    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
        """최적의 LLM 제공자를 선택하여 텍스트 생성"""
        
        # 이미지 포함 여부 확인 (향후 구현)
        has_images = False
        
        # 토큰 길이 추정 (매우 간단한 근사)
        estimated_tokens = self.primary_provider.count_tokens(prompt)
        
        # 라우팅 결정 로직
        selected_provider = self.choose_provider(prompt, estimated_tokens, has_images)
        
        try:
            # 선택된 제공자로 시도
            return await selected_provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as e:
            logger.warning(f"주 제공자({selected_provider.__class__.__name__})로 생성 실패: {str(e)}. Fallback으로 시도합니다.")
            
            # Fallback 제공자 결정
            fallback = self.fallback_provider if selected_provider == self.primary_provider else self.primary_provider
            
            try:
                # Fallback 제공자로 시도
                response = await fallback.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens, 
                    temperature=temperature
                )
                
                # Fallback 사용 여부 메타데이터 추가
                response.metadata["used_fallback"] = True
                response.metadata["primary_provider_error"] = str(e)
                
                return response
            except Exception as fallback_error:
                # 모든 시도 실패
                logger.error(f"Fallback({fallback.__class__.__name__}) 생성도 실패: {str(fallback_error)}")
                raise RuntimeError(f"모든 LLM 제공자 호출 실패: {str(e)} 및 {str(fallback_error)}")
    
    def choose_provider(self, prompt: str, estimated_tokens: int, has_images: bool) -> LLMProvider:
        """라우팅 기준에 따라 적절한 제공자 선택"""
        
        # 이미지 분석이 필요한 경우 OpenAI 사용 (Claude는 아직 이미지 처리 미지원으로 가정)
        if has_images:
            return self.openai
        
        # 토큰 길이가 매우 긴 경우 OpenAI 선택 (GPT-4o가 더 긴 컨텍스트 지원)
        if estimated_tokens > 100000:  # 매우 긴 문서
            return self.openai
        
        # 기본적으로 주 제공자 반환 (Claude)
        return self.primary_provider


# 싱글톤 인스턴스 제공
llm_router = LLMRouter()

async def generate_text(prompt: str, system_prompt: str = None, max_tokens: int = 1024, temperature: float = 0.2) -> LLMResponse:
    """텍스트 생성 편의 함수"""
    return await llm_router.generate(prompt, system_prompt, max_tokens, temperature)
