"""
하이브리드 검색 어댑터

기존 execute_init_sequential() 결과 구조와 호환되도록
HybridSearchManager 결과를 변환하는 어댑터 모듈
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class InitHybridAdapter:
    """
    init 엔드포인트용 하이브리드 검색 어댑터
    
    기존 execute_init_sequential() 호환성을 유지하면서
    HybridSearchManager의 고급 기능을 활용
    """
    
    def __init__(self):
        self.logger = logger
    
    async def execute_hybrid_init(
        self,
        hybrid_manager,
        llm_manager,
        ticket_data: Dict[str, Any],
        tenant_id: str,
        platform: str = "freshdesk",
        include_summary: bool = True,
        include_similar_tickets: bool = True, 
        include_kb_docs: bool = True,
        top_k_tickets: int = 3,
        top_k_kb: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        하이브리드 검색을 실행하고 기존 형식으로 반환
        
        Args:
            hybrid_manager: HybridSearchManager 인스턴스
            llm_manager: LLMManager 인스턴스 (요약용)
            ticket_data: 티켓 데이터
            기타: 기존 execute_init_sequential과 동일한 파라미터
            
        Returns:
            기존 execute_init_sequential()과 동일한 형식
        """
        import time
        start_time = time.time()
        
        try:
            results = {}
            
            # 1단계: 기존 요약 생성 유지 (사이드 이펙트 방지)
            if include_summary:
                summary_start = time.time()
                self.logger.info("1단계: 기존 요약 생성 시작")
                
                summary_result = await llm_manager._generate_summary_task({
                    "ticket_data": ticket_data
                })
                
                results["summary"] = summary_result
                summary_time = time.time() - summary_start
                self.logger.info(f"1단계 완료: 요약 생성 ({summary_time:.2f}초)")
            
            # 2단계: 하이브리드 검색 (기존 벡터 검색 대체)
            if include_similar_tickets or include_kb_docs:
                search_start = time.time()
                self.logger.info("2단계: 하이브리드 검색 시작")
                
                # 검색 쿼리 구성
                search_query = f"{ticket_data.get('subject', '')} {ticket_data.get('description_text', '')}"
                
                # 하이브리드 검색 실행
                hybrid_results = await hybrid_manager.hybrid_search(
                    query=search_query,
                    tenant_id=tenant_id,
                    platform=platform,
                    top_k=max(top_k_tickets, top_k_kb) if (include_similar_tickets and include_kb_docs) else (top_k_tickets if include_similar_tickets else top_k_kb),
                    doc_types=self._get_doc_types(include_similar_tickets, include_kb_docs),
                    enable_llm_enrichment=True,
                    rerank_results=True,
                    min_similarity=0.7,  # 품질 임계값
                )
                
                # 결과를 기존 형식으로 변환
                unified_search_result = self._convert_to_legacy_format(
                    hybrid_results, 
                    top_k_tickets,
                    top_k_kb,
                    include_similar_tickets,
                    include_kb_docs
                )
                
                results["unified_search"] = unified_search_result
                results["similar_tickets"] = unified_search_result.get("similar_tickets", [])
                results["kb_documents"] = unified_search_result.get("kb_documents", [])
                
                search_time = time.time() - search_start
                self.logger.info(f"2단계 완료: 하이브리드 검색 ({search_time:.2f}초)")
                
                # 하이브리드 검색 품질 로깅
                quality_score = hybrid_results.get("search_quality_score", 0.0)
                self.logger.info(f"하이브리드 검색 품질 점수: {quality_score:.3f}")
            
            # 총 실행시간 및 성공 플래그 (기존 구조 유지)
            total_time = time.time() - start_time
            results.update({
                "total_execution_time": total_time,
                "execution_type": "hybrid_sequential", 
                "success": True,
                "summary_time": results.get("summary", {}).get("execution_time", 0),
                "search_time": search_time if 'search_time' in locals() else 0
            })
            
            self.logger.info(f"하이브리드 순차 실행 완료 (총 {total_time:.2f}초)")
            return results
            
        except Exception as e:
            total_time = time.time() - start_time
            error_msg = f"하이브리드 순차 실행 실패: {str(e)}"
            self.logger.error(f"{error_msg} (실행시간: {total_time:.2f}초)")
            
            # 기존 에러 구조 유지 (사이드 이펙트 방지)
            return {
                "summary": {
                    "task_type": "summary",
                    "error": "하이브리드 실행 실패로 인한 요약 생성 불가",
                    "success": False
                },
                "unified_search": {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "하이브리드 실행 실패로 인한 검색 불가",
                    "success": False
                },
                "similar_tickets": [],
                "kb_documents": [],
                "total_execution_time": total_time,
                "execution_type": "hybrid_sequential",
                "success": False,
                "error": error_msg
            }
    
    def _get_doc_types(self, include_similar_tickets: bool, include_kb_docs: bool) -> List[str]:
        """문서 타입 리스트 생성"""
        doc_types = []
        if include_similar_tickets:
            doc_types.append("ticket")
        if include_kb_docs:
            doc_types.append("kb")
        return doc_types or ["ticket", "kb"]
    
    def _convert_to_legacy_format(
        self, 
        hybrid_results: Dict[str, Any],
        top_k_tickets: int,
        top_k_kb: int,
        include_similar_tickets: bool,
        include_kb_docs: bool
    ) -> Dict[str, Any]:
        """
        하이브리드 검색 결과를 기존 unified_search 형식으로 변환
        """
        # 하이브리드 검색 결과에서 문서 추출
        documents = hybrid_results.get("documents", [])
        metadatas = hybrid_results.get("metadatas", [])
        distances = hybrid_results.get("distances", [])
        
        # 문서 타입별로 분리
        similar_tickets = []
        kb_documents = []
        
        for i, (doc, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            doc_type = metadata.get("source_type", metadata.get("doc_type", "unknown"))
            
            # 기존 형식으로 변환
            doc_item = {
                "content": doc,
                "metadata": metadata,
                "distance": distance,
                "id": metadata.get("id", f"doc_{i}"),
                "source_type": doc_type
            }
            
            if doc_type == "ticket" and include_similar_tickets and len(similar_tickets) < top_k_tickets:
                similar_tickets.append(doc_item)
            elif doc_type == "kb" and include_kb_docs and len(kb_documents) < top_k_kb:
                kb_documents.append(doc_item)
        
        return {
            "task_type": "unified_search",
            "similar_tickets": similar_tickets,
            "kb_documents": kb_documents,
            "success": True,
            "cache_used": hybrid_results.get("cache_used", False),
            "search_quality_score": hybrid_results.get("search_quality_score", 0.0),
            "search_method": "hybrid",
            "total_results": len(documents),
            "performance_metrics": hybrid_results.get("performance_metrics", {})
        }
