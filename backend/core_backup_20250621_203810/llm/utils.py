"""
LLM 유틸리티 함수들

이 모듈은 다음 기능을 제공합니다:
- 벡터 검색 최적화
- 프롬프트 템플릿 관리
- 텍스트 전처리 및 토큰 계산
- 임베딩 유틸리티
- 캐시 관리
"""

import os
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from cachetools import TTLCache
import redis

logger = logging.getLogger(__name__)


# 임베딩 캐시 설정 (최대 1000개, 1시간 TTL)
embedding_cache = TTLCache(maxsize=1000, ttl=3600)

# Issue/Solution 캐시 (최대 500개, 6시간 TTL)
issue_solution_cache = TTLCache(maxsize=500, ttl=21600)


def get_cache_key(text: str, model: str) -> str:
    """임베딩 캐시 키 생성"""
    content = f"{model}:{text}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def get_issue_solution_key(ticket_data: Dict[str, Any]) -> str:
    """Issue/Solution 캐시 키 생성"""
    key_fields = {
        "id": ticket_data.get("id"),
        "subject": ticket_data.get("subject"),
        "description": ticket_data.get("description_text", ticket_data.get("description", "")),
    }
    key_json = json.dumps(key_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(key_json.encode("utf-8")).hexdigest()


class VectorSearchOptimizer:
    """벡터 검색 최적화를 위한 클래스"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        벡터 검색 최적화기 초기화
        
        Args:
            redis_url: Redis 연결 URL
        """
        self.redis_url = redis_url
        self.redis_client = None
        
        try:
            self.redis_client = redis.from_url(redis_url)
            # 연결 테스트
            self.redis_client.ping()
            logger.info(f"Redis 연결 성공: {redis_url}")
        except Exception as e:
            logger.warning(f"Redis 연결 실패: {e}")
            self.redis_client = None
    
    def cache_search_results(self, query_hash: str, results: List[Dict[str, Any]], ttl: int = 3600):
        """검색 결과를 캐시에 저장"""
        if not self.redis_client:
            return
            
        try:
            cache_key = f"search_results:{query_hash}"
            serialized_results = json.dumps(results, ensure_ascii=False)
            self.redis_client.setex(cache_key, ttl, serialized_results)
            logger.debug(f"검색 결과 캐시 저장: {cache_key}")
        except Exception as e:
            logger.warning(f"검색 결과 캐시 저장 실패: {e}")
    
    def get_cached_search_results(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """캐시에서 검색 결과 조회"""
        if not self.redis_client:
            return None
            
        try:
            cache_key = f"search_results:{query_hash}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                results = json.loads(cached_data)
                logger.debug(f"검색 결과 캐시 히트: {cache_key}")
                return results
        except Exception as e:
            logger.warning(f"검색 결과 캐시 조회 실패: {e}")
        
        return None


class PromptTemplate:
    """프롬프트 템플릿 관리 클래스"""
    
    @staticmethod
    def ticket_summary_template() -> str:
        """티켓 요약 생성용 프롬프트 템플릿"""
        return """
티켓 정보를 분석하여 간결한 마크다운 요약을 작성하세요. 최대 500자 이내로 작성해주세요:

## 📋 상황 요약
[핵심 문제와 현재 상태를 1-2줄로 요약]

## 🔍 주요 내용
- 문제: [구체적인 문제]
- 요청: [고객이 원하는 것]
- 조치: [필요한 조치]

## 💡 핵심 포인트
1. [가장 중요한 포인트]
2. [두 번째 중요한 포인트]

참고: 간결하고 명확하게 작성하되, 핵심 정보는 누락하지 마세요.
"""
    
    @staticmethod
    def issue_solution_template() -> str:
        """Issue/Solution 분석용 프롬프트 템플릿"""
        return """
당신은 고객 지원 티켓을 분석하는 AI입니다. 
제공된 티켓 정보를 바탕으로 문제 상황(Issue)과 해결책(Solution)을 구분해서 분석해주세요. 
정확히 다음 JSON 형식으로만 응답하세요:

{"issue": "구체적인 문제 상황", "solution": "해결책 또는 조치사항"}

다른 설명이나 텍스트를 추가하지 말고 오직 위의 JSON 형식만 반환하세요.
"""


def calculate_embedding_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    두 임베딩 벡터 사이의 코사인 유사도를 계산합니다.
    
    Args:
        embedding1: 첫 번째 임베딩 벡터
        embedding2: 두 번째 임베딩 벡터
        
    Returns:
        코사인 유사도 (-1 ~ 1, 1에 가까울수록 유사)
    """
    import numpy as np
    
    # 벡터를 numpy 배열로 변환
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    # 코사인 유사도 계산
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    return float(similarity)


def optimize_text_for_embedding(text: str, max_length: int = 8000) -> str:
    """
    임베딩 생성을 위해 텍스트를 최적화합니다.
    
    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        
    Returns:
        최적화된 텍스트
    """
    if not text:
        return ""
    
    # 기본 정리
    cleaned_text = text.strip()
    
    # HTML 태그 제거
    import re
    cleaned_text = re.sub(r'<[^>]+>', ' ', cleaned_text)
    
    # 연속된 공백을 단일 공백으로 변환
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    # 길이 제한
    if len(cleaned_text) > max_length:
        cleaned_text = cleaned_text[:max_length]
        logger.warning(f"텍스트가 {max_length}자로 잘렸습니다.")
    
    return cleaned_text


def truncate_text_to_token_limit(text: str, max_tokens: int = 8000, encoding_name: str = "cl100k_base") -> str:
    """
    토큰 제한에 맞춰 텍스트를 자릅니다.
    
    Args:
        text: 원본 텍스트
        max_tokens: 최대 토큰 수
        encoding_name: 토크나이저 인코딩 이름
        
    Returns:
        잘린 텍스트
    """
    try:
        import tiktoken
        
        encoding = tiktoken.get_encoding(encoding_name)
        tokens = encoding.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        # 토큰 제한에 맞춰 자르기
        truncated_tokens = tokens[:max_tokens]
        truncated_text = encoding.decode(truncated_tokens)
        
        logger.warning(f"텍스트가 {len(tokens)}개 토큰에서 {max_tokens}개 토큰으로 잘렸습니다.")
        return truncated_text
        
    except ImportError:
        logger.warning("tiktoken 라이브러리가 없어 단순 문자 수 기반으로 자릅니다.")
        # tiktoken이 없으면 대략적인 계산 (평균 4자 = 1토큰)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            return text[:max_chars]
        return text
    except Exception as e:
        logger.error(f"토큰 계산 중 오류: {e}")
        return text


def extract_section_from_text(text: str, section: str, default: str) -> str:
    """
    텍스트에서 특정 섹션을 추출하는 헬퍼 함수 (확장 버전)
    다양한 형식의 응답에서 문제(issue)와 해결책(solution) 섹션을 정확히 추출합니다.
    """
    import re
    
    # 섹션명을 표준화 (대소문자 무시)
    section_lower = section.lower()
    text_lower = text.lower()
    
    # 한국어/영어 섹션명 매핑
    section_names = {
        'issue': ['issue', '문제', '이슈', '상황', 'problem', '질문'],
        'solution': ['solution', '해결책', '솔루션', '해결 방법', '조치', '대응', '답변', '해결']
    }

    # 현재 섹션에 해당하는 이름들
    current_section_names = section_names.get(section_lower, [section_lower])
    
    # 1. 마크다운 스타일 섹션 찾기 시도 (## Issue, ## Solution 등)
    for name in current_section_names:
        markdown_pattern = rf'(?:#+\s*{name}[\s:]*)|((?<=\n){name}[\s:]+)|(^{name}[\s:]+)'
        section_matches = list(re.finditer(markdown_pattern, text_lower, re.IGNORECASE | re.MULTILINE))
        
        if section_matches:
            start_pos = section_matches[0].end()
            
            # 다음 섹션 찾기 (현재 섹션이 아닌 다른 섹션) - 종료 위치 결정
            end_pos = len(text)
            for next_section in section_names.get('solution' if section_lower == 'issue' else 'issue', []):
                next_section_pattern = rf'(?:#+\s*{next_section}[\s:]*)|((?<=\n){next_section}[\s:]+)|(^{next_section}[\s:]+)'
                next_matches = list(re.finditer(next_section_pattern, text_lower[start_pos:], re.IGNORECASE | re.MULTILINE))
                if next_matches:
                    end_pos = start_pos + next_matches[0].start()
                    break
            
            extracted = text[start_pos:end_pos].strip()
            if extracted:
                return extracted[:500] if len(extracted) > 500 else extracted
    
    # 2. JSON 형식 패턴 (다양한 따옴표 스타일 처리) - 강화된 버전
    json_patterns = []
    for name in current_section_names:
        # 큰 따옴표로 둘러싸인 JSON 키-값
        json_patterns.append(rf'"{name}"[\s:]*"(.*?)(?:"|\n)')
        # 작은 따옴표로 둘러싸인 JSON 키-값
        json_patterns.append(rf"'{name}'[\s:]*'(.*?)(?:'|\n)")
        # 따옴표 혼합 버전
        json_patterns.append(rf'"{name}"[\s:]*\'(.*?)(?:\'|\n)')
        json_patterns.append(rf"'{name}'[\s:]*\"(.*?)(?:\"|\n)")
        # 큰 따옴표 키, 값은 없음
        json_patterns.append(rf'"{name}"[\s:]*([^",\}}]+)')
        # 작은 따옴표 키, 값은 없음
        json_patterns.append(rf"'{name}'[\s:]*([^',\}}]+)")
        # 따옴표 없는 JSON 스타일
        json_patterns.append(rf"{name}[\s:]*([^,\}}]+)")
    
    for pattern in json_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                # 따옴표 제거 (시작/끝에 있는 경우)
                extracted = re.sub(r'^["\']+|["\']+$', '', extracted)
                return extracted[:500] if len(extracted) > 500 else extracted
    
    # 3. 콜론 형식 (다양한 변형) - 강화된 버전
    colon_patterns = []
    for name in current_section_names:
        # 기본 콜론 형식 (다음 섹션까지)
        colon_patterns.append(rf'{name}[\s:]+([^\n].*?)(?=\n\s*\w+:|\Z)')
        # 대문자 섹션명
        colon_patterns.append(rf'{name.upper()}[\s:]+([^\n].*?)(?=\n\s*\w+:|\Z)')
        # 콜론+대시 형식
        colon_patterns.append(rf'{name}[\s:]+-\s*([^\n].*?)(?=\n\s*\w+:|\Z)')
        # 섹션명 다음에 줄바꿈이 있는 경우
        colon_patterns.append(rf'{name}[\s:]*\n+\s*([^\n].*?)(?=\n\s*\w+:|\Z)')
        # 번호형 목록 항목
        colon_patterns.append(rf'\d+[\s.]*{name}[\s:]*([^\n].*?)(?=\n\s*\d+[\s.]*\w+:|\Z)')
    
    for pattern in colon_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted[:500] if len(extracted) > 500 else extracted
    
    # 4. 단락 기반 키워드 검색 - 강화된 버전
    if section_lower in section_names:
        keywords = '|'.join(current_section_names)
        other_keywords = '|'.join(section_names.get('solution' if section_lower == 'issue' else 'issue', []))
        
        # 키워드로 시작하는 단락 찾기
        keyword_paragraph_pattern = rf'(?:^|\n|\s)(?:{keywords})[\s:]+(.*?)(?=(?:^|\n|\s)(?:{other_keywords})[\s:]|$)'
        match = re.search(keyword_paragraph_pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                return extracted[:500] if len(extracted) > 500 else extracted
                
        # 키워드 기반 세분화된 검색
        if section_lower == 'issue':
            issue_indicators = ['고객이', '문제는', '상황은', '이슈는', '오류', 'error', 'problem is']
            for indicator in issue_indicators:
                indicator_match = re.search(rf'{indicator}[^\n]*', text, re.IGNORECASE)
                if indicator_match:
                    return indicator_match.group(0)[:500]
        elif section_lower == 'solution':
            solution_indicators = ['해결 방법', '해결하려면', '권장', '제안', '다음과 같이', '조치', '대응']
            for indicator in solution_indicators:
                indicator_match = re.search(rf'{indicator}[^\n]*', text, re.IGNORECASE)
                if indicator_match:
                    # 해당 문장부터 이후 200자 추출
                    start = indicator_match.start()
                    return text[start:start+300].strip()[:500]
    
    # 5. 위치 기반 추출 (강화된 휴리스틱) - 텍스트 분석 기반 추출
    if section_lower == "issue":
        # issue는 주로 앞쪽에 나타남
        # 텍스트 길이에 따라 적응적으로 추출 비율 조정
        if len(text) < 200:
            return text[:len(text)].strip() if text else default
        elif len(text) < 500:
            return text[:len(text)//2].strip() if text else default
        else:
            # 첫 문단이나 처음 25% 텍스트 반환
            first_paragraph_match = re.search(r'^.*?\n\s*\n', text, re.DOTALL)
            if first_paragraph_match and len(first_paragraph_match.group(0)) > 20:
                return first_paragraph_match.group(0).strip()
            return text[:len(text)//4].strip()[:500]
            
    elif section_lower == "solution":
        # solution은 주로 뒤쪽에 나타남
        if len(text) < 200:
            return text.strip() if text else default
            
        # 텍스트 길이에 따라 적응적으로 추출 비율 조정
        if len(text) < 500:
            return text[len(text)//2:].strip()
        else:
            # 마지막 문단이나 마지막 30% 텍스트 반환
            last_paragraphs = text[int(len(text)*0.7):].strip()
            if last_paragraphs:
                return last_paragraphs[:500]
                
            # 마지막 두 문단 찾기 시도
            paragraphs = re.split(r'\n\s*\n', text)
            if len(paragraphs) >= 2:
                return '\n\n'.join(paragraphs[-2:])[:500]
        
    return default

def validate_api_keys():
    """API 키 유효성 검증"""
    missing_keys = []
    
    if not ANTHROPIC_API_KEY:
        missing_keys.append("ANTHROPIC_API_KEY")
    if not OPENAI_API_KEY:
        missing_keys.append("OPENAI_API_KEY")
    if not GOOGLE_API_KEY:
        missing_keys.append("GOOGLE_API_KEY")
        
    if missing_keys:
        logger.warning(f"다음 API 키가 설정되지 않았습니다: {', '.join(missing_keys)}")
    
    return len(missing_keys) == 0
