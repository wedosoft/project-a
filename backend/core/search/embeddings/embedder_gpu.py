"""
GPU 기반 임베딩 최적화 모듈

기존 core/embedder.py의 OpenAI 기반 임베딩과 함께 사용할 수 있는
GPU 최적화 임베딩 기능을 제공합니다.

Features:
- GPU 기반 sentence-transformers 모델 지원
- 배치 크기 자동 최적화
- 임베딩 캐싱 시스템
- 하이브리드 모드 (GPU/OpenAI 선택적 사용)
"""
import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# 환경변수 로드
backend_dir = Path(__file__).parent.parent
dotenv_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

# GPU 임베딩을 위한 선택적 임포트
try:
    import torch
    from sentence_transformers import SentenceTransformer
    
    logger = logging.getLogger(__name__)
    
    # 디바이스 감지 상세 로그
    logger.info(f"PyTorch 버전: {torch.__version__}")
    logger.info(f"CUDA 사용 가능: {torch.cuda.is_available()}")
    logger.info(f"MPS 백엔드 존재: {hasattr(torch.backends, 'mps')}")
    if hasattr(torch.backends, 'mps'):
        logger.info(f"MPS 사용 가능: {torch.backends.mps.is_available()}")
        logger.info(f"MPS 빌트인: {torch.backends.mps.is_built()}")
    
    # 디바이스 우선순위: CUDA > MPS > CPU
    if torch.cuda.is_available():
        GPU_AVAILABLE = True
        DEVICE = 'cuda'
        gpu_info = f"CUDA GPU: {torch.cuda.get_device_name(0)}"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        GPU_AVAILABLE = True
        DEVICE = 'mps'
        gpu_info = "Apple Silicon MPS"
    else:
        GPU_AVAILABLE = False
        DEVICE = 'cpu'
        gpu_info = "CPU only"
    
    logger.info(f"선택된 디바이스: {DEVICE} ({gpu_info})")
    
    # 추가 MPS 테스트 (Apple Silicon인 경우)
    if hasattr(torch.backends, 'mps'):
        try:
            # MPS 테스트 텐서 생성 시도
            test_tensor = torch.tensor([1.0, 2.0])
            if torch.backends.mps.is_available():
                try:
                    mps_tensor = test_tensor.to('mps')
                    logger.info("✅ MPS 디바이스 테스트 성공")
                except Exception as e:
                    logger.warning(f"❌ MPS 디바이스 테스트 실패: {e}")
        except Exception as e:
            logger.warning(f"MPS 테스트 중 오류: {e}")
    
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"GPU 임베딩 라이브러리를 로드할 수 없습니다: {e}. "
                   "sentence-transformers, torch를 설치하세요.")
    GPU_AVAILABLE = False
    DEVICE = 'cpu'
    torch = None
    SentenceTransformer = None

# 설정
GPU_MODEL_NAME = "all-MiniLM-L6-v2"  # 빠르고 효율적인 모델
DEFAULT_BATCH_SIZE = 32
CACHE_DIR = backend_dir / "data" / "embedding_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 글로벌 변수
_gpu_embedder: Optional[SentenceTransformer] = None


def setup_gpu_embedder(
    model_name: str = GPU_MODEL_NAME, 
    force_reload: bool = False
) -> Optional[SentenceTransformer]:
    """
    GPU/CPU 기반 임베더를 초기화합니다.
    GPU가 없으면 CPU로 fallback합니다.
    
    Args:
        model_name: 사용할 sentence-transformer 모델명
        force_reload: 기존 모델을 강제로 다시 로드할지 여부
    
    Returns:
        초기화된 SentenceTransformer 객체 또는 None (라이브러리 사용 불가시)
    """
    global _gpu_embedder
    
    if SentenceTransformer is None:
        logger.warning("sentence-transformers 라이브러리가 사용 불가합니다.")
        return None
    
    if _gpu_embedder is not None and not force_reload:
        return _gpu_embedder
    
    try:
        device = DEVICE if GPU_AVAILABLE else 'cpu'
        logger.info(f"sentence-transformers 임베더 초기화 중: {model_name} (device: {device})")
        
        _gpu_embedder = SentenceTransformer(model_name, device=device)
        dimension = _gpu_embedder.get_sentence_embedding_dimension()
        
        if GPU_AVAILABLE:
            logger.info(f"GPU 임베더 초기화 완료. 벡터 차원: {dimension}")
        else:
            logger.info(f"CPU 임베더 초기화 완료. 벡터 차원: {dimension}")
        
        return _gpu_embedder
    except Exception as e:
        logger.error(f"sentence-transformers 임베더 초기화 실패: {e}")
        return None


def get_embedding_cache_key(text: str, model_name: str) -> str:
    """임베딩 캐시 키를 생성합니다."""
    content = f"{model_name}:{text}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def get_cached_embeddings(
    texts: List[str], 
    model_name: str
) -> Tuple[List[Optional[List[float]]], List[int]]:
    """
    캐시된 임베딩을 조회합니다.
    
    Args:
        texts: 텍스트 리스트
        model_name: 모델명
        
    Returns:
        (임베딩 리스트, 캐시 미스 인덱스 리스트)
    """
    embeddings = [None] * len(texts)
    cache_miss_indices = []
    
    for i, text in enumerate(texts):
        cache_key = get_embedding_cache_key(text, model_name)
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    embeddings[i] = cached_data['embedding']
            except Exception as e:
                logger.debug(f"캐시 파일 읽기 실패: {cache_file}, {e}")
                cache_miss_indices.append(i)
        else:
            cache_miss_indices.append(i)
    
    cache_hits = len(texts) - len(cache_miss_indices)
    logger.debug(f"캐시 히트: {cache_hits}/{len(texts)}")
    return embeddings, cache_miss_indices


def cache_embeddings(
    texts: List[str], 
    embeddings: List[List[float]], 
    model_name: str, 
    indices: List[int]
):
    """
    임베딩을 캐시에 저장합니다.
    
    Args:
        texts: 텍스트 리스트
        embeddings: 임베딩 리스트
        model_name: 모델명
        indices: 저장할 인덱스 리스트
    """
    for i, embedding in zip(indices, embeddings):
        try:
            cache_key = get_embedding_cache_key(texts[i], model_name)
            cache_file = CACHE_DIR / f"{cache_key}.json"
            
            cache_data = {
                'text': texts[i][:100],  # 첫 100자만 저장 (디버깅용)
                'embedding': embedding,
                'model': model_name,
                'timestamp': time.time()
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.debug(f"캐시 저장 실패: {e}")


def calculate_optimal_batch_size(
    available_memory_gb: float = None
) -> int:
    """
    GPU 메모리에 따른 최적 배치 크기를 계산합니다.
    
    Args:
        available_memory_gb: 사용 가능한 GPU 메모리 (GB)
        
    Returns:
        최적 배치 크기
    """
    if not GPU_AVAILABLE or torch is None:
        return DEFAULT_BATCH_SIZE
    
    try:
        if available_memory_gb is None:
            # GPU 메모리 자동 감지
            total_memory = torch.cuda.get_device_properties(0).total_memory
            available_memory_gb = (total_memory * 0.8) / (1024**3)  # 80% 사용
        
        # 메모리 기반 배치 크기 계산 (경험적 공식)
        if available_memory_gb >= 8:
            return min(512, DEFAULT_BATCH_SIZE * 8)
        elif available_memory_gb >= 4:
            return min(256, DEFAULT_BATCH_SIZE * 4)
        elif available_memory_gb >= 2:
            return min(128, DEFAULT_BATCH_SIZE * 2)
        else:
            return DEFAULT_BATCH_SIZE
    except Exception as e:
        logger.debug(f"GPU 메모리 감지 실패: {e}")
        return DEFAULT_BATCH_SIZE


def embed_documents_gpu(
    docs: List[str], 
    batch_size: int = None, 
    use_cache: bool = True
) -> List[List[float]]:
    """
    sentence-transformers를 사용하여 문서들을 임베딩으로 변환합니다.
    GPU가 있으면 GPU로, 없으면 CPU로 처리합니다.
    
    Args:
        docs: 문서 텍스트 리스트
        batch_size: 배치 크기 (None시 자동 계산)
        use_cache: 캐싱 사용 여부
        
    Returns:
        임베딩 벡터 리스트
    """
    if not docs:
        return []
    
    if SentenceTransformer is None:
        logger.warning("sentence-transformers 라이브러리가 사용 불가능합니다.")
        return []
    
    gpu_embedder = setup_gpu_embedder()
    if gpu_embedder is None:
        raise RuntimeError("sentence-transformers 임베더를 사용할 수 없습니다.")
    
    if batch_size is None:
        batch_size = calculate_optimal_batch_size()
    
    device = DEVICE if GPU_AVAILABLE else 'cpu'
    logger.info(f"sentence-transformers 임베딩 시작: {len(docs)}개 문서, 배치 크기: {batch_size}, device: {device}")
    
    # 캐시 확인
    embeddings = [None] * len(docs)
    cache_miss_indices = []
    
    if use_cache:
        embeddings, cache_miss_indices = get_cached_embeddings(
            docs, GPU_MODEL_NAME
        )
    else:
        cache_miss_indices = list(range(len(docs)))
    
    # 캐시 미스 문서들만 임베딩 생성
    if cache_miss_indices:
        cache_miss_texts = [docs[i] for i in cache_miss_indices]
        
        # 배치별로 처리
        new_embeddings = []
        total_batches = math.ceil(len(cache_miss_texts) / batch_size)
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(cache_miss_texts))
            batch_texts = cache_miss_texts[start_idx:end_idx]
            
            logger.info(f"GPU 배치 {batch_idx+1}/{total_batches} 처리 중... "
                       f"({len(batch_texts)}개 문서)")
            
            try:
                # GPU 배치 임베딩 생성
                batch_embeddings = gpu_embedder.encode(
                    batch_texts,
                    batch_size=len(batch_texts),
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                new_embeddings.extend(batch_embeddings.tolist())
                
            except Exception as e:
                logger.error(f"GPU 배치 임베딩 실패: {e}")
                # GPU 메모리 부족시 배치 크기 감소 후 재시도
                if "out of memory" in str(e).lower() and batch_size > 1:
                    logger.warning(f"GPU 메모리 부족. 배치 크기를 "
                                 f"{batch_size//2}로 감소합니다.")
                    return embed_documents_gpu(docs, batch_size//2, use_cache)
                else:
                    raise
        
        # 캐시에 저장
        if use_cache:
            cache_embeddings(
                cache_miss_texts, new_embeddings, 
                GPU_MODEL_NAME, cache_miss_indices
            )
        
        # 결과 배열에 새로운 임베딩 추가
        for i, embedding in zip(cache_miss_indices, new_embeddings):
            embeddings[i] = embedding
    
    # None 값 확인 (캐시 오류로 인한)
    final_embeddings = []
    for emb in embeddings:
        if emb is None:
            logger.error("임베딩이 None입니다. 이는 예상치 못한 오류입니다.")
            raise RuntimeError("임베딩 생성 실패")
        final_embeddings.append(emb)
    
    logger.info(f"{DEVICE.upper()} 임베딩 완료: {len(final_embeddings)}개 벡터 생성")
    return final_embeddings


def get_gpu_embedder_info() -> Dict[str, Any]:
    """
    GPU 임베더 정보를 반환합니다.
    
    Returns:
        GPU 임베더 상태 정보
    """
    info = {
        "gpu_available": GPU_AVAILABLE,
        "gpu_model": GPU_MODEL_NAME if GPU_AVAILABLE else None,
        "device": DEVICE,
        "cache_enabled": CACHE_DIR.exists(),
        "cache_dir": str(CACHE_DIR)
    }
    
    if GPU_AVAILABLE and torch is not None:
        try:
            info["gpu_name"] = torch.cuda.get_device_name(0)
            gpu_properties = torch.cuda.get_device_properties(0)
            info["gpu_memory_total"] = gpu_properties.total_memory / (1024**3)
            info["optimal_batch_size"] = calculate_optimal_batch_size()
        except Exception as e:
            logger.debug(f"GPU 정보 수집 실패: {e}")
    
    return info


def clear_embedding_cache() -> int:
    """
    임베딩 캐시를 정리합니다.
    
    Returns:
        삭제된 캐시 파일 수
    """
    deleted_count = 0
    try:
        for cache_file in CACHE_DIR.glob("*.json"):
            cache_file.unlink()
            deleted_count += 1
        logger.info(f"임베딩 캐시 정리 완료: {deleted_count}개 파일 삭제")
    except Exception as e:
        logger.error(f"캐시 정리 실패: {e}")
    
    return deleted_count
