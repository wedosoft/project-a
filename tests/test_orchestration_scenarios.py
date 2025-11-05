"""
AI 에이전트 오케스트레이션 시나리오 테스트

이 테스트는 LangGraph 워크플로우의 각 경로를 검증합니다:
1. Scenario 1: Error 티켓 → retrieve_cases 경로
2. Scenario 2: How-to 티켓 → retrieve_kb 경로
3. Scenario 3: 일반 문의 → 직접 propose_solution 경로
"""

import pytest
import asyncio
from backend.agents.orchestrator import compile_workflow
from backend.models.schemas import TicketContext
from backend.models.graph_state import create_initial_state


class TestOrchestrationScenarios:
    """오케스트레이션 시나리오 테스트 스위트"""

    @pytest.mark.asyncio
    async def test_scenario_1_error_ticket_retrieves_cases(self):
        """
        Scenario 1: 에러 티켓 처리

        입력: "Database connection error" 티켓
        예상 플로우:
        1. Router가 "error" 키워드 감지
        2. retrieve_cases 경로로 라우팅
        3. 유사 티켓 검색 (현재 벡터 DB 비어있음)
        4. propose_solution 실행
        5. propose_field_updates 실행
        6. human_approve (자동 승인)
        7. END
        """
        # Given: 에러 티켓
        ticket = TicketContext(
            ticket_id="TEST-001",
            subject="Database connection error",
            description="Production database error: connection timeout after 30s",
            priority="high",
            status="open"
        )

        initial_state = create_initial_state(ticket)

        # When: 워크플로우 실행
        workflow = compile_workflow()
        result = await workflow.ainvoke(initial_state)

        # Then: Router가 retrieve_cases로 라우팅했는지 확인
        assert result["next_node"] == "retrieve_cases", \
            f"Expected 'retrieve_cases' but got '{result.get('next_node')}'"

        # Then: 워크플로우가 완료되었는지 확인
        assert "approval_status" in result, "Workflow should complete with approval_status"
        assert result["approval_status"] == "approved", "Should be auto-approved"

        # Then: 솔루션이 생성되었는지 확인
        assert "proposed_action" in result, "Should have proposed action"

        print("✅ Scenario 1: Error ticket successfully routed to retrieve_cases")

    @pytest.mark.asyncio
    async def test_scenario_2_howto_ticket_retrieves_kb(self):
        """
        Scenario 2: How-to 티켓 처리

        입력: "How to setup email integration" 티켓
        예상 플로우:
        1. Router가 "how to", "setup" 키워드 감지
        2. retrieve_kb 경로로 라우팅
        3. KB 문서 검색
        4. propose_solution 실행
        5. propose_field_updates 실행
        6. human_approve
        7. END
        """
        # Given: How-to 티켓
        ticket = TicketContext(
            ticket_id="TEST-002",
            subject="How to setup email integration",
            description="Please guide me on setting up email integration with Gmail",
            priority="medium",
            status="open"
        )

        initial_state = create_initial_state(ticket)

        # When: 워크플로우 실행
        workflow = compile_workflow()
        result = await workflow.ainvoke(initial_state)

        # Then: Router가 retrieve_kb로 라우팅했는지 확인
        assert result["next_node"] == "retrieve_kb", \
            f"Expected 'retrieve_kb' but got '{result.get('next_node')}'"

        # Then: 워크플로우가 완료되었는지 확인
        assert result["approval_status"] == "approved"

        # Then: 솔루션이 생성되었는지 확인
        assert "proposed_action" in result

        print("✅ Scenario 2: How-to ticket successfully routed to retrieve_kb")

    @pytest.mark.asyncio
    async def test_scenario_3_general_inquiry_direct_solution(self):
        """
        Scenario 3: 일반 문의 처리

        입력: "Pricing inquiry" 티켓
        예상 플로우:
        1. Router가 특정 키워드 미감지
        2. 기본값 retrieve_cases로 라우팅 (또는 직접 propose_solution)
        3. propose_solution 실행
        4. propose_field_updates 실행
        5. human_approve
        6. END
        """
        # Given: 일반 문의 티켓
        ticket = TicketContext(
            ticket_id="TEST-003",
            subject="Pricing inquiry",
            description="What are your pricing plans for enterprise customers?",
            priority="low",
            status="open"
        )

        initial_state = create_initial_state(ticket)

        # When: 워크플로우 실행
        workflow = compile_workflow()
        result = await workflow.ainvoke(initial_state)

        # Then: Router가 기본값으로 라우팅했는지 확인
        assert result["next_node"] in ["retrieve_cases", "propose_solution"], \
            f"Expected default routing but got '{result.get('next_node')}'"

        # Then: 워크플로우가 완료되었는지 확인
        assert result["approval_status"] == "approved"

        # Then: 솔루션이 생성되었는지 확인
        assert "proposed_action" in result

        print("✅ Scenario 3: General inquiry successfully handled")

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        """
        상태 전이 검증

        각 노드가 상태를 올바르게 업데이트하는지 확인:
        1. ticket_context → 초기 상태
        2. next_node → Router가 설정
        3. search_results → Retriever가 설정
        4. proposed_action → Resolver가 설정
        5. approval_status → Human Agent가 설정
        """
        # Given: 에러 티켓
        ticket = TicketContext(
            ticket_id="TEST-STATE-001",
            subject="Login failure",
            description="User cannot login with correct credentials",
            priority="high",
            status="open"
        )

        initial_state = create_initial_state(ticket)

        # When: 워크플로우 실행
        workflow = compile_workflow()
        result = await workflow.ainvoke(initial_state)

        # Then: 각 상태 필드가 업데이트되었는지 확인
        assert "ticket_context" in result, "Should have ticket_context"
        assert "next_node" in result, "Router should set next_node"
        assert "proposed_action" in result, "Resolver should set proposed_action"
        assert "approval_status" in result, "Human agent should set approval_status"

        # Then: 에러가 없는지 확인
        assert len(result.get("errors", [])) == 0, \
            f"Should have no errors, but got: {result.get('errors')}"

        print("✅ State transitions validated successfully")

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """
        에러 핸들링 검증

        잘못된 입력이나 예외 상황에서 워크플로우가 안전하게 처리하는지 확인
        """
        # Given: 빈 티켓 (극단적 케이스)
        ticket = TicketContext(
            ticket_id="TEST-ERROR-001",
            subject="",
            description="",
            priority="low",
            status="open"
        )

        initial_state = create_initial_state(ticket)

        # When: 워크플로우 실행
        workflow = compile_workflow()

        try:
            result = await workflow.ainvoke(initial_state)

            # Then: 워크플로우가 완료되었는지 확인
            assert "approval_status" in result, "Should complete even with empty ticket"

            print("✅ Error handling: Workflow completed safely with empty ticket")

        except Exception as e:
            # Then: 예외가 발생해도 적절히 로깅되어야 함
            pytest.fail(f"Workflow should handle errors gracefully, but raised: {e}")

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """
        타임아웃 처리 검증

        Router와 Retriever의 30초 타임아웃이 작동하는지 확인
        (실제 타임아웃은 발생하지 않지만, 로직이 존재하는지 확인)
        """
        # Given: 정상 티켓
        ticket = TicketContext(
            ticket_id="TEST-TIMEOUT-001",
            subject="Normal ticket",
            description="This should complete within 30 seconds",
            priority="medium",
            status="open"
        )

        initial_state = create_initial_state(ticket)

        # When: 워크플로우 실행 (타임아웃 없이 완료되어야 함)
        workflow = compile_workflow()

        # 전체 워크플로우에 타임아웃 설정 (120초)
        result = await asyncio.wait_for(workflow.ainvoke(initial_state), timeout=120.0)

        # Then: 타임아웃 없이 완료되었는지 확인
        assert "approval_status" in result, "Should complete without timeout"
        assert result["approval_status"] == "approved"

        print("✅ Timeout handling: Workflow completed within timeout")


if __name__ == "__main__":
    """
    테스트 실행 방법:

    # 프로젝트 루트에서 실행
    cd /Users/alan/GitHub/project-a-spinoff
    source venv/bin/activate

    # 모든 시나리오 테스트
    pytest tests/test_orchestration_scenarios.py -v

    # 특정 시나리오만 실행
    pytest tests/test_orchestration_scenarios.py::TestOrchestrationScenarios::test_scenario_1_error_ticket_retrieves_cases -v

    # 자세한 출력과 함께 실행
    pytest tests/test_orchestration_scenarios.py -v -s
    """
    pytest.main([__file__, "-v", "-s"])
