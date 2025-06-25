"""
Test the new modular summarizer system
"""

import asyncio
import pytest
from unittest.mock import Mock, patch

from backend.core.llm.summarizer import (
    CoreSummarizer,
    PromptBuilder, 
    AttachmentSelector,
    QualityValidator,
    ContextOptimizer,
    EmailProcessor,
    HybridSummarizer,
    detect_content_language,
    get_section_titles
)


class TestCoreSummarizer:
    """Test CoreSummarizer functionality"""
    
    def setup_method(self):
        self.summarizer = CoreSummarizer()
    
    def test_initialization(self):
        """Test proper initialization of components"""
        assert isinstance(self.summarizer.prompt_builder, PromptBuilder)
        assert isinstance(self.summarizer.attachment_selector, AttachmentSelector)
        assert isinstance(self.summarizer.quality_validator, QualityValidator)
        assert isinstance(self.summarizer.context_optimizer, ContextOptimizer)
    
    @pytest.mark.asyncio
    async def test_generate_summary_basic(self):
        """Test basic summary generation"""
        with patch.object(self.summarizer.llm_manager, 'generate_response') as mock_llm:
            mock_llm.return_value = """🔍 **문제 상황**
테스트 문제입니다.

🎯 **근본 원인**
테스트 원인입니다.

🔧 **해결 과정**
테스트 해결입니다.

💡 **핵심 포인트**
테스트 포인트입니다."""
            
            result = await self.summarizer.generate_summary(
                content="테스트 내용입니다.",
                content_type="ticket",
                ui_language="ko"
            )
            
            assert "🔍" in result
            assert "🎯" in result
            assert "🔧" in result
            assert "💡" in result
            mock_llm.assert_called_once()


class TestPromptBuilder:
    """Test PromptBuilder functionality"""
    
    def setup_method(self):
        self.builder = PromptBuilder()
    
    def test_build_system_prompt(self):
        """Test system prompt building"""
        prompt = self.builder.build_system_prompt(
            content_type="ticket",
            content_language="ko",
            ui_language="ko"
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "ticket" in prompt.lower() or "티켓" in prompt
    
    def test_build_user_prompt(self):
        """Test user prompt building"""
        prompt = self.builder.build_user_prompt(
            content="테스트 내용",
            content_type="ticket",
            subject="테스트 제목",
            metadata={"test": "value"},
            content_language="ko",
            ui_language="ko"
        )
        
        assert isinstance(prompt, str)
        assert "테스트 내용" in prompt
        assert "테스트 제목" in prompt


class TestAttachmentSelector:
    """Test AttachmentSelector functionality"""
    
    def setup_method(self):
        self.selector = AttachmentSelector()
    
    def test_select_relevant_attachments_empty(self):
        """Test with no attachments"""
        result = self.selector.select_relevant_attachments(
            attachments=[], 
            content="test content",
            subject="test subject"
        )
        
        assert result == []
    
    def test_select_relevant_attachments_with_data(self):
        """Test attachment selection with sample data"""
        attachments = [
            {"name": "error.log", "content_type": "text/plain", "size": 1024},
            {"name": "image.png", "content_type": "image/png", "size": 2048},
            {"name": "config.json", "content_type": "application/json", "size": 512}
        ]
        
        result = self.selector.select_relevant_attachments(
            attachments=attachments,
            content="There was an error in the log file",
            subject="Error investigation"
        )
        
        assert isinstance(result, list)
        assert len(result) <= 3  # Should not exceed maximum


class TestQualityValidator:
    """Test QualityValidator functionality"""
    
    def setup_method(self):
        self.validator = QualityValidator()
    
    def test_validate_summary_quality_good(self):
        """Test quality validation with good summary"""
        good_summary = """🔍 **문제 상황**
시스템에서 로그인 오류가 발생했습니다.

🎯 **근본 원인**
데이터베이스 연결 문제로 인한 인증 실패입니다.

🔧 **해결 과정**
데이터베이스 연결을 복구하고 서비스를 재시작했습니다.

💡 **핵심 포인트**
향후 모니터링을 강화하여 예방하겠습니다."""
        
        result = self.validator.validate_summary_quality(
            summary=good_summary,
            original_content="원본 내용",
            content_language="ko"
        )
        
        assert result['quality_score'] > 0.7
        assert result['is_valid'] is True
        assert isinstance(result['issues'], list)
        assert isinstance(result['recommendations'], list)
    
    def test_validate_summary_quality_poor(self):
        """Test quality validation with poor summary"""
        poor_summary = "짧은 요약"
        
        result = self.validator.validate_summary_quality(
            summary=poor_summary,
            original_content="원본 내용",
            content_language="ko"
        )
        
        assert result['quality_score'] < 0.7
        assert result['is_valid'] is False
        assert len(result['issues']) > 0


class TestLanguageUtils:
    """Test language detection and utilities"""
    
    def test_detect_content_language_korean(self):
        """Test Korean language detection"""
        korean_text = "안녕하세요. 이것은 한국어 텍스트입니다."
        result = detect_content_language(korean_text)
        assert result == "ko"
    
    def test_detect_content_language_english(self):
        """Test English language detection"""
        english_text = "Hello, this is an English text with standard words."
        result = detect_content_language(english_text)
        assert result == "en"
    
    def test_get_section_titles_korean(self):
        """Test Korean section titles"""
        titles = get_section_titles("ko")
        assert "문제 상황" in titles['problem']
        assert "근본 원인" in titles['cause']
        assert "해결 과정" in titles['solution']
        assert "핵심 포인트" in titles['insights']
    
    def test_get_section_titles_english(self):
        """Test English section titles"""
        titles = get_section_titles("en")
        assert "Problem Situation" in titles['problem']
        assert "Root Cause" in titles['cause']
        assert "Resolution Process" in titles['solution']
        assert "Key Insights" in titles['insights']


class TestHybridSummarizer:
    """Test HybridSummarizer functionality"""
    
    def setup_method(self):
        self.hybrid_summarizer = HybridSummarizer()
    
    @pytest.mark.asyncio
    async def test_generate_hybrid_summary_small(self):
        """Test hybrid summarization with small content"""
        small_content = "짧은 테스트 내용입니다." * 10
        
        with patch.object(self.hybrid_summarizer.core_summarizer, 'generate_summary') as mock_core:
            mock_core.return_value = "테스트 요약"
            
            result = await self.hybrid_summarizer.generate_hybrid_summary(
                content=small_content,
                content_type="ticket",
                ui_language="ko"
            )
            
            assert result == "테스트 요약"
            mock_core.assert_called()


if __name__ == "__main__":
    # Run basic tests
    pytest.main([__file__, "-v"])
