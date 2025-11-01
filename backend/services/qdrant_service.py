"""
Qdrant Service - Vector database operations wrapper

Provides simplified interface for:
- Vector storage and retrieval
- Collection management
- Batch operations
"""
from typing import List, Dict, Any, Optional
from backend.services.vector_search import VectorSearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class QdrantService:
    """
    Qdrant vector database service

    Wraps VectorSearchService for simplified vector operations.
    """

    def __init__(self):
        """Initialize Qdrant service"""
        self.vector_service = VectorSearchService()
        logger.info("QdrantService initialized")

    def store_vector(
        self,
        collection_name: str,
        point_id: str,
        vectors: Dict[str, List[float]],
        payload: Dict[str, Any]
    ) -> bool:
        """
        Store a single vector point

        Args:
            collection_name: Target collection
            point_id: Unique point ID
            vectors: Vector dictionary (e.g., {"content_vec": [...]})
            payload: Metadata payload

        Returns:
            True if successful
        """
        try:
            points = [{
                "id": point_id,
                "vectors": vectors,
                "payload": payload
            }]

            return self.vector_service.upsert_vectors(
                collection_name=collection_name,
                points=points
            )
        except Exception as e:
            logger.error(f"Failed to store vector: {e}")
            raise

    def store_vectors_batch(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        """
        Store multiple vectors in batch

        Args:
            collection_name: Target collection
            points: List of point dictionaries with id, vectors, payload

        Returns:
            True if successful
        """
        try:
            return self.vector_service.upsert_vectors(
                collection_name=collection_name,
                points=points
            )
        except Exception as e:
            logger.error(f"Failed to store vectors batch: {e}")
            raise

    def ensure_collection(
        self,
        collection_name: str,
        vector_names: List[str]
    ) -> bool:
        """
        Ensure collection exists, create if not

        Args:
            collection_name: Collection name
            vector_names: List of vector field names

        Returns:
            True if collection exists or was created
        """
        try:
            return self.vector_service.create_collection(
                collection_name=collection_name,
                vector_names=vector_names
            )
        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            raise

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get collection information

        Args:
            collection_name: Collection name

        Returns:
            Collection info dictionary
        """
        try:
            return self.vector_service.get_collection_info(collection_name)
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            raise
