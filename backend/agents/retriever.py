"""
LangGraph Retriever Agent
Retrieves similar cases and KB articles using hybrid search
"""

import asyncio
from typing import Dict, Any
from backend.models.graph_state import AgentState
from backend.services.hybrid_search import HybridSearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def retrieve_cases(state: AgentState) -> AgentState:
    """
    Retrieve similar cases from issue_cases collection

    Args:
        state: Current agent state with ticket context

    Returns:
        Updated state with similar_cases in search_results
    """
    try:
        logger.info("Retrieving similar cases")

        # Extract search query from ticket context
        ticket_context = state.get("ticket_context", {})
        query_parts = []

        if ticket_context.get("symptom"):
            query_parts.append(ticket_context["symptom"])
        if ticket_context.get("subject"):
            query_parts.append(ticket_context["subject"])
        if ticket_context.get("description"):
            query_parts.append(ticket_context["description"])

        query = " ".join(query_parts)

        if not query:
            logger.warning("No search query available from ticket context")
            return state

        # Search similar cases with timeout
        search_service = HybridSearchService()
        results = await asyncio.wait_for(
            search_service.search(
                collection_name="support_tickets",
                query=query,
                top_k=5,
                use_reranking=True
            ),
            timeout=30.0
        )

        # Update state
        if "search_results" not in state:
            state["search_results"] = {
                "similar_cases": [],
                "kb_procedures": [],
                "total_results": 0
            }
        state["search_results"]["similar_cases"] = [r for r in results]
        state["search_results"]["total_results"] = len(results)

        logger.info(f"Retrieved {len(results)} similar cases")
        return state

    except asyncio.TimeoutError:
        error_msg = "Case retrieval timed out after 30 seconds"
        logger.error(error_msg)
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        return state

    except Exception as e:
        error_msg = f"Error retrieving cases: {str(e)}"
        logger.error(error_msg)
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        return state


async def retrieve_kb(state: AgentState) -> AgentState:
    """
    Retrieve KB articles from kb_procedures collection

    Args:
        state: Current agent state with ticket context

    Returns:
        Updated state with kb_procedures in search_results
    """
    try:
        logger.info("Retrieving KB procedures")

        # Extract search query from ticket context
        ticket_context = state.get("ticket_context", {})
        query_parts = []

        if ticket_context.get("symptom"):
            query_parts.append(ticket_context["symptom"])
        if ticket_context.get("subject"):
            query_parts.append(ticket_context["subject"])
        if ticket_context.get("description"):
            query_parts.append(ticket_context["description"])

        query = " ".join(query_parts)

        if not query:
            logger.warning("No search query available from ticket context")
            return state

        # Search KB procedures with timeout
        search_service = HybridSearchService()
        results = await asyncio.wait_for(
            search_service.search(
                collection_name="kb_procedures",
                query=query,
                top_k=5,
                use_reranking=True
            ),
            timeout=30.0
        )

        # Update state
        if "search_results" not in state:
            state["search_results"] = {
                "similar_cases": [],
                "kb_procedures": [],
                "total_results": 0
            }
        state["search_results"]["kb_procedures"] = [r for r in results]
        state["search_results"]["total_results"] = state["search_results"].get("total_results", 0) + len(results)

        logger.info(f"Retrieved {len(results)} KB articles")
        return state

    except asyncio.TimeoutError:
        error_msg = "KB retrieval timed out after 30 seconds"
        logger.error(error_msg)
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        return state

    except Exception as e:
        error_msg = f"Error retrieving KB articles: {str(e)}"
        logger.error(error_msg)
        if "errors" not in state:
            state["errors"] = []
        state["errors"].append(error_msg)
        return state
