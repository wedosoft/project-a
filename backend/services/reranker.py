"""
Cross-Encoder Reranker Service

Features:
- Jina AI Reranker v2 Base Multilingual model
- Batch processing for efficiency
- GPU detection and automatic device selection
- Model caching for performance
- Score normalization
"""
from typing import List, Dict, Any, Optional, Tuple
import torch
from sentence_transformers import CrossEncoder
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RerankerService:
    """Service for cross-encoder reranking using Jina AI Reranker"""

    def __init__(
        self,
        model_name: str = "jinaai/jina-reranker-v2-base-multilingual",
        device: Optional[str] = None,
        batch_size: int = 8
    ):
        """
        Initialize reranker model

        Args:
            model_name: Model name (default: jina-reranker-v2-base-multilingual)
            device: Device to use ('cuda', 'cpu', or None for auto-detect)
            batch_size: Batch size for processing (default: 8)
        """
        self.model_name = model_name
        self.batch_size = batch_size

        # Auto-detect device if not specified
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info(f"Loading reranker model: {model_name}")
        logger.info(f"Using device: {self.device}")

        # Load cross-encoder model
        self.model = CrossEncoder(
            model_name,
            device=self.device,
            max_length=512
        )

        logger.info("Reranker model loaded successfully")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float]]:
        """
        Rerank documents using cross-encoder

        Args:
            query: Query text
            documents: List of document texts to rerank
            top_k: Number of top results to return (None = all)

        Returns:
            List of (index, score) tuples sorted by score descending
        """
        if not documents:
            return []

        try:
            # Create query-document pairs
            pairs = [[query, doc] for doc in documents]

            # Get relevance scores
            scores = self.model.predict(
                pairs,
                batch_size=self.batch_size,
                show_progress_bar=False
            )

            # Create (index, score) tuples
            ranked = [(i, float(score)) for i, score in enumerate(scores)]

            # Sort by score descending
            ranked.sort(key=lambda x: x[1], reverse=True)

            # Apply top_k if specified
            if top_k is not None:
                ranked = ranked[:top_k]

            logger.info(
                f"Reranked {len(documents)} documents, "
                f"returning top {len(ranked)} results"
            )

            return ranked

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            raise

    def rerank_results(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        content_field: str = "content",
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results with relevance scores

        Args:
            query: Query text
            search_results: List of search result dictionaries
            content_field: Field name containing document text
            top_k: Number of top results to return

        Returns:
            Reranked search results with added 'rerank_score' field
        """
        if not search_results:
            return []

        try:
            # Extract document texts
            documents = [result.get(content_field, "") for result in search_results]

            # Rerank
            ranked_indices = self.rerank(query, documents, top_k=top_k)

            # Build reranked results
            reranked_results = []
            for idx, score in ranked_indices:
                result = search_results[idx].copy()
                result["rerank_score"] = score
                reranked_results.append(result)

            logger.info(f"Reranked {len(search_results)} search results")
            return reranked_results

        except Exception as e:
            logger.error(f"Failed to rerank search results: {e}")
            raise

    def batch_rerank(
        self,
        queries: List[str],
        documents_list: List[List[str]],
        top_k: Optional[int] = None
    ) -> List[List[Tuple[int, float]]]:
        """
        Batch rerank multiple query-document sets

        Args:
            queries: List of query texts
            documents_list: List of document lists (one per query)
            top_k: Number of top results per query

        Returns:
            List of ranked results (one per query)
        """
        if len(queries) != len(documents_list):
            raise ValueError(
                f"Number of queries ({len(queries)}) must match "
                f"number of document lists ({len(documents_list)})"
            )

        try:
            results = []
            for query, documents in zip(queries, documents_list):
                ranked = self.rerank(query, documents, top_k=top_k)
                results.append(ranked)

            logger.info(f"Batch reranked {len(queries)} query-document sets")
            return results

        except Exception as e:
            logger.error(f"Batch reranking failed: {e}")
            raise

    def normalize_scores(
        self,
        scores: List[float],
        method: str = "minmax"
    ) -> List[float]:
        """
        Normalize reranking scores

        Args:
            scores: List of raw scores
            method: Normalization method ('minmax' or 'softmax')

        Returns:
            Normalized scores
        """
        if not scores:
            return []

        if method == "minmax":
            min_score = min(scores)
            max_score = max(scores)
            score_range = max_score - min_score

            if score_range == 0:
                return [1.0] * len(scores)

            return [(s - min_score) / score_range for s in scores]

        elif method == "softmax":
            # Convert to torch tensor for softmax
            scores_tensor = torch.tensor(scores)
            normalized = torch.softmax(scores_tensor, dim=0)
            return normalized.tolist()

        else:
            raise ValueError(f"Unknown normalization method: {method}")

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get model information

        Returns:
            Dictionary with model metadata
        """
        return {
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "max_length": 512,
            "gpu_available": torch.cuda.is_available(),
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        }
