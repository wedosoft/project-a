"""
Unit tests for HybridSearchService

Tests:
- Service initialization
- Dense search integration
- Sparse search integration
- RRF fusion algorithm
- Cross-encoder reranking
- Batch search
- Search statistics
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from backend.services.hybrid_search import HybridSearchService


@pytest.fixture
def mock_vector_service():
    """Mock VectorSearchService"""
    service = MagicMock()
    service.search = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_sparse_service():
    """Mock SparseSearchService"""
    service = MagicMock()
    service.bm25_search = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_reranker_service():
    """Mock RerankerService"""
    service = MagicMock()
    service.rerank_results = MagicMock(return_value=[])
    return service


@pytest.fixture
def hybrid_service(mock_vector_service, mock_sparse_service, mock_reranker_service):
    """Hybrid search service with mocked dependencies"""
    return HybridSearchService(
        vector_service=mock_vector_service,
        sparse_service=mock_sparse_service,
        reranker_service=mock_reranker_service,
        rrf_k=60,
        dense_weight=0.5,
        sparse_weight=0.5
    )


class TestServiceInitialization:
    """Test service initialization"""

    def test_init_with_services(self, mock_vector_service, mock_sparse_service, mock_reranker_service):
        """Test initialization with provided services"""
        service = HybridSearchService(
            vector_service=mock_vector_service,
            sparse_service=mock_sparse_service,
            reranker_service=mock_reranker_service,
            rrf_k=100,
            dense_weight=0.6,
            sparse_weight=0.4
        )

        assert service.vector_service == mock_vector_service
        assert service.sparse_service == mock_sparse_service
        assert service.reranker_service == mock_reranker_service
        assert service.rrf_k == 100
        assert service.dense_weight == 0.6
        assert service.sparse_weight == 0.4

    def test_init_default_services(self):
        """Test initialization with default services"""
        with patch('backend.services.hybrid_search.VectorSearchService'), \
             patch('backend.services.hybrid_search.SparseSearchService'), \
             patch('backend.services.hybrid_search.RerankerService'):
            service = HybridSearchService()
            assert service.rrf_k == 60
            assert service.dense_weight == 0.5
            assert service.sparse_weight == 0.5


class TestDenseSearch:
    """Test dense search integration"""

    @pytest.mark.asyncio
    async def test_dense_search_success(self, hybrid_service, mock_vector_service):
        """Test successful dense search"""
        mock_vector_service.search.return_value = [
            {"id": "1", "content": "doc1", "score": 0.9},
            {"id": "2", "content": "doc2", "score": 0.8}
        ]

        results = await hybrid_service._dense_search(
            "test_collection", "query", 10, None
        )

        assert len(results) == 2
        assert results[0]["id"] == "1"
        mock_vector_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_dense_search_failure(self, hybrid_service, mock_vector_service):
        """Test dense search handles failures gracefully"""
        mock_vector_service.search.side_effect = Exception("Dense search error")

        results = await hybrid_service._dense_search(
            "test_collection", "query", 10, None
        )

        assert len(results) == 0


class TestSparseSearch:
    """Test sparse search integration"""

    @pytest.mark.asyncio
    async def test_sparse_search_success(self, hybrid_service, mock_sparse_service):
        """Test successful sparse search"""
        mock_sparse_service.bm25_search.return_value = [
            {"id": "1", "content": "doc1", "score": 0.85},
            {"id": "3", "content": "doc3", "score": 0.75}
        ]

        results = await hybrid_service._sparse_search(
            "test_collection", "query", 10, None
        )

        assert len(results) == 2
        assert results[0]["id"] == "1"
        mock_sparse_service.bm25_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_sparse_search_failure(self, hybrid_service, mock_sparse_service):
        """Test sparse search handles failures gracefully"""
        mock_sparse_service.bm25_search.side_effect = Exception("Sparse search error")

        results = await hybrid_service._sparse_search(
            "test_collection", "query", 10, None
        )

        assert len(results) == 0


class TestRRFFusion:
    """Test RRF fusion algorithm"""

    def test_rrf_fusion_basic(self, hybrid_service):
        """Test basic RRF fusion"""
        dense_results = [
            {"id": "1", "content": "doc1", "score": 0.9},
            {"id": "2", "content": "doc2", "score": 0.8}
        ]
        sparse_results = [
            {"id": "2", "content": "doc2", "score": 0.85},
            {"id": "3", "content": "doc3", "score": 0.75}
        ]

        fused = hybrid_service._rrf_fusion(dense_results, sparse_results, top_k=10)

        assert len(fused) == 3
        # Doc2 should rank highest (appears in both)
        assert fused[0]["id"] == "2"
        assert "rrf_score" in fused[0]
        assert "dense_rank" in fused[0]
        assert "sparse_rank" in fused[0]

    def test_rrf_fusion_top_k(self, hybrid_service):
        """Test RRF fusion with top_k limit"""
        dense_results = [
            {"id": str(i), "content": f"doc{i}", "score": 0.9 - i*0.1}
            for i in range(5)
        ]
        sparse_results = [
            {"id": str(i), "content": f"doc{i}", "score": 0.85 - i*0.1}
            for i in range(5)
        ]

        fused = hybrid_service._rrf_fusion(dense_results, sparse_results, top_k=3)

        assert len(fused) == 3

    def test_rrf_fusion_empty_results(self, hybrid_service):
        """Test RRF fusion with empty results"""
        fused = hybrid_service._rrf_fusion([], [], top_k=10)

        assert len(fused) == 0

    def test_rrf_fusion_score_calculation(self, hybrid_service):
        """Test RRF score calculation"""
        dense_results = [{"id": "1", "content": "doc1", "score": 0.9}]
        sparse_results = [{"id": "1", "content": "doc1", "score": 0.85}]

        fused = hybrid_service._rrf_fusion(dense_results, sparse_results, top_k=10)

        # RRF score = dense_weight/(k+rank_dense) + sparse_weight/(k+rank_sparse)
        # = 0.5/(60+1) + 0.5/(60+1) = 0.5/61 + 0.5/61 ≈ 0.0164
        assert len(fused) == 1
        assert abs(fused[0]["rrf_score"] - 0.0164) < 0.001


class TestReranking:
    """Test cross-encoder reranking"""

    def test_apply_reranking_success(self, hybrid_service, mock_reranker_service):
        """Test successful reranking"""
        results = [
            {"id": "1", "content": "doc1", "rrf_score": 0.02},
            {"id": "2", "content": "doc2", "rrf_score": 0.015}
        ]

        mock_reranker_service.rerank_results.return_value = [
            {"id": "2", "content": "doc2", "rerank_score": 0.95},
            {"id": "1", "content": "doc1", "rerank_score": 0.85}
        ]

        reranked = hybrid_service._apply_reranking("query", results, top_k=2)

        assert len(reranked) == 2
        assert reranked[0]["id"] == "2"
        mock_reranker_service.rerank_results.assert_called_once()

    def test_apply_reranking_failure(self, hybrid_service, mock_reranker_service):
        """Test reranking fallback on failure"""
        results = [
            {"id": "1", "content": "doc1", "rrf_score": 0.02},
            {"id": "2", "content": "doc2", "rrf_score": 0.015}
        ]

        mock_reranker_service.rerank_results.side_effect = Exception("Rerank error")

        reranked = hybrid_service._apply_reranking("query", results, top_k=2)

        # Should return original results on error
        assert len(reranked) == 2
        assert reranked == results[:2]

    def test_apply_reranking_empty(self, hybrid_service, mock_reranker_service):
        """Test reranking with empty results"""
        reranked = hybrid_service._apply_reranking("query", [], top_k=10)

        assert len(reranked) == 0
        mock_reranker_service.rerank_results.assert_not_called()


class TestHybridSearch:
    """Test complete hybrid search"""

    @pytest.mark.asyncio
    async def test_search_full_pipeline(self, hybrid_service, mock_vector_service, mock_sparse_service, mock_reranker_service):
        """Test complete hybrid search pipeline"""
        # Mock dense results
        mock_vector_service.search.return_value = [
            {"id": "1", "content": "doc1", "score": 0.9},
            {"id": "2", "content": "doc2", "score": 0.8}
        ]

        # Mock sparse results
        mock_sparse_service.bm25_search.return_value = [
            {"id": "2", "content": "doc2", "score": 0.85},
            {"id": "3", "content": "doc3", "score": 0.75}
        ]

        # Mock reranking
        mock_reranker_service.rerank_results.return_value = [
            {"id": "2", "content": "doc2", "rerank_score": 0.95, "rrf_score": 0.02},
            {"id": "1", "content": "doc1", "rerank_score": 0.88, "rrf_score": 0.015},
            {"id": "3", "content": "doc3", "rerank_score": 0.82, "rrf_score": 0.01}
        ]

        results = await hybrid_service.search(
            collection_name="test_collection",
            query="test query",
            top_k=3,
            use_reranking=True
        )

        assert len(results) == 3
        assert results[0]["id"] == "2"
        assert "rerank_score" in results[0]
        mock_vector_service.search.assert_called_once()
        mock_sparse_service.bm25_search.assert_called_once()
        mock_reranker_service.rerank_results.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_without_reranking(self, hybrid_service, mock_vector_service, mock_sparse_service, mock_reranker_service):
        """Test hybrid search without reranking"""
        mock_vector_service.search.return_value = [
            {"id": "1", "content": "doc1", "score": 0.9}
        ]
        mock_sparse_service.bm25_search.return_value = [
            {"id": "2", "content": "doc2", "score": 0.85}
        ]

        results = await hybrid_service.search(
            collection_name="test_collection",
            query="test query",
            top_k=2,
            use_reranking=False
        )

        assert len(results) <= 2
        mock_reranker_service.rerank_results.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_custom_top_k(self, hybrid_service, mock_vector_service, mock_sparse_service):
        """Test search with custom dense/sparse top_k"""
        mock_vector_service.search.return_value = []
        mock_sparse_service.bm25_search.return_value = []

        await hybrid_service.search(
            collection_name="test_collection",
            query="test query",
            top_k=5,
            dense_top_k=15,
            sparse_top_k=20
        )

        # Verify custom top_k passed to searches
        args, kwargs = mock_vector_service.search.call_args
        assert kwargs.get('top_k') == 15

        args, kwargs = mock_sparse_service.bm25_search.call_args
        assert kwargs.get('top_k') == 20


class TestBatchSearch:
    """Test batch search"""

    @pytest.mark.asyncio
    async def test_batch_search(self, hybrid_service, mock_vector_service, mock_sparse_service):
        """Test batch search for multiple queries"""
        mock_vector_service.search.return_value = []
        mock_sparse_service.bm25_search.return_value = []

        queries = ["query1", "query2", "query3"]

        results = await hybrid_service.batch_search(
            collection_name="test_collection",
            queries=queries,
            top_k=5
        )

        assert len(results) == 3
        assert all(isinstance(r, list) for r in results)


class TestSearchStatistics:
    """Test search statistics"""

    def test_get_stats_basic(self, hybrid_service):
        """Test basic search statistics"""
        results = [
            {
                "id": "1",
                "rrf_score": 0.02,
                "rerank_score": 0.9,
                "dense_rank": 1,
                "sparse_rank": 2
            },
            {
                "id": "2",
                "rrf_score": 0.015,
                "rerank_score": 0.85,
                "dense_rank": None,
                "sparse_rank": 1
            },
            {
                "id": "3",
                "rrf_score": 0.01,
                "rerank_score": 0.8,
                "dense_rank": 2,
                "sparse_rank": None
            }
        ]

        stats = hybrid_service.get_search_stats(results)

        assert stats["total_results"] == 3
        assert stats["dense_only"] == 1
        assert stats["sparse_only"] == 1
        assert stats["both"] == 1
        assert stats["avg_rrf_score"] > 0
        assert stats["avg_rerank_score"] > 0

    def test_get_stats_empty(self, hybrid_service):
        """Test stats with empty results"""
        stats = hybrid_service.get_search_stats([])

        assert stats["total_results"] == 0
        assert stats["avg_rrf_score"] == 0.0
        assert stats["avg_rerank_score"] == 0.0
        assert stats["dense_only"] == 0
        assert stats["sparse_only"] == 0
        assert stats["both"] == 0
