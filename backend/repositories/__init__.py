"""
Repositories package for database operations

Provides repository classes for CRUD operations on:
- issue_blocks table (IssueRepository)
- kb_blocks table (KBRepository)
"""
from backend.repositories.issue_repository import IssueRepository
from backend.repositories.kb_repository import KBRepository

__all__ = [
    "IssueRepository",
    "KBRepository",
]
