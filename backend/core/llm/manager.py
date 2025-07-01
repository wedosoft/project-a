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
        import time
        
        try:
            summary_start_time = time.time()
            logger.info(f"🎯 [조회 티켓 요약] 시작 - ID: {ticket_data.get('id', 'unknown')}")
            
            # 새로운 모듈식 요약 시스템 사용
            from core.llm.summarizer.core.summarizer import core_summarizer
            
            # 순수 텍스트만 사용 (description_text는 필수 필드)
            content = ticket_data.get("description_text", "")
            
            if not content.strip():
                ticket_id = ticket_data.get('id', 'unknown')
                has_desc_text = bool(ticket_data.get('description_text'))
                has_desc = bool(ticket_data.get('description'))
                logger.warning(f"티켓 {ticket_id} 내용이 비어있음 - description_text: {has_desc_text}, description: {has_desc}")
                logger.debug(f"티켓 {ticket_id} 데이터 구조: {list(ticket_data.keys())}")
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
            
            # 조회티켓(realtime_ticket)은 첨부파일 처리 제외 (속도 최적화)
            metadata = {
                "status": ticket_data.get("status"),
                "priority": ticket_data.get("priority"),
                "created_at": ticket_data.get("created_at"),
                "has_conversations": tenant_metadata.get('has_conversations', False),
                "conversation_count": tenant_metadata.get('conversation_count', 0)
            }
            
            # 새로운 요약 시스템으로 생성 (YAML 템플릿 기반)
            summary = await core_summarizer.generate_summary(
                content=content,
                content_type="realtime_ticket",  # 실시간 티켓 전용 YAML 템플릿 사용 (최고 품질)
                subject=ticket_data.get("subject", ""),
                metadata=metadata,
                ui_language="ko"
            )
            
            summary_time = time.time() - summary_start_time
            logger.info(f"⏱️ [조회 티켓 요약] 완료 - ID: {ticket_data.get('id')} - 소요시간: {summary_time:.2f}초")
            
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
    
    async def generate_similar_ticket_summaries(self, similar_tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        유사 티켓들에 대한 요약 생성 (순차 처리)
        
        Args:
            similar_tickets: 유사 티켓 목록 [{
                "id": "123",
                "title": "제목", 
                "content": "내용",
                "score": 0.85,
                "metadata": {...}
            }]
            
        Returns:
            요약이 포함된 유사 티켓 목록
        """
        summarized_tickets = []
        
        for i, ticket in enumerate(similar_tickets):
            try:
                logger.info(f"🔍 [유사 티켓 요약] {i+1}/{len(similar_tickets)} 요약 생성 중 (ID: {ticket.get('id', 'unknown')})")
                
                # 티켓 데이터 구조 변환 (generate_ticket_summary 형식에 맞춤)
                ticket_data_for_summary = {
                    "id": ticket.get("id"),
                    "subject": ticket.get("title", ""),
                    "description_text": ticket.get("content", ""),  # Vector DB의 content 사용
                    "description": ticket.get("content", ""),       # 폴백용
                    "status": ticket.get("metadata", {}).get("status"),
                    "priority": ticket.get("metadata", {}).get("priority"),
                    "created_at": ticket.get("metadata", {}).get("created_at"),
                    "tenant_metadata": ticket.get("metadata", {})
                }
                
                # YAML 템플릿 기반 유사 티켓 요약 생성
                try:
                    import time
                    ticket_start_time = time.time()
                    
                    # 유사 티켓용 간소화된 요약 생성 (직접 core_summarizer 호출)
                    from core.llm.summarizer.core.summarizer import core_summarizer
                    
                    summary_result = await core_summarizer.generate_summary(
                        content=ticket_data_for_summary.get("description_text", ""),
                        content_type="ticket",  # 일반 ticket 템플릿 사용 (조회 티켓보다 간소화)
                        subject=ticket_data_for_summary.get("subject", ""),
                        metadata=ticket_data_for_summary.get("tenant_metadata", {}),
                        ui_language="ko"
                    )
                    
                    ticket_time = time.time() - ticket_start_time
                    logger.info(f"⏱️ [유사 티켓 {i+1}] 요약 소요시간: {ticket_time:.2f}초")
                    
                    # 요약 결과 검증
                    if summary_result and summary_result.strip():
                        summary_text = f"{summary_result}\n\n**🎯 유사도**: {ticket.get('score', 0.0):.3f}"
                    else:
                        logger.warning(f"Empty summary result for ticket {ticket.get('id')}, using fallback")
                        ticket_title = ticket.get("title", "제목 없음")
                        summary_text = f"## 🔍 {ticket_title}\n\n**문제 상황**: 유사 티켓 요약 생성 실패\n\n**🎯 유사도**: {ticket.get('score', 0.0):.3f}"
                    
                    logger.info(f"✅ [유사 티켓 요약] 티켓 {ticket.get('id')} YAML 템플릿 기반 요약 완료 ({len(summary_text)}자)")
                    logger.info(f"\n📄 [유사 티켓 {ticket.get('id')}] \n{summary_text}")
                    
                except Exception as e:
                    logger.error(f"❌ [유사 티켓 요약] 티켓 {ticket.get('id')} YAML 템플릿 요약 실패: {e}")
                    # 폴백: 간단한 마크다운 요약
                    ticket_title = ticket.get("title", "제목 없음")
                    ticket_content = ticket.get("content", "")
                    summary_parts = []
                    summary_parts.append(f"## 🔍 {ticket_title}")
                    summary_parts.append(f"**유사 문제**: {ticket_content[:300] if ticket_content else '내용 없음'}...")
                    summary_parts.append(f"**유사도**: {ticket.get('score', 0.0):.3f}")
                    summary_text = "\n\n".join(summary_parts)
                    logger.warning(f"⚠️ [유사 티켓 요약] 티켓 {ticket.get('id')} 폴백 요약 사용")
                    logger.info(f"\n📄 [유사 티켓 {ticket.get('id')} - 폴백] \n{summary_text}")
                
                # 결과 구성
                summarized_ticket = {
                    "id": ticket.get("id"),
                    "title": ticket.get("title", ""),
                    "content": summary_text,  # YAML 템플릿 기반 마크다운 요약
                    "score": ticket.get("score", 0.0),
                    "metadata": ticket.get("metadata", {})
                }
                
                summarized_tickets.append(summarized_ticket)
                
            except Exception as e:
                print(f"❌ [유사 티켓 요약] 티켓 {ticket.get('id', 'unknown')} 요약 생성 실패: {e}")
                # 실패한 경우 원본 content 사용
                fallback_ticket = {
                    "id": ticket.get("id"),
                    "title": ticket.get("title", ""),
                    "content": ticket.get("content", "요약 생성에 실패했습니다.")[:200] + "...",
                    "score": ticket.get("score", 0.0),
                    "metadata": ticket.get("metadata", {})
                }
                summarized_tickets.append(fallback_ticket)
        
        logger.info(f"🎯 [유사 티켓 요약] 완료: {len(summarized_tickets)}건 처리")
        return summarized_tickets
    
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
    
    async def _unified_search_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합 검색 태스크 - 유사 티켓과 KB 문서를 한 번에 검색
        
        Args:
            inputs: 입력 데이터 딕셔너리
                - ticket_data: 티켓 데이터
                - tenant_id: 테넌트 ID
                - top_k_tickets: 유사 티켓 수 (기본값: 5)
                - top_k_kb: KB 문서 수 (기본값: 5)
        
        Returns:
            통합 검색 결과
        """
        try:
            from core.search.optimizer import get_search_optimizer
            
            ticket_data = inputs.get("ticket_data", {})
            tenant_id = inputs.get("tenant_id", "")
            top_k_tickets = inputs.get("top_k_tickets", 5)
            top_k_kb = inputs.get("top_k_kb", 5)
            
            # 검색 쿼리 구성 (로그 개선)
            subject = ticket_data.get("subject", "")
            description = ticket_data.get("description_text", "")
            search_query = f"{subject} {description}".strip()
            
            logger.info(f"티켓 {ticket_data.get('id', 'unknown')} 검색 쿼리: '{search_query[:100]}...'")
            
            if len(search_query) > 500:
                search_query = search_query[:500]
            
            # 통합 벡터 검색 실행
            search_optimizer = get_search_optimizer()
            search_result = await search_optimizer.unified_vector_search(
                query_text=search_query,
                tenant_id=tenant_id,
                ticket_id=str(ticket_data.get("id", "")),
                top_k_tickets=top_k_tickets,
                top_k_kb=top_k_kb
            )
            
            return {
                "task_type": "unified_search",
                "similar_tickets": search_result.get("similar_tickets", []),
                "kb_documents": search_result.get("kb_documents", []),
                "execution_time": search_result.get("performance_metrics", {}).get("total_time", 0),
                "cache_used": search_result.get("cache_used", False),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"통합 검색 태스크 실행 실패: {e}")
            return {
                "task_type": "unified_search",
                "similar_tickets": [],
                "kb_documents": [],
                "error": f"통합 검색 실패: {str(e)}",
                "success": False
            }

    async def _generate_summary_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 요약 생성 태스크
        
        Args:
            inputs: 입력 데이터 딕셔너리
                - ticket_data: 티켓 데이터
        
        Returns:
            요약 생성 결과
        """
        try:
            from core.llm.integrations.langchain.chains.summarization import SummarizationChain
            
            # SummarizationChain 인스턴스 생성
            summarization_chain = SummarizationChain(self)
            
            # 요약 체인 실행
            result = await summarization_chain.run(
                ticket_data=inputs.get("ticket_data", {})
            )
            
            return {
                "task_type": "summary",
                "summary": result,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"요약 생성 태스크 실행 실패: {e}")
            return {
                "task_type": "summary",
                "error": f"요약 생성 실패: {str(e)}",
                "success": False
            }
    
    async def execute_init_sequential(
        self,
        ticket_data: Dict[str, Any],
        qdrant_client: Any,
        tenant_id: str,
        include_summary: bool = True,
        include_similar_tickets: bool = True,
        include_kb_docs: bool = True,
        top_k_tickets: int = 3,
        top_k_kb: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        /init 엔드포인트를 위한 순차 실행 메서드 (병렬 처리 제거)
        
        순차적으로 실행:
        1. 실시간 티켓 요약 생성 (1-2초)
        2. 벡터 검색 (유사 티켓 + KB 문서) (2초)
        
        Args:
            ticket_data: 티켓 데이터
            qdrant_client: Qdrant 클라이언트
            tenant_id: 테넌트 ID
            include_summary: 요약 생성 여부
            include_similar_tickets: 유사 티켓 검색 여부
            include_kb_docs: KB 문서 검색 여부
            top_k_tickets: 유사 티켓 수
            top_k_kb: KB 문서 수
            
        Returns:
            실행 결과 딕셔너리
        """
        import time
        start_time = time.time()
        
        logger.info(f"순차 실행 시작 (ticket_id: {ticket_data.get('id')})")
        
        results = {}
        
        try:
            # 1단계: 실시간 티켓 요약 생성 (1-2초)
            if include_summary:
                summary_start = time.time()
                logger.info("1단계: 실시간 티켓 요약 생성 시작")
                
                summary_result = await self._generate_summary_task({
                    "ticket_data": ticket_data
                })
                
                results["summary"] = summary_result
                summary_time = time.time() - summary_start
                logger.info(f"1단계 완료: 요약 생성 ({summary_time:.2f}초)")
            
            # 2단계: 벡터 검색 (유사 티켓 + KB 문서) (2초)
            if include_similar_tickets or include_kb_docs:
                search_start = time.time()
                logger.info("2단계: 벡터 검색 시작")
                
                search_result = await self._unified_search_task({
                    "ticket_data": ticket_data,
                    "tenant_id": tenant_id,
                    "platform": "freshdesk",
                    "top_k_tickets": top_k_tickets,
                    "top_k_kb": top_k_kb
                })
                
                results["unified_search"] = search_result
                
                # 하위 호환성을 위한 개별 키
                if search_result.get("success"):
                    results["similar_tickets"] = search_result.get("similar_tickets", [])
                    results["kb_documents"] = search_result.get("kb_documents", [])
                
                search_time = time.time() - search_start
                logger.info(f"2단계 완료: 벡터 검색 ({search_time:.2f}초)")
            
            total_time = time.time() - start_time
            logger.info(f"순차 실행 완료 (ticket_id: {ticket_data.get('id')}, 총 실행시간: {total_time:.2f}초)")
            
            return {
                **results,
                "total_execution_time": total_time,
                "execution_type": "sequential",
                "success": True
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"순차 실행 실패: {str(e)}"
            logger.error(f"{error_msg} (실행시간: {total_time:.2f}초)")
            
            return {
                "summary": {
                    "task_type": "summary",
                    "error": "실행 실패로 인한 요약 생성 불가",
                    "success": False
                },
                "unified_search": {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "실행 실패로 인한 검색 불가",
                    "success": False
                },
                "similar_tickets": [],
                "kb_documents": [],
                "total_execution_time": total_time,
                "execution_type": "sequential",
                "success": False,
                "error": error_msg
            }
    
    async def generate_for_use_case(self, 
                                   use_case: str,
                                   messages: List[Dict[str, str]], 
                                   **kwargs) -> LLMResponse:
        """
        Use Case 기반 자동 모델 선택 - LangChain의 진정한 장점!
        
        환경변수만 변경하면 즉시 모델이 바뀜:
        - REALTIME_MODEL_NAME=gpt-4o-mini
        - BATCH_MODEL_NAME=gemini-1.5-flash
        - SUMMARIZATION_MODEL_NAME=claude-3-haiku
        
        Args:
            use_case: "realtime", "batch", "summarization" 등
            messages: 메시지 리스트
            **kwargs: 추가 파라미터
            
        Returns:
            LLM 응답
        """
        # 설정에서 자동으로 provider와 model 선택
        provider, model = self.config_manager.get_model_for_use_case(use_case)
        use_case_config = self.config_manager.get_use_case_config(use_case)
        
        # Use case별 기본 설정 적용
        if use_case_config:
            kwargs.setdefault("max_tokens", use_case_config.get("max_tokens", 1000))
            kwargs.setdefault("temperature", use_case_config.get("temperature", 0.3))
        
        logger.info(f"🎯 Use Case '{use_case}': {provider.value} - {model}")
        
        return await self.generate(
            messages=messages,
            model=model,
            provider=provider,
            **kwargs
        )
    
    async def stream_for_use_case(
        self,
        use_case: str,
        messages: List[Dict[str, str]] = None,
        system_prompt: str = None,
        user_prompt: str = None,
        **kwargs
    ):
        """
        Use case별 모델로 스트리밍 응답 생성
        
        Args:
            use_case: 사용 사례 (realtime, batch, summarization)
            messages: 메시지 리스트 (우선순위 1)
            system_prompt: 시스템 프롬프트 (우선순위 2)
            user_prompt: 사용자 프롬프트 (우선순위 2)
            **kwargs: 추가 파라미터
            
        Yields:
            str: 스트리밍 텍스트 청크
        """
        try:
            # Use case별 설정 가져오기
            provider, model_name = self.config_manager.get_model_for_use_case(use_case)
            config = self.config_manager.get_use_case_config(use_case)
            
            logger.info(f"🎯 Use Case '{use_case}' 스트리밍: {provider} - {model_name}")
            
            # 기본 파라미터 설정
            stream_params = {
                "model": model_name,
                "temperature": config.get("temperature", 0.2),
                "max_tokens": config.get("max_tokens", 1000),
                "stream": True,
                **kwargs
            }
            
            # 메시지 구성
            if messages:
                stream_params["messages"] = messages
            elif system_prompt and user_prompt:
                stream_params["messages"] = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            else:
                raise ValueError("messages 또는 system_prompt/user_prompt가 필요합니다")
            
            # Provider별 스트리밍 호출
            if provider not in self.providers:
                raise ValueError(f"Provider {provider}가 초기화되지 않았습니다")
            
            provider_instance = self.providers[provider]
            
            # 스트리밍 지원 확인
            if hasattr(provider_instance, 'stream_chat'):
                async for chunk in provider_instance.stream_chat(**stream_params):
                    yield chunk
            else:
                # 스트리밍 미지원 시 일반 응답 반환
                logger.warning(f"Provider {provider}가 스트리밍을 지원하지 않습니다. 일반 응답으로 대체합니다.")
                response = await self.generate_for_use_case(use_case, **kwargs)
                if response.success:
                    yield response.content
                else:
                    yield f"Error: {response.error}"
                    
        except Exception as e:
            logger.error(f"Use case '{use_case}' 스트리밍 실패: {e}")
            yield f"Error: 스트리밍 생성 중 오류가 발생했습니다: {str(e)}"
    
    async def stream_generate_for_use_case(
        self, 
        use_case: str,
        messages: List[Dict[str, str]] = None,
        system_prompt: str = None,
        user_prompt: str = None,
        **kwargs
    ):
        """
        Use case에 따라 설정된 모델로 스트리밍 텍스트 생성
        
        Args:
            use_case: realtime, batch, summarization 등
            messages: 대화 메시지 리스트 (우선순위 높음)
            system_prompt: 시스템 프롬프트 (messages 없을 때 사용)
            user_prompt: 사용자 프롬프트 (messages 없을 때 사용)
            **kwargs: 추가 파라미터
        """
        try:
            # Use case 기반 설정 가져오기
            provider, model_name = self.config_manager.get_model_for_use_case(use_case)
            config = self.config_manager.get_use_case_config(use_case)
            
            logger.info(f"🎯 Use Case '{use_case}' 스트리밍: {provider.value} - {model_name}")
            
            # 메시지 구성
            if not messages:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                if user_prompt:
                    messages.append({"role": "user", "content": user_prompt})
            
            # 제공자 가져오기
            if provider not in self.providers:
                raise ValueError(f"Provider {provider.value} not available")
            
            provider_instance = self.providers[provider]
            
            # 요청 객체 생성
            request = LLMRequest(
                messages=messages,
                model=model_name,
                max_tokens=config.get('max_tokens', kwargs.get('max_tokens', 1000)),
                temperature=config.get('temperature', kwargs.get('temperature', 0.1)),
                **{k: v for k, v in kwargs.items() if k not in ['max_tokens', 'temperature']}
            )
            
            # 스트리밍 지원 확인 및 실행
            try:
                # 스트리밍 생성 시도
                async for chunk in provider_instance.stream_generate(request):
                    yield chunk
            except AttributeError:
                logger.warning(f"Provider {provider.value}가 스트리밍을 지원하지 않습니다. 일반 응답으로 대체합니다.")
                # 일반 응답으로 fallback
                response = await self.generate_for_use_case(
                    use_case=use_case,
                    messages=messages,
                    **kwargs
                )
                if response.success:
                    yield response.content
                else:
                    yield f"Error: {response.error}"
                    
        except Exception as e:
            logger.error(f"Use case '{use_case}' 스트리밍 생성 오류: {e}")
            yield f"Error: {str(e)}"

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
