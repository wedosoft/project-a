"""
최적화된 벡터 검색 함수

병렬 검색, 배치 처리, 사전 필터링 등을 통해 검색 성능을 향상시킵니다.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


class OptimizedVectorSearch:
    """최적화된 벡터 검색 클래스"""
    
    def __init__(self, vector_db):
        """
        Args:
            vector_db: 벡터 데이터베이스 인스턴스
        """
        self.vector_db = vector_db
        self._search_cache = {}  # 메모리 캐시 (짧은 TTL)
        
    async def unified_search(
        self,
        query: str,
        tenant_id: str,
        platform: str = "freshdesk",
        limit: int = 10,
        score_threshold: float = 0.7,
        exclude_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        티켓과 KB 문서를 한 번에 검색합니다.
        
        Args:
            query: 검색 쿼리
            tenant_id: 테넌트 ID
            platform: 플랫폼
            limit: 각 타입별 최대 결과 수
            score_threshold: 최소 유사도 점수
            exclude_id: 제외할 티켓 ID
            
        Returns:
            (유사 티켓 리스트, KB 문서 리스트)
        """
        # 캐시 키 생성
        cache_key = self._generate_cache_key(query, tenant_id, platform, limit)
        
        # 메모리 캐시 확인 (5분 TTL)
        if cache_key in self._search_cache:
            cached_time, cached_result = self._search_cache[cache_key]
            if (datetime.now() - cached_time).seconds < 300:  # 5분
                logger.info("🎯 [메모리 캐시 히트] 통합 검색 결과")
                tickets, kb_docs = cached_result
                # exclude_id 필터링 적용
                if exclude_id:
                    tickets = [t for t in tickets if t.get('id') != exclude_id]
                return tickets, kb_docs
        
        # 병렬 검색 실행
        logger.info(f"🔍 [통합 검색] 티켓과 KB 문서 병렬 검색 시작")
        
        tickets_task = self._search_tickets(
            query, tenant_id, platform, limit, score_threshold, exclude_id
        )
        kb_docs_task = self._search_kb_docs(
            query, tenant_id, platform, limit, score_threshold
        )
        
        # 병렬 실행
        tickets, kb_docs = await asyncio.gather(tickets_task, kb_docs_task)
        
        # 캐시 저장
        self._search_cache[cache_key] = (datetime.now(), (tickets, kb_docs))
        
        # 캐시 크기 제한 (최대 100개)
        if len(self._search_cache) > 100:
            # 가장 오래된 항목 제거
            oldest_key = min(self._search_cache.keys(), 
                           key=lambda k: self._search_cache[k][0])
            del self._search_cache[oldest_key]
        
        logger.info(f"✅ [통합 검색] 완료 - 티켓: {len(tickets)}개, KB: {len(kb_docs)}개")
        
        return tickets, kb_docs
    
    async def _search_tickets(
        self,
        query: str,
        tenant_id: str,
        platform: str,
        limit: int,
        score_threshold: float,
        exclude_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """티켓 검색 (최적화)"""
        from core.search.embeddings import embed_documents
        
        # 쿼리 임베딩 생성
        query_embeddings = embed_documents([query])
        if not query_embeddings:
            return []
        
        query_embedding = query_embeddings[0]
        
        # 벡터 검색 실행
        results = await self._execute_search(
            query_embedding,
            tenant_id,
            platform,
            "ticket",
            limit,
            exclude_id
        )
        
        # 점수 필터링 및 후처리
        filtered_results = []
        for result in results:
            if result.get("score", 0) >= score_threshold:
                # 메타데이터 정리
                processed_result = self._process_ticket_result(result)
                filtered_results.append(processed_result)
        
        return filtered_results
    
    async def _search_kb_docs(
        self,
        query: str,
        tenant_id: str,
        platform: str,
        limit: int,
        score_threshold: float
    ) -> List[Dict[str, Any]]:
        """KB 문서 검색 (최적화)"""
        from core.search.embeddings import embed_documents
        
        # 쿼리 임베딩 생성
        query_embeddings = embed_documents([query])
        if not query_embeddings:
            return []
        
        query_embedding = query_embeddings[0]
        
        # 벡터 검색 실행
        results = await self._execute_search(
            query_embedding,
            tenant_id,
            platform,
            "article",
            limit,
            None
        )
        
        # 점수 필터링 및 후처리
        filtered_results = []
        for result in results:
            if result.get("score", 0) >= score_threshold:
                # 메타데이터 정리
                processed_result = self._process_kb_result(result)
                filtered_results.append(processed_result)
        
        return filtered_results
    
    async def _execute_search(
        self,
        query_embedding: List[float],
        tenant_id: str,
        platform: str,
        doc_type: str,
        limit: int,
        exclude_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """실제 벡터 검색 실행"""
        try:
            # 검색 파라미터 구성
            search_params = {
                "query_embedding": query_embedding,
                "top_k": limit,
                "tenant_id": tenant_id,
                "platform": platform,
                "doc_type": doc_type
            }
            
            # exclude_id가 있으면 필터에 추가
            if exclude_id and doc_type == "ticket":
                search_params["exclude_id"] = exclude_id
            
            # 벡터 검색 실행
            search_response = self.vector_db.search(**search_params)
            
            if isinstance(search_response, dict):
                return search_response.get("results", [])
            else:
                return search_response
                
        except Exception as e:
            logger.error(f"벡터 검색 실행 중 오류: {e}")
            return []
    
    def _process_ticket_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """티켓 검색 결과 후처리"""
        metadata = result.get("metadata", {})
        
        return {
            "id": result.get("original_id") or metadata.get("original_id"),
            "subject": result.get("subject") or metadata.get("subject", ""),
            "content": result.get("content", ""),
            "score": result.get("score", 0.0),
            "priority": result.get("priority", metadata.get("priority", 1)),
            "status": result.get("status", metadata.get("status", 2)),
            "created_at": result.get("created_at", metadata.get("created_at")),
            "has_attachments": result.get("has_attachments", False),
            "attachment_count": result.get("attachment_count", 0),
            "metadata": {
                k: v for k, v in metadata.items() 
                if k not in ["source", "content", "embedding"]
            }
        }
    
    def _process_kb_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """KB 문서 검색 결과 후처리"""
        metadata = result.get("metadata", {})
        
        return {
            "id": result.get("original_id") or metadata.get("original_id"),
            "title": result.get("title") or metadata.get("title", ""),
            "content": result.get("content", ""),
            "score": result.get("score", 0.0),
            "url": metadata.get("url", ""),
            "created_at": result.get("created_at", metadata.get("created_at")),
            "updated_at": result.get("updated_at", metadata.get("updated_at")),
            "metadata": {
                k: v for k, v in metadata.items() 
                if k not in ["source", "content", "embedding"]
            }
        }
    
    def _generate_cache_key(
        self,
        query: str,
        tenant_id: str,
        platform: str,
        limit: int
    ) -> str:
        """캐시 키 생성"""
        key_data = f"{query[:100]}:{tenant_id}:{platform}:{limit}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def batch_search(
        self,
        queries: List[str],
        tenant_id: str,
        platform: str = "freshdesk",
        doc_type: str = "ticket",
        limit_per_query: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        여러 쿼리를 배치로 검색합니다.
        
        Args:
            queries: 검색 쿼리 리스트
            tenant_id: 테넌트 ID
            platform: 플랫폼
            doc_type: 문서 타입
            limit_per_query: 쿼리당 최대 결과 수
            
        Returns:
            {쿼리: 검색결과리스트} 형태의 딕셔너리
        """
        if not queries:
            return {}
        
        logger.info(f"🎯 [배치 검색] {len(queries)}개 쿼리 배치 검색 시작")
        
        # 임베딩 배치 생성
        from core.search.embeddings import embed_documents
        query_embeddings = embed_documents(queries)
        
        if len(query_embeddings) != len(queries):
            logger.error("임베딩 생성 실패")
            return {query: [] for query in queries}
        
        # 병렬 검색 작업 생성
        search_tasks = []
        for query, embedding in zip(queries, query_embeddings):
            task = self._execute_search(
                embedding,
                tenant_id,
                platform,
                doc_type,
                limit_per_query,
                None
            )
            search_tasks.append(task)
        
        # 병렬 실행
        results = await asyncio.gather(*search_tasks)
        
        # 결과 매핑
        query_results = {}
        for query, result_list in zip(queries, results):
            if doc_type == "ticket":
                processed = [self._process_ticket_result(r) for r in result_list]
            else:
                processed = [self._process_kb_result(r) for r in result_list]
            query_results[query] = processed
        
        logger.info(f"✅ [배치 검색] 완료")
        
        return query_results