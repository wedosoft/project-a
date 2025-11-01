"""
Hybrid Search Service combining Dense + Sparse + Reranking

Features:
- Multi-vector dense search (Qdrant)
- BM25 sparse search (PostgreSQL)
- Cross-encoder reranking (Jina AI)
- RRF (Reciprocal Rank Fusion) for score combination
- Configurable weights and top-k
"""
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from collections import defaultdict

from backend.services.vector_search import VectorSearchService
from backend.services.sparse_search import SparseSearchService
from backend.services.reranker import RerankerService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class HybridSearchService:
    """
    Hybrid search combining dense vector search, sparse BM25, and reranking

    Search pipeline:
    1. Dense search (multi-vector embeddings in Qdrant)
    2. Sparse search (BM25 with PostgreSQL pg_trgm)
    3. RRF fusion (combine dense + sparse scores)
    4. Cross-encoder reranking (final relevance scoring)
    """

    def __init__(
        self,
        vector_service: Optional[VectorSearchService] = None,
        sparse_service: Optional[SparseSearchService] = None,
        reranker_service: Optional[RerankerService] = None,
        rrf_k: int = 60,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5
    ):
        """
        Initialize hybrid search service

        Args:
            vector_service: Vector search service (default: new instance)
            sparse_service: Sparse search service (default: new instance)
            reranker_service: Reranker service (default: new instance)
            rrf_k: RRF constant (default: 60)
            dense_weight: Weight for dense search (default: 0.5)
            sparse_weight: Weight for sparse search (default: 0.5)
        """
        self.vector_service = vector_service or VectorSearchService()
        self.sparse_service = sparse_service or SparseSearchService()
        self.reranker_service = reranker_service or RerankerService()

        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight

        logger.info("HybridSearchService initialized")
        logger.info(f"RRF k={rrf_k}, dense_weight={dense_weight}, sparse_weight={sparse_weight}")

    async def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
        dense_top_k: Optional[int] = None,
        sparse_top_k: Optional[int] = None,
        use_reranking: bool = True,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining dense, sparse, and reranking

        Args:
            collection_name: Collection to search
            query: Search query
            top_k: Final number of results to return
            dense_top_k: Top-k for dense search (default: top_k * 2)
            sparse_top_k: Top-k for sparse search (default: top_k * 2)
            use_reranking: Whether to apply cross-encoder reranking
            filters: Optional metadata filters

        Returns:
            List of search results with hybrid scores
        """
        # Set default top-k values
        dense_top_k = dense_top_k or top_k * 2
        sparse_top_k = sparse_top_k or top_k * 2

        try:
            # Run dense and sparse searches in parallel
            dense_task = self._dense_search(
                collection_name, query, dense_top_k, filters
            )
            sparse_task = self._sparse_search(
                collection_name, query, sparse_top_k, filters
            )

            dense_results, sparse_results = await asyncio.gather(
                dense_task, sparse_task
            )

            logger.info(f"Dense search returned {len(dense_results)} results")
            logger.info(f"Sparse search returned {len(sparse_results)} results")

            # Apply RRF fusion
            fused_results = self._rrf_fusion(
                dense_results, sparse_results, top_k * 2
            )

            logger.info(f"RRF fusion produced {len(fused_results)} results")

            # Apply cross-encoder reranking if enabled
            if use_reranking and fused_results:
                fused_results = self._apply_reranking(
                    query, fused_results, top_k
                )
                logger.info(f"Reranking produced {len(fused_results)} final results")
            else:
                fused_results = fused_results[:top_k]

            return fused_results

        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            raise

    async def _dense_search(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run dense vector search"""
        try:
            results = await self.vector_service.search(
                collection_name=collection_name,
                query=query,
                top_k=top_k,
                filters=filters
            )
            return results
        except Exception as e:
            logger.warning(f"Dense search failed: {e}, returning empty results")
            return []

    async def _sparse_search(
        self,
        collection_name: str,
        query: str,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Run sparse BM25 search"""
        try:
            results = await self.sparse_service.bm25_search(
                collection_name=collection_name,
                query=query,
                top_k=top_k,
                filters=filters
            )
            return results
        except Exception as e:
            logger.warning(f"Sparse search failed: {e}, returning empty results")
            return []

    def _rrf_fusion(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine dense and sparse results

        RRF formula: score(d) = Σ(weight_i / (k + rank_i(d)))

        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            top_k: Number of results to return

        Returns:
            Fused results sorted by RRF score
        """
        # Build document index and scores
        doc_scores = defaultdict(lambda: {
            'rrf_score': 0.0,
            'dense_rank': None,
            'sparse_rank': None,
            'dense_score': 0.0,
            'sparse_score': 0.0,
            'data': None
        })

        # Process dense results
        for rank, result in enumerate(dense_results, start=1):
            doc_id = result['id']
            rrf_score = self.dense_weight / (self.rrf_k + rank)

            doc_scores[doc_id]['rrf_score'] += rrf_score
            doc_scores[doc_id]['dense_rank'] = rank
            doc_scores[doc_id]['dense_score'] = result.get('score', 0.0)
            doc_scores[doc_id]['data'] = result

        # Process sparse results
        for rank, result in enumerate(sparse_results, start=1):
            doc_id = result['id']
            rrf_score = self.sparse_weight / (self.rrf_k + rank)

            doc_scores[doc_id]['rrf_score'] += rrf_score
            doc_scores[doc_id]['sparse_rank'] = rank
            doc_scores[doc_id]['sparse_score'] = result.get('score', 0.0)

            # Use sparse result data if not already set
            if doc_scores[doc_id]['data'] is None:
                doc_scores[doc_id]['data'] = result

        # Convert to list and sort by RRF score
        fused_results = []
        for doc_id, scores in doc_scores.items():
            result = scores['data'].copy()
            result['rrf_score'] = scores['rrf_score']
            result['dense_rank'] = scores['dense_rank']
            result['sparse_rank'] = scores['sparse_rank']
            result['dense_score'] = scores['dense_score']
            result['sparse_score'] = scores['sparse_score']
            fused_results.append(result)

        # Sort by RRF score descending
        fused_results.sort(key=lambda x: x['rrf_score'], reverse=True)

        return fused_results[:top_k]

    def _apply_reranking(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Apply cross-encoder reranking to results

        Args:
            query: Search query
            results: Results to rerank
            top_k: Number of results to return

        Returns:
            Reranked results
        """
        if not results:
            return []

        try:
            # Rerank using cross-encoder
            reranked = self.reranker_service.rerank_results(
                query=query,
                search_results=results,
                content_field='content',
                top_k=top_k
            )

            return reranked

        except Exception as e:
            logger.error(f"Reranking failed: {e}, returning RRF results")
            return results[:top_k]

    async def batch_search(
        self,
        collection_name: str,
        queries: List[str],
        top_k: int = 10,
        use_reranking: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        Batch hybrid search for multiple queries

        Args:
            collection_name: Collection to search
            queries: List of search queries
            top_k: Number of results per query
            use_reranking: Whether to apply reranking

        Returns:
            List of search results for each query
        """
        tasks = [
            self.search(
                collection_name=collection_name,
                query=query,
                top_k=top_k,
                use_reranking=use_reranking
            )
            for query in queries
        ]

        results = await asyncio.gather(*tasks)
        return list(results)

    def get_search_stats(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get statistics about search results

        Args:
            results: Search results

        Returns:
            Statistics dictionary
        """
        if not results:
            return {
                'total_results': 0,
                'avg_rrf_score': 0.0,
                'avg_rerank_score': 0.0,
                'dense_only': 0,
                'sparse_only': 0,
                'both': 0
            }

        dense_only = sum(1 for r in results if r.get('dense_rank') and not r.get('sparse_rank'))
        sparse_only = sum(1 for r in results if r.get('sparse_rank') and not r.get('dense_rank'))
        both = sum(1 for r in results if r.get('dense_rank') and r.get('sparse_rank'))

        avg_rrf = sum(r.get('rrf_score', 0.0) for r in results) / len(results)
        avg_rerank = sum(r.get('rerank_score', 0.0) for r in results) / len(results) if any('rerank_score' in r for r in results) else 0.0

        return {
            'total_results': len(results),
            'avg_rrf_score': avg_rrf,
            'avg_rerank_score': avg_rerank,
            'dense_only': dense_only,
            'sparse_only': sparse_only,
            'both': both
        }
