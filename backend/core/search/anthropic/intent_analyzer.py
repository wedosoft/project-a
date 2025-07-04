"""
Anthropic 의도 분석기 (상담원 채팅 전용)

상담원의 자연어 요청을 분석하여 검색 의도, 우선순위, 키워드, 필터를 추출합니다.
기존 하이브리드 검색 시스템과 통합하여 정확한 검색 결과를 제공합니다.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchContext:
    """검색 컨텍스트 정보"""
    intent: str
    urgency: str
    keywords: List[str]
    filters: Dict[str, Any]
    original_query: str
    clean_query: str


class AnthropicIntentAnalyzer:
    """
    상담원 채팅을 위한 의도 분석기
    
    자연어 쿼리를 분석하여 다음 정보를 추출합니다:
    - 의도 분류 (problem_solving, info_gathering, learning, analysis)
    - 우선순위 (immediate, today, general, reference)
    - 키워드 추출
    - 검색 필터 (날짜, 카테고리, 상태 등)
    """
    
    def __init__(self):
        self.intents = ["problem_solving", "info_gathering", "learning", "analysis"]
        self.urgency_levels = ["immediate", "today", "general", "reference"]
        
        # 지원하는 검색 패턴 정의
        self.search_patterns = {
            "시간": {
                "keywords": ["오늘", "이번 주", "최근", "지난", "어제"],
                "examples": ["오늘 생성된 티켓", "이번 주 해결된 케이스"]
            },
            "카테고리": {
                "keywords": ["결제", "로그인", "API", "기술", "계정"],
                "examples": ["결제 문제", "API 오류"]
            },
            "복합": {
                "keywords": ["긴급", "VIP", "중요", "우선순위"],
                "examples": ["긴급한 VIP 고객 API 문제"]
            }
        }
    
    async def analyze_search_intent(self, query: str, context: Optional[Dict[str, Any]] = None) -> SearchContext:
        """
        검색 의도를 분석하여 SearchContext 반환
        
        Args:
            query: 상담원의 자연어 쿼리
            context: 추가 컨텍스트 정보 (선택사항)
            
        Returns:
            SearchContext: 분석된 검색 컨텍스트
        """
        try:
            logger.info(f"상담원 쿼리 분석 시작: '{query[:50]}...'")
            
            # 1. 의도 분류
            intent = self._classify_intent(query)
            
            # 2. 우선순위 평가
            urgency = self._assess_urgency(query)
            
            # 3. 키워드 추출
            keywords = self._extract_keywords(query)
            
            # 4. 필터 파싱
            filters = self._parse_filters(query)
            
            # 5. 쿼리 정제
            clean_query = self._clean_query(query)
            
            search_context = SearchContext(
                intent=intent,
                urgency=urgency,
                keywords=keywords,
                filters=filters,
                original_query=query,
                clean_query=clean_query
            )
            
            logger.info(f"의도 분석 완료: intent={intent}, urgency={urgency}, keywords={len(keywords)}개")
            return search_context
            
        except Exception as e:
            logger.error(f"의도 분석 실패: {e}")
            # 기본 컨텍스트 반환
            return SearchContext(
                intent="general",
                urgency="general",
                keywords=[query],
                filters={},
                original_query=query,
                clean_query=query
            )
    
    def _classify_intent(self, query: str) -> str:
        """
        쿼리의 의도를 분류합니다
        
        Returns:
            str: 분류된 의도 (problem_solving, info_gathering, learning, analysis)
        """
        query_lower = query.lower()
        
        # 문제 해결 의도
        problem_keywords = ["해결", "문제", "오류", "에러", "고장", "안됨", "방법", "어떻게"]
        if any(keyword in query_lower for keyword in problem_keywords):
            return "problem_solving"
        
        # 정보 수집 의도
        info_keywords = ["찾아", "검색", "알려", "보여", "확인", "조회"]
        if any(keyword in query_lower for keyword in info_keywords):
            return "info_gathering"
        
        # 학습 의도
        learning_keywords = ["배우", "공부", "이해", "설명", "가이드", "튜토리얼"]
        if any(keyword in query_lower for keyword in learning_keywords):
            return "learning"
        
        # 분석 의도
        analysis_keywords = ["통계", "분석", "현황", "상태", "몇개", "얼마나", "트렌드"]
        if any(keyword in query_lower for keyword in analysis_keywords):
            return "analysis"
        
        return "general"
    
    def _assess_urgency(self, query: str) -> str:
        """
        쿼리의 우선순위를 평가합니다
        
        Returns:
            str: 우선순위 (immediate, today, general, reference)
        """
        query_lower = query.lower()
        
        # 즉시 처리 필요
        immediate_keywords = ["긴급", "urgent", "지금", "당장", "빨리", "급해"]
        if any(keyword in query_lower for keyword in immediate_keywords):
            return "immediate"
        
        # 오늘 처리 필요
        today_keywords = ["오늘", "today", "금일", "현재", "지금"]
        if any(keyword in query_lower for keyword in today_keywords):
            return "today"
        
        # 참고용
        reference_keywords = ["참고", "reference", "나중에", "여유", "틈날때"]
        if any(keyword in query_lower for keyword in reference_keywords):
            return "reference"
        
        return "general"
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        쿼리에서 중요한 키워드를 추출합니다
        
        Returns:
            List[str]: 추출된 키워드 목록
        """
        # 기본 키워드 추출 (공백 기준)
        basic_keywords = query.split()
        
        # 불용어 제거
        stop_words = {
            "의", "가", "이", "은", "는", "을", "를", "에", "에서", "로", "으로",
            "와", "과", "그리고", "또는", "하지만", "그러나", "그래서", "따라서",
            "찾아", "보여", "알려", "해줘", "주세요", "주시기", "바랍니다"
        }
        
        keywords = [kw for kw in basic_keywords if kw not in stop_words and len(kw) > 1]
        
        # 특수 키워드 패턴 추가
        special_patterns = {
            r"API\s*[오오류류]": ["API", "오류"],
            r"결제\s*[문제]": ["결제", "문제"],
            r"로그인\s*[이슈문제]": ["로그인", "문제"],
            r"VIP\s*[고객]": ["VIP", "고객"]
        }
        
        for pattern, pattern_keywords in special_patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                keywords.extend(pattern_keywords)
        
        # 중복 제거하면서 순서 유지
        unique_keywords = []
        for keyword in keywords:
            if keyword not in unique_keywords:
                unique_keywords.append(keyword)
        
        return unique_keywords[:10]  # 최대 10개까지만
    
    def _parse_filters(self, query: str) -> Dict[str, Any]:
        """
        쿼리에서 검색 필터를 추출합니다
        
        Returns:
            Dict[str, Any]: 추출된 필터 정보
        """
        filters = {}
        
        # 1. 날짜 필터
        date_filter = self._extract_date_filter(query)
        if date_filter:
            filters.update(date_filter)
        
        # 2. 우선순위 필터
        priority_filter = self._extract_priority_filter(query)
        if priority_filter:
            filters["priority"] = priority_filter
        
        # 3. 상태 필터
        status_filter = self._extract_status_filter(query)
        if status_filter:
            filters["status"] = status_filter
        
        # 4. 카테고리 필터
        category_filter = self._extract_category_filter(query)
        if category_filter:
            filters["category"] = category_filter
        
        # 5. 문서 타입 필터
        doc_type_filter = self._extract_doc_type_filter(query)
        if doc_type_filter:
            filters["doc_types"] = doc_type_filter
        
        return filters
    
    def _extract_date_filter(self, query: str) -> Optional[Dict[str, Any]]:
        """날짜 관련 필터 추출"""
        date_patterns = [
            (r"오늘", {"date_range": self._get_date_range(1)}),
            (r"어제", {"date_range": self._get_date_range(1, offset_days=1)}),
            (r"지난\s*(\d+)\s*일", "last_days"),
            (r"이번\s*주|지난\s*주", {"date_range": self._get_date_range(7)}),
            (r"이번\s*달|지난\s*달", {"date_range": self._get_date_range(30)}),
            (r"최근", {"date_range": self._get_date_range(7)})
        ]
        
        for pattern, filter_data in date_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if isinstance(filter_data, dict):
                    return filter_data
                elif filter_data == "last_days":
                    days = int(match.group(1))
                    return {"date_range": self._get_date_range(days)}
        
        return None
    
    def _extract_priority_filter(self, query: str) -> Optional[List[str]]:
        """우선순위 필터 추출"""
        priority_patterns = [
            (r"긴급|urgent", ["urgent", "high"]),
            (r"높은\s*우선순위|high", ["high"]),
            (r"중요한?", ["high", "medium"]),
            (r"낮은\s*우선순위|low", ["low"])
        ]
        
        for pattern, priorities in priority_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return priorities
        
        return None
    
    def _extract_status_filter(self, query: str) -> Optional[List[str]]:
        """상태 필터 추출"""
        status_patterns = [
            (r"해결된?|solved|closed", ["solved", "closed"]),
            (r"진행\s*중|pending|open", ["open", "pending"]),
            (r"대기|waiting", ["waiting_on_customer", "waiting_on_third_party"]),
            (r"새로운?|new", ["new"])
        ]
        
        for pattern, statuses in status_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return statuses
        
        return None
    
    def _extract_category_filter(self, query: str) -> Optional[str]:
        """카테고리 필터 추출"""
        category_patterns = [
            (r"결제|billing|payment", "billing"),
            (r"로그인|login|auth", "authentication"),
            (r"기술\s*지원|technical", "technical"),
            (r"계정|account", "account"),
            (r"API", "api"),
            (r"네트워크|network", "network"),
            (r"보안|security", "security")
        ]
        
        for pattern, category in category_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return category
        
        return None
    
    def _extract_doc_type_filter(self, query: str) -> Optional[List[str]]:
        """문서 타입 필터 추출"""
        doc_type_patterns = [
            (r"티켓|ticket", ["ticket"]),
            (r"지식베이스|KB|knowledge", ["article", "kb"]),
            (r"문서|document", ["article"]),
            (r"첨부파일|attachment", ["attachment"])
        ]
        
        for pattern, doc_types in doc_type_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return doc_types
        
        return None
    
    def _clean_query(self, query: str) -> str:
        """
        쿼리에서 필터 키워드를 제거하고 정제합니다
        
        Returns:
            str: 정제된 쿼리
        """
        clean_query = query
        
        # 필터 키워드 제거 패턴
        filter_patterns = [
            r"오늘|어제|지난\s*\d+\s*일|이번\s*주|지난\s*주|이번\s*달|지난\s*달|최근",
            r"긴급|urgent|높은\s*우선순위|중요한?|낮은\s*우선순위",
            r"해결된?|solved|closed|진행\s*중|pending|open|대기|waiting|새로운?",
            r"찾아|보여|알려|해줘|주세요|주시기|바랍니다"
        ]
        
        for pattern in filter_patterns:
            clean_query = re.sub(pattern, "", clean_query, flags=re.IGNORECASE)
        
        # 여러 공백을 하나로 통합하고 앞뒤 공백 제거
        clean_query = re.sub(r'\s+', ' ', clean_query).strip()
        
        return clean_query if clean_query else query
    
    def _get_date_range(self, days: int, offset_days: int = 0) -> Dict[str, str]:
        """
        날짜 범위를 계산합니다
        
        Args:
            days: 기간 (일)
            offset_days: 오프셋 (일)
            
        Returns:
            Dict[str, str]: 시작일과 종료일
        """
        end_date = datetime.now() - timedelta(days=offset_days)
        start_date = end_date - timedelta(days=days)
        
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }