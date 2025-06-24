"""
통합된 LLM Manager

기존의 llm_router와 langchain 기반 llm_manager를 통합한 메인 매니저입니다.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from cachetools import TTLCache

from .models.base import LLMProvider, LLMRequest, LLMResponse
from .models.providers import ProviderConfig, ProviderStats
from .providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from .filters.conversation import SmartConversationFilter
from .utils.config import ConfigManager
from .utils.routing import ProviderRouter
from .utils.metrics import MetricsCollector
from .scalable_key_manager import scalable_key_manager, APIKeyStrategy

logger = logging.getLogger(__name__)


class LLMManager:
    """
    통합 LLM 관리자
    
    여러 LLM 제공자를 관리하고, 요청을 적절한 제공자로 라우팅하며,
    성능 모니터링과 캐싱을 제공합니다.
    """
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.router = ProviderRouter()
        self.metrics = MetricsCollector()
        self.conversation_filter = SmartConversationFilter()
        
        # 확장 가능한 API 키 관리자
        self.key_manager = scalable_key_manager
        
        # Provider 인스턴스들
        self.providers: Dict[LLMProvider, Any] = {}
        
        # 캐시
        self.response_cache = TTLCache(maxsize=1000, ttl=3600)
        self.embedding_cache = TTLCache(maxsize=1000, ttl=3600)
        
        # 초기화
        self._initialize_providers()
        
        logger.info(f"LLMManager 초기화 완료 - {len(self.providers)}개 제공자 로드됨")
    
    def _initialize_providers(self):
        """제공자들 초기화"""
        
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                self.providers[LLMProvider.OPENAI] = OpenAIProvider(openai_key)
                logger.info("OpenAI Provider 초기화 완료")
            except Exception as e:
                logger.error(f"OpenAI Provider 초기화 실패: {e}")
        
        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                self.providers[LLMProvider.ANTHROPIC] = AnthropicProvider(anthropic_key)
                logger.info("Anthropic Provider 초기화 완료")
            except Exception as e:
                logger.error(f"Anthropic Provider 초기화 실패: {e}")
        
        # Gemini
        gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                self.providers[LLMProvider.GEMINI] = GeminiProvider(gemini_key)
                logger.info("Gemini Provider 초기화 완료")
            except Exception as e:
                logger.error(f"Gemini Provider 초기화 실패: {e}")
    
    async def generate(self, 
                      messages: List[Dict[str, str]], 
                      model: Optional[str] = None,
                      provider: Optional[LLMProvider] = None,
                      **kwargs) -> LLMResponse:
        """
        텍스트 생성
        
        Args:
            messages: 대화 메시지 리스트
            model: 사용할 모델명
            provider: 선호하는 제공자
            **kwargs: 추가 파라미터
            
        Returns:
            LLM 응답
        """
        request = LLMRequest(
            messages=messages,
            model=model,
            **kwargs
        )
        
        # 캐시 확인
        cache_key = self._get_cache_key(request)
        if cache_key in self.response_cache:
            logger.debug("캐시에서 응답 반환")
            return self.response_cache[cache_key]
        
        # 제공자 선택
        if provider and provider in self.providers:
            selected_provider = self.providers[provider]
            provider_name = provider
        else:
            provider_name, selected_provider = await self.router.select_provider(
                self.providers, request
            )
        
        if not selected_provider:
            raise RuntimeError("사용 가능한 LLM 제공자가 없습니다.")
        
        logger.info(f"{provider_name.value} 제공자로 텍스트 생성 시작")
        
        try:
            # 생성 실행
            response = await selected_provider.generate(request)
            
            # 메트릭 수집
            self.metrics.record_request(provider_name, response)
            
            # 성공한 응답은 캐시에 저장
            if response.success:
                self.response_cache[cache_key] = response
            
            return response
            
        except Exception as e:
            logger.error(f"{provider_name.value} 제공자 실패: {e}")
            # 폴백 시도
            return await self._try_fallback(request, exclude_provider=provider_name)
    
    async def generate_ticket_summary(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 요약 생성
        
        Args:
            ticket_data: 티켓 정보
            
        Returns:
            요약 정보
        """
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description_text", "")
        conversations = ticket_data.get("conversations", [])
        
        # 스마트 대화 필터링
        if conversations:
            conversations = self.conversation_filter.filter_conversations_unlimited(conversations)
        
        # 프롬프트 구성
        prompt_parts = [f"티켓 제목: {subject}"]
        if description:
            prompt_parts.append(f"티켓 설명: {description}")
        
        if conversations:
            prompt_parts.append("주요 대화 내용:")
            for conv in conversations[:10]:  # 최대 10개만 포함
                sender = "사용자" if conv.get("user_id") else "상담원"
                body = self._extract_conversation_body(conv)
                prompt_parts.append(f"- {sender}: {body[:200]}...")
        
        messages = [
            {
                "role": "system",
                "content": (
                    "티켓 정보를 분석하여 간결한 마크다운 요약을 작성하세요. "
                    "최대 500자 이내로 작성해주세요."
                )
            },
            {
                "role": "user", 
                "content": "\n".join(prompt_parts)
            }
        ]
        
        try:
            # 요약용 모델 설정 사용
            provider = LLMProvider.GEMINI  # 요약은 Gemini 사용
            
            response = await self.generate(
                messages=messages,
                provider=provider,
                max_tokens=1000,
                temperature=0.1
            )
            
            if response.success:
                return {
                    "summary": response.content,
                    "key_points": ["주요 포인트 1", "주요 포인트 2"],
                    "sentiment": "중립적",
                    "priority_recommendation": "보통",
                    "urgency_level": "보통"
                }
            else:
                raise Exception(response.error)
                
        except Exception as e:
            logger.error(f"티켓 요약 생성 실패: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 티켓 제목: {subject}",
                "key_points": ["요약 생성 오류", "수동 검토 필요"],
                "sentiment": "중립적",
                "priority_recommendation": "확인 필요",
                "urgency_level": "보통"
            }
    
    async def get_embeddings(self, texts: List[str], model: Optional[str] = None) -> List[List[float]]:
        """임베딩 생성"""
        # OpenAI를 임베딩 제공자로 사용
        if LLMProvider.OPENAI in self.providers:
            provider = self.providers[LLMProvider.OPENAI]
            return await provider.get_embeddings(texts, model)
        else:
            logger.error("임베딩 생성을 위한 OpenAI 제공자가 없습니다.")
            return []
    
    async def health_check(self) -> Dict[str, bool]:
        """모든 제공자의 건강 상태 확인"""
        health_status = {}
        
        for provider_type, provider in self.providers.items():
            try:
                health_status[provider_type.value] = await provider.health_check()
            except Exception as e:
                logger.error(f"{provider_type.value} 건강 상태 확인 실패: {e}")
                health_status[provider_type.value] = False
        
        return health_status
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 정보 반환"""
        return self.metrics.get_stats()
    
    def _get_cache_key(self, request: LLMRequest) -> str:
        """캐시 키 생성"""
        import hashlib
        content = f"{request.messages}_{request.model}_{request.max_tokens}_{request.temperature}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _extract_conversation_body(self, conv: Dict[str, Any]) -> str:
        """대화 본문 추출"""
        for field in ["body_text", "body", "text", "content", "message"]:
            if field in conv and conv[field]:
                return str(conv[field])
        return str(conv)[:100]
    
    async def _try_fallback(self, request: LLMRequest, exclude_provider: LLMProvider) -> LLMResponse:
        """폴백 제공자 시도"""
        available_providers = {
            k: v for k, v in self.providers.items() 
            if k != exclude_provider
        }
        
        if not available_providers:
            return LLMResponse(
                provider=exclude_provider,
                model=request.model or "unknown",
                content="",
                success=False,
                error="모든 제공자 사용 불가"
            )
        
        provider_name, provider = await self.router.select_provider(
            available_providers, request
        )
        
        logger.info(f"폴백: {provider_name.value} 제공자 시도")
        
        try:
            response = await provider.generate(request)
            self.metrics.record_request(provider_name, response)
            return response
        except Exception as e:
            logger.error(f"폴백 제공자도 실패: {e}")
            return LLMResponse(
                provider=provider_name,
                model=request.model or "unknown", 
                content="",
                success=False,
                error=str(e)
            )
