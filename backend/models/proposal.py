"""
AI Proposal data models
"""
from pydantic import BaseModel
from typing import Dict, Any, List


class SimilarCase(BaseModel):
    """Similar case from retrieval"""
    ticket_id: str
    summary: str
    similarity_score: float
    resolution: str


class KBProcedure(BaseModel):
    """KB procedure from retrieval"""
    doc_id: str
    title: str
    steps: List[str]
    notes: str = ""


class AIProposal(BaseModel):
    """AI-generated proposal for agent"""
    draft_response: str
    field_updates: Dict[str, Any]
    similar_cases: List[SimilarCase]
    kb_procedures: List[KBProcedure]
    justification: str
    confidence_score: float = 0.0
