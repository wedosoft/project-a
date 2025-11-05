"""
Base Repository with RLS Support

Provides foundation for tenant-scoped database operations
with Row-Level Security (RLS) context management.

Author: AI Assistant POC
Date: 2025-11-05
"""

from supabase import create_client, Client
from backend.config import get_settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseRepository:
    """
    Base repository class with RLS tenant context support.

    All repositories should inherit from this class to ensure
    proper tenant isolation via RLS policies.
    """

    def __init__(self):
        """Initialize Supabase client."""
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self._current_tenant_id: Optional[str] = None

    async def set_tenant_context(self, tenant_id: str) -> None:
        """
        Set RLS tenant context for all queries in this session.

        This calls the set_current_tenant() PostgreSQL function
        which sets app.current_tenant_id session variable.

        Args:
            tenant_id: Tenant identifier for RLS filtering

        Raises:
            Exception: If setting context fails
        """
        try:
            result = self.client.rpc(
                'set_current_tenant',
                {'tenant_id_param': tenant_id}
            ).execute()

            self._current_tenant_id = tenant_id
            logger.debug(f"Set tenant context to: {tenant_id}")

        except Exception as e:
            logger.error(f"Failed to set tenant context: {e}")
            raise

    async def get_current_tenant(self) -> Optional[str]:
        """
        Get current tenant context from session.

        Returns:
            Current tenant_id or None if not set
        """
        try:
            result = self.client.rpc('get_current_tenant').execute()
            return result.data if result.data else self._current_tenant_id
        except Exception as e:
            logger.warning(f"Could not get current tenant: {e}")
            return self._current_tenant_id

    def with_tenant(self, tenant_id: str):
        """
        Context manager for tenant-scoped operations.

        Usage:
            async with repo.with_tenant('tenant-123'):
                config = await repo.get_config()

        Args:
            tenant_id: Tenant identifier

        Returns:
            Self for chaining
        """
        class TenantContext:
            def __init__(self, repository, tenant_id):
                self.repository = repository
                self.tenant_id = tenant_id
                self.previous_tenant = None

            async def __aenter__(self):
                self.previous_tenant = self.repository._current_tenant_id
                await self.repository.set_tenant_context(self.tenant_id)
                return self.repository

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                if self.previous_tenant:
                    await self.repository.set_tenant_context(self.previous_tenant)
                else:
                    self.repository._current_tenant_id = None

        return TenantContext(self, tenant_id)

    def _handle_error(self, operation: str, error: Exception):
        """
        Centralized error handling for repository operations.

        Args:
            operation: Description of failed operation
            error: Exception that occurred

        Raises:
            Re-raises exception after logging
        """
        logger.error(f"Repository error during {operation}: {error}")
        raise

    def _validate_tenant_set(self):
        """
        Validate that tenant context is set before operations.

        Raises:
            ValueError: If tenant context not set
        """
        if not self._current_tenant_id:
            raise ValueError(
                "Tenant context not set. Call set_tenant_context() first."
            )
