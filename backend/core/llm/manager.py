"""
통합된 LLM Manager

기존의 llm_router와 langchain 기반 llm_manager를 통합한 메인 매니저입니다.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from cachetools import TTLCache
from jinja2 import Template

from .models.base import LLMProvider, LLMRequest, LLMResponse
from .models.providers import ProviderConfig, ProviderStats
from .providers import OpenAIProvider, AnthropicProvider, GeminiProvider
from .filters.conversation import SmartConversationFilter
from .utils.config import ConfigManager
from .utils.routing import ProviderRouter
from .utils.metrics import MetricsCollector
from .scalable_key_manager import scalable_key_manager, APIKeyStrategy
from core.metadata.normalizer import TenantMetadataNormalizer
from .summarizer.prompt.loader import PromptLoader

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
        
        # 프롬프트 로더 초기화
        self.prompt_loader = PromptLoader()
        
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
        티켓 요약 생성 (YAML 템플릿 사용)
        
        Args:
            ticket_data: 티켓 정보
            
        Returns:
            요약 정보
        """
        try:
            # 새로운 모듈식 요약 시스템 사용
            from core.llm.summarizer.core.summarizer import core_summarizer
            
            # integrated_text 우선 사용, 없으면 description 사용
            content = ticket_data.get("integrated_text") or ticket_data.get("description", "")
            
            if not content.strip():
                logger.warning("티켓 내용이 비어있음")
                return {
                    "summary": "분석할 내용이 없습니다.",
                    "key_points": ["빈 내용"],
                    "sentiment": "중립적",
                    "priority_recommendation": "확인 필요",
                    "urgency_level": "보통"
                }
            
            # 메타데이터 정규화 (tenant_metadata 활용)
            raw_tenant_metadata = ticket_data.get("tenant_metadata", {})
            tenant_metadata = TenantMetadataNormalizer.normalize(raw_tenant_metadata)
            logger.debug(f"메타데이터 정규화 완료: {len(tenant_metadata)}개 필드")
            
            # 첨부파일 정보 통합 (tenant_metadata 우선 사용)
            attachments = []
            if tenant_metadata.get('has_attachments') and tenant_metadata.get('attachments'):
                attachments = tenant_metadata['attachments']
                logger.info(f"tenant_metadata에서 {len(attachments)}개 첨부파일 로드")
            elif ticket_data.get("attachments"):
                attachments = ticket_data.get("attachments", [])
                logger.info(f"ticket_data에서 {len(attachments)}개 첨부파일 로드")
            
            metadata = {
                "status": ticket_data.get("status"),
                "priority": ticket_data.get("priority"),
                "created_at": ticket_data.get("created_at"),
                "attachments": attachments,
                "has_attachments": len(attachments) > 0,
                "attachment_count": len(attachments),
                "has_conversations": tenant_metadata.get('has_conversations', False),
                "conversation_count": tenant_metadata.get('conversation_count', 0)
            }
            
            # 새로운 요약 시스템으로 생성 (OpenAI 강제 사용)
            summary = await core_summarizer.generate_summary(
                content=content,
                content_type="ticket",
                subject=ticket_data.get("subject", ""),
                metadata=metadata,
                ui_language="ko"
            )
            
            # AI 처리 정보 업데이트
            updated_metadata = TenantMetadataNormalizer.update_ai_processing_info(
                tenant_metadata, 
                model_used="gpt-4o-mini-2024-07-18",
                quality_score=4.0  # 기본 품질 점수
            )
            
            return {
                "summary": summary,
                "key_points": ["구조화된 요약"],
                "sentiment": "중립적",
                "priority_recommendation": "보통",
                "urgency_level": "보통",
                "updated_metadata": updated_metadata  # 업데이트된 메타데이터 포함
            }
                
        except Exception as e:
            logger.error(f"티켓 요약 생성 실패: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 오류: {str(e)}",
                "key_points": ["요약 생성 오류", "수동 검토 필요"],
                "sentiment": "중립적",
                "priority_recommendation": "확인 필요",
                "urgency_level": "보통"
            }
    
    async def generate_knowledge_base_summary(self, kb_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        KB 문서 요약 생성 (새로운 모듈식 시스템 사용)
        
        Args:
            kb_data: KB 문서 정보 (title, content 포함)
            
        Returns:
            요약 정보
        """
        try:
            # 새로운 모듈식 요약 시스템 사용
            from core.llm.summarizer.core.summarizer import core_summarizer
            
            # KB 데이터 준비
            content = kb_data.get("content", "")
            
            if not content.strip():
                logger.warning("KB 문서 내용이 비어있음")
                return {
                    "summary": "분석할 내용이 없습니다.",
                    "key_points": ["빈 내용"],
                    "topics": ["미분류"],
                    "category": "확인 필요"
                }
            
            # 메타데이터 준비
            metadata = {
                "category": kb_data.get("category"),
                "tags": kb_data.get("tags", []),
                "created_at": kb_data.get("created_at"),
                "updated_at": kb_data.get("updated_at")
            }
            
            # 새로운 요약 시스템으로 생성 (knowledge_base 타입)
            summary = await core_summarizer.generate_summary(
                content=content,
                content_type="knowledge_base",
                subject=kb_data.get("title", ""),
                metadata=metadata,
                ui_language="ko"
            )
            
            return {
                "summary": summary,
                "key_points": ["구조화된 KB 요약"],
                "topics": ["지식베이스"],
                "category": "기술문서"
            }
                
        except Exception as e:
            logger.error(f"KB 문서 요약 생성 실패: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 오류: {str(e)}",
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
