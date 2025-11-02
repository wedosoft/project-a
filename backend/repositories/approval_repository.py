"""
Approval Repository

Provides CRUD utilities for the `approval_logs` table in Supabase. This
repository is used by the POC workflow to persist agent approvals, modifications
and rejections of AI generated suggestions.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID

from backend.config import get_settings
from backend.models.schemas import (
    ApprovalLog,
    ApprovalLogCreate,
    ApprovalStatus,
)
from backend.utils.logger import get_logger


logger = get_logger(__name__)
settings = get_settings()


class ApprovalRepository:
    """Repository for approval_logs table operations."""

    def __init__(self, supabase_client=None) -> None:
        if supabase_client is None:
            from supabase import create_client  # Lazy import for tests

            self.client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        else:
            self.client = supabase_client

        self.table_name = "approval_logs"
        logger.info("ApprovalRepository initialized for table: %s", self.table_name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_tenant(self, tenant_id: str) -> None:
        """Set tenant context for Row-Level Security policies."""
        self.client.rpc('set_config', {
            'key': 'app.current_tenant_id',
            'value': tenant_id
        }).execute()

    @staticmethod
    def _serialize_payload(data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare payload for Supabase (convert enums, strip None)."""
        serialized: Dict[str, Any] = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, ApprovalStatus):
                serialized[key] = value.value
            elif key == "proposed_field_updates":
                serialized["field_updates"] = value
            else:
                serialized[key] = value
        return serialized

    @staticmethod
    def _deserialize(row: Dict[str, Any]) -> ApprovalLog:
        """Convert Supabase row into ApprovalLog model."""
        row = dict(row)
        if 'field_updates' in row and 'proposed_field_updates' not in row:
            row['proposed_field_updates'] = row.pop('field_updates')
        if 'approval_status' in row and not isinstance(row['approval_status'], ApprovalStatus):
            row['approval_status'] = ApprovalStatus(row['approval_status'])
        return ApprovalLog(**row)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def log_approval(self, log: ApprovalLogCreate) -> ApprovalLog:
        """Insert a new approval log."""
        try:
            self._set_tenant(log.tenant_id)

            payload = self._serialize_payload(log.model_dump())

            response = self.client.table(self.table_name) \
                .insert(payload) \
                .execute()

            if not response.data:
                raise ValueError("Supabase insert returned no data")

            return self._deserialize(response.data[0])

        except Exception as exc:  # pragma: no cover - pass through
            logger.error("Failed to log approval: %s", exc)
            raise

    async def log_approval_async(self, log: ApprovalLogCreate) -> ApprovalLog:
        """Async wrapper for log_approval."""
        return await asyncio.to_thread(self.log_approval, log)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_logs_by_ticket(self, tenant_id: str, ticket_id: str) -> List[ApprovalLog]:
        """Fetch approval logs for a ticket ordered by creation desc."""
        try:
            self._set_tenant(tenant_id)

            response = self.client.table(self.table_name) \
                .select("*") \
                .eq("ticket_id", ticket_id) \
                .order("created_at", desc=True) \
                .execute()

            rows = response.data or []
            return [self._deserialize(row) for row in rows]

        except Exception as exc:  # pragma: no cover
            logger.error("Failed to fetch approval logs for ticket %s: %s", ticket_id, exc)
            raise

    async def get_logs_by_ticket_async(self, tenant_id: str, ticket_id: str) -> List[ApprovalLog]:
        return await asyncio.to_thread(self.get_logs_by_ticket, tenant_id, ticket_id)

    def count_by_status(self, tenant_id: str, status: ApprovalStatus) -> int:
        """Count approvals by status."""
        try:
            self._set_tenant(tenant_id)

            response = self.client.table(self.table_name) \
                .select("*", count="exact") \
                .eq("approval_status", status.value) \
                .execute()

            return response.count or 0

        except Exception as exc:  # pragma: no cover
            logger.error("Failed to count approvals: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update_approval(
        self,
        tenant_id: str,
        log_id: UUID,
        *,
        final_response: Optional[str] = None,
        approval_status: Optional[ApprovalStatus] = None,
        feedback_notes: Optional[str] = None,
        proposed_field_updates: Optional[Dict[str, Any]] = None
    ) -> ApprovalLog:
        """Update fields on an approval log and return updated row."""
        try:
            self._set_tenant(tenant_id)

            updates: Dict[str, Any] = {}
            if final_response is not None:
                updates['final_response'] = final_response
            if approval_status is not None:
                updates['approval_status'] = approval_status.value
            if feedback_notes is not None:
                updates['feedback_notes'] = feedback_notes
            if proposed_field_updates is not None:
                updates['field_updates'] = proposed_field_updates

            if not updates:
                raise ValueError("No updates provided")

            self.client.table(self.table_name) \
                .update(updates) \
                .eq("id", str(log_id)) \
                .execute()

            query_response = self.client.table(self.table_name) \
                .select("*") \
                .eq("id", str(log_id)) \
                .execute()

            if not query_response.data:
                raise ValueError(f"Approval log {log_id} not found")

            return self._deserialize(query_response.data[0])

        except Exception as exc:  # pragma: no cover
            logger.error("Failed to update approval %s: %s", log_id, exc)
            raise

    async def update_approval_async(
        self,
        tenant_id: str,
        log_id: UUID,
        **updates: Any
    ) -> ApprovalLog:
        return await asyncio.to_thread(self.update_approval, tenant_id, log_id, **updates)
