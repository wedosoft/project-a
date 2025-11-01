"""
Issue Repository for CRUD operations on issue_blocks table

Features:
- Full CRUD operations with Supabase
- Tenant isolation with RLS
- Batch operations for efficiency
- Query filtering by product, component, block_type
- Pagination support
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from backend.config import get_settings
from backend.models.schemas import IssueBlock, IssueBlockCreate, BlockType
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class IssueRepository:
    """Repository for issue_blocks table operations"""

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

        self.table_name = "issue_blocks"
        logger.info(f"IssueRepository initialized for table: {self.table_name}")

    def create(
        self,
        tenant_id: str,
        issue_block: IssueBlockCreate
    ) -> IssueBlock:
        """
        Create a new issue block

        Args:
            tenant_id: Tenant ID for RLS
            issue_block: Issue block data to create

        Returns:
            Created IssueBlock
        """
        try:
            # Set tenant context for RLS
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            # Prepare data
            data = issue_block.model_dump(exclude_unset=True)
            data['tenant_id'] = tenant_id

            # Insert
            response = self.client.table(self.table_name).insert(data).execute()

            if not response.data:
                raise ValueError("Failed to create issue block")

            result = IssueBlock(**response.data[0])
            logger.info(f"Created issue block: {result.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to create issue block: {e}")
            raise

    def get_by_id(
        self,
        tenant_id: str,
        block_id: UUID
    ) -> Optional[IssueBlock]:
        """
        Get issue block by ID

        Args:
            tenant_id: Tenant ID for RLS
            block_id: Issue block UUID

        Returns:
            IssueBlock if found, None otherwise
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

            return IssueBlock(**response.data[0])

        except Exception as e:
            logger.error(f"Failed to get issue block {block_id}: {e}")
            raise

    def get_by_ticket_id(
        self,
        tenant_id: str,
        ticket_id: str,
        block_type: Optional[BlockType] = None
    ) -> List[IssueBlock]:
        """
        Get all issue blocks for a ticket

        Args:
            tenant_id: Tenant ID for RLS
            ticket_id: Ticket ID
            block_type: Optional filter by block type

        Returns:
            List of IssueBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            query = self.client.table(self.table_name)\
                .select("*")\
                .eq("ticket_id", ticket_id)

            if block_type:
                query = query.eq("block_type", block_type.value)

            response = query.execute()

            return [IssueBlock(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Failed to get issue blocks for ticket {ticket_id}: {e}")
            raise

    def list_blocks(
        self,
        tenant_id: str,
        product: Optional[str] = None,
        component: Optional[str] = None,
        block_type: Optional[BlockType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[IssueBlock]:
        """
        List issue blocks with optional filters

        Args:
            tenant_id: Tenant ID for RLS
            product: Optional product filter
            component: Optional component filter
            block_type: Optional block type filter
            limit: Maximum results (default 100)
            offset: Offset for pagination (default 0)

        Returns:
            List of IssueBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            query = self.client.table(self.table_name).select("*")

            if product:
                query = query.eq("product", product)
            if component:
                query = query.eq("component", component)
            if block_type:
                query = query.eq("block_type", block_type.value)

            response = query.range(offset, offset + limit - 1).execute()

            return [IssueBlock(**item) for item in response.data]

        except Exception as e:
            logger.error(f"Failed to list issue blocks: {e}")
            raise

    def update(
        self,
        tenant_id: str,
        block_id: UUID,
        updates: Dict[str, Any]
    ) -> IssueBlock:
        """
        Update an issue block

        Args:
            tenant_id: Tenant ID for RLS
            block_id: Issue block UUID
            updates: Fields to update

        Returns:
            Updated IssueBlock
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
                raise ValueError(f"Issue block {block_id} not found")

            result = IssueBlock(**response.data[0])
            logger.info(f"Updated issue block: {result.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to update issue block {block_id}: {e}")
            raise

    def delete(
        self,
        tenant_id: str,
        block_id: UUID
    ) -> bool:
        """
        Delete an issue block

        Args:
            tenant_id: Tenant ID for RLS
            block_id: Issue block UUID

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

            logger.info(f"Deleted issue block: {block_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete issue block {block_id}: {e}")
            raise

    def batch_create(
        self,
        tenant_id: str,
        issue_blocks: List[IssueBlockCreate]
    ) -> List[IssueBlock]:
        """
        Create multiple issue blocks in batch

        Args:
            tenant_id: Tenant ID for RLS
            issue_blocks: List of issue blocks to create

        Returns:
            List of created IssueBlocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            # Prepare data
            data = [
                {**block.model_dump(exclude_unset=True), 'tenant_id': tenant_id}
                for block in issue_blocks
            ]

            # Batch insert
            response = self.client.table(self.table_name).insert(data).execute()

            results = [IssueBlock(**item) for item in response.data]
            logger.info(f"Created {len(results)} issue blocks in batch")
            return results

        except Exception as e:
            logger.error(f"Failed to batch create issue blocks: {e}")
            raise

    def count(
        self,
        tenant_id: str,
        product: Optional[str] = None,
        component: Optional[str] = None,
        block_type: Optional[BlockType] = None
    ) -> int:
        """
        Count issue blocks with optional filters

        Args:
            tenant_id: Tenant ID for RLS
            product: Optional product filter
            component: Optional component filter
            block_type: Optional block type filter

        Returns:
            Count of matching blocks
        """
        try:
            # Set tenant context
            self.client.rpc('set_config', {
                'key': 'app.current_tenant_id',
                'value': tenant_id
            }).execute()

            query = self.client.table(self.table_name)\
                .select("*", count="exact")

            if product:
                query = query.eq("product", product)
            if component:
                query = query.eq("component", component)
            if block_type:
                query = query.eq("block_type", block_type.value)

            response = query.execute()

            return response.count or 0

        except Exception as e:
            logger.error(f"Failed to count issue blocks: {e}")
            raise
