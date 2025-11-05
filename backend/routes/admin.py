"""
Admin API Routes

Administrative endpoints for tenant management and configuration.

Requires admin API key authentication.

Author: AI Assistant POC
Date: 2025-11-05
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from backend.middleware.admin_auth import verify_admin_key
from backend.repositories.tenant_repository import TenantRepository, TenantConfig
from backend.repositories.proposal_repository import ProposalRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_key)]  # Apply to all routes
)

# Initialize repositories
tenant_repo = TenantRepository()
proposal_repo = ProposalRepository()


# Request/Response Models

class TenantConfigCreate(BaseModel):
    """Request model for creating tenant config."""
    tenant_id: str
    platform: str
    embedding_enabled: bool = True
    analysis_depth: str = "full"
    llm_max_tokens: int = 1500


class TenantConfigUpdate(BaseModel):
    """Request model for updating tenant config."""
    embedding_enabled: Optional[bool] = None
    analysis_depth: Optional[str] = None
    llm_max_tokens: Optional[int] = None


# Routes

@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(config: TenantConfigCreate):
    """
    Create new tenant configuration.

    Args:
        config: Tenant configuration data

    Returns:
        Created tenant configuration

    Example:
        >>> POST /api/v1/admin/tenants
        >>> Headers: X-Admin-API-Key: admin-secret
        >>> {
        ...     "tenant_id": "new-tenant",
        ...     "platform": "freshdesk",
        ...     "embedding_enabled": true,
        ...     "analysis_depth": "full",
        ...     "llm_max_tokens": 2000
        ... }
    """
    try:
        # Check if config already exists
        existing = await tenant_repo.get_config(
            config.tenant_id,
            config.platform,
            use_cache=False
        )

        if existing and existing.id != "default":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Config for {config.tenant_id}:{config.platform} already exists"
            )

        # Create config
        tenant_config = await tenant_repo.create_config(
            tenant_id=config.tenant_id,
            platform=config.platform,
            config_data={
                "embedding_enabled": config.embedding_enabled,
                "analysis_depth": config.analysis_depth,
                "llm_max_tokens": config.llm_max_tokens
            }
        )

        logger.info(f"Created tenant config: {config.tenant_id}:{config.platform}")

        return {
            "status": "created",
            "config": tenant_config.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tenants/{tenant_id}")
async def get_tenant(tenant_id: str, platform: str = "freshdesk"):
    """
    Get tenant configuration.

    Args:
        tenant_id: Tenant identifier
        platform: Platform name (default: freshdesk)

    Returns:
        Tenant configuration

    Example:
        >>> GET /api/v1/admin/tenants/demo-tenant?platform=freshdesk
        >>> Headers: X-Admin-API-Key: admin-secret
    """
    try:
        config = await tenant_repo.get_config(
            tenant_id,
            platform,
            use_cache=False  # Always fetch fresh for admin
        )

        return {
            "config": config.dict(),
            "is_default": config.id == "default"
        }

    except Exception as e:
        logger.error(f"Error fetching tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tenants/{tenant_id}/all")
async def list_tenant_configs(tenant_id: str):
    """
    List all platform configurations for a tenant.

    Args:
        tenant_id: Tenant identifier

    Returns:
        List of configurations across all platforms
    """
    try:
        configs = await tenant_repo.list_configs(tenant_id)

        return {
            "tenant_id": tenant_id,
            "configs": [config.dict() for config in configs],
            "count": len(configs)
        }

    except Exception as e:
        logger.error(f"Error listing configs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    updates: TenantConfigUpdate,
    platform: str = "freshdesk"
):
    """
    Update tenant configuration.

    Args:
        tenant_id: Tenant identifier
        updates: Configuration updates
        platform: Platform name

    Returns:
        Updated configuration

    Example:
        >>> PUT /api/v1/admin/tenants/demo-tenant?platform=freshdesk
        >>> Headers: X-Admin-API-Key: admin-secret
        >>> {
        ...     "embedding_enabled": false,
        ...     "llm_max_tokens": 3000
        ... }
    """
    try:
        # Only include non-None fields
        update_data = {
            k: v for k, v in updates.dict().items() if v is not None
        }

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update fields provided"
            )

        updated_config = await tenant_repo.update_config(
            tenant_id,
            platform,
            update_data
        )

        logger.info(f"Updated tenant config: {tenant_id}:{platform}")

        return {
            "status": "updated",
            "config": updated_config.dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, platform: str = "freshdesk"):
    """
    Delete tenant configuration.

    Args:
        tenant_id: Tenant identifier
        platform: Platform name

    Returns:
        Deletion confirmation

    Example:
        >>> DELETE /api/v1/admin/tenants/demo-tenant?platform=freshdesk
        >>> Headers: X-Admin-API-Key: admin-secret
    """
    try:
        await tenant_repo.delete_config(tenant_id, platform)

        logger.info(f"Deleted tenant config: {tenant_id}:{platform}")

        return {
            "status": "deleted",
            "tenant_id": tenant_id,
            "platform": platform
        }

    except Exception as e:
        logger.error(f"Error deleting tenant: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/tenants/{tenant_id}/stats")
async def get_tenant_stats(tenant_id: str):
    """
    Get proposal statistics for tenant.

    Args:
        tenant_id: Tenant identifier

    Returns:
        Statistics including approval rates, counts, etc.

    Example:
        >>> GET /api/v1/admin/tenants/demo-tenant/stats
        >>> Headers: X-Admin-API-Key: admin-secret
    """
    try:
        await proposal_repo.set_tenant_context(tenant_id)
        stats = await proposal_repo.get_stats(tenant_id)

        return {
            "tenant_id": tenant_id,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear tenant configuration cache.

    Returns:
        Cache clear confirmation

    Example:
        >>> POST /api/v1/admin/cache/clear
        >>> Headers: X-Admin-API-Key: admin-secret
    """
    try:
        tenant_repo.clear_cache()
        logger.info("Cleared tenant config cache via admin API")

        return {
            "status": "cache_cleared",
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


import time
