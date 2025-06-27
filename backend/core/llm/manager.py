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
    통합 LLM 관리자 (싱글톤 패턴)
    
    여러 LLM 제공자를 관리하고, 요청을 적절한 제공자로 라우팅하며,
    성능 모니터링과 캐싱을 제공합니다.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 싱글톤 중복 초기화 방지
        if LLMManager._initialized:
            logger.debug("LLMManager 이미 초기화됨 (싱글톤)")
            return
            
        logger.info("LLMManager 초기화 시작...")
        
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
        
        # 초기화 완료 플래그
        LLMManager._initialized = True
        logger.info("LLMManager 싱글톤 초기화 완료")
        
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
    
    async def generate_knowledge_base_summary(self, kb_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        KB 문서 요약 생성
        
        Args:
            kb_data: KB 문서 정보 (title, content 포함)
            
        Returns:
            요약 정보
        """
        title = kb_data.get("title", "")
        content = kb_data.get("content", "")
        
        # 프롬프트 구성
        prompt_parts = []
        if title:
            prompt_parts.append(f"문서 제목: {title}")
        
        if content:
            # 긴 내용은 잘라서 사용
            content_preview = content[:2000] + ("..." if len(content) > 2000 else "")
            prompt_parts.append(f"문서 내용:\n{content_preview}")
        
        messages = [
            {
                "role": "system",
                "content": (
                    "KB 문서 내용을 분석하여 간결한 마크다운 요약을 작성하세요. "
                    "문서의 주요 내용과 핵심 포인트를 포함해 최대 500자 이내로 작성해주세요."
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
                    "topics": ["주제1", "주제2"],
                    "category": "기술문서"
                }
            else:
                raise Exception(response.error)
                
        except Exception as e:
            logger.error(f"KB 문서 요약 생성 실패: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 문서 제목: {title}",
                "key_points": ["요약 생성 오류", "수동 검토 필요"],
                "topics": ["오류"],
                "category": "확인 필요"
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


# 전역 싱글톤 인스턴스 (편의성 제공)
_global_llm_manager = None

def get_llm_manager() -> LLMManager:
    """
    전역 LLMManager 싱글톤 인스턴스를 반환합니다.
    
    이 함수를 사용하면 어디서든 동일한 LLMManager 인스턴스에 접근할 수 있습니다.
    
    Returns:
        LLMManager: 싱글톤 인스턴스
    """
    global _global_llm_manager
    if _global_llm_manager is None:
        _global_llm_manager = LLMManager()
    return _global_llm_manager

# 기본 인스턴스 생성 (하위 호환성)
default_llm_manager = get_llm_manager()
