"""
Ticket data models
"""
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime


class TicketContext(BaseModel):
    """Ticket context for AI processing"""
    ticket_id: str
    subject: str
    description: str
    status: str
    priority: str
    category: Optional[str] = None
    tags: list[str] = []
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
