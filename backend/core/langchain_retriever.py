"""
LangChain-Qdrant 통합 벡터 검색 모듈

이 모듈은 LangChain과 Qdrant를 직접 통합하여 더 효율적인 벡터 검색을 제공합니다.
기존 retriever.py의 성능 문제를 해결하고 네이티브 필터링을 지원합니다.
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as redis
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from qdrant_client import models

logger = logging.getLogger(__name__)


class OptimizedVectorRetriever:
    """
    LangChain-Qdrant 통합 최적화된 벡터 검색기
    """
    
    def __init__(
        self,
        qdrant_url: str,
        qdrant_api_key: str,
        openai_api_key: str,
        collection_name: str = "documents",
        redis_url: Optional[str] = None,
        cache_ttl: int = 3600
    ):
        """
        벡터 검색기 초기화
        
        Args:
            qdrant_url: Qdrant 클러스터 URL
            qdrant_api_key: Qdrant API 키
            openai_api_key: OpenAI API 키
            collection_name: 벡터 컬렉션 이름
            redis_url: Redis URL (캐싱용)
            cache_ttl: 캐시 TTL (초)
        """
        self.collection_name = collection_name
        self.cache_ttl = cache_ttl
        
        # Qdrant 클라이언트 초기화
        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        
        # OpenAI 임베딩 초기화
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=openai_api_key,
            model="text-embedding-3-small"
        )
        
        # LangChain-Qdrant 벡터스토어 초기화
        self.vector_store = QdrantVectorStore(
            client=self.qdrant_client,
            collection_name=collection_name,
            embedding=self.embeddings  # 'embeddings' -> 'embedding' (단수형)
        )
        
        # Redis 캐시 초기화 (선택사항)
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                logger.info(f"Redis 캐싱 활성화: {redis_url}")
            except Exception as e:
                logger.warning(f"Redis 연결 실패, 캐싱 비활성화: {e}")
        
        logger.info(f"OptimizedVectorRetriever 초기화 완료 (collection: {collection_name})")
    
    def _create_filter(self, company_id: str, doc_type: Optional[str] = None, status: Optional[int] = None) -> Filter:
        """
        Qdrant 필터 생성
        
        Args:
            company_id: 회사 ID
            doc_type: 문서 타입 ("ticket" 또는 "kb")
            status: KB 문서 상태 (2: published)
            
        Returns:
            Qdrant 필터 객체
        """
        conditions = [
            FieldCondition(key="company_id", match=MatchValue(value=company_id))
        ]
        
        if doc_type:
            conditions.append(
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
            )
        
        # KB 문서의 경우 status 필터 추가 (published 상태만)
        if status is not None:
            conditions.append(
                FieldCondition(key="status", match=MatchValue(value=status))
            )
        
        return Filter(must=conditions)
    
    async def _get_cache_key(self, query: str, company_id: str, doc_type: Optional[str], top_k: int) -> str:
        """캐시 키 생성"""
        import hashlib
        cache_data = f"{query}:{company_id}:{doc_type}:{top_k}"
        return f"vector_search:{hashlib.md5(cache_data.encode()).hexdigest()}"
    
    async def _get_cached_result(self, cache_key: str) -> Optional[List[Document]]:
        """캐시에서 결과 조회"""
        if not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                import json
                data = json.loads(cached_data)
                documents = [Document(**doc) for doc in data]
                logger.info(f"캐시 히트: {cache_key}")
                return documents
        except Exception as e:
            logger.warning(f"캐시 조회 실패: {e}")
        
        return None
    
    async def _set_cached_result(self, cache_key: str, documents: List[Document]) -> None:
        """결과를 캐시에 저장"""
        if not self.redis_client:
            return
        
        try:
            import json
            data = [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in documents]
            await self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data, default=str)
            )
            logger.info(f"캐시 저장 완료: {cache_key}")
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")
    
    async def similarity_search_with_filter(
        self,
        query: str,
        company_id: str,
        doc_type: Optional[str] = None,
        top_k: int = 5,  # 기본값을 5로 변경
        use_cache: bool = True
    ) -> List[Document]:
        """
        필터링된 유사도 검색 수행
        
        Args:
            query: 검색 쿼리
            company_id: 회사 ID
            doc_type: 문서 타입 ("ticket" 또는 "kb")
            top_k: 반환할 결과 수
            use_cache: 캐시 사용 여부
            
        Returns:
            검색된 문서 리스트
        """
        start_time = time.time()
        
        # 캐시 확인
        cache_key = await self._get_cache_key(query, company_id, doc_type, top_k)
        if use_cache:
            cached_result = await self._get_cached_result(cache_key)
            if cached_result:
                logger.info(f"캐시된 검색 결과 반환 (company_id: {company_id}, doc_type: {doc_type})")
                return cached_result
        
        # 필터 생성
        filter_condition = self._create_filter(company_id, doc_type)
        
        try:
            logger.info(f"벡터 검색 시작 (company_id: {company_id}, doc_type: {doc_type}, top_k: {top_k})")
            
            # LangChain-Qdrant 통합 검색 수행 (비동기)
            documents = await asyncio.to_thread(
                self.vector_store.similarity_search,
                query=query,
                k=top_k,
                filter=filter_condition
            )
            
            search_time = time.time() - start_time
            logger.info(
                f"벡터 검색 완료 - {len(documents)}개 결과, "
                f"실행시간: {search_time:.2f}초 (company_id: {company_id}, doc_type: {doc_type})"
            )
            
            # 캐시에 저장
            if use_cache:
                await self._set_cached_result(cache_key, documents)
            
            return documents
            
        except Exception as e:
            search_time = time.time() - start_time
            logger.error(f"벡터 검색 실패: {e} (실행시간: {search_time:.2f}초)")
            return []
    
    async def unified_search(
        self,
        query: str,
        company_id: str,
        ticket_id: str = "",
        top_k_tickets: int = 5,
        top_k_kb: int = 5,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        최적화된 통합 벡터 검색 (티켓 + KB 별도 쿼리로 정확한 필터링)
        
        Args:
            query: 검색 쿼리
            company_id: 회사 ID
            ticket_id: 현재 티켓 ID (제외용)
            top_k_tickets: 티켓 검색 결과 수
            top_k_kb: KB 검색 결과 수
            use_cache: 캐시 사용 여부
            
        Returns:
            통합 검색 결과
        """
        start_time = time.time()
        
        logger.info(f"최적화된 통합 벡터 검색 시작 (company_id: {company_id}) - 티켓/KB 개별 필터링")
        
        # 캐시 키 생성 (통합 검색용)
        cache_key = f"unified_search_v2:{hashlib.md5(f'{query}_{company_id}_{top_k_tickets}_{top_k_kb}'.encode()).hexdigest()}"
        
        # 캐시 확인
        if use_cache and self.redis_client:
            try:
                cached_result = await self.redis_client.get(cache_key)
                if cached_result:
                    import json
                    result = json.loads(cached_result)
                    logger.info(f"통합 검색 캐시 히트: {cache_key}")
                    return result
            except Exception as e:
                logger.warning(f"캐시 조회 실패: {e}")
        
        try:
            # 1. 티켓 검색 (company_id + doc_type=ticket + 현재 티켓 제외)
            ticket_filter = self._create_filter(company_id=company_id, doc_type="ticket")
            
            # 현재 티켓 ID 제외 필터 추가 (original_id 필드 사용)
            if ticket_id:
                ticket_filter = models.Filter(
                    must=[
                        ticket_filter,
                        models.Filter(
                            must_not=[
                                models.FieldCondition(
                                    key="original_id",
                                    match=models.MatchValue(value=str(ticket_id))
                                )
                            ]
                        )
                    ]
                )
            
            # 임베딩 한 번만 생성
            logger.info(f"단일 임베딩 생성 시작")
            query_embedding = await asyncio.to_thread(
                self.embeddings.embed_query, query
            )
            
            # 병렬 검색 실행 (임베딩 재사용)
            logger.info(f"병렬 검색 시작 - 티켓: {top_k_tickets}, KB: {top_k_kb}")
            
            # KB 필터 생성
            kb_filter = self._create_filter(company_id=company_id, doc_type="kb", status=2)
            
            # 병렬 실행
            ticket_task = asyncio.to_thread(
                self._search_with_embedding,
                query_embedding,
                ticket_filter,
                top_k_tickets
            )
            
            kb_task = asyncio.to_thread(
                self._search_with_embedding,
                query_embedding, 
                kb_filter,
                top_k_kb
            )
            
            ticket_results, kb_results = await asyncio.gather(ticket_task, kb_task)
            
            logger.info(f"개별 검색 완료 - 티켓: {len(ticket_results)}개, KB: {len(kb_results)}개")
            
            # 3. 결과 변환 (유사도 점수 추가)
            ticket_docs = []
            for doc, score in ticket_results:
                doc.metadata["similarity_score"] = round(score, 3)
                ticket_docs.append(doc)
            
            kb_docs = []
            for doc, score in kb_results:
                doc.metadata["similarity_score"] = round(score, 3)
                kb_docs.append(doc)
            
            total_time = time.time() - start_time
            
            # 캐시 저장
            if use_cache and self.redis_client:
                try:
                    result_to_cache = {
                        "kb_documents": self._format_kb_results(kb_docs),
                        "similar_tickets": self._format_ticket_results(ticket_docs),
                        "performance_metrics": {
                            "total_time": total_time,
                            "kb_count": len(kb_docs),
                            "ticket_count": len(ticket_docs),
                            "cache_hit": False,
                            "search_method": "optimized_separate_queries"
                        }
                    }
                    
                    import json
                    await self.redis_client.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps(result_to_cache, ensure_ascii=False)
                    )
                    logger.info(f"최적화된 통합 검색 결과 캐시 저장: {cache_key}")
                    
                    return result_to_cache
                    
                except Exception as e:
                    logger.warning(f"캐시 저장 실패: {e}")
            
            logger.info(
                f"최적화된 통합 벡터 검색 완료 (개별 필터링) - KB: {len(kb_docs)}개, 티켓: {len(ticket_docs)}개, "
                f"실행시간: {total_time:.2f}초"
            )
            
            return {
                "kb_documents": self._format_kb_results(kb_docs),
                "similar_tickets": self._format_ticket_results(ticket_docs),
                "performance_metrics": {
                    "total_time": total_time,
                    "kb_count": len(kb_docs),
                    "ticket_count": len(ticket_docs),
                    "cache_hit": False,
                    "search_method": "optimized_separate_queries"
                }
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"최적화된 통합 벡터 검색 실패: {e} (실행시간: {total_time:.2f}초)", exc_info=True)
            
            return {
                "kb_documents": [],
                "similar_tickets": [],
                "performance_metrics": {
                    "total_time": total_time,
                    "kb_count": 0,
                    "ticket_count": 0,
                    "cache_hit": False,
                    "error": str(e)
                }
            }
    
    def _format_kb_results(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """KB 검색 결과 포맷팅"""
        results = []
        for doc in documents:
            metadata = doc.metadata
            results.append({
                "id": metadata.get("kb_id", ""),
                "title": metadata.get("title", "제목 없음"),
                "description": metadata.get("description", ""),
                "category": metadata.get("category", "일반"),
                "tags": metadata.get("tags", []),
                "score": metadata.get("score", 0.0),
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "url": metadata.get("url", ""),
                "updated_at": metadata.get("updated_at", ""),
                "status": metadata.get("status", 1)
            })
        return results
    
    def _format_ticket_results(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """티켓 검색 결과 포맷팅"""
        results = []
        for doc in documents:
            metadata = doc.metadata
            results.append({
                "id": metadata.get("ticket_id", ""),
                "title": metadata.get("subject", "제목 없음"),
                "description": metadata.get("description", ""),
                "status": metadata.get("status_name", "알 수 없음"),
                "priority": metadata.get("priority_name", "보통"),
                "created_at": metadata.get("created_at", ""),
                "updated_at": metadata.get("updated_at", ""),
                "requester_name": metadata.get("requester_name", ""),
                "score": metadata.get("score", 0.0),
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "tags": metadata.get("tags", [])
            })
        return results
    
    def _search_with_embedding(
        self,
        query_embedding: List[float],
        filter_condition: Optional[models.Filter],
        k: int
    ) -> List[Tuple[Document, float]]:
        """
        이미 생성된 임베딩으로 벡터 검색 수행
        
        Args:
            query_embedding: 쿼리 임베딩 벡터
            filter_condition: 필터 조건
            k: 반환할 결과 수
            
        Returns:
            (Document, score) 튜플 리스트
        """
        # Qdrant 클라이언트로 직접 검색
        try:
            logger.info(f"qdrant_client 타입: {type(self.qdrant_client)}")
            logger.info(f"qdrant_client 속성: {dir(self.qdrant_client)}")
            search_results = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=filter_condition,
                limit=k,
                with_payload=True
            )
        except Exception as e:
            logger.error(f"Qdrant 검색 실패: {e}")
            logger.error(f"self.qdrant_client: {self.qdrant_client}")
            raise
        
        # Document 객체로 변환
        docs_with_scores = []
        for point in search_results.points:
            # payload에서 text 추출
            content = point.payload.get("text", "")
            metadata = {k: v for k, v in point.payload.items() if k != "text"}
            
            doc = Document(page_content=content, metadata=metadata)
            score = point.score if hasattr(point, 'score') else 0.0
            docs_with_scores.append((doc, score))
            
        return docs_with_scores


def create_optimized_retriever() -> OptimizedVectorRetriever:
    """
    환경변수를 기반으로 최적화된 벡터 검색기 생성
    
    Returns:
        초기화된 OptimizedVectorRetriever 인스턴스
    """
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    if not all([qdrant_url, qdrant_api_key, openai_api_key]):
        raise ValueError("필수 환경변수가 설정되지 않음: QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY")
    
    return OptimizedVectorRetriever(
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        openai_api_key=openai_api_key,
        redis_url=redis_url,
        cache_ttl=1800  # 30분으로 단축하여 최신 데이터 반영
    )
