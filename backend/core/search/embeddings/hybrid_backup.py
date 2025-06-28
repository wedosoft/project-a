"""
하이브리드 임베딩 모듈

GPU(sentence-transformers) 우선 사용하고, 실패 시 OpenAI로 fallback하는
스마트한 임베딩 파이프라인을 제공합니다.

Features:
- GPU 우선 임베딩 (sentence-transformers)
- OpenAI fallback (네트워크/API 키 필요)
- 자동 환경 감지 및 최적 방법 선택
- 통합된 임베딩 API 제공
"""
import logging
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import numpy as np

# 환경변수 로드
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent
dotenv_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger(__name__)

# 임베딩 모듈들 import
from .embedder import embed_documents as openai_embed_documents
from .embedder_gpu import (
    setup_gpu_embedder, 
    embed_documents_gpu, 
    GPU_AVAILABLE,
    DEVICE
)

# 벡터 차원 설정
OPENAI_DIMENSION = 1536  # text-embedding-3-small
SENTENCE_TRANSFORMER_DIMENSION = 384  # all-MiniLM-L6-v2
TARGET_DIMENSION = OPENAI_DIMENSION  # OpenAI 차원으로 통일

# 하이브리드 설정
USE_GPU_FIRST = os.getenv("USE_GPU_FIRST", "true").lower() == "true"
GPU_FALLBACK_TO_OPENAI = os.getenv("GPU_FALLBACK_TO_OPENAI", "true").lower() == "true"

def get_embedding_method() -> str:
    """
    현재 환경에서 사용 가능한 최적의 임베딩 방법을 반환합니다.
    
    우선순위: GPU(CUDA) > MPS(Apple Silicon) > CPU(sentence-transformers) > OpenAI
    """
    try:
        from .embedder_gpu import GPU_AVAILABLE, DEVICE, setup_gpu_embedder
        
        if USE_GPU_FIRST and setup_gpu_embedder() is not None:
            if DEVICE == 'cuda':
                return "gpu"
            elif DEVICE == 'mps':
                return "mps"
            else:
                return "cpu"
        
        # OpenAI fallback
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        
        return "none"
        
    except Exception as e:
        logger.warning(f"임베딩 방법 결정 실패: {e}")
        return "openai" if os.getenv("OPENAI_API_KEY") else "none"

def embed_documents_hybrid(texts: List[str], force_method: Optional[str] = None) -> List[List[float]]:
    """
    하이브리드 임베딩 함수
    
    GPU를 우선 사용하고, 실패 시 OpenAI로 fallback합니다.
    
    Args:
        texts: 임베딩할 텍스트 리스트
        force_method: 강제로 사용할 방법 ("gpu", "openai", None)
    
    Returns:
        임베딩 벡터 리스트
    """
    if not texts:
        return []
    
    start_time = time.time()
    method = force_method or get_embedding_method()
    
    logger.info(f"임베딩 시작: {len(texts)}개 문서, 방법={method}")
    
    # GPU/MPS/CPU 우선 시도
    if method in ["gpu", "mps", "cpu"] or (method != "openai" and USE_GPU_FIRST):
        try:
            embedder = setup_gpu_embedder()
            if embedder is not None:
                device_name = {"gpu": "GPU(CUDA)", "mps": "MPS(Apple Silicon)", "cpu": "CPU"}
                logger.info(f"{device_name.get(method, 'sentence-transformers')} 임베딩 실행 중... (device: {DEVICE})")
                embeddings = embed_documents_gpu(texts)
                
                if embeddings and len(embeddings) == len(texts):
                    embeddings = normalize_embeddings_dimension(embeddings)
                    elapsed = time.time() - start_time
                    logger.info(f"{device_name.get(method, 'sentence-transformers')} 임베딩 완료: {len(embeddings)}개, {elapsed:.2f}초")
                    return embeddings
                else:
                    logger.warning(f"sentence-transformers 임베딩 결과 불일치: {len(embeddings) if embeddings else 0}/{len(texts)}")
            
        except Exception as e:
            logger.warning(f"sentence-transformers 임베딩 실패: {e}")
    
    # OpenAI fallback
    if method == "openai" or GPU_FALLBACK_TO_OPENAI:
        if not os.getenv("OPENAI_API_KEY"):
            logger.error("OpenAI API 키가 없어 임베딩을 수행할 수 없습니다.")
            return []
        
        try:
            logger.info("OpenAI 임베딩으로 fallback")
            embeddings = openai_embed_documents(texts)
            
            if embeddings and len(embeddings) == len(texts):
                embeddings = normalize_embeddings_dimension(embeddings)
                elapsed = time.time() - start_time
                logger.info(f"OpenAI 임베딩 완료: {len(embeddings)}개, {elapsed:.2f}초")
                return embeddings
            else:
                logger.error(f"OpenAI 임베딩 결과 불일치: {len(embeddings) if embeddings else 0}/{len(texts)}")
        
        except Exception as e:
            logger.error(f"OpenAI 임베딩 실패: {e}")
    
    logger.error("모든 임베딩 방법이 실패했습니다.")
    return []

def normalize_embeddings_dimension(embeddings: List[List[float]], target_dim: int = TARGET_DIMENSION) -> List[List[float]]:
    """
    임베딩 벡터의 차원을 통일합니다.
    
    Args:
        embeddings: 임베딩 벡터 리스트
        target_dim: 목표 차원 수
    
    Returns:
        차원이 통일된 임베딩 벡터 리스트
    """
    if not embeddings:
        return []
    
    current_dim = len(embeddings[0])
    
    if current_dim == target_dim:
        return embeddings
    
    logger.info(f"임베딩 차원 변환: {current_dim} -> {target_dim}")
    
    normalized_embeddings = []
    for embedding in embeddings:
        if current_dim < target_dim:
            # 패딩: 부족한 차원을 0으로 채움
            padded = embedding + [0.0] * (target_dim - current_dim)
            normalized_embeddings.append(padded)
        else:
            # 트렁케이션: 초과 차원을 자름
            truncated = embedding[:target_dim]
            normalized_embeddings.append(truncated)
    
    return normalized_embeddings

# 기본 embed_documents 함수를 하이브리드로 설정
embed_documents = embed_documents_hybrid

def log_embedding_status():
    """현재 임베딩 환경 상태를 로깅합니다."""
    try:
        from .embedder_gpu import GPU_AVAILABLE, DEVICE
    except ImportError:
        GPU_AVAILABLE = False
        DEVICE = 'cpu'
    
    logger.info("=== 임베딩 환경 상태 ===")
    logger.info(f"GPU 사용 가능: {GPU_AVAILABLE}")
    if GPU_AVAILABLE:
        if DEVICE == 'cuda':
            logger.info(f"디바이스: CUDA GPU")
        elif DEVICE == 'mps':
            logger.info(f"디바이스: Apple Silicon MPS")
        else:
            logger.info(f"디바이스: {DEVICE}")
    logger.info(f"OpenAI API 키: {'설정됨' if os.getenv('OPENAI_API_KEY') else '없음'}")
    logger.info(f"GPU 우선 사용: {USE_GPU_FIRST}")
    logger.info(f"GPU fallback: {GPU_FALLBACK_TO_OPENAI}")
    logger.info(f"권장 방법: {get_embedding_method()}")
    logger.info("========================")

# 모듈 로드 시 상태 로깅
log_embedding_status()
