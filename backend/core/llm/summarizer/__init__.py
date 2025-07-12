"""
Summarizer module - Modular summarization system
"""

import os
from .core.summarizer import CoreSummarizer, core_summarizer, generate_optimized_summary

# 일반 요약기 사용 (Anthropic 제거)
def get_active_summarizer():
    """일반 요약기 반환"""
    return core_summarizer

# 활성 요약기 인스턴스 생성
active_summarizer = core_summarizer

# 일반 요약 함수
async def generate_smart_summary(content: str, content_type: str = "ticket", **kwargs):
    """스마트 요약 생성 - 일반 템플릿 사용"""
    # 항상 일반 요약기 사용
    return await generate_optimized_summary(
        content=content,
        content_type=content_type,
        **kwargs
    )

# Backward compatibility aliases
generate_summary = generate_optimized_summary  # Legacy alias
ModularSummarizer = CoreSummarizer  # Modern alias for the modular system
from .prompt.builder import PromptBuilder
from .attachment.selector import AttachmentSelector
from .quality.validator import QualityValidator
from .context.optimizer import ContextOptimizer
from .email.processor import EmailProcessor
from .hybrid.summarizer import HybridSummarizer
from .utils.language import LanguageDetector, detect_content_language, get_section_titles
from .utils.agent import determine_agent_ui_language, translate_section_titles, get_agent_localized_summary

__all__ = [
    'CoreSummarizer',
    'ModularSummarizer',  # Modern alias
    'core_summarizer', 
    'active_summarizer',
    'generate_summary',  # Legacy alias
    'generate_optimized_summary',
    'generate_smart_summary',
    'get_active_summarizer',
    'PromptBuilder',
    'AttachmentSelector', 
    'QualityValidator',
    'ContextOptimizer',
    'EmailProcessor',
    'HybridSummarizer',
    'LanguageDetector',
    'detect_content_language',
    'get_section_titles',
    'determine_agent_ui_language',
    'translate_section_titles',
    'get_agent_localized_summary'
]

__version__ = "1.0.0"
