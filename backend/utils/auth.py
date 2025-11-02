"""
Authentication utilities
"""
from fastapi import Header, HTTPException, status
from typing import Optional
from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, description="API Key for authentication")
) -> str:
    """
    Verify API key from request headers

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        API key if valid

    Raises:
        HTTPException 401: If API key is missing or invalid
    """
    # For MVP, we'll use a simple API key check
    # In production, use proper JWT tokens or OAuth

    # Check if API key is provided
    if not x_api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header."
        )

    # For MVP: Accept any non-empty API key
    # TODO: Implement proper API key validation with database lookup
    # Expected API keys should be stored in environment or database

    # Simple validation: API key should be at least 32 characters
    if len(x_api_key) < 32:
        logger.warning("Invalid API key format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )

    logger.debug("API key verified")
    return x_api_key


async def verify_api_key_optional(
    x_api_key: Optional[str] = Header(None, description="API Key for authentication")
) -> Optional[str]:
    """
    Optional API key verification (allows requests without API key)

    Args:
        x_api_key: API key from X-API-Key header

    Returns:
        API key if provided, None otherwise
    """
    if not x_api_key:
        logger.debug("No API key provided (optional)")
        return None

    # Basic validation if key is provided
    if len(x_api_key) < 32:
        logger.warning(f"Invalid API key format: {x_api_key[:8]}...")
        return None

    logger.debug("API key verified (optional)")
    return x_api_key


def generate_api_key() -> str:
    """
    Generate a new API key

    Returns:
        Random API key string (64 characters)
    """
    import secrets
    return secrets.token_urlsafe(48)  # 48 bytes = 64 characters base64
