"""
BM25 Sparse Search Service using PostgreSQL pg_trgm

Features:
- PostgreSQL full-text search with pg_trgm extension
- BM25-like ranking with ts_rank_cd
- Document indexing with GIN indexes
- Efficient text search for Korean and English
"""
from typing import List, Dict, Any, Optional
import asyncpg
from backend.utils.logger import get_logger
from backend.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class SparseSearchService:
    """Service for BM25-like sparse search using PostgreSQL"""

    def __init__(
        self,
        db_host: Optional[str] = None,
        db_port: Optional[int] = None,
        db_name: Optional[str] = None,
        db_user: Optional[str] = None,
        db_password: Optional[str] = None
    ):
        """
        Initialize PostgreSQL connection parameters

        Args:
            db_host: Database host
            db_port: Database port
            db_name: Database name
            db_user: Database user
            db_password: Database password
        """
        self.db_host = db_host or settings.supabase_db_host
        self.db_port = db_port or settings.supabase_db_port
        self.db_name = db_name or settings.supabase_db_name
        self.db_user = db_user or settings.supabase_db_user
        self.db_password = db_password or settings.supabase_db_password

        self.pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                min_size=2,
                max_size=10
            )
            logger.info("PostgreSQL connection pool created")
        return self.pool

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed")

    async def initialize_search_schema(self) -> bool:
        """
        Initialize search schema with pg_trgm extension and indexes

        Returns:
            True if successful
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                # Enable pg_trgm extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                logger.info("pg_trgm extension enabled")

                # Create search_documents table if not exists
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_documents (
                        id TEXT PRIMARY KEY,
                        collection_name TEXT NOT NULL,
                        content TEXT NOT NULL,
                        content_tsvector tsvector GENERATED ALWAYS AS (
                            to_tsvector('simple', content)
                        ) STORED,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                logger.info("search_documents table created")

                # Create GIN index for full-text search
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_documents_tsvector
                    ON search_documents USING GIN (content_tsvector);
                """)

                # Create trigram index for similarity search
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_documents_trigram
                    ON search_documents USING GIN (content gin_trgm_ops);
                """)

                # Create index on collection_name for filtering
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_search_documents_collection
                    ON search_documents (collection_name);
                """)

                logger.info("Search indexes created successfully")
                return True

        except Exception as e:
            logger.error(f"Failed to initialize search schema: {e}")
            raise

    async def index_documents(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]]
    ) -> int:
        """
        Index documents for BM25 search

        Args:
            collection_name: Collection name (e.g., "issues", "kb_articles")
            documents: List of documents with structure:
                {
                    "id": str,
                    "content": str,
                    "metadata": dict (optional)
                }

        Returns:
            Number of documents indexed
        """
        pool = await self._get_pool()
        indexed_count = 0

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    for doc in documents:
                        doc_id = doc["id"]
                        content = doc["content"]
                        metadata = doc.get("metadata", {})

                        await conn.execute("""
                            INSERT INTO search_documents (id, collection_name, content, metadata)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (id) DO UPDATE
                            SET content = EXCLUDED.content,
                                metadata = EXCLUDED.metadata,
                                updated_at = NOW()
                        """, doc_id, collection_name, content, metadata)

                        indexed_count += 1

            logger.info(f"Indexed {indexed_count} documents to collection '{collection_name}'")
            return indexed_count

        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
            raise

    async def bm25_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        BM25-like search using PostgreSQL full-text search

        Args:
            collection_name: Collection to search
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of search results with id, score, content, and metadata
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                # Build query
                tsquery = query.replace(" ", " & ")

                # Base query with ts_rank_cd (BM25-like ranking)
                # Using 'simple' config for better multilingual support (Korean)
                sql = """
                    SELECT
                        id,
                        content,
                        metadata,
                        ts_rank_cd(content_tsvector, to_tsquery('simple', $1)) AS score
                    FROM search_documents
                    WHERE collection_name = $2
                      AND content_tsvector @@ to_tsquery('simple', $1)
                """

                params = [tsquery, collection_name]

                # Add metadata filters if provided
                if filters:
                    filter_conditions = []
                    for key, value in filters.items():
                        params.append(value)
                        filter_conditions.append(
                            f"metadata->>'{key}' = ${len(params)}"
                        )
                    sql += " AND " + " AND ".join(filter_conditions)

                sql += f" ORDER BY score DESC LIMIT {top_k}"

                # Execute search
                rows = await conn.fetch(sql, *params)

                # Format results
                results = [
                    {
                        "id": row["id"],
                        "score": float(row["score"]),
                        "content": row["content"],
                        "metadata": row["metadata"]
                    }
                    for row in rows
                ]

                logger.info(
                    f"BM25 search in '{collection_name}' for '{query}' "
                    f"returned {len(results)} results"
                )
                return results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            raise

    async def similarity_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Trigram similarity search (fuzzy matching)

        Args:
            collection_name: Collection to search
            query: Search query
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of search results with similarity scores
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        id,
                        content,
                        metadata,
                        similarity(content, $1) AS score
                    FROM search_documents
                    WHERE collection_name = $2
                      AND similarity(content, $1) > $3
                    ORDER BY score DESC
                    LIMIT $4
                """, query, collection_name, similarity_threshold, top_k)

                results = [
                    {
                        "id": row["id"],
                        "score": float(row["score"]),
                        "content": row["content"],
                        "metadata": row["metadata"]
                    }
                    for row in rows
                ]

                logger.info(
                    f"Similarity search in '{collection_name}' returned {len(results)} results"
                )
                return results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            raise

    async def delete_documents(
        self,
        collection_name: str,
        document_ids: Optional[List[str]] = None
    ) -> int:
        """
        Delete documents from collection

        Args:
            collection_name: Collection name
            document_ids: Optional list of document IDs to delete
                         If None, deletes all documents in collection

        Returns:
            Number of documents deleted
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                if document_ids:
                    result = await conn.execute("""
                        DELETE FROM search_documents
                        WHERE collection_name = $1 AND id = ANY($2)
                    """, collection_name, document_ids)
                else:
                    result = await conn.execute("""
                        DELETE FROM search_documents
                        WHERE collection_name = $1
                    """, collection_name)

                # Extract number from result string like "DELETE 5"
                deleted_count = int(result.split()[-1])
                logger.info(
                    f"Deleted {deleted_count} documents from '{collection_name}'"
                )
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise

    async def get_document_count(self, collection_name: str) -> int:
        """
        Get total number of documents in collection

        Args:
            collection_name: Collection name

        Returns:
            Document count
        """
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as count
                    FROM search_documents
                    WHERE collection_name = $1
                """, collection_name)

                count = row["count"]
                logger.info(f"Collection '{collection_name}' has {count} documents")
                return count

        except Exception as e:
            logger.error(f"Failed to get document count: {e}")
            raise
