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
from .summarizer import generate_smart_summary

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
            
        logger.debug("LLMManager 초기화 시작...")
        
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
        self.status_mapping_cache = TTLCache(maxsize=10, ttl=7200)  # 2시간 캐시
        
        # 초기화
        self._initialize_providers()
        
        # 초기화 완료 플래그
        LLMManager._initialized = True
        logger.debug("LLMManager 싱글톤 초기화 완료")
        
        logger.info(f"LLMManager 초기화 완료 - {len(self.providers)}개 제공자 로드됨")
    
    def _initialize_providers(self):
        """제공자들 초기화"""
        
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                self.providers[LLMProvider.OPENAI] = OpenAIProvider(openai_key)
                logger.debug("OpenAI Provider 초기화 완료")
            except Exception as e:
                logger.error(f"OpenAI Provider 초기화 실패: {e}")
        
        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                self.providers[LLMProvider.ANTHROPIC] = AnthropicProvider(anthropic_key)
                logger.debug("Anthropic Provider 초기화 완료")
            except Exception as e:
                logger.error(f"Anthropic Provider 초기화 실패: {e}")
        
        # Gemini
        gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                self.providers[LLMProvider.GEMINI] = GeminiProvider(gemini_key)
                logger.debug("Gemini Provider 초기화 완료")
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
        # kwargs에서 LLMRequest에 해당하는 필드만 추출
        valid_fields = {'max_tokens', 'temperature', 'stream', 'metadata'}
        request_kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        request = LLMRequest(
            messages=messages,
            model=model,
            **request_kwargs
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
            
            # 🧠 스마트 요약 시스템 사용 (Anthropic 활성화 시 Constitutional AI 적용)
            
            # 🎯 티켓 내용 + 대화 내역 통합 처리 (토큰 최적화)
            content = ticket_data.get("description_text", "")
            
            # 대화 내역 추가 (중요한 맥락 정보)
            conversations = ticket_data.get("conversations", [])
            if conversations:
                conversation_content = self._extract_conversation_content(conversations, max_conversations=15)  # 20 → 15로 줄임
                if conversation_content:
                    content += f"\n\n=== 대화 내역 ===\n{conversation_content}"
                    logger.info(f"티켓 {ticket_data.get('id')}: 대화 {len(conversations)}개 중 최신 15개 포함")
            
            # 🚀 토큰 수 최적화: 너무 긴 콘텐츠 제한
            if len(content) > 8000:  # 약 2000 토큰 제한
                content = content[:8000] + "\n\n[내용이 길어 일부 생략됨]"
                logger.info(f"티켓 {ticket_data.get('id')}: 콘텐츠 길이 최적화 (8000자로 제한)")
            
            logger.info(f"📊 최종 콘텐츠 길이: {len(content)}자 (예상 토큰: ~{len(content)//4}개)")
            
            # 🚀 캐싱 확인: 동일한 티켓+대화 조합에 대한 캐시 확인
            import hashlib
            cache_key = f"ticket_summary_{ticket_data.get('id')}_{hashlib.md5(content.encode()).hexdigest()[:8]}"
            
            if hasattr(self, 'cache') and self.cache:
                cached_result = self.cache.get(cache_key)
                if cached_result:
                    logger.info(f"✅ 캐시된 요약 사용 - ID: {ticket_data.get('id')}")
                    return cached_result
            
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
            
            # 조회티켓(ticket_view)은 첨부파일 처리 제외 (속도 최적화)
            metadata = {
                "status": ticket_data.get("status"),
                "priority": ticket_data.get("priority"),
                "created_at": ticket_data.get("created_at"),
                "has_conversations": tenant_metadata.get('has_conversations', False),
                "conversation_count": tenant_metadata.get('conversation_count', 0)
            }
            
            # 🧠 스마트 요약 시스템으로 생성 (Anthropic 활성화 시 Constitutional AI 적용)
            summary = await generate_smart_summary(
                content=content,
                content_type="ticket_view",  # 조회 티켓 전용 YAML 템플릿 사용 (최고 품질)
                subject=ticket_data.get("subject", ""),
                metadata=metadata,
                ui_language="ko"
            )
            
            summary_time = time.time() - summary_start_time
            logger.info(f"⚡ [최적화 완료] 티켓 요약 - ID: {ticket_data.get('id')} - 소요시간: {summary_time:.2f}초")
            
            # AI 처리 정보 업데이트  
            updated_metadata = TenantMetadataNormalizer.update_ai_processing_info(
                tenant_metadata, 
                model_used="claude-3-5-haiku-20241022",  # 실제 사용된 모델로 업데이트
                quality_score=4.0  # 기본 품질 점수
            )
            
            result = {
                "summary": summary,
                "key_points": ["구조화된 요약"],
                "sentiment": "중립적", 
                "priority_recommendation": "보통",
                "urgency_level": "보통",
                "updated_metadata": updated_metadata
            }
            
            # 🚀 결과 캐싱: 향후 동일 요청 시 빠른 응답
            if hasattr(self, 'cache') and self.cache:
                try:
                    self.cache.set(cache_key, result, timeout=3600)  # 1시간 캐싱
                    logger.debug(f"💾 요약 결과 캐싱 완료 - ID: {ticket_data.get('id')}")
                except Exception as e:
                    logger.warning(f"캐싱 실패: {e}")
            
            return result
                
        except Exception as e:
            logger.error(f"티켓 요약 생성 실패: {e}")
            return {
                "summary": f"오류로 인해 요약 생성에 실패했습니다. 오류: {str(e)}",
                "key_points": ["요약 생성 오류", "수동 검토 필요"],
                "sentiment": "중립적",
                "priority_recommendation": "확인 필요",
                "urgency_level": "보통"
            }
    
    async def generate_similar_ticket_summaries(self, similar_tickets: List[Dict[str, Any]], ui_language: str = "ko", platform_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        유사 티켓들에 대한 요약 생성 (병렬 처리)
        
        Args:
            similar_tickets: 유사 티켓 목록 [{
                "id": "123",
                "title": "제목", 
                "content": "내용",
                "score": 0.85,
                "metadata": {...}
            }]
            ui_language: UI 언어 (ko, en, ja, zh)
            
        Returns:
            요약이 포함된 유사 티켓 목록
        """
        import asyncio
        import os
        
        # 상태 매핑 정보 가져오기
        status_mapping = {}
        if platform_config:
            try:
                platform_name = platform_config.get("platform", "freshdesk")
                status_mapping = await self.get_status_mapping(platform_name, platform_config)
                logger.info(f"상태 매핑 로드 완료: {len(status_mapping)}개")
            except Exception as e:
                logger.warning(f"상태 매핑 로드 실패, 기본값 사용: {e}")
                status_mapping = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
        
        # 병렬 처리 활성화 확인
        enable_parallel = os.getenv("ENABLE_PARALLEL_PROCESSING", "true").lower() == "true"
        max_concurrent = int(os.getenv("MAX_CONCURRENT_SUMMARIES", "3"))
        
        if not enable_parallel or len(similar_tickets) <= 1:
            # 순차 처리 (기존 로직)
            return await self._generate_similar_tickets_sequential(similar_tickets, ui_language, status_mapping)
        
        # 병렬 처리
        logger.info(f"🚀 [병렬 처리] 유사 티켓 {len(similar_tickets)}개 병렬 요약 시작 (최대 동시 실행: {max_concurrent}개)")
        
        # 세마포어로 동시 실행 제한
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_ticket_with_semaphore(ticket, index):
            async with semaphore:
                return await self._generate_single_ticket_summary(ticket, index, ui_language, status_mapping)
        
        # 모든 티켓에 대해 병렬 작업 생성
        tasks = [
            process_ticket_with_semaphore(ticket, i)
            for i, ticket in enumerate(similar_tickets)
        ]
        
        # 병렬 실행 (예외가 발생해도 다른 작업은 계속 진행)
        import time
        parallel_start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        parallel_time = time.time() - parallel_start_time
        
        # 결과 정리 (성공한 것만 반환)
        summarized_tickets = []
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ [병렬 처리] 티켓 {similar_tickets[i].get('id')} 요약 실패: {result}")
                # 실패한 경우 폴백 처리
                fallback_ticket = self._create_fallback_ticket(similar_tickets[i])
                summarized_tickets.append(fallback_ticket)
            else:
                summarized_tickets.append(result)
                success_count += 1
        
        logger.info(f"⏱️ [병렬 처리] 완료 - 총 {len(similar_tickets)}개 중 {success_count}개 성공, 소요시간: {parallel_time:.2f}초")
        
        return summarized_tickets

    async def _generate_similar_tickets_sequential(self, similar_tickets: List[Dict[str, Any]], ui_language: str = "ko", status_mapping: Dict[int, str] = None) -> List[Dict[str, Any]]:
        """
        유사 티켓들에 대한 요약 생성 (순차 처리 - 기존 로직)
        """
        summarized_tickets = []
        
        for i, ticket in enumerate(similar_tickets):
            try:
                logger.debug(f"🔍 [유사 티켓 요약] {i+1}/{len(similar_tickets)} 요약 생성 중 (ID: {ticket.get('id', 'unknown')})")
                
                # 티켓 데이터 구조 변환 (generate_ticket_summary 형식에 맞춤)
                # 메타데이터 정제: 첨부파일 정보 요약용으로 가공
                tenant_metadata = ticket.get("metadata", {}).copy()
                
                # 첨부파일 정보를 요약에 포함하기 위해 가공 (LLM 선별된 첨부파일 우선 사용)
                attachment_summary = []
                
                # 1순위: LLM 선별된 첨부파일 (relevant_attachments)
                relevant_attachments = ticket.get("metadata", {}).get("relevant_attachments", [])
                if relevant_attachments:
                    logger.info(f"🎯 [첨부파일] LLM 선별된 첨부파일 사용: {len(relevant_attachments)}개")
                    for attachment in relevant_attachments:
                        if isinstance(attachment, dict):
                            name = attachment.get("name", "unknown")
                            size = attachment.get("size", 0)
                            content_type = attachment.get("content_type", "")
                            
                            # 파일 타입별 이쁜 이모지 선택
                            emoji = self._get_file_emoji(name, content_type)
                            
                            if size > 0:
                                size_mb = round(size / (1024*1024), 2)
                                attachment_summary.append(f"{emoji} {name} ({size_mb}MB)")
                            else:
                                attachment_summary.append(f"{emoji} {name}")
                
                # 2순위: 모든 첨부파일 (all_attachments) - 폴백용
                elif ticket.get("metadata", {}).get("all_attachments"):
                    logger.info(f"📎 [첨부파일] 전체 첨부파일 사용 (폴백)")
                    attachments = ticket["metadata"]["all_attachments"]
                    for attachment in attachments:
                        if isinstance(attachment, dict):
                            name = attachment.get("name", "unknown")
                            size = attachment.get("size", 0)
                            content_type = attachment.get("content_type", "")
                            
                            # 파일 타입별 이쁜 이모지 선택
                            emoji = self._get_file_emoji(name, content_type)
                            
                            if size > 0:
                                size_mb = round(size / (1024*1024), 2)
                                attachment_summary.append(f"{emoji} {name} ({size_mb}MB)")
                            else:
                                attachment_summary.append(f"{emoji} {name}")
                
                # 첨부파일 정보 저장 (한 줄씩 표시로 변경)
                if attachment_summary:
                    # 각 파일을 한 줄씩 표시 (이쁜 형태로)
                    formatted_attachments = []
                    for attachment_info in attachment_summary:
                        formatted_attachments.append(f"- {attachment_info}")
                    
                    tenant_metadata['attachment_summary'] = "\n".join(formatted_attachments)
                    tenant_metadata['attachment_count'] = len(attachment_summary)
                    # LLM 선별된 첨부파일도 프롬프트 빌더에서 사용할 수 있도록 보존
                    if relevant_attachments:
                        tenant_metadata['relevant_attachments'] = relevant_attachments
                    logger.info(f"📎 [첨부파일] 요약에 포함됨: {len(attachment_summary)}개 파일")
                else:
                    logger.info(f"📎 [첨부파일] 요약에 포함할 첨부파일 없음")
                
                # 실제 첨부파일 객체는 제거 (URL 생성 방지)
                tenant_metadata.pop('attachments', None)
                tenant_metadata.pop('all_attachments', None)
                
                ticket_data_for_summary = {
                    "id": ticket.get("id"),
                    "subject": ticket.get("subject", ""),
                    "description_text": ticket.get("content", ""),  # Vector DB의 content 사용
                    "description": ticket.get("content", ""),       # 폴백용
                    "status": ticket.get("metadata", {}).get("status"),
                    "priority": ticket.get("metadata", {}).get("priority"),
                    "created_at": ticket.get("metadata", {}).get("created_at"),
                    "tenant_metadata": tenant_metadata  # 정제된 메타데이터 사용
                }
                
                # YAML 템플릿 기반 유사 티켓 요약 생성
                try:
                    import time
                    ticket_start_time = time.time()
                    
                    # 유사 티켓/문서용 요약 생성 (doc_type에 따라 템플릿 선택)
                    from core.llm.summarizer.core.summarizer import core_summarizer
                    
                    # doc_type 확인 - 아티클은 요약하지 않고 스킵
                    metadata = ticket.get("metadata", {})
                    doc_type = metadata.get("doc_type", "ticket")
                    
                    logger.info(f"🔍 [doc_type 확인] ID: {ticket.get('id')}, doc_type: '{doc_type}'")
                    
                    if doc_type == "article":
                        logger.info(f"📚 [KB 문서 스킵] 아티클 ID {ticket.get('id')} - 요약 생성하지 않음")
                        # 아티클은 메타데이터만 사용하므로 요약 생성하지 않음
                        summarized_ticket = {
                            "id": ticket.get("id"),
                            "subject": ticket.get("subject", ""),
                            "content": f"📚 **지식베이스 문서**\n\n**제목**: {ticket.get('subject', '')}\n\n원본 링크에서 확인하세요.",
                            "score": ticket.get("score", 0.0),
                            "metadata": ticket.get("metadata", {})
                        }
                        summarized_tickets.append(summarized_ticket)
                        continue  # 아티클은 LLM 요약 없이 바로 다음으로
                    
                    # 티켓만 요약 생성
                    content_type = "ticket_similar"
                    logger.info(f"🎫 [티켓] 티켓 ID {ticket.get('id')} - ticket_similar 템플릿 사용")
                    
                    summary_result = await generate_smart_summary(
                        content=ticket_data_for_summary.get("description_text", ""),
                        content_type=content_type,  # doc_type에 따라 올바른 템플릿 사용
                        subject=ticket_data_for_summary.get("subject", ""),
                        metadata=ticket_data_for_summary.get("tenant_metadata", {}),
                        ui_language=ui_language
                    )
                    
                    ticket_time = time.time() - ticket_start_time
                    logger.debug(f"⏱️ [유사 티켓 {i+1}] 요약 소요시간: {ticket_time:.2f}초")
                    
                    # 요약 결과 검증
                    if summary_result and summary_result.strip():
                        summary_text = f"{summary_result}\n\n**🎯 유사도**: {ticket.get('score', 0.0):.3f}"
                    else:
                        logger.warning(f"Empty summary result for ticket {ticket.get('id')}, using fallback")
                        ticket_title = ticket.get("subject", "제목 없음")
                        summary_text = f"## 🔍 {ticket_title}\n\n**문제 상황**: 유사 티켓 요약 생성 실패\n\n**🎯 유사도**: {ticket.get('score', 0.0):.3f}"
                    
                    logger.debug(f"✅ [유사 티켓 요약] 티켓 {ticket.get('id')} YAML 템플릿 기반 요약 완료 ({len(summary_text)}자)")
                    # 성능 최적화를 위해 상세 요약 내용 로깅 제거
                    
                except Exception as e:
                    logger.error(f"❌ [유사 티켓 요약] 티켓 {ticket.get('id')} YAML 템플릿 요약 실패: {e}")
                    # 폴백: 간단한 마크다운 요약
                    ticket_title = ticket.get("subject", "제목 없음")
                    ticket_content = ticket.get("content", "")
                    summary_parts = []
                    summary_parts.append(f"## 🔍 {ticket_title}")
                    summary_parts.append(f"**유사 문제**: {ticket_content[:300] if ticket_content else '내용 없음'}...")
                    summary_parts.append(f"**유사도**: {ticket.get('score', 0.0):.3f}")
                    summary_text = "\n\n".join(summary_parts)
                    logger.warning(f"⚠️ [유사 티켓 요약] 티켓 {ticket.get('id')} 폴백 요약 사용")
                    # 성능 최적화를 위해 폴백 요약 내용 로깅 제거
                
                # 결과 구성
                summarized_ticket = {
                    "id": ticket.get("id"),
                    "subject": ticket.get("subject", ""),  # subject 필드만 사용
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
                    "subject": ticket.get("subject", ""),  # subject 필드만 사용
                    "content": ticket.get("content", "요약 생성에 실패했습니다.")[:200] + "...",
                    "score": ticket.get("score", 0.0),
                    "metadata": ticket.get("metadata", {})
                }
                summarized_tickets.append(fallback_ticket)
        
        logger.info(f"🎯 [유사 티켓 요약] 완료: {len(summarized_tickets)}건 처리")
        return summarized_tickets

    async def _generate_single_ticket_summary(self, ticket: Dict[str, Any], index: int, ui_language: str = "ko", status_mapping: Dict[int, str] = None) -> Dict[str, Any]:
        """
        개별 티켓에 대한 요약 생성 (병렬 처리용)
        
        Args:
            ticket: 티켓 정보
            index: 티켓 인덱스
            ui_language: UI 언어
            
        Returns:
            요약이 포함된 티켓 정보
        """
        import time
        
        try:
            ticket_start_time = time.time()
            logger.info(f"🔍 [병렬 요약 {index+1}] 티켓 {ticket.get('id', 'unknown')} 요약 시작")
            
            # 티켓 데이터 구조 변환
            # 메타데이터 정제: 첨부파일 정보 제거 (잘못된 URL 생성 방지)
            tenant_metadata = ticket.get("metadata", {}).copy()
            tenant_metadata.pop('attachments', None)
            tenant_metadata.pop('all_attachments', None)
            tenant_metadata.pop('attachment_count', None)
            
            ticket_data_for_summary = {
                "id": ticket.get("id"),
                "subject": ticket.get("subject") or ticket.get("title", ""),
                "description_text": ticket.get("content", ""),
                "description": ticket.get("content", ""),
                "status": ticket.get("metadata", {}).get("status"),
                "priority": ticket.get("metadata", {}).get("priority"),
                "created_at": ticket.get("metadata", {}).get("created_at"),
                "tenant_metadata": tenant_metadata  # 정제된 메타데이터 사용
            }
            
            # doc_type 확인 - 아티클은 요약하지 않고 스킵
            metadata = ticket.get("metadata", {})
            doc_type = metadata.get("doc_type", "ticket")
            
            if doc_type == "article":
                logger.info(f"📚 [병렬 요약 {index+1}] 아티클 ID {ticket.get('id')} - 요약 생성하지 않음")
                return {
                    "id": ticket.get("id"),
                    "subject": ticket.get("subject", ""),  # subject 필드만 사용
                    "content": f"📚 **지식베이스 문서**\n\n**제목**: {ticket.get('subject', '')}\n\n원본 링크에서 확인하세요.",
                    "score": ticket.get("score", 0.0),
                    "metadata": ticket.get("metadata", {})
                }
            
            # 🧠 스마트 요약 시스템으로 생성 (Anthropic 활성화 시 Constitutional AI 적용)
            summary_result = await generate_smart_summary(
                content=ticket_data_for_summary.get("description_text", ""),
                content_type="ticket_similar",  # 기존 이름 유지 (3섹션 최적화 버전)
                subject=ticket_data_for_summary.get("subject", ""),
                metadata=ticket_data_for_summary.get("tenant_metadata", {}),
                ui_language=ui_language
            )
            
            # 요약 결과 검증 및 포맷팅 (메타데이터 분리)
            if summary_result and summary_result.strip():
                summary_text = summary_result  # 유사도 정보 제거 (메타데이터로 처리)
            else:
                logger.warning(f"[병렬 요약 {index+1}] Empty summary result for ticket {ticket.get('id')}, using fallback")
                ticket_title = ticket.get("subject", "제목 없음")
                summary_text = f"🔴 **문제**\n유사 티켓 요약 생성 실패\n\n⚡ **처리결과**\n요약 생성 오류\n\n📚 **참고자료**\n원본 티켓 확인 필요"
            
            ticket_time = time.time() - ticket_start_time
            logger.info(f"⏱️ [병렬 요약 {index+1}] 티켓 {ticket.get('id')} 완료 - 소요시간: {ticket_time:.2f}초")
            
            # 메타데이터 강화 (요청자, 담당자, 상태 등)
            enhanced_metadata = ticket.get("metadata", {}).copy()
            
            # 원본 status 숫자값 그대로 사용 (프론트에서 레이블 변환)
            original_status = enhanced_metadata.get("status")
            
            enhanced_metadata.update({
                "similarity_score": round(ticket.get("score", 0.0), 3),
                "status": original_status,  # 원본 숫자값 그대로 전송
                "priority": enhanced_metadata.get("priority", 1),  # 원본 숫자값 그대로 사용
                "created_at": enhanced_metadata.get("created_at")  # created_at 필드 추가
            })
            
            return {
                "id": ticket.get("id"),
                "subject": ticket.get("subject") or ticket.get("title", ""),  # subject 필드만 사용
                "content": summary_text,  # 순수 요약 내용만
                "score": ticket.get("score", 0.0),
                "metadata": enhanced_metadata  # 강화된 메타데이터
            }
            
        except Exception as e:
            logger.error(f"❌ [병렬 요약 {index+1}] 티켓 {ticket.get('id')} 요약 실패: {e}")
            # 예외를 다시 raise하여 gather에서 처리할 수 있도록 함
            raise e

    def _create_fallback_ticket(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        요약 생성에 실패한 티켓에 대한 폴백 결과 생성
        
        Args:
            ticket: 원본 티켓 정보
            
        Returns:
            폴백 티켓 정보
        """
        ticket_title = ticket.get("subject", "제목 없음")
        ticket_content = ticket.get("content", "")
        
        fallback_content = f"## 🔍 {ticket_title}\n\n**유사 문제**: {ticket_content[:300] if ticket_content else '내용 없음'}...\n\n**🎯 유사도**: {ticket.get('score', 0.0):.3f}"
        
        return {
            "id": ticket.get("id"),
            "subject": ticket.get("subject") or ticket.get("title", ""),  # subject 필드만 사용
            "content": fallback_content,
            "score": ticket.get("score", 0.0),
            "metadata": ticket.get("metadata", {})
        }
    
    # KB 문서 요약 함수 제거 - 아티클은 메타데이터만 사용하기로 결정

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
    
    def build_prompt(self, context: str, query: str, agent_mode: bool = False) -> str:
        """
        컨텍스트와 쿼리를 기반으로 프롬프트를 구성합니다.
        
        Args:
            context: 검색된 컨텍스트 정보
            query: 사용자 질문
            agent_mode: 에이전트 모드 여부
            
        Returns:
            구성된 프롬프트
        """
        if agent_mode:
            # 스마트 대화 모드 - 구체적인 답변 요구
            system_prompt = """당신은 고객 서비스 전문가입니다. 제공된 컨텍스트를 바탕으로 정확하고 도움이 되는 답변을 제공하세요.

컨텍스트 정보:
{context}

지침:
1. 컨텍스트에서 관련 정보를 찾아 구체적으로 답변하세요
2. 확실하지 않은 정보는 추측하지 마세요
3. 한국어로 친절하고 명확하게 답변하세요
4. 필요시 단계별로 설명하세요"""
        else:
            # 자유 대화 모드 - 일반적인 AI 어시스턴트
            system_prompt = """당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 친절하고 정확하게 답변하세요.

참고 컨텍스트:
{context}

지침:
1. 질문에 대해 도움이 되는 답변을 제공하세요
2. 모르는 것은 모른다고 솔직히 말하세요
3. 한국어로 자연스럽게 대화하세요"""
        
        formatted_prompt = system_prompt.format(context=context)
        return f"{formatted_prompt}\n\n사용자 질문: {query}\n\n답변:"
    
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
    
    def _extract_conversation_content(self, conversations: List[Dict[str, Any]], max_conversations: int = 10) -> str:
        """
        대화 내역에서 중요한 내용 추출 (토큰 제한 고려)
        
        Args:
            conversations: 대화 목록
            max_conversations: 포함할 최대 대화 수
            
        Returns:
            정리된 대화 내용
        """
        if not conversations:
            return ""
            
        # 최신 대화 우선 (중요도 높음)
        recent_conversations = sorted(conversations, 
                                    key=lambda x: x.get('created_at', ''), 
                                    reverse=True)[:max_conversations]
        
        conversation_parts = []
        for i, conv in enumerate(recent_conversations):
            # 발신자 정보
            sender = conv.get('from_email', conv.get('user_name', '시스템'))
            if sender == '시스템':
                sender = '상담원' if conv.get('private', False) else '고객'
            
            # 대화 내용
            body = self._extract_conversation_body(conv)
            if body and len(body.strip()) > 10:  # 의미 있는 내용만
                # 너무 긴 대화는 요약 (토큰 절약)
                if len(body) > 500:
                    body = body[:500] + "..."
                
                timestamp = conv.get('created_at', '')[:10] if conv.get('created_at') else ''
                conversation_parts.append(f"[{timestamp}] {sender}: {body}")
        
        return "\n".join(conversation_parts)
    
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
    
    def _get_file_emoji(self, filename: str, content_type: str = "") -> str:
        """파일 타입별 이쁜 이모지 반환"""
        filename_lower = filename.lower()
        content_type_lower = content_type.lower()
        
        # 이미지 파일
        if any(ext in filename_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']) or 'image/' in content_type_lower:
            if '.gif' in filename_lower or 'gif' in content_type_lower:
                return '🎞️'  # GIF
            return '🖼️'  # 일반 이미지
        
        # 문서 파일
        if '.pdf' in filename_lower or 'pdf' in content_type_lower:
            return '📕'  # PDF
        if any(ext in filename_lower for ext in ['.doc', '.docx']) or 'msword' in content_type_lower:
            return '📝'  # Word 문서
        if any(ext in filename_lower for ext in ['.xls', '.xlsx']) or 'spreadsheet' in content_type_lower:
            return '📊'  # Excel
        if any(ext in filename_lower for ext in ['.ppt', '.pptx']) or 'presentation' in content_type_lower:
            return '📺'  # PowerPoint
        
        # 코드/설정 파일
        if any(ext in filename_lower for ext in ['.json', '.xml', '.yaml', '.yml', '.config']) or 'json' in content_type_lower or 'xml' in content_type_lower:
            return '🗄️'  # 구조화된 데이터
        if any(ext in filename_lower for ext in ['.sql', '.db']):
            return '🗃️'  # 데이터베이스
        
        # 로그/텍스트 파일
        if any(ext in filename_lower for ext in ['.log', '.txt']) or 'text/plain' in content_type_lower:
            if '.log' in filename_lower or 'log' in filename_lower:
                return '📋'  # 로그 파일
            return '📄'  # 일반 텍스트
        
        # 압축 파일
        if any(ext in filename_lower for ext in ['.zip', '.rar', '.7z', '.tar', '.gz']) or 'compressed' in content_type_lower or 'zip' in content_type_lower:
            return '🗜️'  # 압축 파일
        
        # 미디어 파일
        if any(ext in filename_lower for ext in ['.mp3', '.wav', '.mp4', '.avi']) or 'audio/' in content_type_lower or 'video/' in content_type_lower:
            if 'audio/' in content_type_lower or any(ext in filename_lower for ext in ['.mp3', '.wav']):
                return '🎵'  # 오디오
            return '🎬'  # 비디오
        
        # 실행 파일
        if any(ext in filename_lower for ext in ['.exe', '.app', '.dmg']):
            return '⚙️'  # 실행 파일
        
        # 기본값
        return '📎'  # 일반 첨부파일
    
    async def get_status_mapping(self, platform: str, config: Dict[str, Any]) -> Dict[int, str]:
        """
        플랫폼에서 상태 매핑 정보를 가져옵니다.
        
        Args:
            platform: 플랫폼 이름 (예: "freshdesk")
            config: 플랫폼 설정 정보
            
        Returns:
            Dict[int, str]: 상태 ID와 라벨의 매핑
        """
        cache_key = f"status_mapping_{platform}_{config.get('domain', '')}"
        
        # 캐시에서 확인
        if cache_key in self.status_mapping_cache:
            logger.debug(f"상태 매핑 캐시 히트: {cache_key}")
            return self.status_mapping_cache[cache_key]
        
        try:
            if platform == "freshdesk":
                from core.platforms.freshdesk.adapter import FreshdeskAdapter
                
                async with FreshdeskAdapter(config) as adapter:
                    status_mapping = await adapter.fetch_status_mapping()
                    
                # 캐시에 저장
                self.status_mapping_cache[cache_key] = status_mapping
                logger.info(f"상태 매핑 캐시 저장: {len(status_mapping)}개 상태")
                return status_mapping
            else:
                logger.warning(f"지원하지 않는 플랫폼: {platform}")
                return {}
                
        except Exception as e:
            logger.error(f"상태 매핑 가져오기 실패: {e}")
            # 기본 매핑 반환
            return {
                2: "Open",
                3: "Pending", 
                4: "Resolved",
                5: "Closed"
            }

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
