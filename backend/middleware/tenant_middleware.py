"""
Tenant Middleware - Extract and validate tenant_id
"""
import json
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from backend.utils.logger import get_logger
from backend.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and validate tenant_id from requests

    Extracts tenant_id from:
    1. Header: X-Tenant-Id
    2. Query parameter: tenant_id
    3. Request body: ticket_meta.tenant_id (for JSON payloads)

    Sets tenant_id in request.state for downstream use
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and extract tenant_id"""

        # Skip tenant validation for health/docs endpoints
        if request.url.path in ["/api/health", "/api/health/dependencies", "/docs", "/openapi.json", "/redoc"]:
            return await call_next(request)

        tenant_id = None

        # 1. Try to get from header
        tenant_id = request.headers.get("X-Tenant-Id")

        # 2. Try to get from query parameter
        if not tenant_id:
            tenant_id = request.query_params.get("tenant_id")

        # 3. Try to get from JSON body without consuming it downstream
        if not tenant_id and request.headers.get("content-type", "").startswith("application/json"):
            body_bytes = await request.body()
            if body_bytes:
                try:
                    payload = json.loads(body_bytes)
                    tenant_id = payload.get("tenant_id")
                    if not tenant_id:
                        tenant_meta = payload.get("ticket_meta") or {}
                        tenant_id = tenant_meta.get("tenant_id")
                except json.JSONDecodeError:
                    logger.debug("Failed to decode request body for tenant_id extraction")
            # Restore body for downstream handlers
            request._body = body_bytes

        # 4. SECURITY: Require tenant_id for all requests (strict in non-dev)
        if not tenant_id:
            if settings.fastapi_env.lower() == "development":
                tenant_id = "default"
                logger.warning(
                    "Missing tenant_id for %s, falling back to 'default' in development mode",
                    request.url.path
                )
            else:
                logger.error(f"Missing tenant_id for {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing tenant_id. Provide X-Tenant-Id header or tenant_id query parameter."
                )

        # 5. Validate tenant_id format (alphanumeric, hyphens, underscores only)
        if tenant_id and not all(c.isalnum() or c in ['-', '_'] for c in tenant_id):
            logger.error(f"Invalid tenant_id format: {tenant_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tenant_id format. Use alphanumeric characters, hyphens, or underscores only."
            )

        # Store in request state for downstream use
        request.state.tenant_id = tenant_id
        logger.debug(f"Tenant: {tenant_id} | Path: {request.url.path}")

        # Continue processing
        response = await call_next(request)

        # Add tenant_id to response headers for debugging
        response.headers["X-Tenant-Id"] = tenant_id

        return response
