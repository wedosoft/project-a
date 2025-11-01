"""
LangGraph State Schema for AI Contact Center OS

This module defines the state schema for LangGraph workflow orchestration.
Provides both TypedDict (for LangGraph) and Pydantic (for validation) versions
with conversion functions.

State Flow:
    1. ticket_context: Input ticket information
    2. search_results: Retrieved similar cases and KB articles
    3. proposed_action: AI-generated suggestions
    4. approval_status: Human agent decision
    5. errors: Error tracking throughout the workflow
    6. metadata: Additional workflow metadata
"""
from typing import TypedDict, Optional, List, Dict, Any
from typing_extensions import NotRequired

from pydantic import BaseModel, Field, ConfigDict
from backend.models.schemas import (
    TicketContext,
    SearchResult,
    ProposedAction,
    ApprovalStatus
)


# ============================================================================
# TypedDict Definitions (for LangGraph)
# ============================================================================

class SearchResults(TypedDict):
    """Search results container"""
    similar_cases: List[Dict[str, Any]]
    kb_procedures: List[Dict[str, Any]]
    total_results: int


class AgentState(TypedDict):
    """
    LangGraph workflow state.

    This TypedDict is used by LangGraph for state management across nodes.
    All fields are optional (NotRequired) to allow partial state updates.

    State Lifecycle:
        1. START → ticket_context populated
        2. Retriever → search_results populated
        3. Resolution → proposed_action populated
        4. Human → approval_status populated
        5. Any node → errors updated if needed
    """
    ticket_context: NotRequired[Optional[Dict[str, Any]]]
    search_results: NotRequired[Optional[SearchResults]]
    proposed_action: NotRequired[Optional[Dict[str, Any]]]
    approval_status: NotRequired[Optional[str]]  # ApprovalStatus enum value
    errors: NotRequired[List[str]]
    metadata: NotRequired[Dict[str, Any]]


# ============================================================================
# Pydantic Definitions (for Validation)
# ============================================================================

class SearchResultsPydantic(BaseModel):
    """Pydantic version of SearchResults for validation"""
    model_config = ConfigDict(from_attributes=True)

    similar_cases: List[SearchResult] = Field(
        default_factory=list,
        description="List of similar support cases"
    )
    kb_procedures: List[SearchResult] = Field(
        default_factory=list,
        description="List of relevant KB procedures"
    )
    total_results: int = Field(
        default=0,
        ge=0,
        description="Total number of search results"
    )


class AgentStatePydantic(BaseModel):
    """
    Pydantic version of AgentState for validation and serialization.

    Use this for:
    - Input validation before workflow execution
    - State serialization/deserialization
    - API request/response validation
    """
    model_config = ConfigDict(from_attributes=True)

    ticket_context: Optional[TicketContext] = Field(
        None,
        description="Input ticket information"
    )
    search_results: Optional[SearchResultsPydantic] = Field(
        None,
        description="Search results from retriever"
    )
    proposed_action: Optional[ProposedAction] = Field(
        None,
        description="AI-proposed action"
    )
    approval_status: Optional[ApprovalStatus] = Field(
        None,
        description="Human approval decision"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during workflow"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional workflow metadata"
    )


# ============================================================================
# Conversion Functions
# ============================================================================

def pydantic_to_typed_dict(state: AgentStatePydantic) -> AgentState:
    """
    Convert Pydantic AgentState to TypedDict for LangGraph.

    Args:
        state: Pydantic AgentState instance

    Returns:
        TypedDict AgentState for LangGraph

    Example:
        >>> pydantic_state = AgentStatePydantic(ticket_context=ticket)
        >>> typed_dict_state = pydantic_to_typed_dict(pydantic_state)
    """
    result: AgentState = {}

    if state.ticket_context:
        result["ticket_context"] = state.ticket_context.model_dump()

    if state.search_results:
        result["search_results"] = {
            "similar_cases": [r.model_dump() for r in state.search_results.similar_cases],
            "kb_procedures": [r.model_dump() for r in state.search_results.kb_procedures],
            "total_results": state.search_results.total_results
        }

    if state.proposed_action:
        result["proposed_action"] = state.proposed_action.model_dump()

    if state.approval_status:
        result["approval_status"] = state.approval_status.value

    if state.errors:
        result["errors"] = state.errors.copy()

    if state.metadata:
        result["metadata"] = state.metadata.copy()

    return result


def typed_dict_to_pydantic(state: AgentState) -> AgentStatePydantic:
    """
    Convert TypedDict AgentState to Pydantic for validation.

    Args:
        state: TypedDict AgentState from LangGraph

    Returns:
        Pydantic AgentState instance

    Example:
        >>> typed_dict_state: AgentState = {"ticket_context": {...}}
        >>> pydantic_state = typed_dict_to_pydantic(typed_dict_state)
    """
    return AgentStatePydantic(
        ticket_context=TicketContext(**state["ticket_context"]) if state.get("ticket_context") else None,
        search_results=SearchResultsPydantic(
            similar_cases=[SearchResult(**r) for r in state["search_results"]["similar_cases"]],
            kb_procedures=[SearchResult(**r) for r in state["search_results"]["kb_procedures"]],
            total_results=state["search_results"]["total_results"]
        ) if state.get("search_results") else None,
        proposed_action=ProposedAction(**state["proposed_action"]) if state.get("proposed_action") else None,
        approval_status=ApprovalStatus(state["approval_status"]) if state.get("approval_status") else None,
        errors=state.get("errors", []),
        metadata=state.get("metadata", {})
    )


def create_initial_state(ticket_context: TicketContext) -> AgentState:
    """
    Create initial AgentState for workflow execution.

    Args:
        ticket_context: Input ticket information

    Returns:
        Initial AgentState with only ticket_context populated

    Example:
        >>> ticket = TicketContext(ticket_id="123", ...)
        >>> initial_state = create_initial_state(ticket)
    """
    return {
        "ticket_context": ticket_context.model_dump(),
        "errors": [],
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "workflow_version": "1.0.0"
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================

def add_error(state: AgentState, error: str) -> AgentState:
    """
    Add error to state.

    Args:
        state: Current AgentState
        error: Error message to add

    Returns:
        Updated AgentState with error added
    """
    errors = state.get("errors", [])
    errors.append(error)
    state["errors"] = errors
    return state


def has_errors(state: AgentState) -> bool:
    """
    Check if state has any errors.

    Args:
        state: Current AgentState

    Returns:
        True if state has errors, False otherwise
    """
    return len(state.get("errors", [])) > 0


def get_latest_error(state: AgentState) -> Optional[str]:
    """
    Get the most recent error from state.

    Args:
        state: Current AgentState

    Returns:
        Latest error message or None if no errors
    """
    errors = state.get("errors", [])
    return errors[-1] if errors else None


# Import datetime for metadata
from datetime import datetime
