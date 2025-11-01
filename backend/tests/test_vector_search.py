"""
Unit tests for Vector Search Service

Tests:
- Service initialization
- Collection creation with multi-vectors
- Embedding generation
- Vector upsert
- Similarity search
- Hybrid search with RRF
- Multi-vector search
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import numpy as np

from backend.services.vector_search import VectorSearchService


@pytest.fixture
def mock_qdrant_client():
    """Fixture for mock Qdrant client"""
    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    return client


@pytest.fixture
def mock_embedding_model():
    """Fixture for mock embedding model"""
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = 1024
    model.encode.return_value = np.random.rand(2, 1024)  # 2 texts, 1024 dim
    return model


@pytest.fixture
def vector_service(mock_qdrant_client, mock_embedding_model):
    """Fixture for VectorSearchService with mocked dependencies"""
    with patch("backend.services.vector_search.QdrantClient", return_value=mock_qdrant_client):
        with patch("backend.services.vector_search.SentenceTransformer", return_value=mock_embedding_model):
            service = VectorSearchService(
                qdrant_url="http://localhost:6333",
                qdrant_api_key="test-key"
            )
            return service


class TestServiceInitialization:
    """Test service initialization"""

    def test_init_with_custom_params(self, vector_service):
        """Test service initializes with custom parameters"""
        assert vector_service.qdrant_url == "http://localhost:6333"
        assert vector_service.qdrant_api_key == "test-key"
        assert vector_service.embedding_dim == 1024


class TestCollectionManagement:
    """Test collection creation and management"""

    def test_create_collection_new(self, vector_service, mock_qdrant_client):
        """Test creating a new collection"""
        mock_qdrant_client.get_collections.return_value = MagicMock(collections=[])

        result = vector_service.create_collection(
            collection_name="test_collection",
            vector_names=["symptom_vec", "cause_vec", "resolution_vec"]
        )

        assert result is True
        mock_qdrant_client.create_collection.assert_called_once()

    def test_create_collection_exists(self, vector_service, mock_qdrant_client):
        """Test creating a collection that already exists"""
        existing_collection = MagicMock()
        existing_collection.name = "test_collection"
        mock_qdrant_client.get_collections.return_value = MagicMock(
            collections=[existing_collection]
        )

        result = vector_service.create_collection(
            collection_name="test_collection",
            vector_names=["symptom_vec"]
        )

        assert result is True
        mock_qdrant_client.create_collection.assert_not_called()

    def test_get_collection_info(self, vector_service, mock_qdrant_client):
        """Test getting collection information"""
        mock_info = MagicMock()
        mock_info.vectors_count = 1000
        mock_info.points_count = 500
        mock_info.status.value = "green"
        mock_qdrant_client.get_collection.return_value = mock_info

        info = vector_service.get_collection_info("test_collection")

        assert info["vectors_count"] == 1000
        assert info["points_count"] == 500
        assert info["status"] == "green"

    def test_delete_collection(self, vector_service, mock_qdrant_client):
        """Test deleting a collection"""
        result = vector_service.delete_collection("test_collection")

        assert result is True
        mock_qdrant_client.delete_collection.assert_called_once_with(
            collection_name="test_collection"
        )


class TestEmbeddingGeneration:
    """Test embedding generation"""

    def test_generate_embeddings(self, vector_service, mock_embedding_model):
        """Test embedding generation for texts"""
        texts = ["This is a symptom", "This is a resolution"]

        embeddings = vector_service.generate_embeddings(texts)

        assert embeddings.shape == (2, 1024)
        mock_embedding_model.encode.assert_called_once()

    def test_generate_embeddings_empty(self, vector_service):
        """Test embedding generation with empty input"""
        embeddings = vector_service.generate_embeddings([])

        assert embeddings.shape == (0,)


class TestVectorOperations:
    """Test vector upsert and search"""

    def test_upsert_vectors(self, vector_service, mock_qdrant_client):
        """Test upserting vectors to collection"""
        points = [
            {
                "id": "1",
                "vectors": {
                    "symptom_vec": [0.1] * 1024,
                    "cause_vec": [0.2] * 1024,
                    "resolution_vec": [0.3] * 1024
                },
                "payload": {"ticket_id": "123"}
            }
        ]

        result = vector_service.upsert_vectors(
            collection_name="test_collection",
            points=points
        )

        assert result is True
        mock_qdrant_client.upsert.assert_called_once()

    def test_search_similar(self, vector_service, mock_qdrant_client):
        """Test similarity search"""
        mock_hit = MagicMock()
        mock_hit.id = "1"
        mock_hit.score = 0.95
        mock_hit.payload = {"ticket_id": "123", "text": "Test"}

        mock_qdrant_client.search.return_value = [mock_hit]

        results = vector_service.search_similar(
            collection_name="test_collection",
            query_vector=[0.1] * 1024,
            vector_name="symptom_vec",
            top_k=10
        )

        assert len(results) == 1
        assert results[0]["id"] == "1"
        assert results[0]["score"] == 0.95
        assert results[0]["payload"]["ticket_id"] == "123"

    def test_search_similar_with_filters(self, vector_service, mock_qdrant_client):
        """Test similarity search with filters"""
        mock_qdrant_client.search.return_value = []

        results = vector_service.search_similar(
            collection_name="test_collection",
            query_vector=[0.1] * 1024,
            vector_name="symptom_vec",
            top_k=10,
            filters={"tenant_id": "abc123"}
        )

        assert len(results) == 0
        # Verify filter was passed
        call_args = mock_qdrant_client.search.call_args
        assert call_args[1]["query_filter"] is not None


class TestHybridSearch:
    """Test hybrid search with RRF"""

    def test_hybrid_search_rrf(self, vector_service):
        """Test RRF fusion of dense and sparse results"""
        dense_results = [
            {"id": "1", "score": 0.95, "payload": {"text": "A"}},
            {"id": "2", "score": 0.85, "payload": {"text": "B"}},
            {"id": "3", "score": 0.75, "payload": {"text": "C"}}
        ]

        sparse_results = [
            {"id": "2", "score": 0.90, "payload": {"text": "B"}},
            {"id": "4", "score": 0.80, "payload": {"text": "D"}},
            {"id": "1", "score": 0.70, "payload": {"text": "A"}}
        ]

        fused = vector_service.hybrid_search(dense_results, sparse_results, k=60)

        # Both results should be fused
        assert len(fused) == 4
        # Results should have RRF scores
        assert "rrf_score" in fused[0]
        # ID "1" and "2" should rank higher (appear in both)
        top_ids = {fused[0]["id"], fused[1]["id"]}
        assert "1" in top_ids or "2" in top_ids

    def test_hybrid_search_empty_sparse(self, vector_service):
        """Test RRF with empty sparse results"""
        dense_results = [
            {"id": "1", "score": 0.95, "payload": {"text": "A"}}
        ]

        fused = vector_service.hybrid_search(dense_results, [], k=60)

        assert len(fused) == 1
        assert fused[0]["id"] == "1"

    def test_hybrid_search_empty_dense(self, vector_service):
        """Test RRF with empty dense results"""
        sparse_results = [
            {"id": "1", "score": 0.90, "payload": {"text": "A"}}
        ]

        fused = vector_service.hybrid_search([], sparse_results, k=60)

        assert len(fused) == 1
        assert fused[0]["id"] == "1"


class TestMultiVectorSearch:
    """Test multi-vector weighted search"""

    def test_multi_vector_search(self, vector_service, mock_qdrant_client, mock_embedding_model):
        """Test search across multiple vector fields"""
        # Mock search results
        mock_hit1 = MagicMock()
        mock_hit1.id = "1"
        mock_hit1.score = 0.9
        mock_hit1.payload = {"text": "A"}

        mock_hit2 = MagicMock()
        mock_hit2.id = "2"
        mock_hit2.score = 0.8
        mock_hit2.payload = {"text": "B"}

        mock_qdrant_client.search.return_value = [mock_hit1, mock_hit2]

        results = vector_service.search_with_multi_vectors(
            collection_name="test_collection",
            query_text="test query",
            vector_names=["symptom_vec", "resolution_vec"],
            weights=[0.7, 0.3],
            top_k=10
        )

        # Should return aggregated results
        assert len(results) > 0
        assert "aggregated_score" in results[0]

    def test_multi_vector_search_equal_weights(self, vector_service, mock_qdrant_client, mock_embedding_model):
        """Test multi-vector search with equal weights"""
        mock_qdrant_client.search.return_value = []

        results = vector_service.search_with_multi_vectors(
            collection_name="test_collection",
            query_text="test query",
            vector_names=["symptom_vec", "cause_vec", "resolution_vec"],
            weights=None,  # Should default to equal weights
            top_k=5
        )

        # Search should be called 3 times (one per vector field)
        assert mock_qdrant_client.search.call_count == 3

    def test_multi_vector_search_invalid_weights(self, vector_service):
        """Test multi-vector search with invalid weights"""
        with pytest.raises(ValueError, match="Number of weights must match"):
            vector_service.search_with_multi_vectors(
                collection_name="test_collection",
                query_text="test",
                vector_names=["vec1", "vec2"],
                weights=[0.5],  # Wrong number of weights
                top_k=5
            )

    def test_multi_vector_search_weights_not_sum_to_one(self, vector_service):
        """Test multi-vector search with weights not summing to 1.0"""
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            vector_service.search_with_multi_vectors(
                collection_name="test_collection",
                query_text="test",
                vector_names=["vec1", "vec2"],
                weights=[0.3, 0.5],  # Sum is 0.8, not 1.0
                top_k=5
            )
