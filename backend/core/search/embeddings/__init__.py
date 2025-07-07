"""
임베딩 모듈

Vector DB 단독 운영에 최적화된 임베딩 시스템입니다.

🌍 다국어 최적화 임베딩:
- 환경변수 USE_MULTILINGUAL_EMBEDDING으로 제어
- 기본값: OpenAI text-embedding-3-large (3072차원)  
- true: OpenAI text-embedding-3-large (3072차원, 다국어 최적화)
"""

import os
import logging

from .embedder import *
from .multilingual import *

logger = logging.getLogger(__name__)

USE_MULTILINGUAL = os.getenv("USE_MULTILINGUAL_EMBEDDING", "false").lower() == "true"

if USE_MULTILINGUAL:
    try:
        from .embedder import embed_documents_optimized
        
        def embed_documents(texts):
            """다국어 최적화 임베딩 (3072차원)"""
            if not texts:
                return []
            
            try:
                return embed_documents_optimized(texts, mode="multilingual")
            except Exception as e:
                logger.error(f"다국어 임베딩 실패, OpenAI 기본 모드로 폴백: {e}")
                from .embedder import embed_documents as openai_embed
                return openai_embed(texts)
        
        logger.info("🌍 다국어 최적화 임베딩 시스템 활성화 (3072차원)")
        
    except ImportError as e:
        logger.warning(f"다국어 임베딩 모듈 로드 실패, 기본 OpenAI 사용: {e}")
        from .embedder import embed_documents
else:
    from .embedder import embed_documents
    logger.info("📊 기본 OpenAI 임베딩 시스템 사용 (3072차원)")

__all__ = [
    'embed_documents',
    'embed_documents_optimized',
    'embed_documents_multilingual',
]
