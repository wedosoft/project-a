"""
Context Builder 모듈

이 모듈은 검색 결과에서 최적화된 컨텍스트를 구성하는 기능을 제공합니다.
중복 청크 제거, 토큰 제한, 컨텍스트 최적화 등의 기능을 구현합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import logging
import tiktoken # Ensure tiktoken is correctly installed and importable
from typing import List, Dict, Any, Tuple, Optional
import re
from difflib import SequenceMatcher

# 로깅 설정
logger = logging.getLogger(__name__)

# 토큰 카운터 초기화 (OpenAI 모델 기준)
# 네트워크 연결이 없는 환경에서는 토큰 카운터를 비활성화
tokenizer = None
try:
    tokenizer = tiktoken.encoding_for_model("text-embedding-3-small")
except:
    try:
        tokenizer = tiktoken.get_encoding("cl100k_base")  # 기본값으로 fallback
    except Exception as e:
        print(f"Warning: tiktoken 초기화 실패, 토큰 카운팅 비활성화: {e}")
        tokenizer = None

# 설정값
MAX_CONTEXT_TOKENS = 8000  # 최대 8K 토큰으로 상향 조정
MIN_CHUNK_TOKENS = 100     # 최소 청크 크기
SIMILARITY_THRESHOLD = 0.8  # 중복 감지 임계값

# New helper function for sentence splitting
def _split_into_sentences(text: str) -> List[str]:
    if not text or not text.strip():
        return []
    # Corrected regex: ensure backslashes are properly escaped for special characters
    # and use standard quotation marks.
    sentences = re.split(r'(?<=[.!?\"\'”’])\s+', text.strip()) # Original problematic line
    # Attempting a more robust regex, carefully escaping:
    # The original regex had issues with mixed quote types and escaping.
    # Let's simplify and use standard quotes, ensuring Python string literal compatibility.
    # Python's raw strings (r'') handle backslashes differently.
    # For re.split, the pattern r'(?<=[.!?])\s+' is common.
    # If including quotes, they must be handled carefully.
    # Example: r'(?<=[.!?"\'“”’])\s+' -> r'(?<=[.!?"\'\u201C\u201D\u2019])\s+'
    # For simplicity and to avoid further syntax errors from complex quote handling in regex:
    text_normalized_quotes = text.replace('\u201C', '"').replace('\u201D', '"').replace('\u2018', "'").replace('\u2019', "'")
    sentences = re.split(r'(?<=[.!?])\s+', text_normalized_quotes.strip()) # Simpler split after normalizing quotes
    
    # Fallback or refined splitting if the above is too simple:
    # This regex tries to handle ., !, ?, and closing quotes followed by space.
    # It's crucial that quotes in the regex pattern itself are correctly escaped for Python strings.
    # sentences = re.split(r'(?<=[.!?][\"\'”’]?)\s+', text.strip()) # Trying to be more inclusive
    
    # Let's use a simpler, more standard sentence splitting regex first, then refine if needed.
    # This one splits by common sentence terminators followed by whitespace.
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    # If we need to handle quotes specifically as part of the terminator:
    # sentences = re.split(r'(?<=[.!?]["\']?)\s+', text.strip())

    # The original regex was: r'(?<=[.!?\\"\\\'”’])\\s+'
    # Corrected for Python string literal and regex engine:
    # The issue might be the smart quotes ” and ’. Let's replace them or use unicode escapes.
    text_to_split = text.strip().replace('”', '"').replace('’', "'")
    sentences = re.split(r'(?<=[.!?"\'])s*\s+', text_to_split)


    # Final attempt at a robust regex for sentence splitting, handling various terminators and quotes
    # This regex looks for ., !, or ? possibly followed by a quote, then whitespace.
    # Standard quotes ' and " are used in the pattern.
    pattern = r'(?<=[.!?][\'\"]?)\s+'
    # Normalize smart quotes to standard quotes before splitting
    normalized_text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    sentences = re.split(pattern, normalized_text.strip())
    
    return [s.strip() for s in sentences if s.strip()]


def count_tokens(text: str) -> int:
    """텍스트의 토큰 수를 정확히 계산"""
    if not text:
        return 0
    if tokenizer is None:
        # 토큰 카운터가 없는 경우 대략적인 추정 (1 토큰 ≈ 4 글자)
        return len(text) // 4
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


def extract_most_relevant_parts(
    docs: List[str], 
    metadatas: List[Dict[str, Any]], 
    query: str, 
    target_tokens_per_doc: int = 400 # Default target token count per document after extraction
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    For each document, extracts the most query-relevant sentences up to a target token count.
    Filters out documents that become empty after extraction.
    """
    if not query or not docs:
        logger.debug("No query or docs provided to extract_most_relevant_parts, returning original.")
        return docs, metadatas

    processed_docs_intermediate = []
    processed_metadatas_intermediate = []

    query_words = set(query.lower().split())
    if not query_words: # Handle empty query string after split
        logger.debug("Query words are empty, returning original docs.")
        return docs, metadatas

    for i, doc_content in enumerate(docs):
        current_metadata = metadatas[i] if i < len(metadatas) else {}
        if not doc_content or not doc_content.strip():
            processed_docs_intermediate.append("") # Corrected empty string
            processed_metadatas_intermediate.append(current_metadata)
            logger.debug(f"Document {i} is empty or whitespace, keeping as is.")
            continue

        sentences = _split_into_sentences(doc_content)
        if not sentences:
            processed_docs_intermediate.append("") # Corrected empty string
            processed_metadatas_intermediate.append(current_metadata)
            logger.debug(f"Document {i} resulted in no sentences after split, keeping as empty.")
            continue

        scored_sentences = []
        for sentence_text in sentences:
            # Simple scoring: count common words (case-insensitive)
            # Corrected stripping of punctuation for set creation
            sentence_words = set(re.sub(r'[^\w\s]', '', s).lower() for s in sentence_text.split())
            common_words = query_words.intersection(sentence_words)
            score = len(common_words)
            
            if score > 0: # Only consider sentences with some relevance
                scored_sentences.append({'text': sentence_text, 'score': score, 'tokens': count_tokens(sentence_text)})
        
        scored_sentences.sort(key=lambda x: x['score'], reverse=True)

        selected_sentences_texts = []
        current_tokens_for_doc = 0
        original_doc_tokens = count_tokens(doc_content)
        
        actual_target_for_this_doc = min(target_tokens_per_doc, original_doc_tokens)

        for scored_sentence_info in scored_sentences:
            sentence_to_add = scored_sentence_info['text']
            tokens_for_sentence = scored_sentence_info['tokens']

            if current_tokens_for_doc + tokens_for_sentence <= actual_target_for_this_doc:
                selected_sentences_texts.append(sentence_to_add)
                current_tokens_for_doc += tokens_for_sentence
            elif not selected_sentences_texts: 
                if tokens_for_sentence > 0 : 
                    estimated_chars_per_token = len(sentence_to_add) / tokens_for_sentence
                    target_chars = int(actual_target_for_this_doc * estimated_chars_per_token)
                    truncated_text = sentence_to_add[:target_chars]
                    
                    while count_tokens(truncated_text) > actual_target_for_this_doc and len(truncated_text) > 5: 
                        truncate_by = max(1, int(len(truncated_text) * 0.1)) 
                        truncated_text = truncated_text[:-truncate_by]
                    
                    if count_tokens(truncated_text) <= actual_target_for_this_doc and truncated_text:
                        selected_sentences_texts.append(truncated_text)
                        current_tokens_for_doc += count_tokens(truncated_text)
                break # Stop after considering the most relevant (but too long) sentence
            else: # Already have some sentences, and next one exceeds budget
                break 
        
        if not selected_sentences_texts:
            logger.debug(f"Doc {i} ('{doc_content[:30]}...') had no relevant sentences fitting token budget for query '{query[:30]}...'. Resulting doc will be empty.")
            processed_docs_intermediate.append("") # Corrected empty string
        else:
            # Join selected sentences. They are already sorted by relevance.
            processed_docs_intermediate.append(" ".join(selected_sentences_texts))
        
        processed_metadatas_intermediate.append(current_metadata)
            
    # Filter out documents that became effectively empty (or were initially empty)
    final_processed_docs = []
    final_processed_metadatas = []
    for i_orig, doc_text_orig in enumerate(processed_docs_intermediate): # Renamed loop variables to avoid conflict
        if doc_text_orig.strip(): # If doc is not just whitespace
            final_processed_docs.append(doc_text_orig)
            final_processed_metadatas.append(processed_metadatas_intermediate[i_orig])
        else:
            source_info = processed_metadatas_intermediate[i_orig].get('source', 'N/A')
            logger.info(f"Document at original input index {i_orig} (metadata source: {source_info}) was filtered out as it became empty after relevance extraction.")

    logger.info(f"Relevance extraction: {len(docs)} docs in -> {len(final_processed_docs)} docs out.")
    return final_processed_docs, final_processed_metadatas


def build_optimized_context(
    docs: List[str], 
    metadatas: List[Dict[str, Any]], 
    query_for_context: Optional[str] = None, # Added query parameter, made optional
    max_tokens: int = MAX_CONTEXT_TOKENS
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    """검색 결과에서 최적화된 컨텍스트 구성"""
    initial_docs_count = len(docs)
    
    # 1. 중복 청크 제거
    unique_docs, unique_metadatas = remove_duplicate_chunks(docs, metadatas)
    deduplicated_count = len(unique_docs)
    
    # 2. (New Step) 각 문서에서 쿼리와 관련된 핵심 부분 추출
    if query_for_context and unique_docs: # Only run if query is provided and there are docs
        logger.info(f"Starting relevance extraction for {deduplicated_count} unique docs with query: '{query_for_context[:50]}...'")
        try:
            relevant_parts_docs, relevant_parts_metadatas = extract_most_relevant_parts(
                unique_docs, 
                unique_metadatas, 
                query_for_context
                # Default target_tokens_per_doc (400) will be used from function definition
            )
        except Exception as e:
            logger.error(f"Error during relevance extraction: {e}")
            relevant_parts_docs, relevant_parts_metadatas = unique_docs, unique_metadatas # Fallback to unique docs
    else: # If no query or no docs after deduplication, skip relevance extraction
        logger.info("Skipping relevance extraction (no query or no unique docs).")
        relevant_parts_docs, relevant_parts_metadatas = unique_docs, unique_metadatas
    
    extracted_parts_count = len(relevant_parts_docs)

    # 3. 토큰 제한 적용 (using documents processed by relevance extraction)
    optimized_docs, optimized_metadatas_final = optimize_context_length(
        relevant_parts_docs, 
        relevant_parts_metadatas, 
        max_tokens
    )
    
    # 4. 최종 컨텍스트 생성
    final_context_str = "\\n\\n".join(optimized_docs)
    
    # 5. 메타데이터 준비
    final_summary_metadata = {
        "original_docs_count": initial_docs_count,
        "after_deduplication_count": deduplicated_count,
        "after_relevance_extraction_count": extracted_parts_count,
        "final_optimized_docs_count": len(optimized_docs),
        "token_count": count_tokens(final_context_str),
        "query_used_for_extraction": bool(query_for_context)
    }
    
    logger.info(f"Context build summary: Original {initial_docs_count} -> Deduplicated {deduplicated_count} -> Extracted {extracted_parts_count} -> Final Optimized {len(optimized_docs)}. Total tokens: {final_summary_metadata['token_count']}")
    
    return final_context_str, optimized_metadatas_final, final_summary_metadata

# def extract_most_relevant_parts(docs: List[str], query: str, max_tokens: int = MAX_CONTEXT_TOKENS) -> List[str]:
# 이전 함수는 위에 새로 구현된 extract_most_relevant_parts(docs, metadatas, query, ...) 로 대체됩니다.
# 주석 처리 또는 삭제합니다.
