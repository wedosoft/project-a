"""
Unit tests for KBRepository

Tests:
- Repository initialization
- CRUD operations
- Batch operations
- Search and filtering
- RLS tenant isolation
"""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend.repositories.kb_repository import KBRepository
from backend.models.schemas import KBBlock, KBBlockCreate


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
def kb_repo(mock_supabase):
    """Fixture for KBRepository with mocked client"""
    return KBRepository(supabase_client=mock_supabase)


class TestRepositoryInitialization:
    """Test repository initialization"""

    def test_init_with_client(self, mock_supabase):
        """Test initialization with provided client"""
        repo = KBRepository(supabase_client=mock_supabase)
        assert repo.client == mock_supabase
        assert repo.table_name == "kb_blocks"

    def test_init_default_client(self):
        """Test initialization with default client (requires env vars)"""
        with patch('supabase.create_client'):
            repo = KBRepository()
            assert repo.table_name == "kb_blocks"


class TestCreateOperation:
    """Test create operations"""

    def test_create_kb_block(self, kb_repo, mock_supabase):
        """Test creating a single KB block"""
        block_data = KBBlockCreate(
            tenant_id="test-tenant",
            article_id="KB-001",
            intent="Test intent",
            step="1. First step\n2. Second step"
        )

        mock_supabase.execute.return_value.data = [{
            "id": str(uuid4()),
            "tenant_id": "test-tenant",
            "article_id": "KB-001",
            "intent": "Test intent",
            "step": "1. First step\n2. Second step",
            "constraint": None,
            "example": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        result = kb_repo.create("test-tenant", block_data)

        assert isinstance(result, KBBlock)
        assert result.tenant_id == "test-tenant"
        assert result.article_id == "KB-001"
        mock_supabase.rpc.assert_called_once()
        mock_supabase.insert.assert_called_once()

    def test_batch_create(self, kb_repo, mock_supabase):
        """Test batch creating multiple KB blocks"""
        blocks = [
            KBBlockCreate(
                tenant_id="test-tenant",
                article_id=f"KB-{i:03d}",
                intent=f"Intent {i}"
            )
            for i in range(3)
        ]

        mock_supabase.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "article_id": f"KB-{i:03d}",
                "intent": f"Intent {i}",
                "step": None,
                "constraint": None,
                "example": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            }
            for i in range(3)
        ]

        results = kb_repo.batch_create("test-tenant", blocks)

        assert len(results) == 3
        assert all(isinstance(r, KBBlock) for r in results)
        mock_supabase.insert.assert_called_once()


class TestReadOperation:
    """Test read operations"""

    def test_get_by_id_found(self, kb_repo, mock_supabase):
        """Test getting KB block by ID when found"""
        block_id = uuid4()

        mock_supabase.execute.return_value.data = [{
            "id": str(block_id),
            "tenant_id": "test-tenant",
            "article_id": "KB-001",
            "intent": "Test intent",
            "step": None,
            "constraint": None,
            "example": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        result = kb_repo.get_by_id("test-tenant", block_id)

        assert result is not None
        assert result.id == block_id
        mock_supabase.eq.assert_called_with("id", str(block_id))

    def test_get_by_id_not_found(self, kb_repo, mock_supabase):
        """Test getting KB block by ID when not found"""
        block_id = uuid4()
        mock_supabase.execute.return_value.data = []

        result = kb_repo.get_by_id("test-tenant", block_id)

        assert result is None

    def test_get_by_article_id(self, kb_repo, mock_supabase):
        """Test getting all blocks for an article"""
        mock_supabase.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "article_id": "KB-001",
                "intent": "Intent 1",
                "step": None,
                "constraint": None,
                "example": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "article_id": "KB-001",
                "intent": "Intent 2",
                "step": None,
                "constraint": None,
                "example": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            }
        ]

        results = kb_repo.get_by_article_id("test-tenant", "KB-001")

        assert len(results) == 2
        assert all(r.article_id == "KB-001" for r in results)


class TestListOperation:
    """Test list operations"""

    def test_list_blocks_pagination(self, kb_repo, mock_supabase):
        """Test listing blocks with pagination"""
        mock_supabase.execute.return_value.data = [
            {
                "id": str(uuid4()),
                "tenant_id": "test-tenant",
                "article_id": f"KB-{i:03d}",
                "intent": f"Intent {i}",
                "step": None,
                "constraint": None,
                "example": None,
                "meta": None,
                "embedding_id": None,
                "created_at": "2024-01-01T00:00:00Z"
            }
            for i in range(5)
        ]

        results = kb_repo.list_blocks("test-tenant", limit=10)

        assert len(results) == 5
        mock_supabase.range.assert_called_once()

    def test_list_blocks_with_offset(self, kb_repo, mock_supabase):
        """Test pagination with offset"""
        mock_supabase.execute.return_value.data = []

        kb_repo.list_blocks("test-tenant", limit=20, offset=40)

        mock_supabase.range.assert_called_with(40, 59)


class TestSearchOperation:
    """Test search operations"""

    def test_search_by_intent(self, kb_repo, mock_supabase):
        """Test searching KB blocks by intent keyword"""
        mock_supabase.execute.return_value.data = [{
            "id": str(uuid4()),
            "tenant_id": "test-tenant",
            "article_id": "KB-001",
            "intent": "Login troubleshooting",
            "step": None,
            "constraint": None,
            "example": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        results = kb_repo.search_by_intent("test-tenant", "login")

        assert len(results) == 1
        assert "login" in results[0].intent.lower()
        mock_supabase.ilike.assert_called_once()

    def test_search_by_intent_limit(self, kb_repo, mock_supabase):
        """Test search with custom limit"""
        mock_supabase.execute.return_value.data = []

        kb_repo.search_by_intent("test-tenant", "auth", limit=10)

        mock_supabase.limit.assert_called_with(10)


class TestUpdateOperation:
    """Test update operations"""

    def test_update_block(self, kb_repo, mock_supabase):
        """Test updating KB block"""
        block_id = uuid4()
        updates = {"intent": "Updated intent"}

        mock_supabase.execute.return_value.data = [{
            "id": str(block_id),
            "tenant_id": "test-tenant",
            "article_id": "KB-001",
            "intent": "Updated intent",
            "step": None,
            "constraint": None,
            "example": None,
            "meta": None,
            "embedding_id": None,
            "created_at": "2024-01-01T00:00:00Z"
        }]

        result = kb_repo.update("test-tenant", block_id, updates)

        assert result.intent == "Updated intent"
        mock_supabase.update.assert_called_once_with(updates)

    def test_update_block_not_found(self, kb_repo, mock_supabase):
        """Test updating non-existent block raises error"""
        block_id = uuid4()
        updates = {"intent": "Updated intent"}
        mock_supabase.execute.return_value.data = []

        with pytest.raises(ValueError, match="not found"):
            kb_repo.update("test-tenant", block_id, updates)


class TestDeleteOperation:
    """Test delete operations"""

    def test_delete_block(self, kb_repo, mock_supabase):
        """Test deleting KB block"""
        block_id = uuid4()

        result = kb_repo.delete("test-tenant", block_id)

        assert result is True
        mock_supabase.delete.assert_called_once()
        mock_supabase.eq.assert_called_with("id", str(block_id))


class TestCountOperation:
    """Test count operations"""

    def test_count_blocks(self, kb_repo, mock_supabase):
        """Test counting all blocks"""
        mock_supabase.execute.return_value.count = 15

        count = kb_repo.count("test-tenant")

        assert count == 15

    def test_count_empty(self, kb_repo, mock_supabase):
        """Test count returns 0 when None"""
        mock_supabase.execute.return_value.count = None

        count = kb_repo.count("test-tenant")

        assert count == 0
