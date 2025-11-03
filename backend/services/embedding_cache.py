"""
Singleton Embedding Model Cache

Ensures the embedding model is loaded only once and shared across the application.
"""
from typing import Optional
from sentence_transformers import SentenceTransformer
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EmbeddingModelCache:
    """Singleton cache for embedding model to avoid reloading"""

    _instance: Optional['EmbeddingModelCache'] = None
    _model: Optional[SentenceTransformer] = None
    _model_name: Optional[str] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(self, model_name: str = "BAAI/bge-m3") -> SentenceTransformer:
        """
        Get cached embedding model or load it if not cached

        Args:
            model_name: Name of the embedding model

        Returns:
            Loaded SentenceTransformer model
        """
        # If model is already loaded and same name, return cached
        if self._model is not None and self._model_name == model_name:
            logger.debug(f"Using cached embedding model: {model_name}")
            return self._model

        # Load new model
        logger.info(f"Loading embedding model: {model_name}")
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        logger.info(f"Embedding model loaded successfully: {model_name}")

        return self._model

    def clear_cache(self):
        """Clear the cached model from memory"""
        if self._model is not None:
            logger.info(f"Clearing cached embedding model: {self._model_name}")
            del self._model
            self._model = None
            self._model_name = None


# Global singleton instance
_embedding_cache = EmbeddingModelCache()


def get_embedding_model(model_name: str = "BAAI/bge-m3") -> SentenceTransformer:
    """
    Get the embedding model (cached singleton)

    Args:
        model_name: Name of the embedding model

    Returns:
        Cached SentenceTransformer model
    """
    return _embedding_cache.get_model(model_name)
