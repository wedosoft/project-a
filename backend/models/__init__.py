"""
Data Models
"""
from backend.models.ticket import TicketContext
from backend.models.proposal import AIProposal, SimilarCase, KBProcedure
from backend.models.feedback import ApprovalLog, ApprovalStatus

__all__ = [
    "TicketContext",
    "AIProposal",
    "SimilarCase",
    "KBProcedure",
    "ApprovalLog",
    "ApprovalStatus",
]
