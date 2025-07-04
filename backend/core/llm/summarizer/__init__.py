"""
Summarizer module - Modular summarization system
"""

import os
from .core.summarizer import CoreSummarizer, core_summarizer, generate_optimized_summary

# 🧠 Anthropic 프롬프트 엔지니어링 시스템 통합
def get_active_summarizer():
    """환경변수에 따라 적절한 요약기를 반환"""
    if os.getenv('ENABLE_ANTHROPIC_PROMPTS', 'false').lower() == 'true':
        try:
            from .core.anthropic_summarizer import AnthropicSummarizer
            return AnthropicSummarizer()
        except ImportError:
            # Anthropic 요약기 로드 실패 시 기본 요약기 사용
            return core_summarizer
    return core_summarizer

# 활성 요약기 인스턴스 생성
active_summarizer = get_active_summarizer()

# 🔄 동적 요약 함수 - 환경변수에 따라 적절한 요약기 사용
async def generate_smart_summary(content: str, content_type: str = "ticket", **kwargs):
    """스마트 요약 생성 - Anthropic 활성화 시 Constitutional AI 사용"""
    current_summarizer = get_active_summarizer()
    
    # AnthropicSummarizer인 경우 전용 메서드 사용
    if hasattr(current_summarizer, 'generate_anthropic_summary'):
        # 🧠 Anthropic용 content_type 매핑
        anthropic_content_type_map = {
            "ticket_view": "ticket_view",  # AnthropicSummarizer에서 내부적으로 anthropic_ticket_view 사용
            "ticket_similar": "ticket_similar",
            "ticket": "ticket_view"
        }
        mapped_content_type = anthropic_content_type_map.get(content_type, content_type)
        
        # AnthropicSummarizer 전용 매개변수 처리
        subject = kwargs.get('subject', '')
        metadata = kwargs.get('metadata', {})
        content_language = kwargs.get('content_language', 'ko')
        ui_language = kwargs.get('ui_language', 'ko')
        
        return await current_summarizer.generate_anthropic_summary(
            content=content,
            content_type=mapped_content_type,
            subject=subject,
            metadata=metadata,
            content_language=content_language,
            ui_language=ui_language
        )
    
    # 기본 요약기인 경우 기존 방식 사용
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
    'active_summarizer',  # 🧠 Dynamic summarizer
    'generate_summary',  # Legacy alias
    'generate_optimized_summary',
    'generate_smart_summary',  # 🚀 Smart summarizer
    'get_active_summarizer',  # 🔄 Factory function
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
