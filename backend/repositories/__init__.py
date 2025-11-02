"""
Repositories package for database operations

Provides repository classes for CRUD operations on:
- issue_blocks table (IssueRepository)
- kb_blocks table (KBRepository)
- approval_logs table (ApprovalRepository)
"""
from backend.repositories.issue_repository import IssueRepository
from backend.repositories.kb_repository import KBRepository
from backend.repositories.approval_repository import ApprovalRepository

__all__ = [
    "IssueRepository",
    "KBRepository",
    "ApprovalRepository",
]
