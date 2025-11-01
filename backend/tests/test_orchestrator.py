"""
LangGraph Orchestrator Integration Tests
Tests workflow graph construction and execution paths
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.agents.orchestrator import (
    build_graph,
    compile_workflow,
    router_condition,
    approval_condition,
    error_handler,
    human_approve,
)


@pytest.fixture
def mock_ticket_state():
    """티켓 관련 state (error 키워드 포함)"""
    return {
        "ticket_context": {
            "ticket_id": "TEST-001",
            "subject": "Database connection error",
            "description": "Production database error",
            "priority": "high"
        },
        "next_node": "retrieve_cases",
        "errors": []
    }


@pytest.fixture
def mock_kb_state():
    """KB 관련 state (how to 키워드 포함)"""
    return {
        "ticket_context": {
            "ticket_id": "TEST-002",
            "subject": "How to configure SSL",
            "description": "Need guide for SSL configuration",
            "priority": "medium"
        },
        "next_node": "retrieve_kb",
        "errors": []
    }


class TestWorkflowGraph:
    """워크플로우 그래프 구조 테스트"""

    def test_build_graph(self):
        """그래프 생성 테스트"""
        graph = build_graph()
        assert graph is not None
        assert hasattr(graph, 'nodes')

    def test_compile_workflow(self):
        """워크플로우 컴파일 테스트"""
        workflow = compile_workflow()
        assert workflow is not None

    def test_graph_nodes(self):
        """모든 노드가 추가되었는지 확인"""
        graph = build_graph()
        nodes = graph.nodes

        expected_nodes = {
            "router_decision",
            "retrieve_cases",
            "retrieve_kb",
            "propose_solution",
            "propose_field_updates",
            "human_approve",
            "error_handler"
        }

        assert all(node in nodes for node in expected_nodes)


class TestRouterCondition:
    """라우터 조건 테스트"""

    def test_route_to_cases(self, mock_ticket_state):
        """retrieve_cases 경로 테스트"""
        result = router_condition(mock_ticket_state)
        assert result == "retrieve_cases"

    def test_route_to_kb(self, mock_kb_state):
        """retrieve_kb 경로 테스트"""
        result = router_condition(mock_kb_state)
        assert result == "retrieve_kb"

    def test_route_to_solution_default(self):
        """기본 경로 테스트"""
        state = {"next_node": "propose_solution"}
        result = router_condition(state)
        assert result == "propose_solution"


class TestApprovalCondition:
    """승인 조건 테스트"""

    def test_approval_approved(self):
        """approved 상태로 END"""
        from langgraph.graph import END
        state = {"approval_status": "approved"}
        result = approval_condition(state)
        assert result == END

    def test_approval_modified(self):
        """modified 상태로 propose_solution 루프백"""
        state = {"approval_status": "modified"}
        result = approval_condition(state)
        assert result == "propose_solution"

    def test_approval_rejected(self):
        """rejected 상태로 END"""
        from langgraph.graph import END
        state = {"approval_status": "rejected"}
        result = approval_condition(state)
        assert result == END

    def test_approval_default(self):
        """기본값 (approved) 테스트"""
        from langgraph.graph import END
        state = {}
        result = approval_condition(state)
        assert result == END


class TestErrorHandler:
    """에러 핸들러 테스트"""

    @pytest.mark.asyncio
    async def test_error_handler_with_errors(self):
        """에러가 있는 경우"""
        state = {
            "errors": ["Error 1", "Error 2"],
            "ticket_context": {"ticket_id": "TEST-001"}
        }

        result = await error_handler(state)

        assert result["error_handled"] is True
        assert result["final_status"] == "error"

    @pytest.mark.asyncio
    async def test_error_handler_without_errors(self):
        """에러가 없는 경우"""
        state = {
            "ticket_context": {"ticket_id": "TEST-001"}
        }

        result = await error_handler(state)

        assert result["error_handled"] is True
        assert result["final_status"] == "error"


class TestHumanApprove:
    """승인 노드 테스트"""

    @pytest.mark.asyncio
    async def test_human_approve_auto_approved(self):
        """자동 승인 테스트"""
        state = {
            "ticket_context": {"ticket_id": "TEST-001"},
            "proposed_action": {"draft_response": "Test solution"}
        }

        result = await human_approve(state)

        assert result["approval_status"] == "approved"


class TestWorkflowExecution:
    """전체 워크플로우 실행 테스트"""

    @pytest.mark.asyncio
    async def test_ticket_flow_nodes_exist(self):
        """티켓 플로우 노드 존재 확인"""
        graph = build_graph()

        # 티켓 플로우에 필요한 노드들
        required_nodes = ["router_decision", "retrieve_cases", "propose_solution", "human_approve"]

        for node in required_nodes:
            assert node in graph.nodes

    @pytest.mark.asyncio
    async def test_kb_flow_nodes_exist(self):
        """KB 플로우 노드 존재 확인"""
        graph = build_graph()

        # KB 플로우에 필요한 노드들
        required_nodes = ["router_decision", "retrieve_kb", "propose_solution", "human_approve"]

        for node in required_nodes:
            assert node in graph.nodes
