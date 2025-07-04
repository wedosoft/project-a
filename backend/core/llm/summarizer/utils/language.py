"""
Language detection and processing utilities
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LanguageProfile:
    """Language characteristics profile"""
    code: str
    name: str
    confidence: float
    character_ratio: float
    keyword_matches: int
    total_chars: int


class LanguageDetector:
    """
    Advanced language detection for multilingual content
    """
    
    def __init__(self):
        self.language_patterns = {
            'ko': {
                'char_range': ('\uac00', '\ud7af'),  # Hangul syllables
                'keywords': ['입니다', '합니다', '있습니다', '됩니다', '해서', '에서', '으로', '에게', '의해'],
                'punctuation': ['。', '？', '！']
            },
            'ja': {
                'char_range': [('\u3040', '\u309f'), ('\u30a0', '\u30ff')],  # Hiragana + Katakana
                'keywords': ['です', 'ます', 'である', 'として', 'について', 'により', 'において'],
                'punctuation': ['。', '？', '！']
            },
            'zh': {
                'char_range': ('\u4e00', '\u9fff'),  # CJK Unified Ideographs
                'keywords': ['的', '了', '是', '在', '有', '和', '为', '这', '也', '或'],
                'punctuation': ['。', '？', '！', '，']
            },
            'en': {
                'keywords': ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had'],
                'punctuation': ['.', '?', '!', ',']
            }
        }
        
        self.section_titles = {
            'ko': {
                'problem': '🔍 **문제 상황**',
                'cause': '🎯 **근본 원인**', 
                'solution': '🔧 **해결 과정**',
                'insights': '💡 **핵심 포인트**'
            },
            'en': {
                'problem': '🔍 **Problem Situation**',
                'cause': '🎯 **Root Cause**',
                'solution': '🔧 **Resolution Process**', 
                'insights': '💡 **Key Insights**'
            },
            'ja': {
                'problem': '🔍 **問題状況**',
                'cause': '🎯 **根本原因**',
                'solution': '🔧 **解決プロセス**',
                'insights': '💡 **重要なポイント**'
            },
            'zh': {
                'problem': '🔍 **问题情况**',
                'cause': '🎯 **根本原因**',
                'solution': '🔧 **解决过程**',
                'insights': '💡 **关键要点**'
            }
        }
    
    def detect_language(self, text: str, detailed: bool = False) -> str | LanguageProfile:
        """
        Detect the primary language of the text
        
        Args:
            text: Text to analyze
            detailed: Whether to return detailed analysis
            
        Returns:
            Language code or detailed LanguageProfile
        """
        if not text or len(text.strip()) < 10:
            # 짧은 텍스트의 경우 한국어를 기본값으로 사용 (UI 언어와 일치)
            return 'ko' if not detailed else LanguageProfile('ko', 'Korean', 0.5, 0.0, 0, len(text))
        
        profiles = []
        
        for lang_code, lang_config in self.language_patterns.items():
            profile = self._analyze_language(text, lang_code, lang_config)
            profiles.append(profile)
        
        # Sort by confidence
        profiles.sort(key=lambda x: x.confidence, reverse=True)
        
        if detailed:
            return profiles[0]
        else:
            return profiles[0].code
    
    def _analyze_language(self, text: str, lang_code: str, config: Dict[str, Any]) -> LanguageProfile:
        """Analyze text for specific language characteristics"""
        total_chars = len(text)
        confidence = 0.0
        character_ratio = 0.0
        keyword_matches = 0
        
        if total_chars == 0:
            return LanguageProfile(lang_code, lang_code.upper(), 0.0, 0.0, 0, 0)
        
        # Character-based analysis
        if 'char_range' in config:
            char_count = 0
            char_ranges = config['char_range']
            
            if isinstance(char_ranges, tuple):
                char_ranges = [char_ranges]
            
            for char_range in char_ranges:
                start_char, end_char = char_range
                char_count += sum(1 for c in text if start_char <= c <= end_char)
            
            character_ratio = char_count / total_chars
            # Give Korean stronger weight when Korean characters are present
            if lang_code == 'ko' and character_ratio > 0.2:
                # Korean content with good character ratio gets boosted confidence
                korean_boost = character_ratio * 0.7  # Increased from 0.6 to 0.7
                logger.debug(f"Korean content boost: {korean_boost:.2f} (char ratio: {character_ratio:.2f})")
                confidence += korean_boost
            else:
                confidence += character_ratio * 0.6
        
        # Keyword-based analysis
        if 'keywords' in config:
            text_lower = text.lower()
            keyword_matches = sum(1 for keyword in config['keywords'] if keyword in text_lower)
            keyword_score = min(keyword_matches / len(config['keywords']), 1.0)
            confidence += keyword_score * 0.3
        
        # Punctuation analysis
        if 'punctuation' in config:
            punct_count = sum(1 for punct in config['punctuation'] if punct in text)
            punct_ratio = min(punct_count / (total_chars / 100), 1.0)  # Normalize by text length
            confidence += punct_ratio * 0.1
        
        # Language-specific adjustments
        if lang_code == 'en' and character_ratio == 0.0:
            # For English, high ASCII ratio is a good indicator, but be careful with mixed-language content
            ascii_ratio = sum(1 for c in text if ord(c) < 128) / total_chars
            
            # Check if this might be mixed content with significant Korean characters
            korean_char_count = sum(1 for c in text if '\uac00' <= c <= '\ud7af')
            korean_ratio = korean_char_count / total_chars
            
            # If Korean characters are significant (>20%), reduce English confidence boost
            if korean_ratio > 0.2:
                # Mixed content: reduce English confidence boost
                ascii_boost = ascii_ratio * 0.4  # Reduced from 0.8 to 0.4
                logger.debug(f"Mixed content detected (Korean: {korean_ratio:.2f}), reducing English boost to {ascii_boost:.2f}")
            else:
                # Pure ASCII content: full confidence boost
                ascii_boost = ascii_ratio * 0.8
            
            confidence = max(confidence, ascii_boost)
        
        return LanguageProfile(
            code=lang_code,
            name=lang_code.upper(),
            confidence=min(confidence, 1.0),
            character_ratio=character_ratio,
            keyword_matches=keyword_matches,
            total_chars=total_chars
        )
    
    def get_section_titles(self, language: str = 'ko') -> Dict[str, str]:
        """Get section titles for specified language"""
        return self.section_titles.get(language, self.section_titles['ko'])
    
    def get_mixed_language_content(self, text: str) -> Dict[str, float]:
        """Analyze mixed language content ratios"""
        results = {}
        
        for lang_code in self.language_patterns.keys():
            profile = self._analyze_language(text, lang_code, self.language_patterns[lang_code])
            results[lang_code] = profile.confidence
        
        return results


class TextProcessor:
    """
    Advanced text processing utilities
    """
    
    def __init__(self):
        self.language_detector = LanguageDetector()
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for processing"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove trailing whitespace
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        
        # Normalize quotes
        text = re.sub(r'["""]', '"', text)
        text = re.sub(r"[''']", "'", text)
        
        return text.strip()
    
    def extract_key_phrases(self, text: str, language: str = 'auto') -> List[str]:
        """Extract key phrases from text"""
        if language == 'auto':
            language = self.language_detector.detect_language(text)
        
        phrases = []
        
        # Look for quoted phrases
        quoted_phrases = re.findall(r'"([^"]+)"', text)
        phrases.extend([phrase.strip() for phrase in quoted_phrases if len(phrase.strip()) > 3])
        
        # Look for emphasized text
        emphasized = re.findall(r'\*\*([^*]+)\*\*', text)
        phrases.extend([phrase.strip() for phrase in emphasized if len(phrase.strip()) > 3])
        
        # Look for technical terms (words with dots, hyphens, or mixed case)
        technical_terms = re.findall(r'\b[A-Za-z]+(?:[.-][A-Za-z0-9]+)+\b', text)
        phrases.extend(technical_terms)
        
        # Language-specific phrase extraction
        if language == 'ko':
            # Korean compound nouns and technical terms
            korean_phrases = re.findall(r'[가-힣]{2,}(?:\s+[가-힣]{2,})*', text)
            phrases.extend([phrase.strip() for phrase in korean_phrases if len(phrase.strip()) > 4])
        
        # Remove duplicates and filter
        unique_phrases = []
        for phrase in phrases:
            cleaned = phrase.strip()
            if cleaned and len(cleaned) > 2 and cleaned not in unique_phrases:
                unique_phrases.append(cleaned)
        
        return unique_phrases[:10]  # Return top 10 phrases
    
    def calculate_text_complexity(self, text: str) -> Dict[str, Any]:
        """Calculate various text complexity metrics"""
        if not text:
            return {'complexity_score': 0.0, 'metrics': {}}
        
        sentences = text.split('.')
        words = text.split()
        
        metrics = {
            'total_characters': len(text),
            'total_words': len(words),
            'total_sentences': len([s for s in sentences if s.strip()]),
            'avg_words_per_sentence': len(words) / max(len(sentences), 1),
            'avg_chars_per_word': len(text) / max(len(words), 1),
            'unique_words': len(set(word.lower() for word in words)),
            'vocabulary_ratio': len(set(word.lower() for word in words)) / max(len(words), 1)
        }
        
        # Calculate complexity score (0.0 to 1.0)
        complexity_factors = [
            min(metrics['avg_words_per_sentence'] / 20, 1.0),  # Sentence length
            min(metrics['avg_chars_per_word'] / 10, 1.0),      # Word length
            metrics['vocabulary_ratio'],                        # Vocabulary diversity
            min(len(re.findall(r'[,;:(){}[\]]', text)) / max(len(words), 1), 1.0)  # Punctuation density
        ]
        
        complexity_score = sum(complexity_factors) / len(complexity_factors)
        
        return {
            'complexity_score': round(complexity_score, 3),
            'metrics': metrics,
            'readability_level': self._get_readability_level(complexity_score)
        }
    
    def _get_readability_level(self, score: float) -> str:
        """Get readability level description"""
        if score < 0.3:
            return "Simple"
        elif score < 0.5:
            return "Moderate"  
        elif score < 0.7:
            return "Complex"
        else:
            return "Very Complex"


# Global instances
language_detector = LanguageDetector()
text_processor = TextProcessor()


async def detect_content_language_llm(content: str, ui_language: str = 'ko') -> str:
    """
    LLM 기반 언어 감지 - 정확성과 다국어 지원 향상 (성능 최적화: 규칙 기반 우선)
    
    Args:
        content: Content to analyze
        ui_language: UI language preference (used for short/ambiguous content)
    
    Returns:
        Detected or preferred language code
    """
    # 매우 짧은 텍스트는 UI 언어 사용
    if not content or len(content.strip()) < 20:
        logger.debug(f"짧은 콘텐츠({len(content)}자) - UI 언어 '{ui_language}' 적용")
        return ui_language
    
    # 🚀 하이브리드 접근: 규칙 기반 먼저 시도, 애매할 때만 LLM 사용
    try:
        rule_based_result = detect_content_language(content, ui_language)
        
        # 규칙 기반이 명확한 결과를 줄 때는 LLM 호출 생략 (성능 최적화)
        confidence_indicators = [
            len([c for c in content if ord(c) > 0x1100 and ord(c) < 0x11FF]),  # 한글
            len([c for c in content if ord(c) > 0x4E00 and ord(c) < 0x9FFF]),  # 중문
            len([c for c in content if ord(c) > 0x3040 and ord(c) < 0x309F])   # 일문
        ]
        max_confidence = max(confidence_indicators)
        
        # 특정 언어 문자가 많으면 (전체의 30% 이상) 규칙 기반 결과 신뢰
        if max_confidence > len(content) * 0.3:
            logger.debug(f"고신뢰도 규칙 기반 언어 감지: '{rule_based_result}' (LLM 호출 생략)")
            return rule_based_result
            
    except Exception as e:
        logger.debug(f"규칙 기반 언어 감지 실패: {e}")
    
    # 애매한 경우에만 LLM 사용 (다국어 정확성 보장)
    
    try:
        # LLM을 통한 언어 감지
        from core.llm.manager import LLMManager
        
        # 빠른 모델로 언어 판단 (토큰 절약)
        truncated_content = content[:800] if len(content) > 800 else content
        
        prompt = f"""텍스트의 주요 언어를 판단하세요. 기술용어나 다른 언어 단어가 섞여있어도 전체 맥락에서 주요 언어를 판단하세요.

지원 언어:
- ko: 한국어
- en: 영어  
- ja: 일본어
- zh: 중국어

텍스트:
{truncated_content}

응답 형식: 언어코드만 (ko/en/ja/zh)"""

        llm_manager = LLMManager()
        
        # 빠른 모델로 언어 감지 - LLMRequest 대신 직접 generate 호출
        messages = [{"role": "user", "content": prompt}]
        response_obj = await llm_manager.generate(
            messages=messages,
            max_tokens=10,
            temperature=0.0
        )
        response = response_obj.content if response_obj.success else ""
        
        detected_lang = response.strip().lower()
        
        # 유효한 언어 코드인지 확인
        valid_languages = ['ko', 'en', 'ja', 'zh']
        if detected_lang in valid_languages:
            logger.debug(f"LLM 언어 감지 결과: '{detected_lang}' (콘텐츠 길이: {len(content)}자)")
            return detected_lang
        else:
            logger.warning(f"LLM이 유효하지 않은 언어 코드 반환: '{detected_lang}' - UI 언어 '{ui_language}' 사용")
            return ui_language
            
    except Exception as e:
        logger.error(f"LLM 언어 감지 실패: {e} - UI 언어 '{ui_language}' 사용")
        return ui_language


def detect_content_language(content: str, ui_language: str = 'ko') -> str:
    """
    동기 버전 - 기존 호환성을 위해 유지 (규칙 기반 폴백)
    
    Args:
        content: Content to analyze
        ui_language: UI language preference (used for short/ambiguous content)
    
    Returns:
        Detected or preferred language code
    """
    if not content or len(content.strip()) < 30:
        # 매우 짧은 텍스트만 UI 언어를 우선 적용
        logger.debug(f"짧은 콘텐츠({len(content)}자) - UI 언어 '{ui_language}' 적용")
        return ui_language
    
    # 간단한 규칙 기반 감지 (폴백용)
    korean_chars = sum(1 for c in content if '\uac00' <= c <= '\ud7af')
    total_chars = len(content)
    
    if korean_chars > total_chars * 0.3:  # 30% 이상이 한글이면 한국어
        logger.debug(f"규칙 기반 한국어 감지: {korean_chars}/{total_chars} ({korean_chars/total_chars:.2f})")
        return 'ko'
    
    # 영어 키워드 체크
    english_words = ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'with', 'this']
    content_lower = content.lower()
    english_matches = sum(1 for word in english_words if f' {word} ' in f' {content_lower} ')
    
    if english_matches >= 3:  # 영어 키워드 3개 이상
        logger.debug(f"규칙 기반 영어 감지: {english_matches}개 키워드 매칭")
        return 'en'
    
    # 기본값은 UI 언어
    logger.debug(f"규칙 기반 감지 실패 - UI 언어 '{ui_language}' 적용")
    return ui_language


def get_section_titles(ui_language: str = 'ko') -> Dict[str, str]:
    """Convenience function for getting section titles"""
    return language_detector.get_section_titles(ui_language)
