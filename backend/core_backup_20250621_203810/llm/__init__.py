"""
LLM 모듈 - LLM 제공자 관리 및 라우팅

이 패키지는 다음 기능을 제공합니다:
- 다중 LLM 제공자 지원 (OpenAI, Anthropic, Google Gemini)
- 가중치 기반 제공자 선택 및 폴백 로직
- 성능 모니터링 및 통계 수집
- 벡터 검색 최적화
- 티켓 요약 생성
"""

from .clients import (
    LLMProvider,
    AnthropicProvider,
    OpenAIProvider,
    GeminiProvider,
    EmbeddingClient
)

from .models import (
    LLMResponse,
    EmbeddingResponse
)

from .router import (
    LLMRouter,
    LLMProviderWeights,
    LLMProviderSelector
)

from .utils import (
    VectorSearchOptimizer,
    PromptTemplate,
    calculate_embedding_similarity,
    optimize_text_for_embedding,
    truncate_text_to_token_limit
)

# 편의를 위한 주요 클래스들 노출
__all__ = [
    # 클라이언트 클래스
    "LLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "EmbeddingClient",
    
    # 모델 클래스
    "LLMResponse",
    "EmbeddingResponse",
    
    # 라우터 클래스
    "LLMRouter",
    "LLMProviderWeights",
    "LLMProviderSelector",
    
    # 유틸리티 함수
    "VectorSearchOptimizer",
    "PromptTemplate",
    "calculate_embedding_similarity",
    "optimize_text_for_embedding",
    "truncate_text_to_token_limit"
]

# 패키지 메타데이터
__version__ = "1.0.0"
__author__ = "We Do Soft Inc."
__description__ = "Modular LLM routing and management system"
