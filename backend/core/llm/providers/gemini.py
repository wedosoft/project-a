"""
Gemini Provider 구현체
"""

import asyncio
import logging
import time
from typing import List, Optional, AsyncGenerator

import google.generativeai as genai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import BaseLLMProvider
from ..models.base import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API 제공자"""
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        genai.configure(api_key=api_key)
        self.client = None  # 모델별로 동적 생성
        self._available_models = None  # 레지스트리에서 동적으로 로드
    
    @property
    def provider_type(self) -> LLMProvider:
        return LLMProvider.GEMINI
    
    @property
    def available_models(self) -> List[str]:
        """레지스트리에서 사용 가능한 모델 목록 반환"""
        if self._available_models is None:
            try:
                from ..registry import get_model_registry
                registry = get_model_registry()
                models = registry.get_available_models(
                    provider="gemini",
                    include_deprecated=False
                )
                self._available_models = [model.name for model in models]
            except Exception as e:
                logger.warning(f"Failed to load models from registry: {e}")
                # 폴백: 기본 모델 목록
                self._available_models = [
                    "gemini-1.5-flash",
                    "gemini-1.5-flash-latest",
                    "gemini-1.5-pro"
                ]
        return self._available_models
    
    def _get_default_model(self) -> str:
        """레지스트리에서 기본 모델 반환"""
        try:
            from ..registry import get_model_registry
            import os
            registry = get_model_registry()
            environment = os.getenv('ENVIRONMENT', 'development')
            env_config = registry.get_environment_config(environment)
            
            if env_config and env_config.default_provider == "gemini":
                return env_config.default_chat_model
            
            # 환경 설정이 없으면 첫 번째 사용 가능한 모델 사용
            models = self.available_models
            return models[0] if models else "gemini-1.5-flash-latest"
        except Exception as e:
            logger.warning(f"Failed to get default model from registry: {e}")
            return "gemini-1.5-flash-latest"
    
    @retry(
        retry=retry_if_exception_type((
            asyncio.TimeoutError,
            genai.types.generation_types.BlockedPromptException,
            genai.types.generation_types.StopCandidateException,
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """텍스트 생성"""
        start_time = time.time()
        
        try:
            # 모델별로 클라이언트 생성
            model_name = request.model or self._get_default_model()
            if self.client is None or getattr(self, '_current_model', None) != model_name:
                self.client = genai.GenerativeModel(model_name)
                self._current_model = model_name
            
            # 메시지들을 Gemini 형식으로 변환
            contents = []
            system_instruction = ""
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    contents.append({'role': 'user', 'parts': [msg["content"]]})
                elif msg["role"] == "assistant":
                    contents.append({'role': 'model', 'parts': [msg["content"]]})
            
            # 시스템 지시사항이 있으면 첫 번째 사용자 메시지에 포함
            if system_instruction and contents:
                if contents[0]['role'] == 'user':
                    contents[0]['parts'][0] = f"System Instructions: {system_instruction}\n\nUser Query: {contents[0]['parts'][0]}"
            
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=request.max_tokens or 2048,
                temperature=request.temperature or 0.7,
            )
            
            response = await self.client.generate_content_async(
                contents=contents,
                generation_config=generation_config,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # 응답 텍스트 추출
            generated_text = ""
            if response.candidates and response.candidates[0].content:
                if response.candidates[0].content.parts:
                    generated_text = response.candidates[0].content.parts[0].text
            
            return LLMResponse(
                provider=self.provider_type,
                model=request.model or "gemini-1.5-flash-latest",
                content=generated_text,
                usage=None,  # Gemini는 별도로 토큰 계산 필요
                latency_ms=latency_ms,
                success=True,
                metadata={
                    "finish_reason": response.candidates[0].finish_reason.name if response.candidates and response.candidates[0].finish_reason else "UNKNOWN"
                }
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Gemini API 오류: {e}")
            
            return LLMResponse(
                provider=self.provider_type,
                model=request.model or "gemini-1.5-flash-latest",
                content="",
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """스트리밍 텍스트 생성"""
        try:
            # 메시지들을 Gemini 형식으로 변환
            contents = []
            system_instruction = ""
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    contents.append({'role': 'user', 'parts': [msg["content"]]})
                elif msg["role"] == "assistant":
                    contents.append({'role': 'model', 'parts': [msg["content"]]})
            
            # 시스템 지시사항이 있으면 첫 번째 사용자 메시지에 포함
            if system_instruction and contents:
                if contents[0]['role'] == 'user':
                    contents[0]['parts'][0] = f"System Instructions: {system_instruction}\n\nUser Query: {contents[0]['parts'][0]}"
            
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=request.max_tokens or 2048,
                temperature=request.temperature or 0.7,
            )
            
            response = await self.client.generate_content_async(
                contents=contents,
                generation_config=generation_config,
                stream=True
            )
            
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        except Exception as e:
            logger.error(f"Gemini 스트리밍 오류: {e}")
            yield f"Error: {str(e)}"
    
    async def get_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """임베딩 생성"""
        try:
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model=model or "models/embedding-001",
                    content=text
                )
                embeddings.append(result['embedding'])
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Gemini 임베딩 오류: {e}")
            return []
    
    async def health_check(self) -> bool:
        """건강 상태 확인"""
        try:
            # 간단한 테스트 메시지로 건강 상태 확인
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            response = await self.generate(test_request)
            return response.success
        except Exception:
            return False
