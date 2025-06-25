"""
Summarizer module - Modular summarization system
"""

from .core.summarizer import CoreSummarizer, core_summarizer, generate_optimized_summary

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
    'generate_summary',  # Legacy alias
    'generate_optimized_summary',
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
