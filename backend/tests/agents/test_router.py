"""
Unit tests for Router Agent
"""
import pytest
from backend.agents.router import context_router


@pytest.fixture
def mock_state_kb():
    """Mock state for KB routing"""
    return {
        "ticket_context": {
            "subject": "How to setup email",
            "description": "Need guide for email configuration"
        }
    }


@pytest.fixture
def mock_state_case():
    """Mock state for case routing"""
    return {
        "ticket_context": {
            "subject": "Login error",
            "description": "Getting error when trying to login"
        }
    }


@pytest.fixture
def mock_state_with_results():
    """Mock state with existing search results"""
    return {
        "ticket_context": {
            "subject": "Test",
            "description": "Test"
        },
        "search_results": {
            "similar_cases": [{"id": "1"}]
        }
    }


class TestContextRouter:
    """Test context_router function"""

    @pytest.mark.asyncio
    async def test_route_to_kb(self, mock_state_kb):
        """Test routing to KB retrieval"""
        result = await context_router(mock_state_kb)
        assert result == "retrieve_kb"

    @pytest.mark.asyncio
    async def test_route_to_cases(self, mock_state_case):
        """Test routing to case retrieval"""
        result = await context_router(mock_state_case)
        assert result == "retrieve_cases"

    @pytest.mark.asyncio
    async def test_route_to_solution(self, mock_state_with_results):
        """Test routing to solution when results exist"""
        result = await context_router(mock_state_with_results)
        assert result == "propose_solution"

    @pytest.mark.asyncio
    async def test_route_default(self):
        """Test default routing"""
        state = {
            "ticket_context": {
                "subject": "Random text",
                "description": "No specific keywords"
            }
        }
        result = await context_router(state)
        assert result == "retrieve_cases"
