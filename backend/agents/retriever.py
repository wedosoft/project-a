"""
LangGraph Retriever Agent
Retrieves similar cases and KB articles using hybrid search

POC Modifications:
- Integrates with tenant_configs for embedding control
- Uses Supabase issue_blocks and kb_blocks tables
- Supports tenant isolation via RLS

Author: AI Assistant POC
Date: 2025-11-05
"""

import asyncio
from typing import Dict, Any, List
from backend.models.graph_state import AgentState
from backend.services.hybrid_search import HybridSearchService
from backend.repositories.tenant_repository import TenantRepository
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def retrieve_cases(state: AgentState) -> AgentState:
    """
    Retrieve similar cases from issue_blocks table (POC).

    POC Changes:
    - Uses issue_blocks table instead of Qdrant collection
    - Checks tenant config for embedding_enabled
    - Returns empty if embedding disabled

    Args:
        state: Current agent state with ticket context and tenant_config

    Returns:
        Updated state with similar_cases in search_results
    """
    try:
        logger.info("Retrieving similar cases")

        # Check if embedding is enabled
        tenant_config = state.get("tenant_config")
        if not tenant_config or not tenant_config.get("embedding_enabled"):
            logger.info("Embedding disabled for tenant, skipping case retrieval")
            if "search_results" not in state:
                state["search_results"] = {
                    "similar_cases": [],
                    "kb_procedures": [],
                    "total_results": 0
                }
            return state

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
        # POC: Using HybridSearchService which should be configured to use issue_blocks
        search_service = HybridSearchService()
        results = await asyncio.wait_for(
            search_service.search(
                collection_name="issue_blocks",  # Changed to issue_blocks table
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
    Retrieve KB articles from kb_blocks table (POC).

    POC Changes:
    - Uses kb_blocks table instead of Qdrant collection
    - Checks tenant config for embedding_enabled
    - Returns empty if embedding disabled

    Args:
        state: Current agent state with ticket context and tenant_config

    Returns:
        Updated state with kb_procedures in search_results
    """
    try:
        logger.info("Retrieving KB procedures")

        # Check if embedding is enabled
        tenant_config = state.get("tenant_config")
        if not tenant_config or not tenant_config.get("embedding_enabled"):
            logger.info("Embedding disabled for tenant, skipping KB retrieval")
            if "search_results" not in state:
                state["search_results"] = {
                    "similar_cases": [],
                    "kb_procedures": [],
                    "total_results": 0
                }
            return state

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
        # POC: Using HybridSearchService which should be configured to use kb_blocks
        search_service = HybridSearchService()
        results = await asyncio.wait_for(
            search_service.search(
                collection_name="kb_blocks",  # Changed to kb_blocks table
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
