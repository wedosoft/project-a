"""
문서 임베딩 모듈

이 모듈은 문서를 벡터 임베딩으로 변환하는 함수를 제공합니다.
OpenAI API를 사용하여 텍스트 임베딩을 생성합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
import os
import logging
from typing import List, Any, Dict, Tuple
from chromadb.utils import embedding_functions
import math
import tiktoken
import re

# 로깅 설정
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다. (임베딩용)")

# OpenAI 임베딩 함수 설정
MODEL_NAME = "text-embedding-ada-002"
embed_fn = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name=MODEL_NAME
)

# 토큰 인코더 초기화
tokenizer = tiktoken.encoding_for_model(MODEL_NAME)

# OpenAI API 제한 설정
MAX_TOKENS_PER_CHUNK = 8000  # API 제한 8192에서 약간의 여유를 둠
MAX_BATCH_SIZE = 50  # 한 번에 처리할 최대 문서 수
CHUNK_OVERLAP = 200  # 청크 간 중복 토큰 수

def count_tokens(text: str) -> int:
    """텍스트의 토큰 수를 계산합니다."""
    return len(tokenizer.encode(text))

def split_into_chunks(text: str, max_tokens: int = MAX_TOKENS_PER_CHUNK, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    긴 텍스트를 청크로 분할합니다.
    각 청크는 최대 토큰 수를 초과하지 않으며, 청크 간에 일부 중복이 있습니다.
    """
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
    
    logger.info(f"텍스트({len(tokens)} 토큰)를 {len(chunks)}개 청크로 분할")
    return chunks

def process_documents(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    문서 리스트를 처리하여 필요한 경우 청크로 분할합니다.
    각 문서는 'id', 'text', 'metadata'를 포함한 딕셔너리여야 합니다.
    문서를 청크로 분할할 경우 원본 메타데이터를 유지하고 청크 번호를 추가합니다.
    """
    processed_docs = []
    
    for i, doc in enumerate(docs):
        doc_id = doc.get('id', f"doc_{i}")
        doc_text = doc.get('text', '')
        doc_metadata = doc.get('metadata', {})
        
        token_count = count_tokens(doc_text)
        
        if token_count <= MAX_TOKENS_PER_CHUNK:
            # 토큰 수가 제한 이내인 경우 그대로 사용
            processed_docs.append(doc)
        else:
            # 토큰 수가 제한을 초과하는 경우 청크로 분할
            logger.warning(f"문서 '{doc_id}'가 토큰 제한을 초과합니다 ({token_count} > {MAX_TOKENS_PER_CHUNK}). 청크로 분할합니다.")
            chunks = split_into_chunks(doc_text, MAX_TOKENS_PER_CHUNK, CHUNK_OVERLAP)
            
            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_doc = {
                    'id': f"{doc_id}_chunk_{chunk_idx}",
                    'text': chunk_text,
                    'metadata': {
                        **doc_metadata,
                        'chunk_index': chunk_idx,
                        'total_chunks': len(chunks),
                        'original_id': doc_id
                    }
                }
                processed_docs.append(chunk_doc)
    
    return processed_docs

def embed_documents(docs: List[str]) -> List[List[float]]:
    """
    문서 리스트를 임베딩 벡터 리스트로 변환합니다.
    대용량 문서를 처리하기 위해 배치 처리를 수행합니다.
    참고: 이 함수는 이미 청크로 분할된 문서를 가정합니다.
    """
    # 문서가 없으면 빈 리스트 반환
    if not docs:
        return []
    
    # 문서 수에 따라 배치 처리
    total_docs = len(docs)
    num_batches = math.ceil(total_docs / MAX_BATCH_SIZE)
    all_embeddings = []
    
    logger.info(f"총 {total_docs}개 문서를 {num_batches}개 배치로 처리합니다.")
    
    for i in range(num_batches):
        start_idx = i * MAX_BATCH_SIZE
        end_idx = min((i + 1) * MAX_BATCH_SIZE, total_docs)
        batch = docs[start_idx:end_idx]
        
        logger.info(f"배치 {i+1}/{num_batches} 처리 중... ({start_idx}~{end_idx-1})")
        try:
            batch_embeddings = embed_fn(batch)
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"임베딩 생성 중 오류 발생: {e}")
            # 문제 문서 식별을 위한 진단 정보 출력
            for j, doc in enumerate(batch):
                logger.debug(f"문서 {start_idx + j} 토큰 수: {count_tokens(doc)}")
            raise
        
    return all_embeddings