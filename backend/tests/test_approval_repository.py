"""Unit tests for ApprovalRepository"""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from backend.models.schemas import ApprovalLogCreate, ApprovalStatus
from backend.repositories.approval_repository import ApprovalRepository


@pytest.fixture
def mock_supabase():
    """Mocked Supabase client"""
    client = MagicMock()

    # RPC mock for set_config
    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(data=None, count=None)
    client.rpc.return_value = rpc_mock

    # Table chainable methods
    client.table.return_value = client
    client.insert.return_value = client
    client.update.return_value = client
    client.select.return_value = client
    client.eq.return_value = client
    client.order.return_value = client

    # Default execute response
    client.execute.return_value = MagicMock(data=[], count=0)

    return client


@pytest.fixture
def approval_repo(mock_supabase):
    return ApprovalRepository(supabase_client=mock_supabase)


class TestLogApproval:
    def test_log_approval_success(self, approval_repo, mock_supabase):
        log_data = ApprovalLogCreate(
            tenant_id="tenant-a",
            ticket_id="TICKET-100",
            draft_response="draft",
            final_response="final",
            proposed_field_updates={"priority": "high"},
            approval_status=ApprovalStatus.APPROVED,
            agent_id="agent-001",
            feedback_notes="looks good"
        )

        inserted_row = {
            "id": str(uuid4()),
            "tenant_id": log_data.tenant_id,
            "ticket_id": log_data.ticket_id,
            "draft_response": log_data.draft_response,
            "final_response": log_data.final_response,
            "field_updates": log_data.proposed_field_updates,
            "approval_status": log_data.approval_status.value,
            "agent_id": log_data.agent_id,
            "feedback_notes": log_data.feedback_notes,
            "created_at": "2025-11-02T08:30:00Z"
        }

        mock_supabase.execute.return_value = MagicMock(data=[inserted_row], count=None)

        result = approval_repo.log_approval(log_data)

        assert result.ticket_id == log_data.ticket_id
        assert result.approval_status == ApprovalStatus.APPROVED
        mock_supabase.table.assert_called_with("approval_logs")
        mock_supabase.insert.assert_called_once()
        args, _ = mock_supabase.insert.call_args
        assert args[0]["approval_status"] == "approved"


class TestGetLogs:
    def test_get_logs_by_ticket(self, approval_repo, mock_supabase):
        tenant_id = "tenant-a"
        ticket_id = "TICKET-101"
        rows = [
            {
                "id": str(uuid4()),
                "tenant_id": tenant_id,
                "ticket_id": ticket_id,
                "approval_status": "approved",
                "draft_response": None,
                "final_response": "final message",
                "field_updates": None,
                "agent_id": "agent-002",
                "feedback_notes": None,
                "created_at": "2025-11-02T08:31:00Z"
            }
        ]
        mock_supabase.execute.return_value = MagicMock(data=rows, count=None)

        results = approval_repo.get_logs_by_ticket(tenant_id, ticket_id)

        mock_supabase.eq.assert_called_with("ticket_id", ticket_id)
        assert len(results) == 1
        assert results[0].approval_status == ApprovalStatus.APPROVED


class TestUpdateApproval:
    def test_update_approval(self, approval_repo, mock_supabase):
        tenant_id = "tenant-a"
        log_id = uuid4()
        updated_row = {
            "id": str(log_id),
            "tenant_id": tenant_id,
            "ticket_id": "TICKET-102",
            "approval_status": "modified",
            "draft_response": "draft",
            "final_response": "new final",
            "field_updates": {"priority": "medium"},
            "agent_id": "agent-003",
            "feedback_notes": "updated",
            "created_at": "2025-11-02T08:32:00Z"
        }
        mock_supabase.execute.side_effect = [
            MagicMock(data=None, count=None),  # update execute
            MagicMock(data=[updated_row], count=None)  # select execute
        ]

        result = approval_repo.update_approval(
            tenant_id,
            log_id,
            final_response="new final",
            approval_status=ApprovalStatus.MODIFIED,
            feedback_notes="updated"
        )

        mock_supabase.update.assert_called_once()
        mock_supabase.eq.assert_any_call("id", str(log_id))
        assert result.approval_status == ApprovalStatus.MODIFIED
        assert result.final_response == "new final"


class TestCountByStatus:
    def test_count_by_status(self, approval_repo, mock_supabase):
        mock_supabase.execute.return_value = MagicMock(data=[], count=4)

        count = approval_repo.count_by_status("tenant-a", ApprovalStatus.APPROVED)

        mock_supabase.eq.assert_called_with("approval_status", "approved")
        assert count == 4
