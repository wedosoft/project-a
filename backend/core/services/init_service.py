"""
Ticket Initialization Service

티켓 초기화 로직을 담당하는 서비스 클래스입니다.
기존 init_endpoint()의 복잡한 로직을 분해하여 관리성을 향상시킵니다.
"""

import logging
import os
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

from core.constants import SearchConfig, APILimits
from core.cache.redis_pool import RedisCache
from api.models.responses import InitResponse, TicketSummaryContent, SimilarTicketItem, DocumentInfo

logger = logging.getLogger(__name__)


@dataclass
class InitializationRequest:
    """티켓 초기화 요청 파라미터"""
    ticket_id: str
    tenant_id: str
    platform: str
    domain: str
    api_key: str
    include_summary: bool = True
    include_kb_docs: bool = True
    include_similar_tickets: bool = True
    top_k_tickets: int = 3
    top_k_kb: int = 3
    ui_language: str = "ko"
    retry_reason: Optional[str] = None


@dataclass
class InitializationResult:
    """티켓 초기화 결과"""
    ticket_data: Dict[str, Any]
    ticket_summary: Optional[TicketSummaryContent]
    similar_tickets: List[SimilarTicketItem]
    kb_documents: List[DocumentInfo]
    context_id: str
    metadata: Dict[str, Any]


class TicketInitializationService:
    """
    티켓 초기화 서비스
    
    복잡한 초기화 로직을 단계별로 분해하여 관리합니다.
    """
    
    def __init__(self):
        self.cache = RedisCache(key_prefix="ticket_init")
        self.enable_full_streaming = os.getenv("ENABLE_FULL_STREAMING_MODE", "true").lower() == "true"
        
    async def initialize_ticket(self, request: InitializationRequest) -> InitializationResult:
        """
        티켓 전체 초기화 프로세스
        
        Args:
            request: 초기화 요청 파라미터
            
        Returns:
            InitializationResult: 초기화 결과
        """
        logger.info(f"티켓 초기화 시작 - ID: {request.ticket_id}, 테넌트: {request.tenant_id}")
        
        # 1. 캐시 확인
        cache_key = f"{request.tenant_id}:{request.ticket_id}:{request.ui_language}"
        cached_result = await self._check_cache(cache_key)
        if cached_result and not request.retry_reason:
            logger.info(f"캐시된 결과 반환 - 티켓: {request.ticket_id}")
            return cached_result
        
        # 2. 티켓 데이터 수집
        ticket_data = await self._fetch_ticket_data(request)
        if not ticket_data:
            raise ValueError(f"티켓 {request.ticket_id}를 찾을 수 없습니다")
        
        # 3. 컨텍스트 ID 생성
        context_id = self._generate_context_id(request)
        
        # 4. 병렬 처리로 요약/검색 수행
        summary_task = self._generate_summary(request, ticket_data) if request.include_summary else None
        similar_tickets_task = self._search_similar_tickets(request, ticket_data) if request.include_similar_tickets else None
        kb_docs_task = self._search_kb_documents(request, ticket_data) if request.include_kb_docs else None
        
        # 5. 결과 수집
        ticket_summary = await summary_task if summary_task else None
        similar_tickets = await similar_tickets_task if similar_tickets_task else []
        kb_documents = await kb_docs_task if kb_docs_task else []
        
        # 6. 메타데이터 구성
        metadata = self._build_metadata(request, ticket_data)
        
        # 7. 결과 구성
        result = InitializationResult(
            ticket_data=ticket_data,
            ticket_summary=ticket_summary,
            similar_tickets=similar_tickets,
            kb_documents=kb_documents,
            context_id=context_id,
            metadata=metadata
        )
        
        # 8. 캐시 저장
        await self._save_to_cache(cache_key, result)
        
        logger.info(f"티켓 초기화 완료 - ID: {request.ticket_id}")
        return result
    
    async def initialize_ticket_streaming(self, request: InitializationRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """
        스트리밍 모드 티켓 초기화
        
        Args:
            request: 초기화 요청 파라미터
            
        Yields:
            Dict[str, Any]: 스트리밍 청크
        """
        logger.info(f"스트리밍 티켓 초기화 시작 - ID: {request.ticket_id}")
        
        try:
            # 1. 초기 상태 전송
            yield {
                "type": "status",
                "data": {
                    "message": "티켓 정보 수집 중...",
                    "progress": 10
                }
            }
            
            # 2. 티켓 데이터 수집
            ticket_data = await self._fetch_ticket_data(request)
            if not ticket_data:
                yield {
                    "type": "error",
                    "data": {"message": f"티켓 {request.ticket_id}를 찾을 수 없습니다"}
                }
                return
            
            yield {
                "type": "ticket_data",
                "data": ticket_data
            }
            
            # 3. 병렬 처리 시작
            if request.include_summary:
                yield {
                    "type": "status",
                    "data": {
                        "message": "티켓 요약 생성 중...",
                        "progress": 30
                    }
                }
                
                summary = await self._generate_summary(request, ticket_data)
                yield {
                    "type": "summary",
                    "data": summary
                }
            
            if request.include_similar_tickets:
                yield {
                    "type": "status", 
                    "data": {
                        "message": "유사 티켓 검색 중...",
                        "progress": 60
                    }
                }
                
                similar_tickets = await self._search_similar_tickets(request, ticket_data)
                yield {
                    "type": "similar_tickets",
                    "data": similar_tickets
                }
            
            if request.include_kb_docs:
                yield {
                    "type": "status",
                    "data": {
                        "message": "지식베이스 검색 중...",
                        "progress": 80
                    }
                }
                
                kb_docs = await self._search_kb_documents(request, ticket_data)
                yield {
                    "type": "kb_documents", 
                    "data": kb_docs
                }
            
            # 4. 완료
            context_id = self._generate_context_id(request)
            metadata = self._build_metadata(request, ticket_data)
            
            yield {
                "type": "complete",
                "data": {
                    "context_id": context_id,
                    "metadata": metadata,
                    "progress": 100
                }
            }
            
        except Exception as e:
            logger.error(f"스트리밍 초기화 오류: {e}")
            yield {
                "type": "error",
                "data": {"message": f"초기화 중 오류 발생: {str(e)}"}
            }
    
    async def _check_cache(self, cache_key: str) -> Optional[InitializationResult]:
        """캐시에서 초기화 결과 확인"""
        try:
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                return InitializationResult(**cached_data)
        except Exception as e:
            logger.warning(f"캐시 조회 실패: {e}")
        return None
    
    async def _save_to_cache(self, cache_key: str, result: InitializationResult):
        """초기화 결과를 캐시에 저장"""
        try:
            cache_data = {
                "ticket_data": result.ticket_data,
                "ticket_summary": result.ticket_summary.__dict__ if result.ticket_summary else None,
                "similar_tickets": [item.__dict__ for item in result.similar_tickets],
                "kb_documents": [doc.__dict__ for doc in result.kb_documents],
                "context_id": result.context_id,
                "metadata": result.metadata
            }
            await self.cache.set(cache_key, cache_data, ttl=3600)  # 1시간 캐시
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")
    
    async def _fetch_ticket_data(self, request: InitializationRequest) -> Optional[Dict[str, Any]]:
        """Freshdesk에서 티켓 데이터 수집"""
        try:
            from core.platforms.freshdesk.adapter import FreshdeskAdapter
            
            config = {
                "domain": request.domain,
                "api_key": request.api_key,
                "tenant_id": request.tenant_id
            }
            
            async with FreshdeskAdapter(config) as adapter:
                ticket_detail = await adapter.fetch_ticket_details(request.ticket_id)
                return ticket_detail
                
        except Exception as e:
            logger.error(f"티켓 데이터 수집 실패: {e}")
            return None
    
    async def _generate_summary(self, request: InitializationRequest, ticket_data: Dict[str, Any]) -> Optional[TicketSummaryContent]:
        """티켓 요약 생성"""
        try:
            from core.llm.manager import LLMManager
            
            llm_manager = LLMManager()
            summary_result = await llm_manager.generate_ticket_summary_optimized(
                ticket_data=ticket_data,
                tenant_id=request.tenant_id,
                ui_language=request.ui_language
            )
            
            if summary_result and "summary" in summary_result:
                return TicketSummaryContent(
                    summary=summary_result["summary"],
                    key_points=summary_result.get("key_points", []),
                    sentiment=summary_result.get("sentiment", "중립적"),
                    priority_recommendation=summary_result.get("priority_recommendation", "보통"),
                    urgency_level=summary_result.get("urgency_level", "보통")
                )
                
        except Exception as e:
            logger.error(f"티켓 요약 생성 실패: {e}")
        
        return None
    
    async def _search_similar_tickets(self, request: InitializationRequest, ticket_data: Dict[str, Any]) -> List[SimilarTicketItem]:
        """유사 티켓 검색"""
        try:
            from core.database.vectordb import search_vector_db
            
            # 검색 쿼리 구성
            query_parts = []
            if ticket_data.get("subject"):
                query_parts.append(ticket_data["subject"])
            if ticket_data.get("description"):
                query_parts.append(ticket_data["description"][:500])  # 처음 500자만
            
            query = " ".join(query_parts)
            
            # 벡터 검색 수행
            results = await search_vector_db(
                query=query,
                tenant_id=request.tenant_id,
                platform=request.platform,
                doc_types=["ticket"],
                limit=request.top_k_tickets,
                exclude_id=request.ticket_id
            )
            
            # SimilarTicketItem 객체로 변환
            similar_tickets = []
            for result in results:
                metadata = result.get("metadata", {})
                similar_tickets.append(SimilarTicketItem(
                    id=metadata.get("original_id", ""),
                    subject=metadata.get("subject", ""),
                    similarity_score=result.get("score", 0.0),
                    status=metadata.get("status", ""),
                    priority=metadata.get("priority", ""),
                    created_at=metadata.get("created_at", ""),
                    summary=result.get("content", "")[:200]  # 처음 200자
                ))
            
            return similar_tickets
            
        except Exception as e:
            logger.error(f"유사 티켓 검색 실패: {e}")
            return []
    
    async def _search_kb_documents(self, request: InitializationRequest, ticket_data: Dict[str, Any]) -> List[DocumentInfo]:
        """지식베이스 문서 검색"""
        try:
            from core.database.vectordb import search_vector_db
            
            # 검색 쿼리 구성 (티켓과 동일)
            query_parts = []
            if ticket_data.get("subject"):
                query_parts.append(ticket_data["subject"])
            if ticket_data.get("description"):
                query_parts.append(ticket_data["description"][:500])
            
            query = " ".join(query_parts)
            
            # 벡터 검색 수행
            results = await search_vector_db(
                query=query,
                tenant_id=request.tenant_id,
                platform=request.platform,
                doc_types=["kb"],
                limit=request.top_k_kb
            )
            
            # DocumentInfo 객체로 변환
            documents = []
            for result in results:
                metadata = result.get("metadata", {})
                documents.append(DocumentInfo(
                    id=metadata.get("original_id", ""),
                    title=metadata.get("title", ""),
                    content=result.get("content", ""),
                    score=result.get("score", 0.0),
                    metadata=metadata
                ))
            
            return documents
            
        except Exception as e:
            logger.error(f"지식베이스 검색 실패: {e}")
            return []
    
    def _generate_context_id(self, request: InitializationRequest) -> str:
        """컨텍스트 ID 생성"""
        import uuid
        return f"{request.tenant_id}_{request.ticket_id}_{uuid.uuid4().hex[:8]}"
    
    def _build_metadata(self, request: InitializationRequest, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """메타데이터 구성"""
        return {
            "processing_time": datetime.now().isoformat(),
            "platform": request.platform,
            "tenant_id": request.tenant_id,
            "ui_language": request.ui_language,
            "ticket_status": ticket_data.get("status"),
            "ticket_priority": ticket_data.get("priority"),
            "retry_reason": request.retry_reason,
            "full_streaming_mode": self.enable_full_streaming
        }


# 전역 서비스 인스턴스
ticket_init_service = TicketInitializationService()