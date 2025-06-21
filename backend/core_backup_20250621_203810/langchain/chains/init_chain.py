"""
초기화 병렬 체인 모듈

이 모듈은 /init 엔드포인트의 핵심 로직을 langchain 구조로 래핑합니다.
기존 LLMRouter의 execute_init_parallel_chain() 로직을 90%+ 재활용하여
티켓 요약, 유사 티켓 검색, KB 문서 검색을 병렬로 처리합니다.
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional

from langchain.schema.runnable import Runnable, RunnableParallel, RunnableLambda
from langchain.schema import BaseMessage

logger = logging.getLogger(__name__)


class InitParallelChain:
    """
    초기화 병렬 체인 클래스
    
    기존 LLMRouter의 execute_init_parallel_chain() 로직을 90%+ 재활용하여
    langchain Runnable 구조로 래핑한 클래스입니다.
    
    주요 기능:
    - 티켓 요약 생성 (병렬)
    - 유사 티켓 + KB 문서 통합 검색 (병렬)
    - 성능 최적화된 벡터 검색
    """
    
    def __init__(self, llm_router=None):
        """
        초기화 병렬 체인 생성
        
        Args:
            llm_router: 기존 LLMRouter 인스턴스 (90%+ 코드 재활용용)
        """
        self.llm_router = llm_router
        self._temp_top_k_tickets = 5  # 기본값
        self._temp_top_k_kb = 5  # 기본값
        
    async def execute_init_parallel_chain(
        self,
        ticket_data: Dict[str, Any],
        qdrant_client: Any,
        company_id: str,
        include_summary: bool = True,
        include_similar_tickets: bool = True,
        include_kb_docs: bool = True,
        top_k_tickets: int = 5,  # 사용자 설정 유사 티켓 수 (1-5)
        top_k_kb: int = 5,       # 사용자 설정 KB 문서 수 (1-5)
    ) -> Dict[str, Any]:
        """
        초기화 병렬 체인을 실행하고 결과를 반환합니다.
        
        기존 LLMRouter.execute_init_parallel_chain() 로직을 90%+ 재활용
        
        Args:
            ticket_data: Freshdesk 티켓 데이터
            qdrant_client: Qdrant 벡터 DB 클라이언트
            company_id: 회사 식별자
            include_summary: 요약 생성 여부
            include_similar_tickets: 유사 티켓 검색 여부
            include_kb_docs: KB 문서 검색 여부
            top_k_tickets: 사용자 설정 유사 티켓 수
            top_k_kb: 사용자 설정 KB 문서 수
            
        Returns:
            병렬 작업 실행 결과 딕셔너리
        """
        start_time = time.time()
        logger.info(f"Langchain InitParallelChain 체인 실행 시작 (ticket_id: {ticket_data.get('id')})")
        
        try:
            # RunnableParallel 체인 생성
            parallel_chain = self.create_init_parallel_chain(
                ticket_data,
                qdrant_client,
                company_id,
                include_summary=include_summary,
                include_similar_tickets=include_similar_tickets,
                include_kb_docs=include_kb_docs,
                top_k_tickets=top_k_tickets,
                top_k_kb=top_k_kb,
            )
            
            # 체인 실행을 위한 입력 데이터 준비
            chain_inputs = {
                "ticket_data": ticket_data,
                "qdrant_client": qdrant_client,
                "company_id": company_id,
                "platform": "freshdesk",  # 기본값
                "top_k_tickets": top_k_tickets,
                "top_k_kb": top_k_kb
            }
            
            # 체인 실행
            results = await parallel_chain.ainvoke(chain_inputs)
            
            total_execution_time = time.time() - start_time
            logger.info(f"Langchain InitParallelChain 체인 실행 완료 (ticket_id: {ticket_data.get('id')}, 총 실행시간: {total_execution_time:.2f}초)")
            
            # 결과 구조화 (기존 로직 재활용)
            final_result = {
                "summary": results.get("summary"),
                "unified_search": results.get("unified_search", {}),  # unified_search 키 유지
                "total_execution_time": total_execution_time,
                "chain_type": "langchain_init_parallel_chain"
            }
            
            # 하위 호환성을 위해 개별 키도 추가
            unified_search = results.get("unified_search", {})
            if unified_search:
                final_result["similar_tickets"] = unified_search.get("similar_tickets")
                final_result["kb_documents"] = unified_search.get("kb_documents")
            else:
                final_result["similar_tickets"] = results.get("similar_tickets")
                final_result["kb_documents"] = results.get("kb_documents")
            
            return final_result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Langchain InitParallelChain 체인 실행 실패: {str(e)}"
            logger.error(f"{error_msg} (실행시간: {execution_time:.2f}초)")
            
            # 에러 발생 시 기본 구조 반환 (기존 로직 재활용)
            return {
                "summary": {
                    "task_type": "summary",
                    "error": "체인 실행 실패로 인한 요약 생성 불가",
                    "success": False
                },
                "unified_search": {
                    "task_type": "unified_search",
                    "similar_tickets": [],
                    "kb_documents": [],
                    "error": "체인 실행 실패로 인한 검색 불가",
                    "success": False
                },
                "similar_tickets": {
                    "task_type": "similar_tickets", 
                    "error": "체인 실행 실패로 인한 유사 티켓 검색 불가",
                    "success": False
                },
                "kb_documents": {
                    "task_type": "kb_documents",
                    "error": "체인 실행 실패로 인한 지식베이스 검색 불가", 
                    "success": False
                },
                "total_execution_time": execution_time,
                "chain_type": "langchain_init_parallel_chain",
                "chain_error": error_msg
            }

    def create_init_parallel_chain(
        self,
        ticket_data: Dict[str, Any],
        qdrant_client: Any,
        company_id: str,
        include_summary: bool = True,
        include_similar_tickets: bool = True,
        include_kb_docs: bool = True,
        top_k_tickets: int = 5,
        top_k_kb: int = 5,
    ) -> RunnableParallel:
        """
        초기화 프로세스를 위한 Langchain RunnableParallel 체인을 생성합니다.
        
        기존 LLMRouter.create_init_parallel_chain() 로직을 90%+ 재활용
        
        최적화된 버전: 벡터 검색을 통합하여 성능을 향상시킵니다.
        1. 티켓 요약 생성 (max_tokens 축소로 속도 향상)
        2. 통합 벡터 검색 (유사 티켓 + KB 문서를 한 번에 처리)
        
        성능 최적화 포인트:
        - 임베딩 생성 1회로 단축 (기존 2회에서)
        - LLM 분석 제거로 유사 티켓 처리 속도 대폭 향상
        - 직접 벡터 검색으로 외부 의존성 제거
        
        Args:
            ticket_data: Freshdesk 티켓 데이터
            qdrant_client: Qdrant 벡터 DB 클라이언트
            company_id: 회사 식별자
            include_summary: 요약 생성 여부
            include_similar_tickets: 유사 티켓 검색 여부
            include_kb_docs: KB 문서 검색 여부
            top_k_tickets: 유사 티켓 수
            top_k_kb: KB 문서 수
            
        Returns:
            RunnableParallel 체인 객체
        """
        
        # top_k 값들을 임시 인스턴스 변수로 설정 (RunnableLambda에서 사용)
        self._temp_top_k_tickets = top_k_tickets
        self._temp_top_k_kb = top_k_kb
        
        tasks = {}
        
        if include_summary:
            tasks["summary"] = RunnableLambda(self._generate_summary_task)
        
        # 유사 티켓이나 KB 문서 중 하나라도 필요하면 통합 검색 실행
        if include_similar_tickets or include_kb_docs:
            tasks["unified_search"] = RunnableLambda(self._unified_search_task)

        parallel_chain = RunnableParallel(tasks)
        
        logger.info(f"최적화된 Langchain InitParallelChain 체인 생성 완료 (ticket_id: {ticket_data.get('id')}, "
                   f"태스크 수: {len(tasks)}개)")
        return parallel_chain

    async def _generate_summary_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        티켓 요약 생성 태스크
        
        기존 LLMRouter._generate_summary_task() 로직을 90%+ 재활용
        """
        if not self.llm_router:
            logger.error("LLMRouter 인스턴스가 없어 요약 생성을 건너뜁니다.")
            return {
                "task_type": "summary",
                "error": "LLMRouter 인스턴스 없음",
                "success": False
            }
            
        try:
            # 기존 LLMRouter의 _generate_summary_task 메서드 재활용
            return await self.llm_router._generate_summary_task(inputs)
        except Exception as e:
            logger.error(f"요약 생성 태스크 실행 실패: {e}")
            return {
                "task_type": "summary",
                "error": f"요약 생성 실패: {str(e)}",
                "success": False
            }

    async def _unified_search_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        통합 벡터 검색 태스크 - KB 문서와 유사 티켓을 한 번에 검색
        
        기존 LLMRouter._unified_search_task() 로직을 90%+ 재활용
        
        최적화 포인트:
        1. 벡터 검색 횟수를 2회에서 1회로 줄임 (임베딩 생성 1회로 단축)
        2. 직접 벡터 검색으로 SearchOptimizer 의존성 제거하여 단순화
        3. LLM 분석 생략으로 응답 속도 대폭 향상 (9초+ -> 1초 목표)
        """
        if not self.llm_router:
            logger.error("LLMRouter 인스턴스가 없어 통합 검색을 건너뜁니다.")
            return {
                "task_type": "unified_search",
                "similar_tickets": [],
                "kb_documents": [],
                "error": "LLMRouter 인스턴스 없음",
                "success": False
            }
            
        try:
            # 기존 LLMRouter의 _unified_search_task 메서드 재활용
            return await self.llm_router._unified_search_task(inputs)
        except Exception as e:
            logger.error(f"통합 검색 태스크 실행 실패: {e}")
            return {
                "task_type": "unified_search",
                "similar_tickets": [],
                "kb_documents": [],
                "error": f"통합 검색 실패: {str(e)}",
                "success": False
            }

    def _create_empty_search_result(self, execution_time: float) -> Dict[str, Any]:
        """
        빈 검색 결과 생성 (기존 LLMRouter 로직 재활용)
        """
        if self.llm_router and hasattr(self.llm_router, '_create_empty_search_result'):
            return self.llm_router._create_empty_search_result(execution_time)
        
        # fallback 구현
        return {
            "task_type": "unified_search",
            "similar_tickets": [],
            "kb_documents": [],
            "execution_time": execution_time,
            "success": True,
            "cache_used": False
        }


# 편의 함수들 (기존 패턴 유지)
async def create_init_chain(llm_router=None) -> InitParallelChain:
    """
    InitParallelChain 인스턴스 생성 편의 함수
    
    Args:
        llm_router: 기존 LLMRouter 인스턴스
        
    Returns:
        InitParallelChain 인스턴스
    """
    return InitParallelChain(llm_router=llm_router)


async def execute_init_parallel_processing(
    ticket_data: Dict[str, Any],
    qdrant_client: Any,
    company_id: str,
    llm_router=None,
    **kwargs
) -> Dict[str, Any]:
    """
    초기화 병렬 처리 실행 편의 함수
    
    Args:
        ticket_data: 티켓 데이터
        qdrant_client: Qdrant 클라이언트
        company_id: 회사 ID
        llm_router: LLM Router 인스턴스
        **kwargs: 추가 매개변수
        
    Returns:
        처리 결과
    """
    init_chain = await create_init_chain(llm_router=llm_router)
    return await init_chain.execute_init_parallel_chain(
        ticket_data=ticket_data,
        qdrant_client=qdrant_client,
        company_id=company_id,
        **kwargs
    )
