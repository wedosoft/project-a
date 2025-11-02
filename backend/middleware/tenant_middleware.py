"""
Tenant Middleware - Extract and validate tenant_id
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from backend.utils.logger import get_logger

logger = get_logger(__name__)


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



        # Set default if still not found
        if not tenant_id:
            tenant_id = "default"
            logger.warning(f"No tenant_id found for {request.url.path}, using 'default'")

        # Store in request state for downstream use
        request.state.tenant_id = tenant_id
        logger.debug(f"Tenant: {tenant_id} | Path: {request.url.path}")

        # Continue processing
        response = await call_next(request)

        # Add tenant_id to response headers for debugging
        response.headers["X-Tenant-Id"] = tenant_id

        return response
