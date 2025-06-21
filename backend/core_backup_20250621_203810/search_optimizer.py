"""
통합 벡터 검색 모듈 (LangChain-Qdrant 통합)

이 모듈은 KB와 티켓 검색을 통합하여 단일 벡터 검색으로 처리하고,
LangChain-Qdrant를 사용한 최적화된 검색을 제공합니다.
"""

import logging
import time
from typing import Any, Dict, Optional

# LangChain-Qdrant 통합 모듈 import
from .langchain_retriever import OptimizedVectorRetriever, create_optimized_retriever

logger = logging.getLogger(__name__)


class VectorSearchOptimizer:
    """벡터 검색 최적화 클래스 (LangChain-Qdrant 통합)"""
    
    def __init__(self, redis_url: Optional[str] = None, cache_ttl: int = 3600):
        """
        벡터 검색 최적화기 초기화
        
        Args:
            redis_url: Redis 연결 URL (사용되지 않음 - 리트리버 내부에서 관리)
            cache_ttl: 캐시 생존 시간 (사용되지 않음 - 리트리버 내부에서 관리)
        """
        # LangChain-Qdrant 최적화 검색기 초기화
        try:
            self.retriever = create_optimized_retriever()
            logger.info("LangChain-Qdrant 통합 검색기 초기화 완료")
        except Exception as e:
            logger.error(f"LangChain-Qdrant 검색기 초기화 실패: {e}")
            raise
        
        logger.info("VectorSearchOptimizer 초기화 완료 (LangChain-Qdrant 통합)")
    
    async def unified_vector_search(
        self,
        query_text: str,
        company_id: str,
        ticket_id: str = "",
        top_k_tickets: int = 5,  # 기본값을 5로 변경
        top_k_kb: int = 5        # 기본값을 5로 변경
    ) -> Dict[str, Any]:
        """
        LangChain-Qdrant 기반 통합 벡터 검색 (최적화됨)
        
        Args:
            query_text: 검색할 텍스트
            company_id: 회사 ID
            ticket_id: 현재 티켓 ID (제외용)
            top_k_tickets: 티켓 검색 결과 수
            top_k_kb: KB 검색 결과 수
            
        Returns:
            통합 검색 결과
        """
        start_time = time.time()
        
        try:
            # LangChain-Qdrant 리트리버를 사용한 통합 검색 (단일 호출)
            logger.info(f"LangChain-Qdrant 통합 벡터 검색 시작 (company_id: {company_id})")
            
            # 통합 검색 수행 (KB와 티켓을 병렬로 검색)
            search_result = await self.retriever.unified_search(
                query=query_text,
                company_id=company_id,
                ticket_id=ticket_id,
                top_k_tickets=top_k_tickets,
                top_k_kb=top_k_kb,
                use_cache=True
            )
            
            execution_time = time.time() - start_time
            
            logger.info(
                f"LangChain-Qdrant 통합 벡터 검색 완료 - KB: {len(search_result['kb_documents'])}개, "
                f"티켓: {len(search_result['similar_tickets'])}개, 실행시간: {execution_time:.2f}초"
            )
            
            # 결과 구조를 기존 API와 호환되도록 조정
            return {
                "similar_tickets": search_result.get("similar_tickets", []),
                "kb_documents": search_result.get("kb_documents", []),
                "cache_used": search_result.get("performance_metrics", {}).get("cache_hit", False),
                "performance_metrics": {
                    "total_time": execution_time,
                    "cache_hit": search_result.get("performance_metrics", {}).get("cache_hit", False),
                    "kb_count": len(search_result.get("kb_documents", [])),
                    "ticket_count": len(search_result.get("similar_tickets", [])),
                    "search_method": "langchain_qdrant_unified"
                }
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"LangChain-Qdrant 통합 벡터 검색 실패: {e}", exc_info=True)
            
            # 에러 시 빈 결과 반환
            return {
                "similar_tickets": [],
                "kb_documents": [],
                "cache_used": False,
                "performance_metrics": {
                    "total_time": execution_time,
                    "cache_hit": False,
                    "error": str(e),
                    "search_method": "langchain_qdrant_unified"
                }
            }


# 싱글톤 인스턴스
search_optimizer = None

def get_search_optimizer(redis_url: Optional[str] = None) -> VectorSearchOptimizer:
    """
    벡터 검색 최적화기 싱글톤 인스턴스 반환
    
    Args:
        redis_url: Redis 연결 URL (사용되지 않음 - 리트리버 내부에서 관리)
        
    Returns:
        VectorSearchOptimizer 인스턴스
    """
    global search_optimizer
    
    if search_optimizer is None:
        search_optimizer = VectorSearchOptimizer(redis_url=redis_url)
        
    return search_optimizer
