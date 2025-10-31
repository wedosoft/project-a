"""
LangGraph State Schema
"""
from typing import TypedDict, List, Optional, Dict, Any


class AgentState(TypedDict):
    """
    Shared state across LangGraph workflow

    Flow:
    1. Input: ticket_id, ticket_content, ticket_meta
    2. Retriever: similar_cases, kb_procedures
    3. Resolution: draft_response, field_updates, justification
    4. Human: approval_status, final_response
    """

    # Input (from API)
    ticket_id: str
    ticket_content: str
    ticket_meta: Dict[str, Any]

    # Retriever outputs
    similar_cases: Optional[List[Dict[str, Any]]]
    kb_procedures: Optional[List[Dict[str, Any]]]

    # Resolution outputs
    draft_response: Optional[str]
    field_updates: Optional[Dict[str, Any]]
    justification: Optional[str]

    # Human outputs
    approval_status: Optional[str]  # approved | modified | rejected
    final_response: Optional[str]
    final_field_updates: Optional[Dict[str, Any]]

    # Control
    current_step: str
    error: Optional[str]
