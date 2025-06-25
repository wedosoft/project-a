"""
Hybrid summarization module for handling large content with adaptive strategies
"""

import re
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..core.summarizer import CoreSummarizer
from ..email.processor import EmailProcessor
from ..context.optimizer import ContextOptimizer

logger = logging.getLogger(__name__)


@dataclass
class HybridStrategy:
    """Configuration for hybrid summarization strategy"""
    name: str
    max_content_length: int
    chunk_size: int
    overlap_size: int
    use_rolling: bool
    preserve_context: bool


class HybridSummarizer:
    """
    Hybrid summarization system that adapts strategy based on content size and type
    """
    
    def __init__(self):
        self.core_summarizer = CoreSummarizer()
        self.email_processor = EmailProcessor()
        self.context_optimizer = ContextOptimizer()
        
        # Define strategies based on content size
        self.strategies = {
            'small': HybridStrategy(
                name='standard',
                max_content_length=15000,
                chunk_size=15000,
                overlap_size=0,
                use_rolling=False,
                preserve_context=True
            ),
            'medium': HybridStrategy(
                name='chunked',
                max_content_length=35000,
                chunk_size=18000,
                overlap_size=2000,
                use_rolling=False,
                preserve_context=True
            ),
            'large': HybridStrategy(
                name='rolling',
                max_content_length=100000,
                chunk_size=12000,
                overlap_size=3000,
                use_rolling=True,
                preserve_context=False
            )
        }
    
    async def generate_hybrid_summary(
        self,
        content: str,
        content_type: str = "ticket",
        subject: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        ui_language: str = "ko"
    ) -> str:
        """
        Generate summary using hybrid approach based on content characteristics
        
        Args:
            content: Content to summarize
            content_type: Type of content
            subject: Subject/title
            metadata: Additional metadata
            ui_language: UI language
            
        Returns:
            Generated summary
        """
        try:
            logger.info(f"Starting hybrid summarization - Original size: {len(content):,} chars")
            
            # 1. Preprocess content (email deduplication, cleanup)
            preprocessed_content = await self._preprocess_content(content, content_type)
            logger.info(f"Content preprocessed - Size: {len(preprocessed_content):,} chars")
            
            # 2. Select strategy based on content size
            strategy = self._select_strategy(preprocessed_content)
            logger.info(f"Selected strategy: {strategy.name}")
            
            # 3. Apply strategy-specific summarization
            if strategy.name == 'standard':
                return await self._standard_summarization(
                    preprocessed_content, content_type, subject, metadata, ui_language
                )
            elif strategy.name == 'chunked':
                return await self._chunked_summarization(
                    preprocessed_content, content_type, subject, metadata, ui_language, strategy
                )
            elif strategy.name == 'rolling':
                return await self._rolling_summarization(
                    preprocessed_content, content_type, subject, metadata, ui_language, strategy
                )
            else:
                # Fallback to standard
                return await self._standard_summarization(
                    preprocessed_content[:15000], content_type, subject, metadata, ui_language
                )
                
        except Exception as e:
            logger.error(f"Hybrid summarization failed: {e}")
            # Fallback to core summarizer with truncated content
            return await self.core_summarizer.generate_summary(
                content=content[:15000],
                content_type=content_type,
                subject=subject,
                metadata=metadata,
                ui_language=ui_language
            )
    
    async def _preprocess_content(self, content: str, content_type: str) -> str:
        """Preprocess content to reduce size and improve quality"""
        if content_type == "email" or self._is_email_content(content):
            # Use email-specific preprocessing
            processed_email = self.email_processor.process_email_content(
                content, preserve_thread=True, extract_actions=True
            )
            
            # Reconstruct cleaned content
            preprocessed = processed_email.content
            
            # Add key points and actions as structured information
            if processed_email.key_points:
                preprocessed += "\n\n주요 포인트:\n" + "\n".join([f"- {point}" for point in processed_email.key_points])
            
            if processed_email.action_items:
                preprocessed += "\n\n액션 아이템:\n" + "\n".join([f"- {action}" for action in processed_email.action_items])
                
            return preprocessed
        else:
            # Apply general content optimization
            optimization_result = self.context_optimizer.optimize_content_context(
                content, content_type
            )
            return optimization_result.optimized_content
    
    def _is_email_content(self, content: str) -> bool:
        """Detect if content is email-based"""
        email_indicators = [
            r'^From:\s*.*@',
            r'^To:\s*.*@',
            r'^Subject:',
            r'wrote:$',
            r'님이 작성:',
            r'@.*\.(com|org|net)'
        ]
        
        for pattern in email_indicators:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                return True
        
        return False
    
    def _select_strategy(self, content: str) -> HybridStrategy:
        """Select appropriate strategy based on content characteristics"""
        content_length = len(content)
        
        if content_length <= self.strategies['small'].max_content_length:
            return self.strategies['small']
        elif content_length <= self.strategies['medium'].max_content_length:
            return self.strategies['medium']
        else:
            return self.strategies['large']
    
    async def _standard_summarization(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
        ui_language: str
    ) -> str:
        """Standard single-pass summarization"""
        return await self.core_summarizer.generate_summary(
            content=content,
            content_type=content_type,
            subject=subject,
            metadata=metadata,
            ui_language=ui_language
        )
    
    async def _chunked_summarization(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
        ui_language: str,
        strategy: HybridStrategy
    ) -> str:
        """Chunked summarization with final integration"""
        chunks = self._split_content_with_overlap(content, strategy.chunk_size, strategy.overlap_size)
        logger.info(f"Processing {len(chunks)} chunks for chunked summarization")
        
        if len(chunks) <= 1:
            return await self._standard_summarization(content, content_type, subject, metadata, ui_language)
        
        # Generate summaries for each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            chunk_summary = await self.core_summarizer.generate_summary(
                content=chunk,
                content_type=content_type,
                subject=f"{subject} (Part {i+1})",
                metadata=metadata,
                ui_language=ui_language
            )
            chunk_summaries.append(chunk_summary)
        
        # Integrate chunk summaries
        return await self._integrate_summaries(chunk_summaries, content_type, ui_language)
    
    async def _rolling_summarization(
        self,
        content: str,
        content_type: str,
        subject: str,
        metadata: Optional[Dict[str, Any]],
        ui_language: str,
        strategy: HybridStrategy
    ) -> str:
        """Rolling summarization maintaining context across chunks"""
        chunks = self._split_content_with_overlap(content, strategy.chunk_size, strategy.overlap_size)
        logger.info(f"Processing {len(chunks)} chunks for rolling summarization")
        
        if len(chunks) <= 1:
            return await self._standard_summarization(content, content_type, subject, metadata, ui_language)
        
        current_summary = ""
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing rolling chunk {i+1}/{len(chunks)}")
            
            if i == 0:
                # First chunk: standard summarization
                current_summary = await self.core_summarizer.generate_summary(
                    content=chunk,
                    content_type=content_type,
                    subject=subject,
                    metadata=metadata,
                    ui_language=ui_language
                )
            else:
                # Subsequent chunks: integrate with existing summary
                rolling_content = self._create_rolling_integration_prompt(
                    current_summary, chunk, ui_language
                )
                current_summary = await self.core_summarizer.generate_summary(
                    content=rolling_content,
                    content_type="integration",
                    subject=f"{subject} (Rolling Update {i+1})",
                    metadata=metadata,
                    ui_language=ui_language
                )
        
        return current_summary
    
    def _split_content_with_overlap(self, content: str, chunk_size: int, overlap_size: int) -> List[str]:
        """Split content into overlapping chunks"""
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        position = 0
        
        while position < len(content):
            # Determine chunk end position
            chunk_end = min(position + chunk_size, len(content))
            
            # Try to break at sentence boundary
            if chunk_end < len(content):
                # Look for sentence end within last 200 characters
                search_start = max(chunk_end - 200, position)
                sentence_end = content.rfind('.', search_start, chunk_end)
                if sentence_end > search_start:
                    chunk_end = sentence_end + 1
            
            chunk = content[position:chunk_end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move position forward (accounting for overlap)
            if chunk_end >= len(content):
                break
            position = max(position + 1, chunk_end - overlap_size)
        
        return chunks
    
    def _create_rolling_integration_prompt(self, existing_summary: str, new_chunk: str, ui_language: str) -> str:
        """Create prompt for rolling integration"""
        if ui_language == "ko":
            return f"""기존 요약과 새로운 내용을 통합하여 업데이트된 요약을 생성하세요.

=== 기존 누적 요약 ===
{existing_summary}

=== 새로운 내용 ===
{new_chunk}

위의 기존 요약과 새로운 내용을 분석하여 다음 4개 섹션으로 통합된 요약을 작성하세요:

🔍 **문제 상황**
🎯 **근본 원인** 
🔧 **해결 과정**
💡 **핵심 포인트**

중요: 기존 요약의 핵심 정보를 유지하면서 새로운 내용을 자연스럽게 통합하세요."""
        else:
            return f"""Integrate the existing summary with new content to create an updated comprehensive summary.

=== EXISTING CUMULATIVE SUMMARY ===
{existing_summary}

=== NEW CONTENT ===
{new_chunk}

Analyze the existing summary and new content above to create an integrated summary with these 4 sections:

🔍 **Problem Situation**
🎯 **Root Cause**
🔧 **Resolution Process** 
💡 **Key Insights**

Important: Preserve key information from the existing summary while naturally integrating the new content."""
    
    async def _integrate_summaries(self, summaries: List[str], content_type: str, ui_language: str) -> str:
        """Integrate multiple summaries into final summary"""
        if len(summaries) == 1:
            return summaries[0]
        
        combined_summaries = "\n\n--- 구분 ---\n\n".join(summaries)
        
        integration_prompt = self._create_integration_prompt(combined_summaries, ui_language)
        
        return await self.core_summarizer.generate_summary(
            content=integration_prompt,
            content_type="integration",
            subject="통합 요약",
            metadata={"summary_type": "integration"},
            ui_language=ui_language
        )
    
    def _create_integration_prompt(self, combined_summaries: str, ui_language: str) -> str:
        """Create prompt for final integration"""
        if ui_language == "ko":
            return f"""다음은 긴 티켓의 여러 부분에 대한 요약들입니다. 이들을 하나의 일관된 최종 요약으로 통합하세요.

=== 분할된 요약들 ===
{combined_summaries}

위의 분할된 요약들을 분석하여 다음 4개 섹션으로 통합된 요약을 작성하세요:

🔍 **문제 상황**
- 모든 분할 요약의 문제 상황 통합
- 전체적인 기술 이슈나 비즈니스 요구사항
- 관련된 모든 제품/서비스/시스템

🎯 **근본 원인**
- 통합된 근본 원인 분석
- 모든 기여 요소들
- 전체적인 시스템 맥락

🔧 **해결 과정**
- 전체적인 현재 해결 단계
- 완료된 모든 액션들과 결과 통합
- 진행 중인 모든 작업
- 모든 계획된 액션들

💡 **핵심 포인트**
- 모든 기술 사양과 설정
- 모든 제한사항과 요구사항
- 통합된 모범 사례와 절차
- 모든 관련 문서, 리소스, 첨부파일

통합 원칙: 중복 내용을 자연스럽게 병합하고, 모든 중요 정보를 포함하며, 원본 용어를 최대한 보존하세요."""
        else:
            return f"""The following are summaries of different parts of a long ticket. Please integrate them into one coherent final summary.

=== DIVIDED SUMMARIES ===
{combined_summaries}

Analyze the divided summaries and create an integrated summary with the following 4 sections:

🔍 **Problem Situation**
- Integrate problem situations from all divided summaries
- Overall technical issues or business requirements
- All related products/services/systems

🎯 **Root Cause**
- Integrated root cause analysis
- All contributing factors
- Overall system context

🔧 **Resolution Process**
- Overall current stage of resolution process
- All completed actions and results integrated
- All currently ongoing work
- All planned actions

💡 **Key Insights**
- All technical specifications and configurations
- All limitations and requirements
- Integrated best practices and procedures
- All related documentation, resources, and attachments

Integration principles: Naturally merge overlapping content, include all important information, and preserve original terminology."""
