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
    # Check if API key is provided
    if not x_api_key:
        logger.warning("Missing API key in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header."
        )

    # Validate API key format (minimum length)
    if len(x_api_key) < 32:
        logger.warning("Invalid API key format: too short")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )

    # SECURITY: Verify against configured API keys
    # Expected API keys should be stored in environment variable (comma-separated)
    # Example: ALLOWED_API_KEYS="key1,key2,key3"
    allowed_keys_str = settings.allowed_api_keys if hasattr(settings, 'allowed_api_keys') else None

    if allowed_keys_str:
        allowed_keys = [k.strip() for k in allowed_keys_str.split(',')]
        if x_api_key not in allowed_keys:
            logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
    else:
        # DEVELOPMENT MODE: If no allowed keys configured, just validate format
        # TODO: In production, this should fail if ALLOWED_API_KEYS is not set
        logger.warning(
            "ALLOWED_API_KEYS not configured. "
            "API key validation is bypassed for development. "
            "Set ALLOWED_API_KEYS environment variable in production!"
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
