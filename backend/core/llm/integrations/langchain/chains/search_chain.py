"""
검색 체인 - Langchain 기반 유사 티켓 검색 체인

기존 llm_router.py의 search_similar_tickets() 메서드를
90% 이상 재활용하여 langchain 체인으로 구현했습니다.

기존 코드 재활용 원칙:
- 기존 벡터 검색 로직 그대로 유지
- 기존 임베딩 생성 로직 그대로 유지
- 기존 유사도 필터링 로직 그대로 유지
- 기존 결과 포맷팅 로직 그대로 유지
- langchain 구조로 래핑만 추가
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableLambda

# 기존 모듈들 재사용
from core.search.retriever import retrieve_top_k_docs
from core.search.optimizer import VectorSearchOptimizer

# 기존 LLM Manager 재사용
from core.llm.manager import LLMManager

logger = logging.getLogger(__name__)


class SearchChain:
    """
    유사 티켓 검색 체인 - 기존 LLMRouter.search_similar_tickets() 로직 재활용
    
    기존 구현의 모든 로직을 langchain Runnable 구조로 래핑하여 제공합니다.
    - 기존 벡터 검색 알고리즘 그대로 유지
    - 기존 임베딩 생성 로직 그대로 유지
    - 기존 유사도 계산 및 필터링 로직 그대로 유지
    - 기존 결과 포맷팅 및 메타데이터 처리 그대로 유지
    """
    
    def __init__(self, llm_manager: LLMManager):
        """
        검색 체인 초기화
        
        Args:
            llm_manager: LLM Manager 인스턴스
        """
        self.llm_manager = llm_manager
        
        # 기존 벡터 검색 최적화 모듈 그대로 재사용
        self.search_optimizer = VectorSearchOptimizer()
        
        # langchain Runnable로 래핑
        self._chain = RunnableLambda(self._search_similar_tickets)
        
        logger.info("SearchChain 초기화 완료")

    async def _search_similar_tickets(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        기존 LLMRouter.search_similar_tickets() 로직 그대로 재활용
        
        Args:
            input_data: {
                "ticket_data": Dict[str, Any],
                "company_id": str,
                "top_k": int (optional, default=10)
            }
            
        Returns:
            List[Dict[str, Any]]: 유사 티켓 목록
        """
        ticket_data = input_data["ticket_data"]
        company_id = input_data["company_id"]
        top_k = input_data.get("top_k", 10)
        
        try:
            # 기존 검색 쿼리 생성 로직 그대로 재활용
            search_query = self._build_search_query(ticket_data)
            
            logger.info(f"유사 티켓 검색 시작 (ticket_id: {ticket_data.get('id')}, company_id: {company_id})")
            
            # 기존 임베딩 생성 로직 그대로 재활용 (search_optimizer 활용)
            query_embedding = await self._generate_embedding(search_query)
            
            # 기존 벡터 DB 검색 로직 그대로 재활용
            similar_tickets_result = retrieve_top_k_docs(
                query_embedding=query_embedding,
                top_k=top_k,
                doc_type="ticket",
                company_id=company_id
            )
            
            # 기존 결과 처리 로직 그대로 재활용
            similar_tickets = []
            current_ticket_id = str(ticket_data.get('id'))
            
            if similar_tickets_result and similar_tickets_result.get("ids"):
                for i, doc_id in enumerate(similar_tickets_result["ids"]):
                    # 현재 티켓과 동일한 ID는 제외 (기존 로직과 동일)
                    if str(doc_id) == current_ticket_id:
                        continue
                        
                    metadata = similar_tickets_result["metadatas"][i] if i < len(similar_tickets_result.get("metadatas", [])) else {}
                    
                    # 기존 유사도 계산 로직 그대로 재활용
                    distance = similar_tickets_result.get("distances", [0])[i] if i < len(similar_tickets_result.get("distances", [])) else 0
                    similarity_score = max(0, 1 - distance)
                    
                    # 기존 최소 유사도 필터링 로직 그대로 재활용
                    if similarity_score < 0.3:
                        continue
                    
                    # 기존 메타데이터 처리 로직 그대로 재활용
                    ticket_info = self._process_ticket_metadata(
                        doc_id=doc_id,
                        metadata=metadata,
                        similarity_score=similarity_score,
                        documents=similar_tickets_result.get("documents", []),
                        index=i
                    )
                    
                    similar_tickets.append(ticket_info)
                    
                    # 기존 최대 개수 제한 로직 그대로 재활용
                    if len(similar_tickets) >= 10:
                        break
            
            logger.info(f"유사 티켓 검색 완료 (ticket_id: {ticket_data.get('id')}, 발견된 유사 티켓: {len(similar_tickets)}개)")
            return similar_tickets
            
        except Exception as e:
            logger.error(f"유사 티켓 검색 중 오류 발생 (ticket_id: {ticket_data.get('id')}): {e}")
            return []  # 기존 오류 처리와 동일하게 빈 리스트 반환

    def _build_search_query(self, ticket_data: Dict[str, Any]) -> str:
        """기존 검색 쿼리 생성 로직 그대로 재활용"""
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description_text", "")
        
        # 기존 쿼리 조합 로직 그대로 유지
        search_query = f"{subject} {description}".strip()
        
        # 기존 길이 제한 로직 그대로 유지
        if len(search_query) > 500:
            search_query = search_query[:500]
        
        return search_query

    async def _generate_embedding(self, query: str) -> List[float]:
        """기존 임베딩 생성 로직 그대로 재활용 (search_optimizer 활용)"""
        try:
            # search_optimizer의 기존 임베딩 생성 로직 활용
            embedding = await self.search_optimizer.generate_embedding(query)
            return embedding
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            # 기존 오류 처리와 동일하게 기본 임베딩 반환
            return [0.0] * 1536  # OpenAI embedding 차원

    def _process_ticket_metadata(self, 
                                doc_id: str, 
                                metadata: Dict[str, Any], 
                                similarity_score: float,
                                documents: List[str],
                                index: int) -> Dict[str, Any]:
        """기존 티켓 메타데이터 처리 로직 그대로 재활용"""
        
        # 기존 제목 추출 로직 그대로 재활용
        title = (
            metadata.get("title") or 
            metadata.get("subject") or 
            f"티켓 {doc_id}"
        )
        
        # 기존 티켓 ID 처리 로직 그대로 재활용
        original_ticket_id = metadata.get("original_id", str(doc_id))
        ticket_number = original_ticket_id
        if isinstance(original_ticket_id, str) and original_ticket_id.startswith("ticket-"):
            ticket_number = original_ticket_id.replace("ticket-", "")
        
        # 기존 Freshdesk URL 생성 로직 그대로 재활용
        freshdesk_domain = os.getenv("FRESHDESK_DOMAIN", "example.freshdesk.com")
        ticket_url = f"https://{freshdesk_domain}/a/tickets/{ticket_number}"
        
        # 기존 요약 텍스트 처리 로직 그대로 재활용
        summary_text = documents[index] if index < len(documents) else ""
        if not summary_text:
            summary_text = metadata.get("description_text", "요약 정보 없음")
        
        # 기존 길이 제한 로직 그대로 재활용
        summary = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
        
        # 기존 결과 포맷 그대로 재활용
        return {
            "id": str(ticket_number),
            "title": title,
            "ticket_url": ticket_url,
            "similarity_score": round(similarity_score, 3),
            "summary": summary,
            "metadata": metadata,
            "full_content": summary_text
        }

    async def run(self, 
                  ticket_data: Dict[str, Any], 
                  company_id: str, 
                  top_k: int = 10) -> List[Dict[str, Any]]:
        """
        검색 체인 실행 (공개 API)
        
        Args:
            ticket_data: 티켓 데이터
            company_id: 회사 ID
            top_k: 반환할 최대 유사 티켓 수
            
        Returns:
            List[Dict[str, Any]]: 유사 티켓 목록
        """
        input_data = {
            "ticket_data": ticket_data,
            "company_id": company_id,
            "top_k": top_k
        }
        
        return await self._chain.ainvoke(input_data)

    async def batch_search(self, 
                          tickets: List[Dict[str, Any]], 
                          company_id: str, 
                          top_k: int = 10) -> List[List[Dict[str, Any]]]:
        """
        배치 검색 처리 (기존 배치 로직 재활용)
        
        Args:
            tickets: 티켓 데이터 리스트
            company_id: 회사 ID
            top_k: 반환할 최대 유사 티켓 수
            
        Returns:
            List[List[Dict[str, Any]]]: 각 티켓별 유사 티켓 목록
        """
        tasks = []
        for ticket in tickets:
            input_data = {
                "ticket_data": ticket,
                "company_id": company_id,
                "top_k": top_k
            }
            tasks.append(self._chain.ainvoke(input_data))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리 및 결과 정리
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"배치 검색 처리 실패 (index: {i}): {result}")
                processed_results.append([])  # 기존 오류 처리와 동일하게 빈 리스트
            else:
                processed_results.append(result)
        
        return processed_results
