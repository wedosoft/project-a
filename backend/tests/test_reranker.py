"""
Unit tests for Reranker Service

Tests:
- Service initialization
- GPU detection
- Single query reranking
- Batch reranking
- Search result reranking
- Score normalization
- Model info retrieval
"""
import pytest
from unittest.mock import MagicMock, patch
import torch

from backend.services.reranker import RerankerService


@pytest.fixture
def mock_cross_encoder():
    """Fixture for mock CrossEncoder"""
    encoder = MagicMock()
    encoder.predict.return_value = [0.9, 0.7, 0.5]
    return encoder


@pytest.fixture
def reranker_service(mock_cross_encoder):
    """Fixture for RerankerService with mocked model"""
    with patch("backend.services.reranker.CrossEncoder", return_value=mock_cross_encoder):
        service = RerankerService(device="cpu")
        return service


class TestServiceInitialization:
    """Test service initialization"""

    def test_init_default_params(self, mock_cross_encoder):
        """Test service initializes with default parameters"""
        with patch("backend.services.reranker.CrossEncoder", return_value=mock_cross_encoder):
            with patch("torch.cuda.is_available", return_value=False):
                service = RerankerService()

                assert service.model_name == "jinaai/jina-reranker-v2-base-multilingual"
                assert service.batch_size == 8
                assert service.device == "cpu"

    def test_init_custom_params(self, mock_cross_encoder):
        """Test service initializes with custom parameters"""
        with patch("backend.services.reranker.CrossEncoder", return_value=mock_cross_encoder):
            service = RerankerService(
                model_name="custom/model",
                device="cuda",
                batch_size=16
            )

            assert service.model_name == "custom/model"
            assert service.batch_size == 16
            assert service.device == "cuda"

    def test_gpu_auto_detection(self, mock_cross_encoder):
        """Test GPU auto-detection"""
        with patch("backend.services.reranker.CrossEncoder", return_value=mock_cross_encoder):
            with patch("torch.cuda.is_available", return_value=True):
                service = RerankerService()
                assert service.device == "cuda"


class TestReranking:
    """Test reranking functionality"""

    def test_rerank_basic(self, reranker_service):
        """Test basic reranking"""
        query = "test query"
        documents = ["doc1", "doc2", "doc3"]

        results = reranker_service.rerank(query, documents)

        assert len(results) == 3
        # Results should be sorted by score descending
        assert results[0][1] >= results[1][1] >= results[2][1]
        # Check indices
        assert all(0 <= idx < 3 for idx, _ in results)

    def test_rerank_with_top_k(self, reranker_service):
        """Test reranking with top_k limit"""
        query = "test query"
        documents = ["doc1", "doc2", "doc3"]

        results = reranker_service.rerank(query, documents, top_k=2)

        assert len(results) == 2
        # Should return top 2 highest scores
        assert results[0][1] >= results[1][1]

    def test_rerank_empty_documents(self, reranker_service):
        """Test reranking with empty document list"""
        results = reranker_service.rerank("test", [])
        assert len(results) == 0

    def test_rerank_single_document(self, reranker_service, mock_cross_encoder):
        """Test reranking with single document"""
        mock_cross_encoder.predict.return_value = [0.8]

        results = reranker_service.rerank("test", ["single doc"])

        assert len(results) == 1
        assert results[0][0] == 0  # Index 0
        assert results[0][1] == 0.8  # Score


class TestRerankResults:
    """Test reranking search results"""

    def test_rerank_search_results(self, reranker_service, mock_cross_encoder):
        """Test reranking search results"""
        mock_cross_encoder.predict.return_value = [0.9, 0.7, 0.5]

        search_results = [
            {"id": "1", "content": "doc1", "score": 0.5},
            {"id": "2", "content": "doc2", "score": 0.6},
            {"id": "3", "content": "doc3", "score": 0.7}
        ]

        reranked = reranker_service.rerank_results(
            query="test",
            search_results=search_results
        )

        assert len(reranked) == 3
        # First result should have highest rerank_score
        assert reranked[0]["rerank_score"] == 0.9
        # Original fields should be preserved
        assert "id" in reranked[0]
        assert "content" in reranked[0]

    def test_rerank_results_custom_field(self, reranker_service, mock_cross_encoder):
        """Test reranking with custom content field"""
        mock_cross_encoder.predict.return_value = [0.8]

        search_results = [
            {"id": "1", "text": "custom field content"}
        ]

        reranked = reranker_service.rerank_results(
            query="test",
            search_results=search_results,
            content_field="text"
        )

        assert len(reranked) == 1
        assert reranked[0]["rerank_score"] == 0.8

    def test_rerank_results_with_top_k(self, reranker_service, mock_cross_encoder):
        """Test reranking results with top_k"""
        mock_cross_encoder.predict.return_value = [0.9, 0.7, 0.5]

        search_results = [
            {"id": str(i), "content": f"doc{i}"} for i in range(3)
        ]

        reranked = reranker_service.rerank_results(
            query="test",
            search_results=search_results,
            top_k=2
        )

        assert len(reranked) == 2

    def test_rerank_empty_results(self, reranker_service):
        """Test reranking empty search results"""
        reranked = reranker_service.rerank_results("test", [])
        assert len(reranked) == 0


class TestBatchReranking:
    """Test batch reranking"""

    def test_batch_rerank(self, reranker_service, mock_cross_encoder):
        """Test batch reranking multiple queries"""
        queries = ["query1", "query2"]
        documents_list = [
            ["doc1", "doc2"],
            ["doc3", "doc4", "doc5"]
        ]

        # Mock different scores for each query
        mock_cross_encoder.predict.side_effect = [
            [0.9, 0.7],  # query1 results
            [0.8, 0.6, 0.4]  # query2 results
        ]

        results = reranker_service.batch_rerank(queries, documents_list)

        assert len(results) == 2
        assert len(results[0]) == 2  # query1 has 2 docs
        assert len(results[1]) == 3  # query2 has 3 docs

    def test_batch_rerank_with_top_k(self, reranker_service, mock_cross_encoder):
        """Test batch reranking with top_k"""
        queries = ["query1"]
        documents_list = [["doc1", "doc2", "doc3"]]

        mock_cross_encoder.predict.return_value = [0.9, 0.7, 0.5]

        results = reranker_service.batch_rerank(
            queries, documents_list, top_k=2
        )

        assert len(results[0]) == 2

    def test_batch_rerank_mismatched_lengths(self, reranker_service):
        """Test batch rerank with mismatched query/doc lengths"""
        queries = ["query1", "query2"]
        documents_list = [["doc1"]]  # Only one doc list

        with pytest.raises(ValueError, match="must match"):
            reranker_service.batch_rerank(queries, documents_list)


class TestScoreNormalization:
    """Test score normalization"""

    def test_normalize_minmax(self, reranker_service):
        """Test min-max normalization"""
        scores = [0.5, 0.7, 0.9, 0.3]

        normalized = reranker_service.normalize_scores(scores, method="minmax")

        assert len(normalized) == 4
        assert min(normalized) == 0.0
        assert max(normalized) == 1.0

    def test_normalize_softmax(self, reranker_service):
        """Test softmax normalization"""
        scores = [0.5, 0.7, 0.9]

        normalized = reranker_service.normalize_scores(scores, method="softmax")

        assert len(normalized) == 3
        # Softmax scores should sum to 1.0
        assert abs(sum(normalized) - 1.0) < 1e-6

    def test_normalize_empty_scores(self, reranker_service):
        """Test normalization with empty scores"""
        normalized = reranker_service.normalize_scores([], method="minmax")
        assert len(normalized) == 0

    def test_normalize_single_score(self, reranker_service):
        """Test normalization with single score"""
        normalized = reranker_service.normalize_scores([0.5], method="minmax")
        assert len(normalized) == 1
        assert normalized[0] == 1.0  # Single value normalizes to 1.0

    def test_normalize_invalid_method(self, reranker_service):
        """Test normalization with invalid method"""
        with pytest.raises(ValueError, match="Unknown normalization method"):
            reranker_service.normalize_scores([0.5], method="invalid")


class TestModelInfo:
    """Test model information retrieval"""

    def test_get_model_info(self, reranker_service):
        """Test getting model information"""
        with patch("torch.cuda.is_available", return_value=False):
            info = reranker_service.get_model_info()

            assert "model_name" in info
            assert "device" in info
            assert "batch_size" in info
            assert info["batch_size"] == 8
            assert info["max_length"] == 512
            assert info["gpu_available"] is False

    def test_get_model_info_with_gpu(self, reranker_service):
        """Test model info with GPU available"""
        with patch("torch.cuda.is_available", return_value=True):
            with patch("torch.cuda.get_device_name", return_value="NVIDIA GPU"):
                info = reranker_service.get_model_info()

                assert info["gpu_available"] is True
                assert info["gpu_name"] == "NVIDIA GPU"
