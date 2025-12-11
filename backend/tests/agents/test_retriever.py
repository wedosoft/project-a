"""
Unit tests for Retriever Agent (Gemini-only mode)
"""
import pytest
from backend.agents.retriever import retrieve_cases, retrieve_kb


@pytest.fixture
def mock_state():
    """Mock AgentState"""
    return {
        "ticket_context": {
            "ticket_id": "123",
            "subject": "Login error",
            "description": "Cannot login to the system",
            "symptom": "Error 401"
        },
        "errors": []
    }


class TestRetrieveCases:
    """Test retrieve_cases function"""

    @pytest.mark.asyncio
    async def test_retrieve_cases_returns_empty_results(self, mock_state):
        """Legacy vector 검색 제거 이후 빈 결과를 반환해야 한다"""
        result = await retrieve_cases(mock_state)

        assert "search_results" in result
        assert result["search_results"]["similar_cases"] == []
        assert result["search_results"]["total_results"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_retrieve_cases_handles_missing_context(self):
        """컨텍스트가 없어도 오류 없이 동작"""
        state = {"ticket_context": {}, "errors": []}
        result = await retrieve_cases(state)

        assert "search_results" not in result or result["search_results"]["similar_cases"] == []


class TestRetrieveKB:
    """Test retrieve_kb function"""

    @pytest.mark.asyncio
    async def test_retrieve_kb_returns_empty_results(self, mock_state):
        """Legacy vector 검색 제거 이후 빈 결과를 반환해야 한다"""
        result = await retrieve_kb(mock_state)

        assert "search_results" in result
        assert result["search_results"]["kb_procedures"] == []
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_retrieve_kb_handles_missing_context(self):
        """컨텍스트가 없어도 오류 없이 동작"""
        state = {"ticket_context": {}, "errors": []}
        result = await retrieve_kb(state)

        assert "search_results" not in result or result["search_results"]["kb_procedures"] == []
