"""
LangGraph orchestrator - 워크플로우 그래프 조립
"""
from typing import Literal
from langgraph.graph import StateGraph, END

from backend.models.graph_state import AgentState
from backend.agents.retriever import retrieve_cases, retrieve_kb
from backend.agents.resolver import propose_solution, propose_field_updates
from backend.agents.router import context_router
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def router_decision_node(state: AgentState) -> AgentState:
    """
    context_router를 호출하고 결과를 state에 저장
    """
    route = await context_router(state)
    state["next_node"] = route
    logger.info(f"Router decision: {route}")
    return state


def router_condition(state: AgentState) -> Literal["retrieve_cases", "retrieve_kb", "propose_solution"]:
    """
    state의 next_node를 읽어서 다음 노드 결정
    """
    next_node = state.get("next_node", "propose_solution")
    logger.debug(f"Routing to: {next_node}")
    return next_node


def approval_condition(state: AgentState) -> Literal["propose_solution", "END"]:
    """
    approval_status에 따라 다음 노드 결정
    """
    approval_status = state.get("approval_status", "approved")

    if approval_status == "modified":
        logger.info("Approval modified, returning to propose_solution")
        return "propose_solution"
    elif approval_status == "rejected":
        logger.info("Approval rejected, ending workflow")
        return END
    else:  # approved
        logger.info("Approval approved, ending workflow")
        return END


async def error_handler(state: AgentState) -> AgentState:
    """
    에러 처리 노드
    """
    errors = state.get("errors", [])
    if errors:
        logger.error(f"Workflow errors: {errors}")
    else:
        logger.warning("Error handler called but no errors in state")

    state["error_handled"] = True
    state["final_status"] = "error"

    return state


async def human_approve(state: AgentState) -> AgentState:
    """
    인간 승인 대기 노드 (현재는 자동 승인)

    TODO: 실제 구현시 human-in-the-loop 패턴 적용
    - FastAPI 엔드포인트에서 approval_status 업데이트
    - 워크플로우 중단 후 대기
    - 승인/거부/수정 결정 받기
    """
    # 현재는 자동 승인
    state["approval_status"] = "approved"
    logger.info("Auto-approved (human approval placeholder)")

    return state


def build_graph() -> StateGraph:
    """
    LangGraph 워크플로우 그래프 생성

    플로우:
    1. START → router_decision_node
    2. router_decision_node → (retrieve_cases | retrieve_kb | propose_solution)
    3. retrieve_cases/retrieve_kb → propose_solution
    4. propose_solution → propose_field_updates
    5. propose_field_updates → human_approve
    6. human_approve → (END | propose_solution)
    """
    graph = StateGraph(AgentState)

    # 노드 추가
    graph.add_node("router_decision", router_decision_node)
    graph.add_node("retrieve_cases", retrieve_cases)
    graph.add_node("retrieve_kb", retrieve_kb)
    graph.add_node("propose_solution", propose_solution)
    graph.add_node("propose_field_updates", propose_field_updates)
    graph.add_node("human_approve", human_approve)
    graph.add_node("error_handler", error_handler)

    # 시작점 설정
    graph.set_entry_point("router_decision")

    # 조건부 엣지: router_decision → (retrieve_cases | retrieve_kb | propose_solution)
    graph.add_conditional_edges(
        "router_decision",
        router_condition,
        {
            "retrieve_cases": "retrieve_cases",
            "retrieve_kb": "retrieve_kb",
            "propose_solution": "propose_solution"
        }
    )

    # 티켓 플로우: retrieve_cases → propose_solution
    graph.add_edge("retrieve_cases", "propose_solution")

    # KB 플로우: retrieve_kb → propose_solution
    graph.add_edge("retrieve_kb", "propose_solution")

    # 공통 플로우: propose_solution → propose_field_updates → human_approve
    graph.add_edge("propose_solution", "propose_field_updates")
    graph.add_edge("propose_field_updates", "human_approve")

    # 승인 분기: human_approve → (END | propose_solution)
    graph.add_conditional_edges(
        "human_approve",
        approval_condition,
        {
            "propose_solution": "propose_solution",
            END: END
        }
    )

    # 에러 핸들링: error_handler → END
    graph.add_edge("error_handler", END)

    logger.info("LangGraph workflow graph built successfully")
    return graph


def compile_workflow():
    """
    워크플로우 컴파일 및 반환

    Returns:
        Compiled LangGraph workflow
    """
    logger.info("Compiling LangGraph workflow...")
    graph = build_graph()
    compiled = graph.compile()
    logger.info("Workflow compiled successfully")
    return compiled
