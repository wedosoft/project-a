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
    
    def __init__(self, use_llm_attachment_selector: bool = True):
        self.prompt_builder = PromptBuilder()
        self.attachment_selector = AttachmentSelector()
        self.quality_validator = QualityValidator()
        self.context_optimizer = ContextOptimizer()
        self.manager = None  # 지연 초기화로 순환 import 방지
        self.use_llm_attachment_selector = use_llm_attachment_selector
        
        # LLM 기반 첨부파일 선별기 (기본 활성화)
        if use_llm_attachment_selector:
            try:
                from ..attachment.llm_selector import LLMAttachmentSelector
                self.llm_attachment_selector = LLMAttachmentSelector()
                logger.info("LLM 기반 첨부파일 선별기 활성화됨")
            except Exception as e:
                logger.warning(f"LLM 첨부파일 선별기 로드 실패: {e}, rule-based 사용")
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
            
            # Content 검증
            if not content or not content.strip():
                logger.warning(f"Empty or None content provided for {content_type}")
                content = f"제목: {subject}\n내용: 상세 내용이 없습니다."
                
            logger.debug(f"Content length: {len(content)} characters")
            
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
            
            # 조회 티켓 프롬프트 디버깅 로그
            if content_type == "ticket_view":
                logger.info(f"\n📝 [조회 티켓 프롬프트 디버깅]")
                logger.info(f"System Prompt 길이: {len(system_prompt)} 문자")
                logger.info(f"System Prompt 미리보기: {system_prompt[:300]}...")
                logger.info(f"User Prompt 길이: {len(user_prompt)} 문자")
                # 한국어/영어 섹션 타이틀 모두 체크
                korean_sections = "🔍 문제 현황" in system_prompt or "💡 원인 분석" in system_prompt
                english_sections = "🔍 Problem Overview" in system_prompt or "💡 Root Cause" in system_prompt
                if korean_sections or english_sections:
                    logger.info("✅ realtime_ticket 템플릿 구조 확인됨")
                else:
                    logger.warning("⚠️ realtime_ticket 템플릿 구조가 누락됨!")
            
            # 5. Generate summary using LLM
            # 메시지 검증
            if not system_prompt or not system_prompt.strip():
                raise ValueError("Empty system prompt generated")
            if not user_prompt or not user_prompt.strip():
                raise ValueError("Empty user prompt generated")
                
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            logger.debug(f"Messages prepared - System: {len(system_prompt)} chars, User: {len(user_prompt)} chars")
            
            # 환경변수로 모델 설정 제어
            import os
            
            if content_type == "ticket_view":
                # 조회 티켓: TICKET_VIEW_ 환경변수 사용
                response = await self._get_manager().generate_for_use_case(
                    messages=messages,
                    use_case="ticket_view"
                )
            else:
                # 유사 티켓: TICKET_SIMILAR_ 환경변수 사용 (빠르고 효율적)
                response = await self._get_manager().generate_for_use_case(
                    messages=messages,
                    use_case="ticket_similar"
                )
            
            summary = response.content.strip() if response.success else "요약 생성 실패"
            
            # 조회 티켓 결과 품질 검증
            if content_type == "ticket_view" and summary:
                # 한국어/영어 섹션 구조 모두 체크
                korean_structure = any(section in summary for section in ["🔍 문제 현황", "💡 원인 분석", "⚡ 해결 진행상황", "🎯 중요 인사이트"])
                english_structure = any(section in summary for section in ["🔍 Problem Overview", "💡 Root Cause", "⚡ Resolution Progress", "🎯 Key Insights"])
                has_structure = korean_structure or english_structure
                if has_structure:
                    logger.info("✅ [조회 티켓] realtime_ticket 구조화된 요약 생성 성공")
                else:
                    logger.warning("⚠️ [조회 티켓] 구조화되지 않은 요약 - 재생성 고려 필요")
                    logger.debug(f"생성된 요약 미리보기: {summary[:500]}...")
            
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
            
            response = await self._get_manager().generate_for_use_case(
                messages=messages,
                use_case="summarization",
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
