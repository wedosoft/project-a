"""
Feedback and approval log models
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ApprovalStatus(str, Enum):
    """Approval status enum"""
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


class ApprovalLog(BaseModel):
    """Approval log for Supabase"""
    tenant_id: str
    ticket_id: str
    draft_response: str
    final_response: str
    field_updates: Dict[str, Any]
    approval_status: ApprovalStatus
    agent_id: str
    feedback_notes: Optional[str] = None
    created_at: Optional[datetime] = None
