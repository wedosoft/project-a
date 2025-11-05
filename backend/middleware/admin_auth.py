"""
Admin API Authentication

Simple API Key authentication for administrative endpoints.

Author: AI Assistant POC
Date: 2025-11-05
"""

from fastapi import HTTPException, Header, status, Depends
from typing import Annotated
import logging

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def verify_admin_key(
    api_key: Annotated[str, Header(alias="X-Admin-API-Key")]
) -> bool:
    """
    Verify admin API key from request headers.

    Args:
        api_key: API key from X-Admin-API-Key header

    Returns:
        True if valid

    Raises:
        HTTPException: If key invalid or missing

    Example:
        >>> from fastapi import APIRouter, Depends
        >>> router = APIRouter(dependencies=[Depends(verify_admin_key)])
        >>> @router.get("/admin/tenants")
        ... def list_tenants():
        ...     return {"tenants": [...]}
    """
    if not api_key:
        logger.warning("Admin API request missing API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    admin_api_key = settings.admin_api_key

    if not admin_api_key:
        logger.error(
            "ADMIN_API_KEY not configured! Admin endpoints are INSECURE."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin authentication not configured"
        )

    # Constant-time comparison to prevent timing attacks
    import hmac
    if not hmac.compare_digest(api_key, admin_api_key):
        logger.warning(
            f"Invalid admin API key attempt: {api_key[:10]}..."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key"
        )

    logger.debug("Admin API key validated successfully")
    return True


def verify_admin_key_optional(
    api_key: Annotated[str | None, Header(alias="X-Admin-API-Key")] = None
) -> bool:
    """
    Optional admin key verification.

    Args:
        api_key: Optional API key from header

    Returns:
        True if key provided and valid, False if not provided

    Raises:
        HTTPException: If key provided but invalid
    """
    if not api_key:
        return False

    return verify_admin_key(api_key)


class AdminAuthMiddleware:
    """
    Middleware for protecting admin routes.

    Usage:
        >>> app.middleware("http")(AdminAuthMiddleware(
        ...     admin_paths=["/api/v1/admin"]
        ... ))
    """

    def __init__(self, admin_paths: list[str] = None):
        """
        Initialize admin auth middleware.

        Args:
            admin_paths: List of path prefixes requiring admin auth
        """
        self.admin_paths = admin_paths or ["/api/v1/admin"]

    async def __call__(self, request, call_next):
        """Process request with admin auth check."""
        # Check if this is an admin path
        if not self._is_admin_path(request.url.path):
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-Admin-API-Key")

        try:
            verify_admin_key(api_key)
            return await call_next(request)
        except HTTPException:
            # Re-raise authentication errors
            raise

    def _is_admin_path(self, path: str) -> bool:
        """Check if path requires admin authentication."""
        return any(path.startswith(prefix) for prefix in self.admin_paths)


def get_admin_headers(api_key: str = None) -> dict:
    """
    Create headers for admin API requests.

    Args:
        api_key: Admin API key (uses env default if not provided)

    Returns:
        Dictionary of headers

    Example:
        >>> headers = get_admin_headers()
        >>> requests.post('/api/v1/admin/tenants', headers=headers, json=...)
    """
    key = api_key or settings.admin_api_key

    if not key:
        raise ValueError("Admin API key not configured")

    return {
        'X-Admin-API-Key': key,
        'Content-Type': 'application/json'
    }


def create_admin_middleware(app):
    """
    Attach admin auth middleware to FastAPI app.

    Args:
        app: FastAPI application instance

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> create_admin_middleware(app)
    """
    if not settings.admin_api_key:
        logger.warning(
            "ADMIN_API_KEY not set! Admin endpoints are INSECURE."
        )
        return None

    middleware = AdminAuthMiddleware(admin_paths=["/api/v1/admin"])
    app.middleware("http")(middleware)

    logger.info("Admin authentication middleware enabled")
    return middleware


# Quick test
if __name__ == "__main__":
    # Test headers generation
    try:
        headers = get_admin_headers("test-admin-key-123")
        print("Admin API Headers:")
        for key, value in headers.items():
            print(f"  {key}: {value}")
    except ValueError as e:
        print(f"Error: {e}")
