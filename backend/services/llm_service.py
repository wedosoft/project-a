"""
LLM Service - Embedding and text generation wrapper

Provides unified interface for:
- Embedding generation (delegates to VectorSearchService)
- Text completion (future implementation)
"""
from typing import List
import numpy as np
from backend.services.vector_search import VectorSearchService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    """
    LLM service for embeddings and text generation

    Currently wraps VectorSearchService for embedding generation.
    Future: Add text completion capabilities.
    """

    def __init__(self):
        """Initialize LLM service with vector search backend"""
        self.vector_service = VectorSearchService()
        logger.info("LLMService initialized")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding generation")
            return [0.0] * self.vector_service.embedding_dim

        try:
            embeddings = self.vector_service.generate_embeddings([text])
            return embeddings[0].tolist()
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        try:
            embeddings = self.vector_service.generate_embeddings(texts)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
