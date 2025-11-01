"""
KB Repository for CRUD operations on kb_blocks table

Features:
- Full CRUD operations with Supabase
- Tenant isolation with RLS
- Batch operations for efficiency
- Query filtering by article_id
- Pagination support
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from backend.config import get_settings
from backend.models.schemas import KBBlock, KBBlockCreate
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class KBRepository:
    """Repository for kb_blocks table operations"""

    def __init__(self, supabase_client=None):
        """
        Initialize repository with Supabase client

        Args:
            supabase_client: Supabase client instance (uses default if None)
        """
        if supabase_client is None:
            from supabase import create_client
            self.client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key
            )
        else:
            self.client = supabase_client

        self.table_name = "kb_blocks"
        logger.info(f"KBRepository initialized for table: {self.table_name}")

    def create(
        self,
        tenant_id: str,
        kb_block: KBBlockCreate
    ) -> KBBlock:
        """
        Create a new KB block

        Args:
            tenant_id: Tenant ID for RLS
            kb_block: KB block data to create

        Returns:
            Created KBBlock
        """
        try:
            # Set tenant context for RLS
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            # Prepare data
            data = kb_block.model_dump(exclude_unset=True, by_alias=True)
            data['tenant_id'] = tenant_id

            # Insert
            response = self.client.table(self.table_name).insert(data).execute()

            if not response.data:
                raise ValueError("Failed to create KB block")

            result = KBBlock(**response.data[0])
            logger.info(f"Created KB block: {result.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to create KB block: {e}")
            raise

    def get_by_id(
        self,
        tenant_id: str,
        block_id: UUID
    ) -> Optional[KBBlock]:
        """
        Get KB block by ID

        Args:
            tenant_id: Tenant ID for RLS
            block_id: KB block UUID

        Returns:
            KBBlock if found, None otherwise
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .select("*")\
                .eq("id", str(block_id))\
                .execute()

            if not response.data:
                return None

            return KBBlock(**response.data[0])

        except Exception as e:
            logger.error(f"Failed to get KB block {block_id}: {e}")
            raise

    def get_by_article_id(
        self,
        tenant_id: str,
        article_id: str
    ) -> List[KBBlock]:
        """
        Get all KB blocks for an article

        Args:
            tenant_id: Tenant ID for RLS
            article_id: Article ID

        Returns:
            List of KBBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .select("*")\
                .eq("article_id", article_id)\
                .execute()

            return [KBBlock(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Failed to get KB blocks for article {article_id}: {e}")
            raise

    def list_blocks(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[KBBlock]:
        """
        List KB blocks with pagination

        Args:
            tenant_id: Tenant ID for RLS
            limit: Maximum results (default 100)
            offset: Offset for pagination (default 0)

        Returns:
            List of KBBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .select("*")\
                .range(offset, offset + limit - 1)\
                .execute()

            return [KBBlock(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Failed to list KB blocks: {e}")
            raise

    def search_by_intent(
        self,
        tenant_id: str,
        intent_keyword: str,
        limit: int = 20
    ) -> List[KBBlock]:
        """
        Search KB blocks by intent keyword

        Args:
            tenant_id: Tenant ID for RLS
            intent_keyword: Keyword to search in intent field
            limit: Maximum results (default 20)

        Returns:
            List of matching KBBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .select("*")\
                .ilike("intent", f"%{intent_keyword}%")\
                .limit(limit)\
                .execute()

            return [KBBlock(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Failed to search KB blocks by intent: {e}")
            raise

    def update(
        self,
        tenant_id: str,
        block_id: UUID,
        updates: Dict[str, Any]
    ) -> KBBlock:
        """
        Update a KB block

        Args:
            tenant_id: Tenant ID for RLS
            block_id: KB block UUID
            updates: Fields to update

        Returns:
            Updated KBBlock
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .update(updates)\
                .eq("id", str(block_id))\
                .execute()

            if not response.data:
                raise ValueError(f"KB block {block_id} not found")

            result = KBBlock(**response.data[0])
            logger.info(f"Updated KB block: {result.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to update KB block {block_id}: {e}")
            raise

    def delete(
        self,
        tenant_id: str,
        block_id: UUID
    ) -> bool:
        """
        Delete a KB block

        Args:
            tenant_id: Tenant ID for RLS
            block_id: KB block UUID

        Returns:
            True if deleted successfully
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .delete()\
                .eq("id", str(block_id))\
                .execute()

            logger.info(f"Deleted KB block: {block_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete KB block {block_id}: {e}")
            raise

    def batch_create(
        self,
        tenant_id: str,
        kb_blocks: List[KBBlockCreate]
    ) -> List[KBBlock]:
        """
        Create multiple KB blocks in batch

        Args:
            tenant_id: Tenant ID for RLS
            kb_blocks: List of KB blocks to create

        Returns:
            List of created KBBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            # Prepare data
            data = [
                {**block.model_dump(exclude_unset=True, by_alias=True), 'tenant_id': tenant_id}
                for block in kb_blocks
            ]

            # Batch insert
            response = self.client.table(self.table_name).insert(data).execute()

            results = [KBBlock(**item) for item in response.data]
            logger.info(f"Created {len(results)} KB blocks in batch")
            return results

        except Exception as e:
            logger.error(f"Failed to batch create KB blocks: {e}")
            raise

    def count(
        self,
        tenant_id: str
    ) -> int:
        """
        Count KB blocks

        Args:
            tenant_id: Tenant ID for RLS

        Returns:
            Count of blocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            response = self.client.table(self.table_name)\
                .select("*", count="exact")\
                .execute()

            return response.count or 0

        except Exception as e:
            logger.error(f"Failed to count KB blocks: {e}")
            raise
