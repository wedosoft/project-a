"""
문서 임베딩 모듈

이 모듈은 문서를 벡터 임베딩으로 변환하는 함수를 제공합니다.
OpenAI API를 사용하여 텍스트 임베딩을 생성합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

from ...constants import ChunkConstants, DocIdPrefix

# 환경변수 로드 - 상대 경로를 사용하여 backend/.env 파일을 찾습니다
backend_dir = Path(__file__).parent.parent  # core 디렉토리의 상위(backend) 디렉토리
dotenv_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

import numpy as np
import tiktoken

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수 로드 후 키 확인
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
    raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다. (임베딩용)")

# OpenAI 임베딩 함수 설정 - 최신 임베딩 모델 사용
MODEL_NAME = "text-embedding-3-large"
import openai

# OpenAI 클라이언트 설정
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# 토큰 인코더 초기화
try:
    # text-embedding-3-small은 cl100k_base 인코딩을 사용
    if MODEL_NAME in ["text-embedding-3-small", "text-embedding-3-large"]:
        tokenizer = tiktoken.get_encoding("cl100k_base")
    else:
        tokenizer = tiktoken.encoding_for_model(MODEL_NAME)
except Exception as e:
    logger.warning(f"tiktoken 모델별 인코딩 로드 실패: {e}")
    try:
        tokenizer = tiktoken.get_encoding("cl100k_base")  # 최신 모델용 fallback
    except Exception as e2:
        logger.error(f"tiktoken 기본 인코딩 로드도 실패: {e2}")
        # 네트워크 문제로 tiktoken을 로드할 수 없는 경우 None으로 설정
        tokenizer = None

# OpenAI API 제한 설정
MAX_TOKENS_PER_CHUNK = 8000  # API 제한 8192에서 약간의 여유를 둠
MAX_BATCH_SIZE = 20  # 한 번에 처리할 최대 문서 수 (50에서 20으로 감소)
MAX_TOKENS_PER_REQUEST = 250000  # OpenAI API 제한 300,000에서 여유를 둠
CHUNK_OVERLAP = 200  # 청크 간 중복 토큰 수

def count_tokens(text: str) -> int:
    """텍스트의 토큰 수를 계산합니다."""
    # 입력값 검증 및 변환
    if text is None:
        return 0
    
    if not isinstance(text, str):
        # 문자열이 아닌 경우 문자열로 변환 시도
        try:
            text = str(text)
        except Exception:
            logger.warning(f"토큰 카운트 실패: 변환할 수 없는 타입 {type(text)}")
            return 0
    
    if not text.strip():
        return 0
    
    if tokenizer is None:
        # 대략적인 토큰 수 계산 (1 토큰 ≈ 4 문자)
        return len(text) // 4
    
    try:
        return len(tokenizer.encode(text))
    except Exception as e:
        logger.warning(f"토큰 카운트 실패: {e}")
        return len(text) // 4  # 폴백 계산

def split_into_chunks(text: str, max_tokens: int = MAX_TOKENS_PER_CHUNK, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    긴 텍스트를 청크로 분할합니다.
    각 청크는 최대 토큰 수를 초과하지 않으며, 청크 간에 일부 중복이 있습니다.
    """
    if tokenizer is None:
        # tokenizer가 없는 경우 문자 기반으로 대략적으로 분할
        char_limit = max_tokens * 4  # 대략적인 문자 수 계산
        if len(text) <= char_limit:
            return [text]
        
        chunks = []
        start_idx = 0
        overlap_chars = overlap * 4
        
        while start_idx < len(text):
            end_idx = min(start_idx + char_limit, len(text))
            chunk_text = text[start_idx:end_idx]
            chunks.append(chunk_text)
            
            start_idx += char_limit - overlap_chars
            if start_idx >= len(text):
                break
        
        return chunks
    
    tokens = tokenizer.encode(text)
    if len(tokens) <= max_tokens:
        return [text]
    
    # 청크로 분할
    chunks = []
    start_idx = 0
    
    while start_idx < len(tokens):
        end_idx = min(start_idx + max_tokens, len(tokens))
        chunk_tokens = tokens[start_idx:end_idx]
        chunk_text = tokenizer.decode(chunk_tokens)
        chunks.append(chunk_text)
        
        # 다음 청크의 시작 위치 계산 (중복 고려)
        start_idx += max_tokens - overlap
        if start_idx >= len(tokens):
            break
    
    return chunks

def process_documents(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    문서 리스트를 처리하여 필요한 경우 청크로 분할합니다.
    각 문서는 'id', 'text', 'metadata'를 포함한 딕셔너리여야 합니다.
    문서를 청크로 분할할 경우 원본 메타데이터를 유지하고 청크 번호를 추가합니다.
    모든 문서와 청크의 metadata에 doc_type 필수 보정(없으면 id 기반 자동 보정, 그래도 없으면 예외)
    """
    processed_docs = []
    
    for i, doc in enumerate(docs):
        doc_id = doc.get('id', f"doc_{i}")
        doc_text = doc.get('text', '')
        doc_metadata = doc.get('metadata', {})
        # doc_type 필수 보정: 없으면 id 기반 자동 보정, 그래도 없으면 예외
        if "doc_type" not in doc_metadata or not doc_metadata["doc_type"]:
            try:
                doc_metadata["doc_type"] = DocIdPrefix.extract_doc_type(str(doc_id))
                logger.debug(f"doc_id '{doc_id}'에서 자동으로 doc_type '{doc_metadata['doc_type']}'을 추출했습니다.")
            except ValueError:
                # doc_id에서 타입을 추출할 수 없는 경우
                pass
        
        if "doc_type" not in doc_metadata or not doc_metadata["doc_type"]:
            raise ValueError(f"문서 {i}의 metadata에 doc_type이 없습니다. id={doc_id}, metadata={doc_metadata}")
        
        token_count = count_tokens(doc_text)
        if token_count <= MAX_TOKENS_PER_CHUNK:
            processed_docs.append(doc)
        else:
            logger.warning(f"문서 '{doc_id}'가 토큰 제한을 초과합니다 ({token_count} > {MAX_TOKENS_PER_CHUNK}). 청크로 분할합니다.")
            chunks = split_into_chunks(doc_text, MAX_TOKENS_PER_CHUNK, CHUNK_OVERLAP)
            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_metadata = doc_metadata.copy()
                chunk_doc_id = ChunkConstants.create_chunk_id(doc_id, chunk_idx)
                chunk_metadata.update({
                    'chunk_index': chunk_idx,
                    'total_chunks': len(chunks),
                    'original_id': doc_id,
                    'is_chunk': True
                })
                # 청크의 doc_type 필수 보정 (부모에서 상속)
                if "doc_type" not in chunk_metadata or not chunk_metadata["doc_type"]:
                    chunk_metadata["doc_type"] = doc_metadata["doc_type"]
                
                if "doc_type" not in chunk_metadata or not chunk_metadata["doc_type"]:
                    raise ValueError(f"청크 {chunk_idx}의 metadata에 doc_type이 없습니다. id={doc_id}, metadata={chunk_metadata}")
                required_fields = ['type', 'source_id', 'updated_at', 'status', 'priority']
                for field in required_fields:
                    if field not in chunk_metadata and field in doc_metadata:
                        chunk_metadata[field] = doc_metadata[field]
                chunk_doc = {
                    'id': f"{doc_id}_chunk_{chunk_idx}",
                    'text': chunk_text,
                    'metadata': chunk_metadata
                }
                processed_docs.append(chunk_doc)
    return processed_docs

def create_optimal_batches(docs: List[str]) -> List[List[str]]:
    """
    문서 리스트를 토큰 제한을 고려한 최적의 배치로 분할합니다.
    각 배치의 총 토큰 수가 MAX_TOKENS_PER_REQUEST를 초과하지 않도록 합니다.
    """
    batches = []
    current_batch = []
    current_tokens = 0
    
    for doc in docs:
        doc_tokens = count_tokens(doc)
        
        # 한 문서가 개별적으로 제한을 초과하는 경우를 확인
        if doc_tokens > MAX_TOKENS_PER_REQUEST:
            logger.warning(f"단일 문서가 토큰 제한을 초과합니다: {doc_tokens} 토큰. 이 문서는 건너뜁니다.")
            continue
            
        # 현재 배치에 문서를 추가했을 때 토큰 제한을 초과하는 경우 새 배치 시작
        if current_tokens + doc_tokens > MAX_TOKENS_PER_REQUEST or len(current_batch) >= MAX_BATCH_SIZE:
            if current_batch:  # 현재 배치가 비어있지 않은 경우에만 추가
                batches.append(current_batch)
            current_batch = [doc]
            current_tokens = doc_tokens
        else:
            current_batch.append(doc)
            current_tokens += doc_tokens
    
    # 마지막 배치 추가
    if current_batch:
        batches.append(current_batch)
    
    logger.info(f"총 {len(docs)}개 문서를 {len(batches)}개 배치로 처리합니다.")
    for i, batch in enumerate(batches):
        batch_tokens = sum(count_tokens(doc) for doc in batch)
        logger.debug(f"배치 {i+1}/{len(batches)} 처리 중... ({batch[0][:30]}...)")
    
    return batches

def embed_documents(docs: List[str]) -> List[List[float]]:
    """
    문서 리스트를 임베딩 벡터 리스트로 변환합니다.
    대용량 문서를 처리하기 위해 배치 처리를 수행합니다.
    각 문서는 토큰 제한에 맞게 자동으로 잘립니다.
    """
    # 문서가 없으면 빈 리스트 반환
    if not docs:
        return []
    
    # 입력 데이터 검증 및 정리
    valid_docs = []
    for i, doc in enumerate(docs):
        if doc is None:
            logger.warning(f"문서 {i}: None 값이 전달됨 - 건너뜀")
            continue
            
        if not isinstance(doc, str):
            logger.warning(f"문서 {i}: 문자열이 아님 ({type(doc)}) - 문자열로 변환 시도")
            try:
                doc = str(doc)
            except Exception as e:
                logger.error(f"문서 {i}: 문자열 변환 실패 - 건너뜀: {e}")
                continue
        
        if not doc.strip():
            logger.warning(f"문서 {i}: 빈 문자열 - 건너뜀")
            continue
            
        valid_docs.append(doc)
    
    if not valid_docs:
        logger.warning("유효한 문서가 없음 - 빈 리스트 반환")
        return []
    
    logger.info(f"유효한 문서 수: {len(valid_docs)}/{len(docs)}")
    
    # 각 문서의 토큰 수를 확인하고 필요시 자르기
    processed_docs = []
    for i, doc in enumerate(valid_docs):
        token_count = count_tokens(doc)
        logger.debug(f"문서 {i} 토큰 수: {token_count}")  # ERROR -> DEBUG로 수정
        
        if token_count > MAX_TOKENS_PER_CHUNK:
            # 토큰 수가 제한을 초과하는 경우 잘라서 처리
            logger.warning(f"문서 {i}가 토큰 제한을 초과합니다 ({token_count} > {MAX_TOKENS_PER_CHUNK}). 텍스트를 잘라서 처리합니다.")
            if tokenizer is None:
                # tokenizer가 없는 경우 문자 기반으로 자르기
                char_limit = MAX_TOKENS_PER_CHUNK * 4
                truncated_text = doc[:char_limit]
            else:
                tokens = tokenizer.encode(doc)
                truncated_tokens = tokens[:MAX_TOKENS_PER_CHUNK]
                truncated_text = tokenizer.decode(truncated_tokens)
            processed_docs.append(truncated_text)
        else:
            processed_docs.append(doc)
    
    # 토큰 제한을 고려하여 최적의 배치로 분할
    batches = create_optimal_batches(processed_docs)
    all_embeddings = []
    
    for i, batch in enumerate(batches):
        logger.info(f"배치 {i+1}/{len(batches)} 처리 중... ({i*len(batch)}~{i*len(batch)+len(batch)-1})")
        try:
            batch_embeddings = []
            for text in batch:
                # 최종 안전장치: 임베딩 생성 전 토큰 수 재확인
                final_token_count = count_tokens(text)
                if final_token_count > MAX_TOKENS_PER_CHUNK:
                    logger.error(f"최종 검사에서 토큰 초과 감지: {final_token_count} 토큰, 추가 절단 실행")
                    if tokenizer is None:
                        # tokenizer가 없는 경우 문자 기반으로 자르기
                        char_limit = MAX_TOKENS_PER_CHUNK * 4
                        text = text[:char_limit]
                    else:
                        tokens = tokenizer.encode(text)
                        truncated_tokens = tokens[:MAX_TOKENS_PER_CHUNK]
                        text = tokenizer.decode(truncated_tokens)
                
                response = client.embeddings.create(
                    model=MODEL_NAME,
                    input=text
                )
                embedding = response.data[0].embedding
                batch_embeddings.append(embedding)
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {e}")
            # 문제 문서 식별을 위한 진단 정보 출력
            total_tokens = sum(count_tokens(doc) for doc in batch)
            logger.error(f"배치 {i+1} 문서 수: {len(batch)}, 총 토큰 수: {total_tokens}")
            for j, doc in enumerate(batch):
                doc_tokens = count_tokens(doc)
                if doc_tokens > 5000:  # 대용량 문서만 상세 로깅
                    logger.error(f"문서 {j} 토큰 수: {doc_tokens}")
                else:
                    logger.debug(f"문서 {j} 토큰 수: {doc_tokens}")  # 진단 정보는 debug로 출력
            raise
        
    return all_embeddings


def embed_documents_with_model(docs: List[str], model_name: str) -> List[List[float]]:
    """
    특정 모델을 사용하여 문서 임베딩 생성
    
    Args:
        docs: 문서 텍스트 리스트
        model_name: 사용할 임베딩 모델명 (예: "text-embedding-3-large")
        
    Returns:
        임베딩 벡터 리스트
    """
    if not docs:
        return []
    
    # 모델별 토큰 제한 설정
    if model_name == "text-embedding-3-large":
        max_tokens = 8191  # text-embedding-3-large의 실제 제한
    elif model_name == "text-embedding-3-small":
        max_tokens = 8191  # text-embedding-3-small의 제한
    else:
        max_tokens = 8000  # 안전한 기본값
    
    # 입력 데이터 검증 및 정리
    valid_docs = []
    for i, doc in enumerate(docs):
        if doc is None:
            logger.warning(f"문서 {i}: None 값이 전달됨 - 건너뜀")
            continue
            
        if not isinstance(doc, str):
            logger.warning(f"문서 {i}: 문자열이 아님 ({type(doc)}) - 문자열로 변환 시도")
            try:
                doc = str(doc)
            except Exception as e:
                logger.error(f"문서 {i}: 문자열 변환 실패 - 건너뜀: {e}")
                continue
        
        if not doc.strip():
            logger.warning(f"문서 {i}: 빈 문자열 - 건너뜀")
            continue
            
        valid_docs.append(doc)
    
    if not valid_docs:
        logger.warning("유효한 문서가 없음 - 빈 리스트 반환")
        return []
    
    logger.info(f"유효한 문서 수: {len(valid_docs)}/{len(docs)}")
    
    # 각 문서의 토큰 수를 확인하고 필요시 자르기
    processed_docs = []
    for i, doc in enumerate(valid_docs):
        token_count = count_tokens(doc)
        logger.debug(f"문서 {i} 토큰 수: {token_count}")
        
        if token_count > max_tokens:
            # 토큰 수가 제한을 초과하는 경우 잘라서 처리
            logger.warning(f"문서 {i}가 토큰 제한을 초과합니다 ({token_count} > {max_tokens}). 텍스트를 잘라서 처리합니다.")
            if tokenizer is None:
                # tokenizer가 없는 경우 문자 기반으로 자르기
                char_limit = max_tokens * 4
                truncated_text = doc[:char_limit]
            else:
                tokens = tokenizer.encode(doc)
                truncated_tokens = tokens[:max_tokens]
                truncated_text = tokenizer.decode(truncated_tokens)
            processed_docs.append(truncated_text)
        else:
            processed_docs.append(doc)
    
    # 배치 처리 (한 번에 하나씩 처리하여 토큰 제한 확실히 지키기)
    all_embeddings = []
    
    for i, text in enumerate(processed_docs):
        logger.info(f"문서 {i+1}/{len(processed_docs)} 처리 중...")
        
        try:
            # 최종 안전장치: 임베딩 생성 전 토큰 수 재확인
            final_token_count = count_tokens(text)
            if final_token_count > max_tokens:
                logger.error(f"최종 검사에서 토큰 초과 감지: {final_token_count} 토큰, 추가 절단 실행")
                if tokenizer is None:
                    char_limit = max_tokens * 4
                    text = text[:char_limit]
                else:
                    tokens = tokenizer.encode(text)
                    truncated_tokens = tokens[:max_tokens]
                    text = tokenizer.decode(truncated_tokens)
            
            response = client.embeddings.create(
                model=model_name,  # 지정된 모델 사용
                input=text
            )
            embedding = response.data[0].embedding
            all_embeddings.append(embedding)
            
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생 (모델: {model_name}, 문서 {i}): {e}")
            raise
        
    return all_embeddings


# =============================================================================
# GPU 최적화 임베딩 통합 인터페이스 (Step 2: GPU 임베딩 최적화)
# =============================================================================

def embed_documents_optimized(
    docs: List[str], 
    mode: str = "multilingual"
) -> List[List[float]]:
    """
    🌍 다국어 최적화 임베딩 생성
    
    Args:
        docs: 문서 텍스트 리스트
        mode: 임베딩 모드 ("multilingual", "openai")
        
    Returns:
        임베딩 벡터 리스트
    """
    if not docs:
        return []
    
    if mode == "multilingual":
        # 🌍 다국어 최적화 시스템 (text-embedding-3-large, 3072차원)
        try:
            import asyncio
            from .multilingual import embed_documents_multilingual, EmbeddingQuality
            
            logger.info(f"🌍 다국어 최적화 임베딩 생성: {len(docs)}개 문서")
            
            # 비동기 함수를 동기 환경에서 실행
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            embed_documents_multilingual(docs, EmbeddingQuality.ULTRA)
                        )
                        return future.result()
                else:
                    return loop.run_until_complete(
                        embed_documents_multilingual(docs, EmbeddingQuality.ULTRA)
                    )
            except RuntimeError:
                return asyncio.run(
                    embed_documents_multilingual(docs, EmbeddingQuality.ULTRA)
                )
                
        except Exception as e:
            logger.error(f"❌ 다국어 임베딩 실패, OpenAI 기본 모드로 폴백: {e}")
            return embed_documents(docs)
    
    elif mode == "openai":
        # 기본 OpenAI 방식 (text-embedding-3-large, 3072차원)
        return embed_documents(docs)
    
    else:
        raise ValueError(f"지원되지 않는 임베딩 모드: {mode}. 'multilingual' 또는 'openai'만 지원됩니다.")


def get_embedder_info() -> Dict[str, Any]:
    """
    사용 가능한 임베더 정보를 반환합니다.
    
    Returns:
        임베더 상태 정보
    """
    info = {
        "openai_available": bool(OPENAI_API_KEY),
        "openai_model": MODEL_NAME,
        "gpu_available": False,
        "gpu_info": None
    }
    
    try:
        from .embedder_gpu import get_gpu_embedder_info
        gpu_info = get_gpu_embedder_info()
        info["gpu_available"] = gpu_info["gpu_available"]
        info["gpu_info"] = gpu_info
    except ImportError:
        logger.debug("GPU 임베딩 모듈을 로드할 수 없습니다.")
    except Exception as e:
        logger.debug(f"GPU 정보 수집 실패: {e}")
    
    return info