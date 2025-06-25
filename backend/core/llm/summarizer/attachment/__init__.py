"""
Attachment management module
"""

from .selector import AttachmentSelector
from .config import AttachmentConfig

# LLM-based selector (optional import due to async nature)
try:
    from .llm_selector import LLMAttachmentSelector, HybridAttachmentSelector, select_relevant_attachments_llm
    _llm_selector_available = True
except ImportError:
    _llm_selector_available = False
    LLMAttachmentSelector = None
    HybridAttachmentSelector = None
    select_relevant_attachments_llm = None

__all__ = ['AttachmentSelector', 'AttachmentConfig']

if _llm_selector_available:
    __all__.extend(['LLMAttachmentSelector', 'HybridAttachmentSelector', 'select_relevant_attachments_llm'])
