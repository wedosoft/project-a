"""
LangGraph Router Agent - 티켓 컨텍스트 기반 라우팅
"""
import asyncio
from backend.models.graph_state import AgentState
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def context_router(state: AgentState) -> str:
    """
    티켓 컨텍스트 기반 라우팅 결정

    Args:
        state: AgentState with ticket_context and search_results

    Returns:
        Next node name: "retrieve_cases" | "retrieve_kb" | "propose_solution"
    """
    try:
        logger.info("Starting context routing")

        async def route_logic():
            # 검색 결과가 이미 있으면 solution 생성
            if state.get("search_results"):
                logger.debug("Search results exist, routing to propose_solution")
                return "propose_solution"

            # 티켓 컨텍스트 분석
            ticket_context = state.get("ticket_context", {})
            subject = ticket_context.get("subject", "").lower()
            description = ticket_context.get("description", "").lower()
            combined_text = f"{subject} {description}"

            logger.debug(f"Analyzing context: subject='{subject[:50]}...', description length={len(description)}")

            # KB 검색 키워드
            kb_keywords = ["how to", "procedure", "guide", "tutorial", "manual", "setup", "configuration"]
            if any(kw in combined_text for kw in kb_keywords):
                logger.info("KB keywords detected, routing to retrieve_kb")
                return "retrieve_kb"

            # 케이스 검색 키워드
            case_keywords = ["error", "issue", "problem", "bug", "failed", "not working", "broken"]
            if any(kw in combined_text for kw in case_keywords):
                logger.info("Issue keywords detected, routing to retrieve_cases")
                return "retrieve_cases"

            # 기본값: 케이스 검색
            logger.info("No specific keywords, defaulting to retrieve_cases")
            return "retrieve_cases"

        next_node = await asyncio.wait_for(route_logic(), timeout=30.0)
        logger.info(f"Routing decision: {next_node}")
        return next_node

    except asyncio.TimeoutError:
        logger.error("Context routing timeout (30s), defaulting to retrieve_cases")
        return "retrieve_cases"
    except Exception as e:
        logger.error(f"Context routing error: {e}", exc_info=True)
        return "retrieve_cases"
