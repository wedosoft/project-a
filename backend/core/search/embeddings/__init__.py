"""
임베딩 모듈

텍스트 임베딩 생성 및 GPU 가속 임베딩을 관리합니다.

하이브리드 임베딩:
- GPU 우선 사용 (sentence-transformers)
- OpenAI fallback 지원
- 자동 환경 감지 및 최적화
"""

from .embedder import *
from .embedder_gpu import *
from .hybrid import *

# 하이브리드 임베딩을 기본으로 설정
from .hybrid import embed_documents_hybrid as embed_documents
from .hybrid import log_embedding_status, get_embedding_method

__all__ = [
    'embed_documents',
    'embed_documents_hybrid', 
    'log_embedding_status',
    'get_embedding_method',
    'GPU_AVAILABLE',
    'DEVICE'
]
