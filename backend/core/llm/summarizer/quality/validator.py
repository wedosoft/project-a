"""
Quality validation module for summary assessment
"""

import re
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of summary quality validation"""
    quality_score: float
    issues: List[str]
    recommendations: List[str]
    is_valid: bool


class QualityValidator:
    """
    Validates summary quality using multiple criteria
    """
    
    def __init__(self):
        self.min_length = 50
        self.max_length = 2000
        self.required_sections = ["🔍", "🎯", "🔧", "💡"]  # Standard emoji sections
        
    def validate_summary_quality(
        self,
        summary: str,
        original_content: str,
        content_language: str = "ko"
    ) -> Dict[str, Any]:
        """
        Comprehensive quality validation of summary
        
        Args:
            summary: Generated summary
            original_content: Original content
            content_language: Language of content
            
        Returns:
            Dictionary with quality metrics and recommendations
        """
        try:
            result = ValidationResult(
                quality_score=0.0,
                issues=[],
                recommendations=[],
                is_valid=False
            )
            
            # 1. Length validation
            length_score = self._validate_length(summary, result)
            
            # 2. Structure validation
            structure_score = self._validate_structure(summary, result)
            
            # 3. Content quality validation
            content_score = self._validate_content_quality(summary, original_content, result)
            
            # 4. Language consistency validation
            language_score = self._validate_language_consistency(summary, content_language, result)
            
            # 5. Format validation
            format_score = self._validate_format(summary, result)
            
            # Calculate overall score
            weights = {
                'length': 0.15,
                'structure': 0.25,
                'content': 0.35,
                'language': 0.15,
                'format': 0.10
            }
            
            overall_score = (
                length_score * weights['length'] +
                structure_score * weights['structure'] +
                content_score * weights['content'] +
                language_score * weights['language'] +
                format_score * weights['format']
            )
            
            result.quality_score = round(overall_score, 3)
            result.is_valid = overall_score >= 0.7
            
            logger.info(f"Quality validation completed - Score: {result.quality_score:.3f}")
            
            return {
                'quality_score': result.quality_score,
                'is_valid': result.is_valid,
                'issues': result.issues,
                'recommendations': result.recommendations,
                'detailed_scores': {
                    'length': length_score,
                    'structure': structure_score,
                    'content': content_score,
                    'language': language_score,
                    'format': format_score
                }
            }
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            return {
                'quality_score': 0.5,
                'is_valid': False,
                'issues': [f"Validation error: {str(e)}"],
                'recommendations': ["Manual review required"],
                'detailed_scores': {}
            }
    
    def _validate_length(self, summary: str, result: ValidationResult) -> float:
        """Validate summary length"""
        length = len(summary.strip())
        
        if length < self.min_length:
            result.issues.append(f"Summary too short ({length} chars, minimum {self.min_length})")
            result.recommendations.append("Include more detailed information")
            return 0.3
        elif length > self.max_length:
            result.issues.append(f"Summary too long ({length} chars, maximum {self.max_length})")
            result.recommendations.append("Condense information more effectively")
            return 0.7
        else:
            # Optimal length range
            if 200 <= length <= 800:
                return 1.0
            elif 100 <= length <= 1200:
                return 0.9
            else:
                return 0.8
    
    def _validate_structure(self, summary: str, result: ValidationResult) -> float:
        """Validate summary structure and organization"""
        score = 0.0
        
        # Check for required emoji sections
        sections_found = 0
        for emoji in self.required_sections:
            if emoji in summary:
                sections_found += 1
        
        section_score = sections_found / len(self.required_sections)
        score += section_score * 0.6
        
        if sections_found < len(self.required_sections):
            missing = len(self.required_sections) - sections_found
            result.issues.append(f"Missing {missing} required sections")
            result.recommendations.append("Include all standard sections (🔍 🎯 🔧 💡)")
        
        # Check for proper markdown formatting
        if re.search(r'\*\*.*?\*\*', summary):  # Bold text
            score += 0.2
        else:
            result.recommendations.append("Use bold formatting for section headers")
        
        # Check for bullet points
        if re.search(r'^[-*]\s', summary, re.MULTILINE):
            score += 0.2
        else:
            result.recommendations.append("Use bullet points for better readability")
        
        return min(score, 1.0)
    
    def _validate_content_quality(self, summary: str, original_content: str, result: ValidationResult) -> float:
        """Validate content quality and relevance"""
        score = 0.0
        
        # Basic content checks
        if len(summary.strip()) == 0:
            result.issues.append("Empty summary")
            return 0.0
        
        # Check for repetitive content
        sentences = summary.split('.')
        unique_sentences = set(s.strip().lower() for s in sentences if s.strip())
        if len(sentences) > 3 and len(unique_sentences) / len(sentences) < 0.8:
            result.issues.append("Repetitive content detected")
            result.recommendations.append("Remove duplicate information")
            score -= 0.2
        
        # Check for generic/placeholder content
        generic_phrases = ["일반적인", "기본적인", "표준적인", "generic", "standard", "typical"]
        generic_count = sum(1 for phrase in generic_phrases if phrase.lower() in summary.lower())
        if generic_count > 2:
            result.issues.append("Too many generic phrases")
            result.recommendations.append("Use more specific, actionable language")
            score -= 0.1
        
        # Check for actionable content
        action_words = ["해결", "처리", "확인", "검토", "개선", "수정", "solve", "fix", "check", "review", "improve"]
        action_count = sum(1 for word in action_words if word.lower() in summary.lower())
        if action_count > 0:
            score += 0.3
        else:
            result.recommendations.append("Include more actionable insights")
        
        # Base content quality score
        score += 0.7
        
        return max(0.0, min(score, 1.0))
    
    def _validate_language_consistency(self, summary: str, content_language: str, result: ValidationResult) -> float:
        """Validate language consistency"""
        if content_language == "ko":
            # Check for Korean text
            korean_chars = len([c for c in summary if '\uac00' <= c <= '\ud7af'])
            if korean_chars < len(summary) * 0.1:
                result.issues.append("Insufficient Korean content for Korean language context")
                result.recommendations.append("Ensure summary uses appropriate Korean language")
                return 0.5
        
        # Check for mixed languages inappropriately
        english_ratio = len(re.findall(r'[a-zA-Z]', summary)) / len(summary) if summary else 0
        korean_ratio = len([c for c in summary if '\uac00' <= c <= '\ud7af']) / len(summary) if summary else 0
        
        if content_language == "ko" and english_ratio > 0.3 and korean_ratio < 0.3:
            result.issues.append("Language mismatch - too much English for Korean context")
            return 0.6
        
        return 1.0
    
    def _validate_format(self, summary: str, result: ValidationResult) -> float:
        """Validate formatting consistency"""
        score = 1.0
        
        # Check for consistent emoji usage
        emoji_pattern = r'[🔍🎯🔧💡📊📈📉⚠️✅❌🚀📋]'
        emojis = re.findall(emoji_pattern, summary)
        
        if not emojis:
            result.recommendations.append("Add emojis for better visual organization")
            score -= 0.3
        
        # Check for proper line breaks
        if '\n' not in summary and len(summary) > 200:
            result.recommendations.append("Add line breaks for better readability")
            score -= 0.2
        
        return max(0.0, score)
    
    def get_quality_threshold_config(self) -> Dict[str, float]:
        """Get quality threshold configuration"""
        return {
            'minimum_acceptable': 0.5,
            'good_quality': 0.7,
            'excellent_quality': 0.9,
            'regeneration_threshold': 0.6
        }
