"""
Vector Search Service using Qdrant

Features:
- Multi-vector embeddings (symptom, cause, resolution for issues / intent, procedure for KB)
- BGE-M3 embedding model
- Hybrid search with RRF (Reciprocal Rank Fusion)
- Filtering and boosting
"""
from typing import List, Dict, Any, Optional, Tuple
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition
from sentence_transformers import SentenceTransformer
import numpy as np
from backend.utils.logger import get_logger
from backend.config import get_settings
from backend.services.embedding_cache import get_embedding_model

logger = get_logger(__name__)
settings = get_settings()


class VectorSearchService:
    """Service for vector-based semantic search using Qdrant"""

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        embedding_model: str = "BAAI/bge-m3"
    ):
        """
        Initialize Qdrant client and embedding model (cached singleton)

        Args:
            qdrant_url: Qdrant server URL (default from env)
            qdrant_api_key: Qdrant API key (default from env)
            embedding_model: Embedding model name (default: bge-m3)
        """
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.qdrant_api_key = qdrant_api_key or getattr(settings, "QDRANT_API_KEY", None)

        # Initialize Qdrant client
        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )

        # Use cached embedding model (singleton) - only loads once!
        self.embedding_model = get_embedding_model(embedding_model)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")

    def create_collection(
        self,
        collection_name: str,
        vector_names: List[str],
        distance: Distance = Distance.COSINE
    ) -> bool:
        """
        Create a collection with multi-vector support

        Args:
            collection_name: Name of the collection
            vector_names: List of vector field names (e.g., ["symptom_vec", "cause_vec"])
            distance: Distance metric (COSINE, DOT, EUCLID)

        Returns:
            True if successful
        """
        try:
            # Check if collection already exists
            collections = self.client.get_collections().collections
            if any(col.name == collection_name for col in collections):
                logger.info(f"Collection '{collection_name}' already exists")
                return True

            # Create multi-vector config
            vectors_config = {
                name: VectorParams(
                    size=self.embedding_dim,
                    distance=distance
                )
                for name in vector_names
            }

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config
            )

            logger.info(
                f"Created collection '{collection_name}' with vectors: {vector_names}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of text strings

        Returns:
            Numpy array of embeddings (shape: [len(texts), embedding_dim])
        """
        if not texts:
            return np.array([])

        embeddings = self.embedding_model.encode(
            texts,
            normalize_embeddings=True,  # For cosine similarity
            show_progress_bar=False
        )

        return embeddings

    def upsert_vectors(
        self,
        collection_name: str,
        points: List[Dict[str, Any]]
    ) -> bool:
        """
        Upsert vectors to a collection

        Args:
            collection_name: Name of the collection
            points: List of point dictionaries with structure:
                {
                    "id": str or int,
                    "vectors": {"symptom_vec": [...], "cause_vec": [...]},
                    "payload": {"ticket_id": "123", "text": "..."}
                }

        Returns:
            True if successful
        """
        try:
            qdrant_points = [
                PointStruct(
                    id=point["id"],
                    vector=point["vectors"],
                    payload=point.get("payload", {})
                )
                for point in points
            ]

            self.client.upsert(
                collection_name=collection_name,
                points=qdrant_points
            )

            logger.info(
                f"Upserted {len(points)} points to collection '{collection_name}'"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to upsert vectors to '{collection_name}': {e}"
            )
            raise

    def search_similar(
        self,
        collection_name: str,
        query_vector: List[float],
        vector_name: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors

        Args:
            collection_name: Name of the collection
            query_vector: Query vector
            vector_name: Name of the vector field to search (e.g., "symptom_vec")
            top_k: Number of results to return
            filters: Optional filters {"tenant_id": "123"}
            score_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of search results with id, score, and payload
        """
        try:
            # Build filter if provided
            query_filter = None
            if filters:
                conditions = [
                    FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                    for key, value in filters.items()
                ]
                query_filter = Filter(must=conditions)

            # Search (use tuple for named vector in multi-vector collections)
            # In qdrant-client >= 1.8.0, use tuple (vector_name, vector) instead of using parameter
            results = self.client.search(
                collection_name=collection_name,
                query_vector=(vector_name, query_vector),
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )

            # Format results
            formatted_results = [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in results
            ]

            logger.info(
                f"Found {len(formatted_results)} results in '{collection_name}' "
                f"for vector '{vector_name}'"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed in '{collection_name}': {e}")
            raise

    def hybrid_search(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search using Reciprocal Rank Fusion (RRF)

        Args:
            dense_results: Results from dense vector search
            sparse_results: Results from sparse (BM25) search
            k: RRF constant (default: 60)

        Returns:
            Fused and re-ranked results
        """
        # Build score dictionaries
        rrf_scores: Dict[str, float] = {}

        # Process dense results
        for rank, result in enumerate(dense_results, 1):
            doc_id = str(result["id"])
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        # Process sparse results
        for rank, result in enumerate(sparse_results, 1):
            doc_id = str(result["id"])
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        # Build result list (combine payloads from both sources)
        result_map = {}
        for result in dense_results + sparse_results:
            doc_id = str(result["id"])
            if doc_id not in result_map:
                result_map[doc_id] = result

        # Merge results
        fused_results = []
        for doc_id, score in sorted_ids:
            if doc_id in result_map:
                result = result_map[doc_id].copy()
                result["rrf_score"] = score
                fused_results.append(result)

        logger.info(
            f"RRF fusion: {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"→ {len(fused_results)} fused results"
        )
        return fused_results

    def search_with_multi_vectors(
        self,
        collection_name: str,
        query_text: str,
        vector_names: List[str],
        weights: Optional[List[float]] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using multiple vector fields with optional weighting

        Args:
            collection_name: Name of the collection
            query_text: Query text
            vector_names: List of vector field names to search
            weights: Optional weights for each vector (must sum to 1.0)
            top_k: Number of results
            filters: Optional filters

        Returns:
            Weighted and merged search results
        """
        # Generate query embedding
        query_embedding = self.generate_embeddings([query_text])[0].tolist()

        # Default equal weights
        if weights is None:
            weights = [1.0 / len(vector_names)] * len(vector_names)

        if len(weights) != len(vector_names):
            raise ValueError("Number of weights must match number of vector names")

        if abs(sum(weights) - 1.0) > 1e-6:
            raise ValueError("Weights must sum to 1.0")

        # Search each vector field
        all_results = []
        for vector_name, weight in zip(vector_names, weights):
            results = self.search_similar(
                collection_name=collection_name,
                query_vector=query_embedding,
                vector_name=vector_name,
                top_k=top_k * 2,  # Get more candidates
                filters=filters
            )

            # Apply weight to scores
            for result in results:
                result["weighted_score"] = result["score"] * weight
                result["vector_source"] = vector_name

            all_results.extend(results)

        # Aggregate scores by document ID
        score_map: Dict[str, float] = {}
        result_map: Dict[str, Dict[str, Any]] = {}

        for result in all_results:
            doc_id = str(result["id"])
            score_map[doc_id] = score_map.get(doc_id, 0) + result["weighted_score"]

            if doc_id not in result_map:
                result_map[doc_id] = result

        # Sort by aggregated score
        sorted_ids = sorted(score_map.items(), key=lambda x: x[1], reverse=True)

        # Build final results
        final_results = []
        for doc_id, score in sorted_ids[:top_k]:
            result = result_map[doc_id].copy()
            result["aggregated_score"] = score
            final_results.append(result)

        logger.info(
            f"Multi-vector search on {vector_names} returned {len(final_results)} results"
        )
        return final_results

    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection

        Args:
            collection_name: Name of the collection to delete

        Returns:
            True if successful
        """
        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            raise

    async def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        vector_name: str = "content_vec"
    ) -> List[Dict[str, Any]]:
        """
        Search with text query (generates embedding automatically)

        This method is called by HybridSearchService.

        Args:
            collection_name: Name of the collection
            query: Text query
            top_k: Number of results
            filters: Optional filters
            vector_name: Vector field name (default: content_vec)

        Returns:
            List of search results
        """
        try:
            # Generate embedding from text query
            query_embedding = self.generate_embeddings([query])[0].tolist()

            # Use existing search_similar method
            results = self.search_similar(
                collection_name=collection_name,
                query_vector=query_embedding,
                vector_name=vector_name,
                top_k=top_k,
                filters=filters
            )

            return results

        except Exception as e:
            logger.error(f"Text search failed in '{collection_name}': {e}")
            raise

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get collection information

        Args:
            collection_name: Name of the collection

        Returns:
            Collection info dictionary
        """
        try:
            info = self.client.get_collection(collection_name=collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value
            }
        except Exception as e:
            logger.error(f"Failed to get collection info '{collection_name}': {e}")
            raise
