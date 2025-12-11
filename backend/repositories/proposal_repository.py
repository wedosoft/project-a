"""
Proposal Repository

Manages AI-generated proposals with versioning and status tracking.

Author: AI Assistant POC
Date: 2025-11-05
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel
from uuid import UUID
import logging

from backend.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class Proposal(BaseModel):
    """Proposal model matching database schema."""
    id: str
    tenant_id: str
    ticket_id: str
    proposal_version: int = 1

    # Proposal content
    draft_response: str
    field_updates: Optional[Dict[str, Any]] = None
    field_reasons: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: Optional[str] = None  # high | medium | low
    mode: Optional[str] = None  # synthesis | direct | fallback

    # References
    similar_cases: Optional[List[Dict]] = None
    kb_references: Optional[List[Dict]] = None

    # Status tracking
    status: str = "draft"  # draft | approved | rejected | superseded
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # Metadata
    analysis_time_ms: Optional[int] = None
    token_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalLog(BaseModel):
    """Approval log model for audit trail."""
    id: str
    proposal_id: str
    action: str  # approve | reject | refine
    agent_email: Optional[str] = None
    feedback: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProposalRepository(BaseRepository):
    """
    Repository for proposal CRUD operations and versioning.

    Handles:
    - Proposal creation and retrieval
    - Status updates (draft → approved/rejected/superseded)
    - Version management for refinements
    - Approval log audit trail
    """

    async def create(self, proposal_data: Dict[str, Any]) -> Proposal:
        """
        Create new proposal.

        Args:
            proposal_data: Proposal fields (tenant_id, ticket_id, draft_response, etc.)

        Returns:
            Created Proposal object

        Raises:
            Exception: If creation fails

        Example:
            >>> repo = ProposalRepository()
            >>> await repo.set_tenant_context('demo-tenant')
            >>> proposal = await repo.create({
            ...     'tenant_id': 'demo-tenant',
            ...     'ticket_id': 'TKT-123',
            ...     'draft_response': 'Here is the solution...',
            ...     'confidence': 'high',
            ...     'mode': 'synthesis'
            ... })
        """
        try:
            result = self.client.table("proposals").insert(
                proposal_data
            ).execute()

            if result.data and len(result.data) > 0:
                proposal = Proposal(**result.data[0])
                logger.info(
                    f"Created proposal {proposal.id} for ticket {proposal.ticket_id}"
                )
                return proposal

            raise Exception("No data returned from insert")

        except Exception as e:
            self._handle_error("create_proposal", e)

    async def get_by_id(self, proposal_id: str) -> Optional[Proposal]:
        """
        Fetch proposal by ID.

        Args:
            proposal_id: Proposal UUID

        Returns:
            Proposal object or None if not found
        """
        try:
            result = self.client.table("proposals").select("*").eq(
                "id", proposal_id
            ).execute()

            if result.data and len(result.data) > 0:
                return Proposal(**result.data[0])

            logger.warning(f"Proposal {proposal_id} not found")
            return None

        except Exception as e:
            logger.error(f"Error fetching proposal: {e}")
            return None

    async def get_by_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None
    ) -> List[Proposal]:
        """
        Get all proposals for a ticket.

        Args:
            ticket_id: Ticket identifier
            status: Optional status filter (draft, approved, etc.)

        Returns:
            List of Proposal objects ordered by creation date
        """
        try:
            query = self.client.table("proposals").select("*").eq(
                "ticket_id", ticket_id
            )

            if status:
                query = query.eq("status", status)

            result = query.order("created_at", desc=True).execute()

            if result.data:
                return [Proposal(**item) for item in result.data]

            return []

        except Exception as e:
            logger.error(f"Error fetching proposals for ticket: {e}")
            return []

    async def get_latest_for_ticket(self, ticket_id: str) -> Optional[Proposal]:
        """
        Get most recent proposal for a ticket.

        Args:
            ticket_id: Ticket identifier

        Returns:
            Latest Proposal or None
        """
        proposals = await self.get_by_ticket(ticket_id)
        return proposals[0] if proposals else None

    async def update_status(
        self,
        proposal_id: str,
        status: str,
        approved_by: Optional[str] = None,
        rejection_reason: Optional[str] = None
    ) -> Proposal:
        """
        Update proposal status.

        Args:
            proposal_id: Proposal UUID
            status: New status (approved, rejected, superseded)
            approved_by: Email of approver (for approved status)
            rejection_reason: Reason for rejection (for rejected status)

        Returns:
            Updated Proposal

        Raises:
            Exception: If update fails or proposal not found
        """
        try:
            updates: Dict[str, Any] = {"status": status}

            if status == "approved":
                updates["approved_by"] = approved_by
                updates["approved_at"] = datetime.now().isoformat()
            elif status == "rejected":
                updates["rejection_reason"] = rejection_reason

            result = self.client.table("proposals").update(updates).eq(
                "id", proposal_id
            ).execute()

            if result.data and len(result.data) > 0:
                proposal = Proposal(**result.data[0])
                logger.info(f"Updated proposal {proposal_id} status to {status}")
                return proposal

            raise Exception(f"Proposal {proposal_id} not found")

        except Exception as e:
            self._handle_error(f"update_status({proposal_id})", e)

    async def create_version(
        self,
        original_id: str,
        refined_data: Dict[str, Any]
    ) -> Proposal:
        """
        Create new version for refinement.

        Marks original as 'superseded' and creates new version with
        incremented proposal_version.

        Args:
            original_id: Original proposal UUID
            refined_data: Updated proposal fields

        Returns:
            New Proposal version

        Raises:
            Exception: If original not found or creation fails
        """
        try:
            # Fetch original
            original = await self.get_by_id(original_id)
            if not original:
                raise Exception(f"Original proposal {original_id} not found")

            # Mark original as superseded
            await self.update_status(original_id, "superseded")

            # Create new version
            new_version_data = {
                "tenant_id": original.tenant_id,
                "ticket_id": original.ticket_id,
                "proposal_version": original.proposal_version + 1,
                **refined_data
            }

            new_proposal = await self.create(new_version_data)

            logger.info(
                f"Created version {new_proposal.proposal_version} "
                f"for ticket {original.ticket_id}"
            )

            return new_proposal

        except Exception as e:
            self._handle_error(f"create_version({original_id})", e)

    async def log_approval_action(
        self,
        proposal_id: str,
        action: str,
        agent_email: Optional[str] = None,
        feedback: Optional[str] = None
    ) -> ApprovalLog:
        """
        Log approval action for audit trail.

        Args:
            proposal_id: Proposal UUID
            action: Action taken (approve, reject, refine)
            agent_email: Email of support agent
            feedback: Optional feedback text

        Returns:
            Created ApprovalLog

        Raises:
            Exception: If logging fails
        """
        try:
            log_data = {
                "proposal_id": proposal_id,
                "action": action,
                "agent_email": agent_email,
                "feedback": feedback
            }

            result = self.client.table("proposal_logs").insert(
                log_data
            ).execute()

            if result.data and len(result.data) > 0:
                log = ApprovalLog(**result.data[0])
                logger.info(f"Logged {action} for proposal {proposal_id}")
                return log

            raise Exception("No data returned from insert")

        except Exception as e:
            self._handle_error("log_approval_action", e)

    async def get_approval_logs(
        self,
        proposal_id: str
    ) -> List[ApprovalLog]:
        """
        Get all approval logs for a proposal.

        Args:
            proposal_id: Proposal UUID

        Returns:
            List of ApprovalLog objects ordered by creation date
        """
        try:
            result = self.client.table("proposal_logs").select("*").eq(
                "proposal_id", proposal_id
            ).order("created_at", desc=False).execute()

            if result.data:
                return [ApprovalLog(**item) for item in result.data]

            return []

        except Exception as e:
            logger.error(f"Error fetching approval logs: {e}")
            return []

    async def get_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get proposal statistics for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Statistics dictionary with counts and rates
        """
        try:
            # This would typically be done with proper SQL aggregation
            # For POC, simple count queries
            all_proposals = self.client.table("proposals").select(
                "status", count="exact"
            ).eq("tenant_id", tenant_id).execute()

            approved = self.client.table("proposals").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("status", "approved").execute()

            rejected = self.client.table("proposals").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("status", "rejected").execute()

            total = all_proposals.count if hasattr(all_proposals, 'count') else 0
            approved_count = approved.count if hasattr(approved, 'count') else 0
            rejected_count = rejected.count if hasattr(rejected, 'count') else 0

            return {
                "total_proposals": total,
                "approved": approved_count,
                "rejected": rejected_count,
                "approval_rate": approved_count / total if total > 0 else 0,
                "rejection_rate": rejected_count / total if total > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return {
                "total_proposals": 0,
                "approved": 0,
                "rejected": 0,
                "approval_rate": 0,
                "rejection_rate": 0
            }
