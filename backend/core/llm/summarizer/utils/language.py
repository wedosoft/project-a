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
            return 'en' if not detailed else LanguageProfile('en', 'English', 0.5, 0.0, 0, len(text))
        
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
            # For English, high ASCII ratio is a good indicator
            ascii_ratio = sum(1 for c in text if ord(c) < 128) / total_chars
            confidence = max(confidence, ascii_ratio * 0.8)
        
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


def detect_content_language(content: str) -> str:
    """Convenience function for language detection"""
    return language_detector.detect_language(content)


def get_section_titles(ui_language: str = 'ko') -> Dict[str, str]:
    """Convenience function for getting section titles"""
    return language_detector.get_section_titles(ui_language)
