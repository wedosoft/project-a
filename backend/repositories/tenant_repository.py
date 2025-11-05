"""
Tenant Repository

Manages tenant configuration with caching and CRUD operations.

Author: AI Assistant POC
Date: 2025-11-05
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

from backend.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class TenantConfig(BaseModel):
    """Tenant configuration model."""
    id: str
    tenant_id: str
    platform: str
    embedding_enabled: bool = True
    analysis_depth: str = "full"  # full | summary | minimal
    llm_max_tokens: int = 1500
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantRepository(BaseRepository):
    """
    Repository for tenant configuration management.

    Features:
    - In-memory caching with TTL
    - CRUD operations
    - Default fallback values
    """

    def __init__(self, cache_ttl_seconds: int = 300):
        """
        Initialize repository with cache.

        Args:
            cache_ttl_seconds: Cache time-to-live in seconds (default: 5 min)
        """
        super().__init__()
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)

    def _get_cache_key(self, tenant_id: str, platform: str) -> str:
        """Generate cache key."""
        return f"{tenant_id}:{platform}"

    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        if 'timestamp' not in cache_entry:
            return False

        age = datetime.now() - cache_entry['timestamp']
        return age < self.cache_ttl

    def _set_cache(self, tenant_id: str, platform: str, config: TenantConfig):
        """Store config in cache."""
        cache_key = self._get_cache_key(tenant_id, platform)
        self.cache[cache_key] = {
            'config': config,
            'timestamp': datetime.now()
        }
        logger.debug(f"Cached config for {cache_key}")

    def _get_cache(
        self,
        tenant_id: str,
        platform: str
    ) -> Optional[TenantConfig]:
        """Retrieve config from cache if valid."""
        cache_key = self._get_cache_key(tenant_id, platform)
        cache_entry = self.cache.get(cache_key)

        if cache_entry and self._is_cache_valid(cache_entry):
            logger.debug(f"Cache hit for {cache_key}")
            return cache_entry['config']

        logger.debug(f"Cache miss for {cache_key}")
        return None

    def _invalidate_cache(self, tenant_id: str, platform: str):
        """Remove config from cache."""
        cache_key = self._get_cache_key(tenant_id, platform)
        if cache_key in self.cache:
            del self.cache[cache_key]
            logger.debug(f"Invalidated cache for {cache_key}")

    async def get_config(
        self,
        tenant_id: str,
        platform: str,
        use_cache: bool = True
    ) -> TenantConfig:
        """
        Get tenant configuration with caching.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name (freshdesk, zendesk, etc.)
            use_cache: Whether to use cache (default: True)

        Returns:
            TenantConfig with settings or defaults

        Example:
            >>> repo = TenantRepository()
            >>> config = await repo.get_config('demo-tenant', 'freshdesk')
            >>> config.embedding_enabled
            True
        """
        # Check cache first
        if use_cache:
            cached = self._get_cache(tenant_id, platform)
            if cached:
                return cached

        try:
            # Fetch from database
            result = self.client.table("tenant_configs").select("*").eq(
                "tenant_id", tenant_id
            ).eq("platform", platform).execute()

            if result.data and len(result.data) > 0:
                config = TenantConfig(**result.data[0])
                self._set_cache(tenant_id, platform, config)
                return config

            # No config found, return defaults
            logger.info(
                f"No config found for {tenant_id}:{platform}, using defaults"
            )
            return self._get_default_config(tenant_id, platform)

        except Exception as e:
            logger.error(f"Error fetching config: {e}")
            # Fallback to defaults on error
            return self._get_default_config(tenant_id, platform)

    def _get_default_config(
        self,
        tenant_id: str,
        platform: str
    ) -> TenantConfig:
        """
        Get default configuration.

        Returns:
            TenantConfig with default values
        """
        return TenantConfig(
            id="default",
            tenant_id=tenant_id,
            platform=platform,
            embedding_enabled=True,
            analysis_depth="full",
            llm_max_tokens=1500
        )

    async def create_config(
        self,
        tenant_id: str,
        platform: str,
        config_data: Dict[str, Any]
    ) -> TenantConfig:
        """
        Create new tenant configuration.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name
            config_data: Configuration values

        Returns:
            Created TenantConfig

        Raises:
            Exception: If creation fails or config already exists
        """
        try:
            data = {
                "tenant_id": tenant_id,
                "platform": platform,
                **config_data
            }

            result = self.client.table("tenant_configs").insert(
                data
            ).execute()

            if result.data and len(result.data) > 0:
                config = TenantConfig(**result.data[0])
                self._set_cache(tenant_id, platform, config)
                logger.info(f"Created config for {tenant_id}:{platform}")
                return config

            raise Exception("No data returned from insert")

        except Exception as e:
            self._handle_error(f"create_config({tenant_id}:{platform})", e)

    async def update_config(
        self,
        tenant_id: str,
        platform: str,
        updates: Dict[str, Any]
    ) -> TenantConfig:
        """
        Update tenant configuration.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name
            updates: Fields to update

        Returns:
            Updated TenantConfig

        Raises:
            Exception: If update fails
        """
        try:
            # Invalidate cache first
            self._invalidate_cache(tenant_id, platform)

            result = self.client.table("tenant_configs").update(
                updates
            ).eq("tenant_id", tenant_id).eq("platform", platform).execute()

            if result.data and len(result.data) > 0:
                config = TenantConfig(**result.data[0])
                self._set_cache(tenant_id, platform, config)
                logger.info(f"Updated config for {tenant_id}:{platform}")
                return config

            raise Exception("No data returned from update")

        except Exception as e:
            self._handle_error(f"update_config({tenant_id}:{platform})", e)

    async def delete_config(
        self,
        tenant_id: str,
        platform: str
    ) -> bool:
        """
        Delete tenant configuration.

        Args:
            tenant_id: Tenant identifier
            platform: Platform name

        Returns:
            True if deleted successfully

        Raises:
            Exception: If deletion fails
        """
        try:
            # Invalidate cache
            self._invalidate_cache(tenant_id, platform)

            result = self.client.table("tenant_configs").delete().eq(
                "tenant_id", tenant_id
            ).eq("platform", platform).execute()

            logger.info(f"Deleted config for {tenant_id}:{platform}")
            return True

        except Exception as e:
            self._handle_error(f"delete_config({tenant_id}:{platform})", e)

    async def list_configs(self, tenant_id: str) -> list[TenantConfig]:
        """
        List all configurations for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of TenantConfig objects
        """
        try:
            result = self.client.table("tenant_configs").select("*").eq(
                "tenant_id", tenant_id
            ).execute()

            if result.data:
                return [TenantConfig(**item) for item in result.data]

            return []

        except Exception as e:
            logger.error(f"Error listing configs: {e}")
            return []

    def clear_cache(self):
        """Clear all cached configurations."""
        self.cache.clear()
        logger.info("Cleared tenant config cache")
