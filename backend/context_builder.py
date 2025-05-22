"""
Context Builder 모듈

이 모듈은 검색 결과에서 최적화된 컨텍스트를 구성하는 기능을 제공합니다.
중복 청크 제거, 토큰 제한, 컨텍스트 최적화 등의 기능을 구현합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import logging
import tiktoken
from typing import List, Dict, Any, Tuple, Optional
import re
from difflib import SequenceMatcher

# 로깅 설정
logger = logging.getLogger(__name__)

# 토큰 카운터 초기화 (OpenAI 모델 기준)
try:
    tokenizer = tiktoken.encoding_for_model("text-embedding-3-small")
except:
    tokenizer = tiktoken.get_encoding("cl100k_base")  # 기본값으로 fallback

# 설정값
MAX_CONTEXT_TOKENS = 6000  # 최대 6K 토큰으로 제한
MIN_CHUNK_TOKENS = 100     # 최소 청크 크기
SIMILARITY_THRESHOLD = 0.8  # 중복 감지 임계값


def count_tokens(text: str) -> int:
    """텍스트의 토큰 수를 정확히 계산"""
    if not text:
        return 0
    return len(tokenizer.encode(text))


def is_similar(text1: str, text2: str, threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """두 텍스트가 유사한지 확인"""
    # 매우 짧은 텍스트는 비교하지 않음
    if len(text1) < 20 or len(text2) < 20:
        return False
    
    # 시퀀스 매처를 사용하여 유사도 계산
    similarity = SequenceMatcher(None, text1, text2).ratio()
    return similarity >= threshold


def remove_duplicate_chunks(docs: List[str], metadatas: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """중복 청크를 감지하고 제거"""
    if not docs:
        return [], []
    
    unique_docs = []
    unique_metadatas = []
    
    # 각 문서에 대해
    for i, doc in enumerate(docs):
        is_duplicate = False
        
        # 이미 추가된 각 문서와 비교
        for unique_doc in unique_docs:
            if is_similar(doc, unique_doc):
                is_duplicate = True
                logger.info(f"중복 청크 감지: {doc[:50]}...")
                break
        
        # 중복이 아니면 추가
        if not is_duplicate:
            unique_docs.append(doc)
            if i < len(metadatas):
                unique_metadatas.append(metadatas[i])
    
    logger.info(f"중복 제거 결과: {len(docs)} -> {len(unique_docs)} 문서")
    return unique_docs, unique_metadatas


def optimize_context_length(docs: List[str], metadatas: List[Dict[str, Any]], max_tokens: int = MAX_CONTEXT_TOKENS) -> Tuple[List[str], List[Dict[str, Any]]]:
    """컨텍스트 길이를 최적화하고 토큰 제한을 적용"""
    if not docs:
        return [], []
    
    optimized_docs = []
    optimized_metadatas = []
    total_tokens = 0
    
    # 각 문서에 대해
    for i, doc in enumerate(docs):
        doc_tokens = count_tokens(doc)
        
        # 이 문서를.추가하면 제한을 초과하는지 확인
        if total_tokens + doc_tokens > max_tokens and optimized_docs:  # 최소한 하나는 포함
            logger.info(f"토큰 제한 도달 ({total_tokens}/{max_tokens}), 나머지 문서 생략")
            break
        
        optimized_docs.append(doc)
        if i < len(metadatas):
            optimized_metadatas.append(metadatas[i])
        total_tokens += doc_tokens
    
    logger.info(f"최적화된 컨텍스트: {len(optimized_docs)} 문서, {total_tokens} 토큰")
    return optimized_docs, optimized_metadatas


def build_optimized_context(docs: List[str], metadatas: List[Dict[str, Any]], max_tokens: int = MAX_CONTEXT_TOKENS) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """검색 결과에서 최적화된 컨텍스트 구성"""
    start_docs_count = len(docs)
    
    # 1. 중복 청크 제거
    unique_docs, unique_metadatas = remove_duplicate_chunks(docs, metadatas)
    
    # 2. 토큰 제한 적용
    optimized_docs, optimized_metadatas = optimize_context_length(unique_docs, unique_metadatas, max_tokens)
    
    # 3. 최종 컨텍스트 생성
    context = "\n\n".join(optimized_docs)
    
    # 4. 메타데이터 준비
    metadata = {
        "original_docs_count": start_docs_count,
        "optimized_docs_count": len(optimized_docs),
        "token_count": count_tokens(context),
        "duplicates_removed": start_docs_count - len(unique_docs),
    }
    
    return context, optimized_metadatas, metadata


def extract_most_relevant_parts(docs: List[str], query: str, max_tokens: int = MAX_CONTEXT_TOKENS) -> List[str]:
    """
    쿼리와 가장 관련성 높은 부분만 추출 (고급 최적화)
    참고: 현재 간단한 구현. 향후 확장 가능.
    """
    # 현재는 단순히 문서를 그대로 반환
    # 향후 쿼리 기반 관련성 판단 로직 구현 가능
    return docs
