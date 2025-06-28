"""
Core summarizer module - Main entry point for the modular summarizer system
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.llm.models.base import LLMProvider
# from core.llm.manager import get_llm_manager  # 순환 import 방지를 위해 제거
from ..prompt.builder import PromptBuilder
from ..attachment.selector import AttachmentSelector
from ..quality.validator import QualityValidator
from ..context.optimizer import ContextOptimizer
from ..utils.language import detect_content_language

logger = logging.getLogger(__name__)


class CoreSummarizer:
    """
    Core summarizer class that orchestrates all summarization components
    """
    
    def __init__(self, use_llm_attachment_selector: bool = False):
        self.prompt_builder = PromptBuilder()
        self.attachment_selector = AttachmentSelector()
        self.quality_validator = QualityValidator()
        self.context_optimizer = ContextOptimizer()
        self.manager = None  # 지연 초기화로 순환 import 방지
        self.use_llm_attachment_selector = use_llm_attachment_selector
        
        # LLM 기반 첨부파일 선별기 (옵션)
        if use_llm_attachment_selector:
            try:
                from ..attachment.llm_selector import HybridAttachmentSelector
                self.llm_attachment_selector = HybridAttachmentSelector(prefer_llm=True)
                logger.info("LLM 기반 첨부파일 선별기 활성화됨")
            except ImportError:
                logger.warning("LLM 첨부파일 선별기 로드 실패, rule-based 사용")
                self.llm_attachment_selector = None
    
    def _get_manager(self):
        """지연 초기화로 순환 import 방지"""
        if self.manager is None:
            from core.llm.manager import get_llm_manager
            self.manager = get_llm_manager()
        return self.manager
        
    async def generate_summary(
        self,
        content: str,
        content_type: str = "ticket",
        subject: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        ui_language: str = "ko"
    ) -> str:
        """
        Generate optimized summary using modular components
        
        Args:
            content: Content to summarize
            content_type: Type of content (ticket, knowledge_base, conversation)
            subject: Subject/title
            metadata: Additional metadata including attachments
            ui_language: UI language (ko, en, ja, zh)
            
        Returns:
            Generated summary
        """
        try:
            logger.info(f"Starting summary generation - Type: {content_type}, Language: {ui_language}")
            
            # 1. Select relevant attachments (choose between LLM or rule-based)
            selected_attachments = []
            if metadata and metadata.get('attachments'):
                if self.use_llm_attachment_selector and hasattr(self, 'llm_attachment_selector') and self.llm_attachment_selector:
                    # LLM 기반 지능형 선별
                    logger.info("LLM 기반 첨부파일 선별 시작")
                    selected_attachments = await self.llm_attachment_selector.select_relevant_attachments(
                        attachments=metadata['attachments'],
                        content=content,
                        subject=subject
                    )
                else:
                    # 기존 rule-based 선별
                    logger.info("Rule-based 첨부파일 선별 시작")
                    selected_attachments = self.attachment_selector.select_relevant_attachments(
                        attachments=metadata['attachments'],
                        content=content,
                        subject=subject
                    )
                logger.info(f"Selected {len(selected_attachments)} relevant attachments from {len(metadata['attachments'])} total")
            
            # 2. Update metadata with selected attachments only
            if selected_attachments:
                metadata = metadata.copy() if metadata else {}
                metadata['relevant_attachments'] = selected_attachments
                # Remove all_attachments to prevent confusion
                metadata.pop('attachments', None)
                metadata.pop('all_attachments', None)
            
            # 3. Detect content language
            content_language = detect_content_language(content)
            
            # 4. Build prompts using new builder
            system_prompt = self.prompt_builder.build_system_prompt(
                content_type=content_type,
                content_language=content_language,
                ui_language=ui_language
            )
            
            user_prompt = self.prompt_builder.build_user_prompt(
                content=content,
                content_type=content_type,
                subject=subject,
                metadata=metadata,
                content_language=content_language,
                ui_language=ui_language
            )
            
            # 5. Generate summary using LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self._get_manager().generate(
                messages=messages,
                provider=LLMProvider.OPENAI,
                max_tokens=1200,
                temperature=0.3
            )
            
            summary = response.content.strip() if response.success else "요약 생성 실패"
            
            # 6. Validate quality
            validation_result = self.quality_validator.validate_summary_quality(
                summary=summary,
                original_content=content,
                content_language=content_language
            )
            
            if validation_result['quality_score'] < 0.7:
                logger.warning(f"Low quality summary detected (score: {validation_result['quality_score']:.2f}), attempting regeneration")
                summary = await self._regenerate_with_quality_focus(
                    content, content_type, subject, metadata, content_language, ui_language
                )
            
            logger.info(f"Summary generation completed - Quality score: {validation_result['quality_score']:.2f}")
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return self._create_fallback_summary(content, content_type, ui_language)
    
    async def _regenerate_with_quality_focus(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
        content_language: str,
        ui_language: str
    ) -> str:
        """
        Regenerate summary with enhanced quality focus
        """
        try:
            # Use enhanced system prompt for quality
            system_prompt = self.prompt_builder.build_enhanced_system_prompt(
                content_type=content_type,
                content_language=content_language,
                ui_language=ui_language
            )
            
            user_prompt = self.prompt_builder.build_user_prompt(
                content=content,
                content_type=content_type,
                subject=subject,
                metadata=metadata,
                content_language=content_language,
                ui_language=ui_language
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self._get_manager().generate(
                messages=messages,
                provider=LLMProvider.OPENAI,
                max_tokens=1500,
                temperature=0.1
            )
            
            return response.content.strip() if response.success else self._create_fallback_summary(content, content_type, ui_language)
            
        except Exception as e:
            logger.error(f"Quality-focused regeneration failed: {e}")
            return self._create_fallback_summary(content, content_type, ui_language)
    
    def _create_fallback_summary(self, content: str, content_type: str, ui_language: str) -> str:
        """
        Create fallback summary when generation fails
        """
        if ui_language == "ko":
            return """🔍 **문제 상황**
요약 생성 중 오류가 발생하여 원본 내용을 기반으로 기본 요약을 제공합니다.

🎯 **근본 원인**
시스템 처리 한계로 인한 요약 생성 실패입니다.

🔧 **해결 과정**
원본 내용을 직접 검토하여 세부사항을 확인해주시기 바랍니다.

💡 **핵심 포인트**
- 원본 데이터 검토 필요
- 수동 분석 권장
- 기술 지원팀 문의 고려"""
        else:
            return """🔍 **Problem Situation**
An error occurred during summary generation. Providing basic summary based on original content.

🎯 **Root Cause**
Summary generation failed due to system processing limitations.

🔧 **Resolution Process**
Please review the original content directly for detailed information.

💡 **Key Insights**
- Original data review required
- Manual analysis recommended
- Consider contacting technical support team"""


# Global instance for backward compatibility
core_summarizer = CoreSummarizer()


async def generate_optimized_summary(
    content: str,
    content_type: str = "ticket",
    subject: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    ui_language: str = "ko"
) -> str:
    """
    Backward compatibility function - delegates to CoreSummarizer
    """
    return await core_summarizer.generate_summary(
        content=content,
        content_type=content_type,
        subject=subject,
        metadata=metadata,
        ui_language=ui_language
    )
