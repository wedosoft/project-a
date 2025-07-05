"""
Context Builder 모듈 (Phase 1-2: 최적화 버전)

이 모듈은 검색 결과에서 최적화된 컨텍스트를 구성하는 기능을 제공합니다.
중복 청크 제거, 토큰 제한, 컨텍스트 최적화, top_k 제한 등의 기능을 구현합니다.

주요 개선사항:
- 강화된 중복 감지 로직 (해시 기반 + 유사도 기반)
- top_k 제한 적용으로 성능 향상
- 개선된 토큰 계산 및 예외 처리
- 문장 분할 정규식 수정
- 컨텍스트 품질 점수 기반 정렬

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import hashlib
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

import tiktoken

# 로깅 설정
logger = logging.getLogger(__name__)

# 토큰 카운터 초기화 (OpenAI 모델 기준)
# text-embedding-3-small은 cl100k_base 인코딩 사용
# 네트워크 연결 문제가 있을 때 graceful fallback 제공
tokenizer = None
try:
    # text-embedding-3-small/large 모델은 cl100k_base 인코딩을 사용
    tokenizer = tiktoken.get_encoding("cl100k_base")
    logger.debug("tiktoken cl100k_base 인코딩 로드 성공")
except Exception as e:
    logger.error(f"tiktoken 인코딩 로드 실패: {e}")
    # 네트워크 문제로 tiktoken을 로드할 수 없는 경우 None으로 설정

# 설정값 (환경변수로 오버라이드 가능)
MAX_CONTEXT_TOKENS = 8000      # 최대 8K 토큰으로 상향 조정
MIN_CHUNK_TOKENS = 100         # 최소 청크 크기
SIMILARITY_THRESHOLD = 0.8     # 중복 감지 임계값
DEFAULT_TOP_K = 50             # 기본 top_k 제한값
TARGET_TOKENS_PER_DOC = 400    # 문서당 목표 토큰 수


def _split_into_sentences(text: str) -> List[str]:
    """텍스트를 문장 단위로 분할합니다."""
    if not text or not text.strip():
        return []
    
    # 스마트 따옴표를 표준 따옴표로 정규화
    normalized_text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    
    # 문장 종료 기호 뒤에 공백이 오는 패턴으로 분할
    # 따옴표가 문장 끝에 올 수 있는 경우를 고려
    pattern = r'(?<=[.!?][\'\"]*)\s+'
    sentences = re.split(pattern, normalized_text.strip())
    
    # 빈 문자열 제거 및 공백 정리
    return [s.strip() for s in sentences if s.strip()]


def count_tokens(text: str) -> int:
    """텍스트의 토큰 수를 정확히 계산합니다."""
    if not text:
        return 0
    
    # tokenizer가 없는 경우 대략적인 계산 사용
    if tokenizer is None:
        # 대략적인 토큰 수 계산 (1 토큰 ≈ 4 문자, 한글은 약간 더 많이)
        # 한글이 포함된 텍스트는 보정 계수 적용
        korean_ratio = len(re.findall(r'[가-힣]', text)) / len(text) if len(text) > 0 else 0
        correction_factor = 3.5 if korean_ratio > 0.5 else 4.0
        return max(1, int(len(text) / correction_factor))
    
    try:
        return len(tokenizer.encode(text))
    except Exception as e:
        logger.warning(f"토큰 인코딩 오류, 대략적 계산 사용: {e}")
        return max(1, len(text) // 4)


def _calculate_content_hash(text: str) -> str:
    """컨텐츠의 해시값을 계산합니다 (빠른 중복 감지용)."""
    # 공백과 구두점을 정규화하여 해시 계산
    normalized = re.sub(r'\s+', ' ', text.strip().lower())
    normalized = re.sub(r'[^\w\s]', '', normalized)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def is_similar(text1: str, text2: str, threshold: float = SIMILARITY_THRESHOLD) -> bool:
    """두 텍스트가 유사한지 확인합니다."""
    # 매우 짧은 텍스트는 비교하지 않음
    if len(text1) < 20 or len(text2) < 20:
        return False
    
    # 길이 차이가 너무 크면 다른 문서로 판단
    length_ratio = min(len(text1), len(text2)) / max(len(text1), len(text2))
    if length_ratio < 0.3:
        return False
    
    # 시퀀스 매처를 사용하여 유사도 계산
    similarity = SequenceMatcher(None, text1, text2).ratio()
    return similarity >= threshold


def remove_duplicate_chunks(
    docs: List[str], 
    metadatas: List[Dict[str, Any]]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """강화된 중복 청크 감지 및 제거 로직입니다."""
    if not docs:
        return [], []
    
    unique_docs = []
    unique_metadatas = []
    seen_hashes: Set[str] = set()
    
    logger.info(f"중복 제거 시작: {len(docs)}개 문서")
    
    # 각 문서에 대해 처리
    for i, doc in enumerate(docs):
        if not doc or not doc.strip():
            continue
            
        # 1차: 해시 기반 빠른 중복 감지
        content_hash = _calculate_content_hash(doc)
        if content_hash in seen_hashes:
            logger.debug(f"해시 기반 중복 감지: {doc[:50]}...")
            continue
        
        # 2차: 유사도 기반 중복 감지 (기존 고유 문서들과 비교)
        is_duplicate = False
        for unique_doc in unique_docs:
            if is_similar(doc, unique_doc):
                is_duplicate = True
                logger.debug(f"유사도 기반 중복 감지: {doc[:50]}...")
                break
        
        # 중복이 아니면 추가
        if not is_duplicate:
            unique_docs.append(doc)
            if i < len(metadatas):
                unique_metadatas.append(metadatas[i])
            seen_hashes.add(content_hash)
    
    logger.info(f"중복 제거 완료: {len(docs)} -> {len(unique_docs)} 문서")
    return unique_docs, unique_metadatas


def _calculate_document_quality_score(
    doc: str, 
    metadata: Dict[str, Any], 
    query: Optional[str] = None
) -> float:
    """문서의 품질 점수를 계산합니다."""
    score = 0.0
    
    # 1. 기본 길이 점수 (너무 짧거나 길지 않은 적정 길이 선호)
    doc_length = len(doc)
    if 200 <= doc_length <= 2000:
        score += 1.0
    elif doc_length < 200:
        score += 0.5
    else:
        score += 0.7
    
    # 2. 토큰 수 기반 점수
    token_count = count_tokens(doc)
    if MIN_CHUNK_TOKENS <= token_count <= TARGET_TOKENS_PER_DOC * 1.5:
        score += 1.0
    elif token_count < MIN_CHUNK_TOKENS:
        score += 0.3
    else:
        score += 0.8
    
    # 3. 메타데이터 기반 점수
    if metadata:
        # 소스 신뢰도 (예: knowledge_base > ticket)
        source = metadata.get('source', '')
        if 'knowledge' in source.lower():
            score += 0.5
        elif 'ticket' in source.lower():
            score += 0.3
        
        # 최신성 점수 (created_at이 있는 경우)
        if 'created_at' in metadata:
            score += 0.2
    
    # 4. 쿼리 관련성 점수 (선택적)
    if query:
        query_words = set(query.lower().split())
        doc_words = set(re.findall(r'\w+', doc.lower()))
        common_words = query_words.intersection(doc_words)
        if common_words:
            relevance_ratio = len(common_words) / len(query_words)
            score += relevance_ratio * 2.0  # 최대 2점 추가
    
    return score


def apply_top_k_limit(
    docs: List[str], 
    metadatas: List[Dict[str, Any]], 
    top_k: int = DEFAULT_TOP_K,
    query: Optional[str] = None
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """top_k 제한을 적용하여 최고 품질의 문서들만 선택합니다."""
    if not docs or len(docs) <= top_k:
        return docs, metadatas
    
    logger.info(f"top_k 제한 적용: {len(docs)} -> {top_k} 문서")
    
    # 각 문서에 품질 점수 계산
    scored_docs = []
    for i, doc in enumerate(docs):
        metadata = metadatas[i] if i < len(metadatas) else {}
        quality_score = _calculate_document_quality_score(doc, metadata, query)
        scored_docs.append({
            'doc': doc,
            'metadata': metadata,
            'score': quality_score,
            'index': i
        })
    
    # 점수 기준으로 정렬하고 상위 top_k개 선택
    scored_docs.sort(key=lambda x: x['score'], reverse=True)
    top_docs = scored_docs[:top_k]
    
    # 원래 순서를 유지하기 위해 인덱스 기준으로 재정렬
    top_docs.sort(key=lambda x: x['index'])
    
    result_docs = [item['doc'] for item in top_docs]
    result_metadatas = [item['metadata'] for item in top_docs]
    
    logger.info(f"top_k 적용 완료: 평균 품질 점수 {sum(item['score'] for item in top_docs) / len(top_docs):.2f}")
    return result_docs, result_metadatas


def extract_most_relevant_parts(
    docs: List[str], 
    metadatas: List[Dict[str, Any]], 
    query: str, 
    target_tokens_per_doc: int = TARGET_TOKENS_PER_DOC
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """각 문서에서 쿼리와 가장 관련성 높은 부분을 추출합니다."""
    if not query or not docs:
        logger.debug("쿼리 또는 문서가 없음, 원본 반환")
        return docs, metadatas

    processed_docs = []
    processed_metadatas = []
    query_words = set(query.lower().split())
    
    if not query_words:
        logger.debug("쿼리 단어가 없음, 원본 반환")
        return docs, metadatas

    logger.info(f"관련성 추출 시작: {len(docs)}개 문서, 쿼리: '{query[:50]}...'")

    for i, doc_content in enumerate(docs):
        current_metadata = metadatas[i] if i < len(metadatas) else {}
        
        if not doc_content or not doc_content.strip():
            continue
            
        # 문장 단위로 분할
        sentences = _split_into_sentences(doc_content)
        if not sentences:
            continue

        # 각 문장의 관련성 점수 계산
        scored_sentences = []
        for sentence_text in sentences:
            # 문장에서 단어 추출 (구두점 제거)
            sentence_words = set(re.sub(r'[^\w\s]', '', sentence_text).lower().split())
            common_words = query_words.intersection(sentence_words)
            
            if common_words:  # 관련성이 있는 문장만 고려
                score = len(common_words) / len(query_words)  # 정규화된 점수
                scored_sentences.append({
                    'text': sentence_text,
                    'score': score,
                    'tokens': count_tokens(sentence_text)
                })
        
        # 점수 기준으로 정렬
        scored_sentences.sort(key=lambda x: x['score'], reverse=True)

        # 목표 토큰 수에 맞춰 문장 선택
        selected_sentences = []
        current_tokens = 0
        original_doc_tokens = count_tokens(doc_content)
        actual_target = min(target_tokens_per_doc, original_doc_tokens)

        for sentence_info in scored_sentences:
            sentence_tokens = sentence_info['tokens']
            
            if current_tokens + sentence_tokens <= actual_target:
                selected_sentences.append(sentence_info['text'])
                current_tokens += sentence_tokens
            elif not selected_sentences:  # 첫 문장이 너무 긴 경우 자르기
                # 문장을 적절히 자르기
                sentence_text = sentence_info['text']
                words = sentence_text.split()
                estimated_words_per_token = len(words) / sentence_tokens if sentence_tokens > 0 else 1
                target_words = int(actual_target * estimated_words_per_token)
                
                if target_words > 0:
                    truncated_text = ' '.join(words[:target_words])
                    if truncated_text:
                        selected_sentences.append(truncated_text)
                        current_tokens = count_tokens(truncated_text)
                break
            else:
                break

        # 선택된 문장들을 점수 순서대로 재배열하고 결합
        if selected_sentences:
            # 원본 문서에서의 등장 순서를 유지하기 위해 위치 기반 정렬
            final_text = ' '.join(selected_sentences)
            processed_docs.append(final_text)
            processed_metadatas.append(current_metadata)

    logger.info(f"관련성 추출 완료: {len(docs)} -> {len(processed_docs)} 문서")
    return processed_docs, processed_metadatas


def optimize_context_length(
    docs: List[str], 
    metadatas: List[Dict[str, Any]], 
    max_tokens: int = MAX_CONTEXT_TOKENS
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """컨텍스트 길이를 최적화하고 토큰 제한을 적용합니다."""
    if not docs:
        return [], []
    
    optimized_docs = []
    optimized_metadatas = []
    total_tokens = 0
    
    logger.info(f"토큰 제한 적용 시작: {len(docs)}개 문서, 최대 {max_tokens} 토큰")
    
    # 각 문서에 대해 순차적으로 처리
    for i, doc in enumerate(docs):
        doc_tokens = count_tokens(doc)
        
        # 이 문서를 추가하면 제한을 초과하는지 확인
        if total_tokens + doc_tokens > max_tokens and optimized_docs:  # 최소한 하나는 포함
            logger.info(f"토큰 제한 도달 ({total_tokens}/{max_tokens}), 나머지 {len(docs) - i}개 문서 생략")
            break
        
        optimized_docs.append(doc)
        if i < len(metadatas):
            optimized_metadatas.append(metadatas[i])
        total_tokens += doc_tokens
    
    logger.info(f"토큰 최적화 완료: {len(optimized_docs)}개 문서, {total_tokens} 토큰")
    return optimized_docs, optimized_metadatas


def build_optimized_context(
    docs: List[str], 
    metadatas: List[Dict[str, Any]], 
    query: Optional[str] = None,
    max_tokens: int = MAX_CONTEXT_TOKENS,
    top_k: Optional[int] = DEFAULT_TOP_K,
    enable_relevance_extraction: bool = True
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """
    검색 결과에서 최적화된 컨텍스트를 구성합니다.
    
    처리 단계:
    1. top_k 제한 적용 (품질 기반 선별)
    2. 중복 청크 제거 (해시 + 유사도 기반)
    3. 관련성 기반 핵심 부분 추출 (옵션)
    4. 토큰 제한 적용
    """
    initial_docs_count = len(docs)
    
    if initial_docs_count == 0:
        return "", [], {"original_docs_count": 0, "final_optimized_docs_count": 0, "token_count": 0}
    
    logger.info(f"컨텍스트 최적화 시작: {initial_docs_count}개 문서")
    
    # 1. top_k 제한 적용 (품질 기반 문서 선별)
    if top_k and top_k > 0:
        filtered_docs, filtered_metadatas = apply_top_k_limit(docs, metadatas, top_k, query)
    else:
        filtered_docs, filtered_metadatas = docs, metadatas
    
    top_k_count = len(filtered_docs)
    
    # 2. 중복 청크 제거 (강화된 알고리즘)
    unique_docs, unique_metadatas = remove_duplicate_chunks(filtered_docs, filtered_metadatas)
    deduplicated_count = len(unique_docs)
    
    # 3. 쿼리 관련성 기반 핵심 부분 추출 (옵션)
    if enable_relevance_extraction and query and unique_docs:
        logger.info(f"관련성 추출 활성화: {deduplicated_count}개 문서")
        try:
            relevant_docs, relevant_metadatas = extract_most_relevant_parts(
                unique_docs, 
                unique_metadatas, 
                query,
                TARGET_TOKENS_PER_DOC
            )
        except Exception as e:
            logger.error(f"관련성 추출 중 오류: {e}")
            relevant_docs, relevant_metadatas = unique_docs, unique_metadatas
    else:
        logger.info("관련성 추출 건너뜀")
        relevant_docs, relevant_metadatas = unique_docs, unique_metadatas
    
    extracted_count = len(relevant_docs)
    
    # 4. 토큰 제한 적용 (최종 단계)
    optimized_docs, optimized_metadatas = optimize_context_length(
        relevant_docs, 
        relevant_metadatas, 
        max_tokens
    )
    
    # 5. 최종 컨텍스트 생성
    final_context = "\n\n".join(optimized_docs)
    final_token_count = count_tokens(final_context)
    
    # 6. 상세 메타데이터 준비
    optimization_metadata = {
        "original_docs_count": initial_docs_count,
        "after_top_k_count": top_k_count,
        "after_deduplication_count": deduplicated_count,
        "after_relevance_extraction_count": extracted_count,
        "final_optimized_docs_count": len(optimized_docs),
        "token_count": final_token_count,
        "query_provided": bool(query),
        "relevance_extraction_enabled": enable_relevance_extraction,
        "top_k_applied": top_k,
        "max_tokens_limit": max_tokens
    }
    
    logger.info(
        f"컨텍스트 최적화 완료: "
        f"원본 {initial_docs_count} -> "
        f"top_k {top_k_count} -> "
        f"중복제거 {deduplicated_count} -> "
        f"관련성추출 {extracted_count} -> "
        f"최종 {len(optimized_docs)}개 문서, "
        f"{final_token_count} 토큰"
    )
    
    return final_context, optimized_metadatas, optimization_metadata
