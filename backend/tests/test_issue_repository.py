"""
Unit tests for IssueRepository

Tests:
- Repository initialization
- CRUD operations
- Batch operations
- Filtering and pagination
- RLS tenant isolation
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend.repositories.issue_repository import IssueRepository
from backend.models.schemas import IssueBlock, IssueBlockCreate, BlockType


@pytest.fixture
def mock_supabase():
    """Fixture for mock Supabase client"""
    client = MagicMock()
    client.table.return_value = client
    client.select.return_value = client
    client.insert.return_value = client
    client.update.return_value = client
    client.delete.return_value = client
    client.eq.return_value = client
    client.ilike.return_value = client
    client.range.return_value = client
    client.limit.return_value = client
    client.rpc.return_value = client
    client.execute.return_value = MagicMock(data=[], count=0)
    return client


@pytest.fixture
def issue_repo(mock_supabase):
    """Fixture for IssueRepository with mocked client"""
    return IssueRepository(supabase_client=mock_supabase)


class TestRepositoryInitialization:
    """Test repository initialization"""

    def test_init_with_client(self, mock_supabase):
        """Test initialization with provided client"""
        repo = IssueRepository(supabase_client=mock_supabase)
        assert repo.client == mock_supabase
        assert repo.table_name == "issue_blocks"

    def test_init_default_client(self):
        """Test initialization with default client (requires env vars)"""
        with patch('supabase.create_client'):
            repo = IssueRepository()
            assert repo.table_name == "issue_blocks"


class TestCreateOperation:
    """Test create operations"""

    def test_create_issue_block(self, issue_repo, mock_supabase):
        """Test creating a single issue block"""
        block_data = IssueBlockCreate(
            tenant_id="test-tenant",
            ticket_id="TICKET-001",
            block_type=BlockType.SYMPTOM,
            content="Test symptom content here"
        )

        mock_supabase.execute.return_value.data = [{
            "id": str(uuid4()),
            "tenant_id": "test-tenant",
            "ticket_id": "TICKET-001",
            "block_type": "symptom",
            "content": "Test symptom content here",
            "product": None,
            "component": None,
            "error_code": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        result = issue_repo.create("test-tenant", block_data)

        assert isinstance(result, IssueBlock)
        assert result.tenant_id == "test-tenant"
        assert result.ticket_id == "TICKET-001"
        mock_supabase.rpc.assert_called_once()
        mock_supabase.insert.assert_called_once()

    def test_batch_create(self, issue_repo, mock_supabase):
        """Test batch creating multiple issue blocks"""
        blocks = [
            IssueBlockCreate(
                tenant_id="test-tenant",
                ticket_id=f"TICKET-{i:03d}",
                block_type=BlockType.SYMPTOM,
                content=f"Symptom content {i} for testing"
            )
            for i in range(3)
        ]

        mock_supabase.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "ticket_id": f"TICKET-{i:03d}",
                "block_type": "symptom",
                "content": f"Symptom content {i} for testing",
                "product": None,
                "component": None,
                "error_code": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            }
            for i in range(3)
        ]

        results = issue_repo.batch_create("test-tenant", blocks)

        assert len(results) == 3
        assert all(isinstance(r, IssueBlock) for r in results)
        mock_supabase.insert.assert_called_once()


class TestReadOperation:
    """Test read operations"""

    def test_get_by_id_found(self, issue_repo, mock_supabase):
        """Test getting issue block by ID when found"""
        block_id = uuid4()

        mock_supabase.execute.return_value.data = [{
            "id": str(block_id),
            "tenant_id": "test-tenant",
            "ticket_id": "TICKET-001",
            "block_type": "symptom",
            "content": "Test symptom content here",
            "product": None,
            "component": None,
            "error_code": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        result = issue_repo.get_by_id("test-tenant", block_id)

        assert result is not None
        assert result.id == block_id
        mock_supabase.eq.assert_called_with("id", str(block_id))

    def test_get_by_id_not_found(self, issue_repo, mock_supabase):
        """Test getting issue block by ID when not found"""
        block_id = uuid4()
        mock_supabase.execute.return_value.data = []

        result = issue_repo.get_by_id("test-tenant", block_id)

        assert result is None

    def test_get_by_ticket_id(self, issue_repo, mock_supabase):
        """Test getting all blocks for a ticket"""
        mock_supabase.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "ticket_id": "TICKET-001",
                "block_type": "symptom",
                "content": "Symptom content test",
                "product": None,
                "component": None,
                "error_code": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "ticket_id": "TICKET-001",
                "block_type": "resolution",
                "content": "Resolution content for testing purposes",
                "product": None,
                "component": None,
                "error_code": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]

        results = issue_repo.get_by_ticket_id("test-tenant", "TICKET-001")

        assert len(results) == 2
        assert all(r.ticket_id == "TICKET-001" for r in results)

    def test_get_by_ticket_id_with_type_filter(self, issue_repo, mock_supabase):
        """Test getting blocks filtered by block type"""
        mock_supabase.execute.return_value.data = [{
            "id": str(uuid4()),
            "tenant_id": "test-tenant",
            "ticket_id": "TICKET-001",
            "block_type": "symptom",
            "content": "Symptom content test",
            "product": None,
            "component": None,
            "error_code": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        results = issue_repo.get_by_ticket_id(
            "test-tenant", "TICKET-001", block_type=BlockType.SYMPTOM
        )

        assert len(results) == 1
        assert results[0].block_type == BlockType.SYMPTOM


class TestListOperation:
    """Test list operations"""

    def test_list_blocks_no_filters(self, issue_repo, mock_supabase):
        """Test listing blocks without filters"""
        mock_supabase.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "ticket_id": f"TICKET-{i:03d}",
                "block_type": "symptom",
                "content": f"Symptom content test {i}",
                "product": None,
                "component": None,
                "error_code": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            }
            for i in range(5)
        ]

        results = issue_repo.list_blocks("test-tenant", limit=10)

        assert len(results) == 5
        mock_supabase.range.assert_called_once()

    def test_list_blocks_with_filters(self, issue_repo, mock_supabase):
        """Test listing blocks with product/component filters"""
        mock_supabase.execute.return_value.data = [{
            "id": str(uuid4()),
            "tenant_id": "test-tenant",
            "ticket_id": "TICKET-001",
            "block_type": "symptom",
            "content": "Symptom content test",
            "product": "Product A",
            "component": "Login",
            "error_code": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        results = issue_repo.list_blocks(
            "test-tenant",
            product="Product A",
            component="Login"
        )

        assert len(results) == 1
        assert results[0].product == "Product A"
        assert results[0].component == "Login"

    def test_list_blocks_pagination(self, issue_repo, mock_supabase):
        """Test pagination with offset and limit"""
        mock_supabase.execute.return_value.data = []

        issue_repo.list_blocks("test-tenant", limit=20, offset=40)

        mock_supabase.range.assert_called_with(40, 59)


class TestUpdateOperation:
    """Test update operations"""

    def test_update_block(self, issue_repo, mock_supabase):
        """Test updating issue block"""
        block_id = uuid4()
        updates = {"content": "Updated symptom content here"}

        mock_supabase.execute.return_value.data = [{
            "id": str(block_id),
            "tenant_id": "test-tenant",
            "ticket_id": "TICKET-001",
            "block_type": "symptom",
            "content": "Updated symptom content here",
            "product": None,
            "component": None,
            "error_code": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        result = issue_repo.update("test-tenant", block_id, updates)

        assert result.content == "Updated symptom content here"
        mock_supabase.update.assert_called_once_with(updates)

    def test_update_block_not_found(self, issue_repo, mock_supabase):
        """Test updating non-existent block raises error"""
        block_id = uuid4()
        updates = {"content": "Updated content"}
        mock_supabase.execute.return_value.data = []

        with pytest.raises(ValueError, match="not found"):
            issue_repo.update("test-tenant", block_id, updates)


class TestDeleteOperation:
    """Test delete operations"""

    def test_delete_block(self, issue_repo, mock_supabase):
        """Test deleting issue block"""
        block_id = uuid4()

        result = issue_repo.delete("test-tenant", block_id)

        assert result is True
        mock_supabase.delete.assert_called_once()
        mock_supabase.eq.assert_called_with("id", str(block_id))


class TestCountOperation:
    """Test count operations"""

    def test_count_all_blocks(self, issue_repo, mock_supabase):
        """Test counting all blocks"""
        mock_supabase.execute.return_value.count = 42

        count = issue_repo.count("test-tenant")

        assert count == 42

    def test_count_with_filters(self, issue_repo, mock_supabase):
        """Test counting with filters"""
        mock_supabase.execute.return_value.count = 5

        count = issue_repo.count(
            "test-tenant",
            product="Product A",
            block_type=BlockType.SYMPTOM
        )

        assert count == 5

    def test_count_empty(self, issue_repo, mock_supabase):
        """Test count returns 0 when no results"""
        mock_supabase.execute.return_value.count = None

        count = issue_repo.count("test-tenant")

        assert count == 0
