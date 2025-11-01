"""
Unit tests for agent utilities
"""
import pytest
import asyncio
from backend.agents.utils import (
    with_timeout,
    with_error_handling,
    extract_query_text,
    calculate_confidence,
    format_search_results
)


class TestWithTimeout:
    """Test with_timeout decorator"""

    @pytest.mark.asyncio
    async def test_timeout_success(self):
        """Test successful execution within timeout"""
        @with_timeout(timeout=1.0)
        async def quick_func():
            await asyncio.sleep(0.1)
            return "success"

        result = await quick_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """Test timeout exceeded"""
        @with_timeout(timeout=0.1)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "should not reach"

        with pytest.raises(asyncio.TimeoutError):
            await slow_func()


class TestWithErrorHandling:
    """Test with_error_handling decorator"""

    @pytest.mark.asyncio
    async def test_error_handling_success(self):
        """Test successful execution"""
        @with_error_handling
        async def success_func(state):
            return state

        state = {"errors": []}
        result = await success_func(state)
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_error_handling_failure(self):
        """Test error handling"""
        @with_error_handling
        async def failing_func(state):
            raise ValueError("Test error")

        state = {"errors": []}
        result = await failing_func(state)
        assert len(result["errors"]) > 0


class TestExtractQueryText:
    """Test extract_query_text function"""

    def test_extract_all_fields(self):
        """Test extraction with all fields"""
        context = {
            "subject": "Login issue",
            "description": "Cannot access account",
            "symptom": "Error 401"
        }
        result = extract_query_text(context)
        assert "Login issue" in result
        assert "Cannot access account" in result
        assert "Error 401" in result

    def test_extract_partial_fields(self):
        """Test extraction with some fields"""
        context = {
            "subject": "Test"
        }
        result = extract_query_text(context)
        assert result == "Test"

    def test_extract_empty(self):
        """Test extraction with empty context"""
        context = {}
        result = extract_query_text(context)
        assert result == ""


class TestCalculateConfidence:
    """Test calculate_confidence function"""

    def test_calculate_with_results(self):
        """Test confidence calculation with results"""
        results = [
            {"score": 0.9},
            {"score": 0.8},
            {"score": 0.7}
        ]
        confidence = calculate_confidence(results)
        assert 0.0 <= confidence <= 1.0

    def test_calculate_empty(self):
        """Test confidence with no results"""
        confidence = calculate_confidence([])
        assert confidence == 0.0


class TestFormatSearchResults:
    """Test format_search_results function"""

    def test_format_results(self):
        """Test formatting search results"""
        cases = [{"id": "1", "content": "Case 1"}]
        kb = [{"id": "2", "content": "KB 1"}]

        result = format_search_results(cases, kb)

        assert result["similar_cases"] == cases
        assert result["kb_procedures"] == kb
        assert result["total_results"] == 2
