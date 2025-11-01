"""
Unit tests for Retriever Agent
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
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


@pytest.fixture
def mock_search_service():
    """Mock HybridSearchService"""
    service = MagicMock()
    service.search = AsyncMock(return_value=[
        {"id": "1", "content": "Similar case 1", "score": 0.9},
        {"id": "2", "content": "Similar case 2", "score": 0.8}
    ])
    return service


class TestRetrieveCases:
    """Test retrieve_cases function"""

    @pytest.mark.asyncio
    async def test_retrieve_cases_success(self, mock_state, mock_search_service):
        """Test successful case retrieval"""
        with patch('backend.agents.retriever.HybridSearchService', return_value=mock_search_service):
            result = await retrieve_cases(mock_state)

            assert "search_results" in result
            assert "similar_cases" in result["search_results"]
            assert len(result["search_results"]["similar_cases"]) == 2
            assert result["search_results"]["total_results"] == 2

    @pytest.mark.asyncio
    async def test_retrieve_cases_no_query(self):
        """Test with empty ticket context"""
        state = {"ticket_context": {}, "errors": []}
        result = await retrieve_cases(state)

        assert "search_results" not in result or not result.get("search_results", {}).get("similar_cases")

    @pytest.mark.asyncio
    async def test_retrieve_cases_timeout(self, mock_state):
        """Test timeout handling"""
        mock_service = MagicMock()
        mock_service.search = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch('backend.agents.retriever.HybridSearchService', return_value=mock_service):
            result = await retrieve_cases(mock_state)

            assert len(result["errors"]) > 0
            assert "timed out" in result["errors"][0].lower()


class TestRetrieveKB:
    """Test retrieve_kb function"""

    @pytest.mark.asyncio
    async def test_retrieve_kb_success(self, mock_state, mock_search_service):
        """Test successful KB retrieval"""
        with patch('backend.agents.retriever.HybridSearchService', return_value=mock_search_service):
            result = await retrieve_kb(mock_state)

            assert "search_results" in result
            assert "kb_procedures" in result["search_results"]
            assert len(result["search_results"]["kb_procedures"]) == 2

    @pytest.mark.asyncio
    async def test_retrieve_kb_error(self, mock_state):
        """Test error handling"""
        mock_service = MagicMock()
        mock_service.search = AsyncMock(side_effect=Exception("Search failed"))

        with patch('backend.agents.retriever.HybridSearchService', return_value=mock_service):
            result = await retrieve_kb(mock_state)

            assert len(result["errors"]) > 0
            assert "error" in result["errors"][0].lower()
