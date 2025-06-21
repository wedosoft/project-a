"""
키워드 패턴 관리자

다국어 키워드 패턴을 로드하고 관리합니다.
"""

import json
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class KeywordPatternManager:
    """다국어 키워드 패턴을 관리하는 클래스"""
    
    def __init__(self):
        self.patterns = {}
        self._load_patterns()
    
    def _load_patterns(self) -> Dict[str, Any]:
        """
        다국어 키워드 패턴 로드
        
        Returns:
            Dict: 언어별 키워드 패턴
        """
        try:
            # 백엔드 config 디렉토리에서 키워드 파일 로드
            config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "multilingual_keywords.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.patterns = json.load(f)
                    logger.info(f"다국어 키워드 패턴 로드 완료: {list(self.patterns.keys())} 언어")
            else:
                logger.warning(f"키워드 패턴 파일을 찾을 수 없습니다: {config_path}")
                self.patterns = self._get_default_patterns()
                
        except Exception as e:
            logger.error(f"키워드 패턴 로드 중 오류: {e}")
            self.patterns = self._get_default_patterns()
    
    def _get_default_patterns(self) -> Dict[str, Any]:
        """
        기본 키워드 패턴 반환 (파일 로드 실패 시 폴백)
        
        Returns:
            Dict: 기본 다국어 키워드 패턴
        """
        return {
            "ko": {
                "high_importance": {
                    "problem_indicators": ["문제", "오류", "에러", "안됩니다", "고장", "버그"],
                    "solution_indicators": ["해결", "방법", "해결책", "시도해보세요", "확인해보세요"],
                    "conclusion_indicators": ["해결됐습니다", "완료", "감사합니다", "종료"],
                    "escalation_indicators": ["긴급", "중요", "빠르게", "우선순위"]
                },
                "medium_importance": {
                    "question_indicators": ["질문", "문의", "궁금", "어떻게", "왜"],
                    "followup_indicators": ["추가로", "그런데", "또한", "참고로"],
                    "confirmation_indicators": ["확인", "맞나요", "정확한가요"]
                },
                "low_importance": {
                    "greeting_indicators": ["안녕하세요", "수고하세요", "감사합니다만"],
                    "filler_indicators": ["그냥", "뭔가", "좀", "약간"]
                }
            },
            "en": {
                "high_importance": {
                    "problem_indicators": ["issue", "problem", "error", "bug", "not working", "broken"],
                    "solution_indicators": ["solution", "fix", "resolve", "try", "please check"],
                    "conclusion_indicators": ["resolved", "fixed", "solved", "completed"],
                    "escalation_indicators": ["urgent", "critical", "asap", "priority"]
                },
                "medium_importance": {
                    "question_indicators": ["question", "how", "what", "why", "when", "where"],
                    "followup_indicators": ["also", "additionally", "furthermore", "moreover"],
                    "confirmation_indicators": ["confirm", "correct", "right", "accurate"]
                },
                "low_importance": {
                    "greeting_indicators": ["hello", "hi", "good morning", "thanks anyway"],
                    "filler_indicators": ["just", "maybe", "probably", "somewhat"]
                }
            }
        }
    
    def get_patterns(self) -> Dict[str, Any]:
        """키워드 패턴 반환"""
        return self.patterns
    
    def reload_patterns(self):
        """패턴을 다시 로드"""
        self._load_patterns()
