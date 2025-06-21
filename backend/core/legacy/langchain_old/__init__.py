"""
Langchain 모듈 - 90%+ 기존 코드 재활용 원칙

기존 llm_router.py의 핵심 로직을 langchain 구조로 분리하여 재구성
공식 아키텍처 지침에 따라 chains, prompts, callbacks로 체계적 분할
"""

from .llm_manager import LLMManager
from .models import LLMResponse, LLMProviderStats, LLMProvider
from .vector_store import VectorStoreManager  
from .embeddings import EmbeddingManager

# 체인 모듈
from .chains import (
    InitParallelChain,
    InitChain,
    SummarizationChain, 
    SearchChain,
    execute_init_parallel_chain
)

# 프롬프트 모듈
from .prompts import (
    PromptTemplates,
    prompt_templates,
    TICKET_SUMMARY_SYSTEM_PROMPT,
    ISSUE_SOLUTION_SYSTEM_PROMPT,
    DEFAULT_SYSTEM_PROMPT
)

# 콜백 모듈
from .callbacks import (
    MetricsCallback,
    AsyncStreamingCallback,
    create_metrics_callback,
    create_async_streaming_callback,
    get_default_callbacks,
    llm_requests_total,
    llm_request_duration_seconds,
    llm_tokens_used_total
)

__all__ = [
    # 핵심 매니저
    "LLMManager",
    "LLMResponse", 
    "LLMProviderStats",
    "VectorStoreManager",
    "EmbeddingManager",
    # 체인
    "InitParallelChain",
    "InitChain",
    "SummarizationChain",
    "SearchChain", 
    "execute_init_parallel_chain",
    # 프롬프트
    "PromptTemplates",
    "prompt_templates",
    "TICKET_SUMMARY_SYSTEM_PROMPT",
    "ISSUE_SOLUTION_SYSTEM_PROMPT", 
    "DEFAULT_SYSTEM_PROMPT",
    # 콜백
    "MetricsCallback",
    "AsyncStreamingCallback",
    "create_metrics_callback",
    "create_async_streaming_callback",
    "get_default_callbacks",
    "llm_requests_total",
    "llm_request_duration_seconds",
    "llm_tokens_used_total"
]
