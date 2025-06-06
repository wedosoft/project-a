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
MODEL_NAME = "text-embedding-3-small"
import openai

# OpenAI 클라이언트 설정
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# 토큰 인코더 초기화
try:
    tokenizer = tiktoken.encoding_for_model(MODEL_NAME)
except:
    tokenizer = tiktoken.get_encoding("cl100k_base")  # 최신 모델용 fallback

# OpenAI API 제한 설정
MAX_TOKENS_PER_CHUNK = 8000  # API 제한 8192에서 약간의 여유를 둠
MAX_BATCH_SIZE = 20  # 한 번에 처리할 최대 문서 수 (50에서 20으로 감소)
MAX_TOKENS_PER_REQUEST = 250000  # OpenAI API 제한 300,000에서 여유를 둠
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
    모든 문서와 청크의 metadata에 doc_type 필수 보정(없으면 id 기반 자동 보정, 그래도 없으면 예외)
    """
    processed_docs = []
    
    for i, doc in enumerate(docs):
        doc_id = doc.get('id', f"doc_{i}")
        doc_text = doc.get('text', '')
        doc_metadata = doc.get('metadata', {})
        # doc_type 필수 보정: 없으면 id 기반 자동 보정, 그래도 없으면 예외
        if "doc_type" not in doc_metadata or not doc_metadata["doc_type"]:
            if str(doc_id).startswith("ticket-"):
                doc_metadata["doc_type"] = "ticket"
            elif str(doc_id).startswith("kb-"):
                doc_metadata["doc_type"] = "kb"
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
                chunk_metadata.update({
                    'chunk_index': chunk_idx,
                    'total_chunks': len(chunks),
                    'original_id': doc_id,
                    'is_chunk': True
                })
                # 청크의 doc_type 필수 보정
                if "doc_type" not in chunk_metadata or not chunk_metadata["doc_type"]:
                    if str(doc_id).startswith("ticket-"):
                        chunk_metadata["doc_type"] = "ticket"
                    elif str(doc_id).startswith("kb-"):
                        chunk_metadata["doc_type"] = "kb"
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
    
    # 각 문서의 토큰 수를 확인하고 필요시 자르기
    processed_docs = []
    for i, doc in enumerate(docs):
        token_count = count_tokens(doc)
        logger.debug(f"문서 {i} 토큰 수: {token_count}")  # ERROR -> DEBUG로 수정
        
        if token_count > MAX_TOKENS_PER_CHUNK:
            # 토큰 수가 제한을 초과하는 경우 잘라서 처리
            logger.warning(f"문서 {i}가 토큰 제한을 초과합니다 ({token_count} > {MAX_TOKENS_PER_CHUNK}). 텍스트를 잘라서 처리합니다.")
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