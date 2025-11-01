"""
Shared utilities for LangGraph agents
"""

import asyncio
from functools import wraps
from typing import Dict, Any, List, Callable

from backend.models.graph_state import AgentState, SearchResults
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def with_timeout(timeout: float = 30.0):
    """
    Apply timeout to async function

    Args:
        timeout: Timeout in seconds (default: 30.0)

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {timeout}s")
                raise
        return wrapper
    return decorator


def with_error_handling(func: Callable) -> Callable:
    """
    Apply error handling to async function

    Args:
        func: Async function to wrap

    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    async def wrapper(state: AgentState, *args, **kwargs) -> AgentState:
        try:
            return await func(state, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            if "errors" not in state:
                state["errors"] = []
            error_msg = f"{func.__name__}: {str(e)}"
            state["errors"].append(error_msg)
            return state
    return wrapper


def extract_query_text(ticket_context: Dict[str, Any]) -> str:
    """
    Extract search query text from ticket context

    Args:
        ticket_context: Ticket context dictionary

    Returns:
        Combined query text
    """
    parts = []

    if "subject" in ticket_context:
        parts.append(ticket_context["subject"])

    if "description" in ticket_context:
        parts.append(ticket_context["description"])

    if "symptom" in ticket_context:
        parts.append(ticket_context["symptom"])

    query = " ".join(parts).strip()
    logger.debug(f"Extracted query text: {query[:100]}...")
    return query


def calculate_confidence(search_results: List[Dict[str, Any]]) -> float:
    """
    Calculate confidence score from search results

    Args:
        search_results: List of search result dictionaries

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not search_results:
        return 0.0

    count = len(search_results)
    avg_score = sum(r.get("score", 0.0) for r in search_results) / count

    # 검색 결과 개수와 평균 score를 고려
    count_factor = min(count / 10.0, 1.0)
    confidence = (avg_score * 0.7) + (count_factor * 0.3)

    confidence = max(0.0, min(1.0, confidence))
    logger.debug(f"Calculated confidence: {confidence:.2f} (results={count}, avg_score={avg_score:.2f})")
    return confidence


def format_search_results(
    similar_cases: List[Dict[str, Any]],
    kb_procedures: List[Dict[str, Any]]
) -> SearchResults:
    """
    Format raw search results to SearchResults TypedDict

    Args:
        similar_cases: List of similar case search results
        kb_procedures: List of KB article search results

    Returns:
        Formatted SearchResults
    """
    total_results = len(similar_cases) + len(kb_procedures)

    formatted: SearchResults = {
        "similar_cases": similar_cases,
        "kb_procedures": kb_procedures,
        "total_results": total_results
    }

    logger.debug(f"Formatted search results: {len(similar_cases)} cases, {len(kb_procedures)} KB articles")
    return formatted
