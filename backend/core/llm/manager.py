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
            # YAML 템플릿 로드
            system_template = self.prompt_loader.load_template("system", "ticket")
            user_template = self.prompt_loader.load_template("user", "ticket")
            
            # 티켓 데이터 준비
            subject = ticket_data.get("subject", "")
            description = ticket_data.get("description", "")
            conversations = ticket_data.get("conversations", [])
            integrated_text = ticket_data.get("integrated_text", "")
            
            # 스마트 대화 필터링
            if conversations:
                conversations = self.conversation_filter.filter_conversations_unlimited(conversations)
            
            # 메타데이터 포맷팅
            metadata_parts = []
            if ticket_data.get("status"):
                metadata_parts.append(f"상태: {ticket_data['status']}")
            if ticket_data.get("priority"):
                metadata_parts.append(f"우선순위: {ticket_data['priority']}")
            if ticket_data.get("created_at"):
                metadata_parts.append(f"생성일: {ticket_data['created_at']}")
            
            metadata_formatted = ", ".join(metadata_parts) if metadata_parts else ""
            
            # 사용자 프롬프트 생성
            user_template_content = user_template.get("template", "")
            instruction_text = user_template.get("instructions", {}).get("ko", "")
            
            jinja_template = Template(user_template_content)
            user_prompt = jinja_template.render(
                subject=subject,
                metadata_formatted=metadata_formatted,
                content=integrated_text or description,
                instruction_text=instruction_text
            )
            
            # 시스템 프롬프트 생성
            system_prompt = system_template.get("template", "") or system_template.get("instructions", {}).get("ko", "")
            
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ]
            
            # 요약 생성
            provider = LLMProvider.GEMINI  # 요약은 Gemini 사용
            
            response = await self.generate(
                messages=messages,
                provider=provider,
                max_tokens=2000,
                temperature=0.1
            )
            
            if response.success:
                return {
                    "summary": response.content,
                    "key_points": ["YAML 템플릿 기반 요약"],
                    "sentiment": "중립적",
                    "priority_recommendation": "보통",
                    "urgency_level": "보통"
                }
            else:
                raise Exception(response.error)
                
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
        KB 문서 요약 생성 (YAML 템플릿 사용)
        
        Args:
            kb_data: KB 문서 정보 (title, content 포함)
            
        Returns:
            요약 정보
        """
        try:
            # YAML 템플릿 로드
            system_template = self.prompt_loader.load_template("system", "knowledge_base")
            user_template = self.prompt_loader.load_template("user", "knowledge_base")
            
            # KB 데이터 준비
            title = kb_data.get("title", "")
            content = kb_data.get("content", "")
            description = kb_data.get("description", "")
            
            # 메타데이터 포맷팅
            metadata_parts = []
            if kb_data.get("category"):
                metadata_parts.append(f"카테고리: {kb_data['category']}")
            if kb_data.get("tags"):
                metadata_parts.append(f"태그: {', '.join(kb_data['tags'])}")
            if kb_data.get("created_at"):
                metadata_parts.append(f"생성일: {kb_data['created_at']}")
            
            metadata_formatted = ", ".join(metadata_parts) if metadata_parts else ""
            
            # 사용자 프롬프트 생성
            user_template_content = user_template.get("template", "")
            instruction_text = user_template.get("instructions", {}).get("ko", "")
            
            jinja_template = Template(user_template_content)
            user_prompt = jinja_template.render(
                title=title,
                metadata_formatted=metadata_formatted,
                content=content or description,
                instruction_text=instruction_text
            )
            
            # 시스템 프롬프트 생성
            system_prompt = system_template.get("template", "") or system_template.get("instructions", {}).get("ko", "")
            
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ]
            
            # 요약 생성
            provider = LLMProvider.GEMINI  # 요약은 Gemini 사용
            
            response = await self.generate(
                messages=messages,
                provider=provider,
                max_tokens=2000,
                temperature=0.1
            )
            
            if response.success:
                return {
                    "summary": response.content,
                    "key_points": ["YAML 템플릿 기반 KB 요약"],
                    "topics": ["지식베이스"],
                    "category": "기술문서"
                }
            else:
                raise Exception(response.error)
                
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
