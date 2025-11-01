"""
Unit tests for Resolution Agent
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from backend.agents.resolver import propose_solution, propose_field_updates


@pytest.fixture
def mock_state_with_search():
    """Mock AgentState with search results"""
    return {
        "ticket_context": {
            "ticket_id": "123",
            "subject": "Login error",
            "description": "Cannot login",
            "priority": "high"
        },
        "search_results": {
            "similar_cases": [{"content": "Case 1"}],
            "kb_procedures": [{"content": "KB 1"}]
        },
        "errors": []
    }


@pytest.fixture
def mock_state_with_proposal():
    """Mock AgentState with proposed action"""
    return {
        "ticket_context": {
            "ticket_id": "123",
            "subject": "Login error",
            "status": "open",
            "priority": "medium"
        },
        "proposed_action": {
            "draft_response": "Please try clearing your cookies",
            "confidence": 0.8
        },
        "errors": []
    }


class TestProposeSolution:
    """Test propose_solution function"""

    @pytest.mark.asyncio
    async def test_propose_solution_success(self, mock_state_with_search):
        """Test successful solution generation"""
        mock_response = MagicMock()
        mock_response.text = "SOLUTION:\nClear cookies and cache\n\nCONFIDENCE: 0.85"

        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(return_value=mock_response)

        with patch('backend.agents.resolver.genai.GenerativeModel', return_value=mock_model):
            with patch('backend.agents.resolver.genai.configure'):
                result = await propose_solution(mock_state_with_search)

                assert "proposed_action" in result
                assert "draft_response" in result["proposed_action"]
                assert "confidence" in result["proposed_action"]

    @pytest.mark.asyncio
    async def test_propose_solution_timeout(self, mock_state_with_search):
        """Test timeout handling"""
        with patch('backend.agents.resolver.genai.configure'):
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
                result = await propose_solution(mock_state_with_search)

                assert len(result["errors"]) > 0


class TestProposeFieldUpdates:
    """Test propose_field_updates function"""

    @pytest.mark.asyncio
    async def test_propose_field_updates_success(self, mock_state_with_proposal):
        """Test successful field updates proposal"""
        mock_response = MagicMock()
        mock_response.text = """PRIORITY: high
STATUS: resolved
TAGS: authentication, cookies
JUSTIFICATION: Based on solution confidence"""

        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(return_value=mock_response)

        with patch('backend.agents.resolver.genai.GenerativeModel', return_value=mock_model):
            with patch('backend.agents.resolver.genai.configure'):
                result = await propose_field_updates(mock_state_with_proposal)

                assert "proposed_action" in result
                assert "proposed_field_updates" in result["proposed_action"]

    @pytest.mark.asyncio
    async def test_propose_field_updates_error(self, mock_state_with_proposal):
        """Test error handling"""
        with patch('backend.agents.resolver.genai.configure', side_effect=Exception("API error")):
            result = await propose_field_updates(mock_state_with_proposal)

            assert len(result["errors"]) > 0
