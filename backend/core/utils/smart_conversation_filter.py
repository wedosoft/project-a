"""
스마트 대화 필터링 유틸리티

대화 내용을 효율적으로 필터링하여 중요한 정보만 추출합니다.
단일 패스로 모든 처리를 완료하여 성능을 최적화합니다.
"""

import re
from typing import List, Dict, Any, Tuple, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SmartConversationFilter:
    """스마트 대화 필터링 클래스"""
    
    # 중요도 점수 가중치
    WEIGHT_KEYWORDS = 0.4
    WEIGHT_SENTIMENT = 0.2
    WEIGHT_LENGTH = 0.1
    WEIGHT_ATTACHMENTS = 0.2
    WEIGHT_POSITION = 0.1
    
    # 중요 키워드 (언어별)
    IMPORTANT_KEYWORDS = {
        'ko': {
            'problem': ['오류', '에러', '문제', '버그', '장애', '이슈', '안됨', '안돼', '실패', '중단'],
            'solution': ['해결', '수정', '완료', '처리', '조치', '배포', '업데이트', '패치'],
            'action': ['확인', '진행', '작업', '테스트', '검토', '분석', '조사'],
            'urgent': ['긴급', '중요', '시급', '즉시', '빠르게', 'ASAP'],
        },
        'en': {
            'problem': ['error', 'bug', 'issue', 'problem', 'fail', 'crash', 'broken', 'wrong'],
            'solution': ['solved', 'fixed', 'resolved', 'completed', 'deployed', 'updated', 'patched'],
            'action': ['check', 'verify', 'test', 'analyze', 'investigate', 'review', 'working'],
            'urgent': ['urgent', 'critical', 'important', 'asap', 'immediately', 'priority'],
        }
    }
    
    # 감정 표현 키워드
    SENTIMENT_KEYWORDS = {
        'positive': ['감사', '고맙', '좋', '훌륭', '완벽', 'thank', 'great', 'perfect', 'excellent'],
        'negative': ['불만', '화남', '실망', '최악', '형편없', 'angry', 'disappointed', 'terrible', 'worst'],
    }
    
    def __init__(self, max_conversations: int = 20, max_chars_per_conv: int = 1000):
        """
        Args:
            max_conversations: 최대 선택할 대화 수
            max_chars_per_conv: 대화당 최대 문자 수
        """
        self.max_conversations = max_conversations
        self.max_chars_per_conv = max_chars_per_conv
        
    def filter_conversations(
        self, 
        conversations: List[Dict[str, Any]], 
        ticket_metadata: Dict[str, Any] = None
    ) -> Tuple[List[int], Dict[str, Any]]:
        """
        대화를 스마트하게 필터링합니다 (단일 패스)
        
        Args:
            conversations: 대화 목록
            ticket_metadata: 티켓 메타데이터 (선택적)
            
        Returns:
            (선택된 대화 인덱스 리스트, 분석 메타데이터)
        """
        if not conversations:
            return [], {}
            
        total_conversations = len(conversations)
        
        # 15개 이하는 모두 포함
        if total_conversations <= 15:
            return list(range(total_conversations)), {
                'method': 'all_included',
                'total': total_conversations,
                'selected': total_conversations
            }
        
        # 단일 패스로 모든 분석 수행
        conversation_scores = []
        detected_language = 'en'  # 기본값
        
        for idx, conv in enumerate(conversations):
            body = conv.get('body_text', '')
            if not body:
                continue
                
            # 1. 언어 감지 (첫 몇 개 대화에서만)
            if idx < 5 and not detected_language:
                if any(korean_char in body for korean_char in '가나다라마바사아자차카타파하'):
                    detected_language = 'ko'
            
            # 2. 중요도 점수 계산
            score = self._calculate_importance_score(
                conv, idx, total_conversations, detected_language
            )
            
            conversation_scores.append({
                'index': idx,
                'score': score,
                'has_attachment': bool(conv.get('attachments')),
                'length': len(body),
                'preview': body[:100]
            })
        
        # 3. 상위 점수 대화 선택
        conversation_scores.sort(key=lambda x: x['score'], reverse=True)
        
        # 필수 포함: 처음 3개와 마지막 3개
        selected_indices = set()
        selected_indices.update(range(min(3, total_conversations)))
        selected_indices.update(range(max(0, total_conversations - 3), total_conversations))
        
        # 점수 기반 추가 선택
        for item in conversation_scores:
            if len(selected_indices) >= self.max_conversations:
                break
            selected_indices.add(item['index'])
        
        # 정렬된 인덱스 반환
        selected_indices = sorted(selected_indices)
        
        # 분석 메타데이터
        metadata = {
            'method': 'smart_filter',
            'total': total_conversations,
            'selected': len(selected_indices),
            'language': detected_language,
            'avg_score': sum(item['score'] for item in conversation_scores) / len(conversation_scores) if conversation_scores else 0,
            'top_scores': [item['score'] for item in conversation_scores[:5]]
        }
        
        return selected_indices, metadata
    
    def _calculate_importance_score(
        self, 
        conv: Dict[str, Any], 
        idx: int, 
        total: int,
        language: str
    ) -> float:
        """대화의 중요도 점수를 계산합니다"""
        body = conv.get('body_text', '').lower()
        score = 0.0
        
        # 1. 키워드 점수
        keyword_score = 0.0
        keywords = self.IMPORTANT_KEYWORDS.get(language, self.IMPORTANT_KEYWORDS['en'])
        
        for category, words in keywords.items():
            category_weight = {
                'problem': 0.3,
                'solution': 0.4,
                'action': 0.2,
                'urgent': 0.1
            }.get(category, 0.1)
            
            if any(word in body for word in words):
                keyword_score += category_weight
        
        score += keyword_score * self.WEIGHT_KEYWORDS
        
        # 2. 감정 점수
        sentiment_score = 0.0
        for sentiment, words in self.SENTIMENT_KEYWORDS.items():
            if any(word in body for word in words):
                sentiment_score += 0.5 if sentiment == 'negative' else 0.3
        
        score += sentiment_score * self.WEIGHT_SENTIMENT
        
        # 3. 길이 점수 (적당한 길이 선호)
        length = len(body)
        if 100 <= length <= 500:
            length_score = 1.0
        elif 50 <= length < 100 or 500 < length <= 1000:
            length_score = 0.7
        else:
            length_score = 0.3
        
        score += length_score * self.WEIGHT_LENGTH
        
        # 4. 첨부파일 점수
        if conv.get('attachments'):
            score += self.WEIGHT_ATTACHMENTS
        
        # 5. 위치 점수 (처음과 끝 선호)
        position_ratio = idx / max(total - 1, 1)
        if position_ratio <= 0.2 or position_ratio >= 0.8:
            position_score = 1.0
        elif position_ratio <= 0.4 or position_ratio >= 0.6:
            position_score = 0.7
        else:
            position_score = 0.4
        
        score += position_score * self.WEIGHT_POSITION
        
        return min(score, 1.0)  # 최대 1.0으로 제한
    
    def format_conversations(
        self,
        conversations: List[Dict[str, Any]],
        selected_indices: List[int]
    ) -> List[str]:
        """선택된 대화를 포맷팅합니다"""
        formatted = []
        
        for idx in selected_indices:
            if idx >= len(conversations):
                continue
                
            conv = conversations[idx]
            body = conv.get('body_text', '')
            
            if body:
                # 문자 수 제한
                if len(body) > self.max_chars_per_conv:
                    body = body[:self.max_chars_per_conv] + '...'
                
                # 포맷팅
                formatted_text = f"대화 {idx + 1}: {body}"
                
                # 첨부파일 정보 추가
                if conv.get('attachments'):
                    attach_count = len(conv['attachments'])
                    formatted_text += f" [첨부파일 {attach_count}개]"
                
                formatted.append(formatted_text)
        
        return formatted