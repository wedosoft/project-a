"""
Unit tests for sync API endpoints
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.routes.sync import sync_state


client = TestClient(app)


@pytest.fixture
def mock_freshdesk():
    """Mock Freshdesk client"""
    with patch("backend.routes.sync.freshdesk") as mock:
        mock.fetch_tickets = AsyncMock(return_value=[
            {
                "id": "12345",
                "subject": "Test ticket",
                "description_text": "Test description",
                "status": 2,
                "priority": 1,
                "type": "Question",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "tags": ["test"]
            }
        ])
        mock.fetch_kb_articles = AsyncMock(return_value=[
            {
                "id": "67890",
                "title": "Test KB article",
                "description_text": "Test KB description",
                "folder_id": 1,
                "category_id": 1,
                "status": 1,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "tags": ["kb"]
            }
        ])
        yield mock


@pytest.fixture
def mock_llm():
    """Mock LLM service"""
    with patch("backend.routes.sync.llm") as mock:
        mock.generate_embedding = MagicMock(return_value=[0.1] * 1024)
        yield mock


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant service"""
    with patch("backend.routes.sync.qdrant") as mock:
        mock.ensure_collection = MagicMock(return_value=True)
        mock.store_vector = MagicMock(return_value=True)
        mock.get_collection_info = MagicMock(return_value={
            "name": "test",
            "points_count": 100,
            "vectors_count": 100,
            "status": "green"
        })
        yield mock


@pytest.fixture
def mock_supabase():
    """Mock Supabase service"""
    with patch("backend.routes.sync.supabase") as mock:
        mock_result = MagicMock()
        mock_result.data = [{"synced_at": "2024-01-01T00:00:00Z"}]

        mock_query = MagicMock()
        mock_query.execute = AsyncMock(return_value=mock_result)
        mock_query.limit = MagicMock(return_value=mock_query)
        mock_query.order = MagicMock(return_value=mock_query)
        mock_query.eq = MagicMock(return_value=mock_query)
        mock_query.select = MagicMock(return_value=mock_query)

        mock.client.table = MagicMock(return_value=mock_query)
        yield mock


@pytest.fixture(autouse=True)
def reset_sync_state():
    """Reset sync state before each test"""
    sync_state["ticket_sync_in_progress"] = False
    sync_state["kb_sync_in_progress"] = False
    yield


class TestSyncTickets:
    """Test POST /api/sync/tickets endpoint"""

    def test_sync_tickets_success(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test successful ticket sync initiation"""
        response = client.post("/api/sync/tickets?limit=100")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "last_sync_time" in data
        assert data["errors"] == []

    def test_sync_tickets_with_since_parameter(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test ticket sync with since parameter"""
        since = datetime.utcnow().isoformat()
        response = client.post(f"/api/sync/tickets?since={since}&limit=50")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_sync_tickets_invalid_since_format(self):
        """Test ticket sync with invalid since format"""
        response = client.post("/api/sync/tickets?since=invalid-date")

        assert response.status_code == 400
        assert "Invalid ISO timestamp" in response.json()["detail"]

    def test_sync_tickets_already_in_progress(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test ticket sync when already in progress"""
        sync_state["ticket_sync_in_progress"] = True

        response = client.post("/api/sync/tickets")

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]

    def test_sync_tickets_limit_validation(self):
        """Test ticket sync limit parameter validation"""
        # Test minimum
        response = client.post("/api/sync/tickets?limit=0")
        assert response.status_code == 422

        # Test maximum
        response = client.post("/api/sync/tickets?limit=501")
        assert response.status_code == 422


class TestSyncKB:
    """Test POST /api/sync/kb endpoint"""

    def test_sync_kb_success(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test successful KB sync initiation"""
        response = client.post("/api/sync/kb?limit=100")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "last_sync_time" in data
        assert data["errors"] == []

    def test_sync_kb_with_since_parameter(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test KB sync with since parameter"""
        since = datetime.utcnow().isoformat()
        response = client.post(f"/api/sync/kb?since={since}&limit=50")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_sync_kb_already_in_progress(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test KB sync when already in progress"""
        sync_state["kb_sync_in_progress"] = True

        response = client.post("/api/sync/kb")

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]


class TestSyncStatus:
    """Test GET /api/sync/status endpoint"""

    def test_get_sync_status_success(self, mock_qdrant, mock_supabase):
        """Test successful sync status retrieval"""
        response = client.get("/api/sync/status")

        assert response.status_code == 200
        data = response.json()

        assert "last_ticket_sync" in data
        assert "last_kb_sync" in data
        assert "total_tickets" in data
        assert "total_kb_articles" in data
        assert "sync_in_progress" in data

    def test_get_sync_status_with_active_sync(self, mock_qdrant, mock_supabase):
        """Test sync status when sync is in progress"""
        sync_state["ticket_sync_in_progress"] = True

        response = client.get("/api/sync/status")

        assert response.status_code == 200
        data = response.json()
        assert data["sync_in_progress"] is True

    def test_get_sync_status_service_unavailable(self, mock_supabase):
        """Test sync status when Qdrant is unavailable"""
        with patch("backend.routes.sync.qdrant") as mock_qdrant:
            mock_qdrant.get_collection_info.side_effect = Exception("Connection failed")

            response = client.get("/api/sync/status")

            # Should still return 200 with warnings logged
            # Total counts will be 0
            assert response.status_code == 200
            data = response.json()
            assert data["total_tickets"] == 0
            assert data["total_kb_articles"] == 0


class TestSyncBackgroundTasks:
    """Test background sync task execution"""

    @pytest.mark.asyncio
    async def test_sync_tickets_task_success(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test ticket sync background task"""
        from backend.routes.sync import sync_tickets_task

        result = await sync_tickets_task(None, 100)

        assert result.success is True
        assert result.items_synced > 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_sync_tickets_task_with_errors(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test ticket sync task with partial failures"""
        mock_qdrant.store_vector.side_effect = [
            True,
            Exception("Storage failed"),
            True
        ]

        from backend.routes.sync import sync_tickets_task

        result = await sync_tickets_task(None, 100)

        # Should continue despite errors
        assert result.success is True  # Partial success
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_sync_kb_task_success(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test KB sync background task"""
        from backend.routes.sync import sync_kb_task

        result = await sync_kb_task(None, 100)

        assert result.success is True
        assert result.items_synced > 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_sync_task_state_management(
        self, mock_freshdesk, mock_llm, mock_qdrant, mock_supabase
    ):
        """Test sync state is properly managed during task execution"""
        from backend.routes.sync import sync_tickets_task

        assert sync_state["ticket_sync_in_progress"] is False

        # Start task
        task = sync_tickets_task(None, 100)

        # Should be in progress during execution
        # (In real scenario, would be True immediately after task start)

        # Complete task
        await task

        # Should be False after completion
        assert sync_state["ticket_sync_in_progress"] is False


class TestSyncModels:
    """Test Pydantic models"""

    def test_sync_request_model(self):
        """Test SyncRequest model validation"""
        from backend.routes.sync import SyncRequest

        # Valid request
        request = SyncRequest(since="2024-01-01T00:00:00Z", limit=100)
        assert request.limit == 100

        # Default limit
        request = SyncRequest()
        assert request.limit == 100

        # Invalid limit (caught by FastAPI validation)
        with pytest.raises(Exception):
            SyncRequest(limit=0)

    def test_sync_result_model(self):
        """Test SyncResult model"""
        from backend.routes.sync import SyncResult

        result = SyncResult(
            success=True,
            items_synced=50,
            last_sync_time="2024-01-01T00:00:00Z",
            errors=[]
        )

        assert result.success is True
        assert result.items_synced == 50
        assert len(result.errors) == 0

    def test_sync_status_model(self):
        """Test SyncStatus model"""
        from backend.routes.sync import SyncStatus

        status = SyncStatus(
            last_ticket_sync="2024-01-01T00:00:00Z",
            last_kb_sync="2024-01-01T00:00:00Z",
            total_tickets=100,
            total_kb_articles=50,
            sync_in_progress=False
        )

        assert status.total_tickets == 100
        assert status.total_kb_articles == 50
        assert status.sync_in_progress is False
