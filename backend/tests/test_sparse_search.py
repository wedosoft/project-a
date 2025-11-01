"""
Unit tests for Sparse Search Service (BM25)

Tests:
- Service initialization
- Schema initialization
- Document indexing
- BM25 search
- Similarity search with trigrams
- Document deletion
- Document counting
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.services.sparse_search import SparseSearchService


@pytest.fixture
def mock_pool():
    """Fixture for mock asyncpg pool"""
    pool = MagicMock()

    # Mock connection context manager
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock()
    conn.fetchrow = AsyncMock()

    # Mock transaction
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction.return_value = transaction

    # Mock acquire
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acquire
    pool.close = AsyncMock()

    return pool, conn


@pytest.fixture
def sparse_service():
    """Fixture for SparseSearchService instance"""
    return SparseSearchService(
        db_host="localhost",
        db_port=5432,
        db_name="test_db",
        db_user="test_user",
        db_password="test_pass"
    )


class TestServiceInitialization:
    """Test service initialization"""

    def test_init_with_params(self, sparse_service):
        """Test service initializes with parameters"""
        assert sparse_service.db_host == "localhost"
        assert sparse_service.db_port == 5432
        assert sparse_service.db_name == "test_db"
        assert sparse_service.pool is None

    @pytest.mark.asyncio
    async def test_get_pool_creates_pool(self, sparse_service):
        """Test pool creation"""
        with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create:
            mock_pool = MagicMock()
            mock_create.return_value = mock_pool

            pool = await sparse_service._get_pool()

            assert pool == mock_pool
            assert sparse_service.pool == mock_pool
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_pool(self, sparse_service):
        """Test pool closing"""
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        sparse_service.pool = mock_pool

        await sparse_service.close()

        assert sparse_service.pool is None
        mock_pool.close.assert_called_once()


class TestSchemaInitialization:
    """Test schema and index creation"""

    @pytest.mark.asyncio
    async def test_initialize_search_schema(self, sparse_service, mock_pool):
        """Test schema initialization"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock

        result = await sparse_service.initialize_search_schema()

        assert result is True
        # Verify extension, table, and index creation
        assert conn_mock.execute.call_count >= 4


class TestDocumentIndexing:
    """Test document indexing"""

    @pytest.mark.asyncio
    async def test_index_documents(self, sparse_service, mock_pool):
        """Test indexing documents"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock

        documents = [
            {
                "id": "doc1",
                "content": "This is a test document",
                "metadata": {"source": "test"}
            },
            {
                "id": "doc2",
                "content": "Another test document"
            }
        ]

        count = await sparse_service.index_documents("test_collection", documents)

        assert count == 2
        assert conn_mock.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_index_empty_documents(self, sparse_service, mock_pool):
        """Test indexing empty document list"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock

        count = await sparse_service.index_documents("test_collection", [])

        assert count == 0
        conn_mock.execute.assert_not_called()


class TestBM25Search:
    """Test BM25 search"""

    @pytest.mark.asyncio
    async def test_bm25_search(self, sparse_service, mock_pool):
        """Test BM25 search"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock

        mock_rows = [
            {
                "id": "doc1",
                "content": "Test document",
                "metadata": {"source": "test"},
                "score": 0.95
            }
        ]
        conn_mock.fetch.return_value = mock_rows

        results = await sparse_service.bm25_search(
            collection_name="test_collection",
            query="test query",
            top_k=10
        )

        assert len(results) == 1
        assert results[0]["id"] == "doc1"
        assert results[0]["score"] == 0.95
        conn_mock.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_bm25_search_with_filters(self, sparse_service, mock_pool):
        """Test BM25 search with metadata filters"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.fetch.return_value = []

        results = await sparse_service.bm25_search(
            collection_name="test_collection",
            query="test",
            top_k=5,
            filters={"source": "test_source"}
        )

        assert len(results) == 0
        conn_mock.fetch.assert_called_once()
        # Verify filter was included in query
        call_args = conn_mock.fetch.call_args
        assert "test_source" in call_args[0]

    @pytest.mark.asyncio
    async def test_bm25_search_empty_results(self, sparse_service, mock_pool):
        """Test BM25 search with no results"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.fetch.return_value = []

        results = await sparse_service.bm25_search(
            collection_name="test_collection",
            query="nonexistent query"
        )

        assert len(results) == 0


class TestSimilaritySearch:
    """Test trigram similarity search"""

    @pytest.mark.asyncio
    async def test_similarity_search(self, sparse_service, mock_pool):
        """Test similarity search"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock

        mock_rows = [
            {
                "id": "doc1",
                "content": "Similar text",
                "metadata": {},
                "score": 0.85
            }
        ]
        conn_mock.fetch.return_value = mock_rows

        results = await sparse_service.similarity_search(
            collection_name="test_collection",
            query="similar text",
            top_k=10,
            similarity_threshold=0.3
        )

        assert len(results) == 1
        assert results[0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_similarity_search_threshold(self, sparse_service, mock_pool):
        """Test similarity search respects threshold"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.fetch.return_value = []

        results = await sparse_service.similarity_search(
            collection_name="test_collection",
            query="test",
            similarity_threshold=0.9  # High threshold
        )

        assert len(results) == 0


class TestDocumentDeletion:
    """Test document deletion"""

    @pytest.mark.asyncio
    async def test_delete_specific_documents(self, sparse_service, mock_pool):
        """Test deleting specific documents"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.execute.return_value = "DELETE 2"

        count = await sparse_service.delete_documents(
            collection_name="test_collection",
            document_ids=["doc1", "doc2"]
        )

        assert count == 2
        conn_mock.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_all_documents(self, sparse_service, mock_pool):
        """Test deleting all documents in collection"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.execute.return_value = "DELETE 5"

        count = await sparse_service.delete_documents(
            collection_name="test_collection"
        )

        assert count == 5


class TestDocumentCount:
    """Test document counting"""

    @pytest.mark.asyncio
    async def test_get_document_count(self, sparse_service, mock_pool):
        """Test getting document count"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.fetchrow.return_value = {"count": 42}

        count = await sparse_service.get_document_count("test_collection")

        assert count == 42
        conn_mock.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_document_count_empty(self, sparse_service, mock_pool):
        """Test getting count for empty collection"""
        pool_mock, conn_mock = mock_pool
        sparse_service.pool = pool_mock
        conn_mock.fetchrow.return_value = {"count": 0}

        count = await sparse_service.get_document_count("empty_collection")

        assert count == 0
