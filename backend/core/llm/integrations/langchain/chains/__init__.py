"""
Langchain 체인 구현 모듈

기존 LLM Router의 체인 로직들을 langchain 구조로 래핑한 모듈들입니다.
90% 이상 기존 코드를 재활용하며 성능 최적화를 위해 분할되었습니다.
"""

"""
Langchain 체인 구현 모듈

기존 LLM Router의 체인 로직들을 langchain 구조로 래핑한 모듈들입니다.
90% 이상 기존 코드를 재활용하며 성능 최적화를 위해 분할되었습니다.
"""

from .summarization import SummarizationChain
from .init_chain import InitParallelChain
from .search_chain import SearchChain

# 호환성을 위한 별칭
InitChain = InitParallelChain

# 편의 함수 정의 (기존 코드와 호환성 유지)
async def execute_init_parallel_chain(
    ticket_data: dict,
    qdrant_client,
    company_id: str,
    llm_router=None,
    **kwargs
):
    """기존 함수 시그니처와 호환성을 위한 래퍼 함수"""
    if llm_router is None:
        from core.llm.manager import LLMManager
        llm_router = LLMManager()
    
    chain = InitParallelChain(llm_router=llm_router)
    return await chain.execute_init_parallel_chain(
        ticket_data=ticket_data,
        qdrant_client=qdrant_client,
        company_id=company_id,
        **kwargs
    )

__all__ = [
    "SummarizationChain",
    "InitParallelChain", 
    "InitChain",  # 호환성 별칭
    "SearchChain",
    "execute_init_parallel_chain"  # 편의 함수
]
