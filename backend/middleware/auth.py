"""
HMAC Authentication Middleware

Validates request signatures from Freshdesk FDK frontend to prevent
unauthorized access and replay attacks.

Uses HMAC-SHA256 with timestamp-based message signing.

Author: AI Assistant POC
Date: 2025-11-05
"""

import hmac
import hashlib
import time
from typing import Callable
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
import logging

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class HMACAuthMiddleware:
    """
    Middleware for HMAC-SHA256 signature validation.

    Request Format:
        Headers:
            X-Timestamp: Unix timestamp (seconds)
            X-Signature: HMAC-SHA256 hex digest
            X-Tenant-ID: Tenant identifier
            X-Platform: Platform name (freshdesk, zendesk, etc.)

        Signature Calculation:
            message = "{timestamp}.{request_body}"
            signature = HMAC-SHA256(secret_key, message)
    """

    def __init__(
        self,
        secret_key: str,
        replay_window_seconds: int = 300,
        required_paths: list[str] = None
    ):
        """
        Initialize HMAC middleware.

        Args:
            secret_key: Shared secret key for HMAC
            replay_window_seconds: Max age for requests (default: 5 min)
            required_paths: Paths that require authentication
        """
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        self.replay_window = replay_window_seconds
        self.required_paths = required_paths or ["/api/v1/assist"]

    async def __call__(
        self,
        request: Request,
        call_next: Callable
    ):
        """
        Process request with HMAC validation.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from next handler or 401/403 error

        Raises:
            HTTPException: If signature invalid or request expired
        """
        # Check if this path requires authentication
        if not self._should_authenticate(request.url.path):
            return await call_next(request)

        try:
            # Extract headers
            timestamp = request.headers.get("X-Timestamp")
            signature = request.headers.get("X-Signature")

            if not timestamp or not signature:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authentication headers (X-Timestamp, X-Signature)"
                )

            # Read request body
            body = await request.body()

            # Validate signature
            if not self._verify_signature(body, timestamp, signature):
                logger.warning(
                    f"Invalid signature for {request.url.path} "
                    f"from {request.client.host}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid request signature"
                )

            # Signature valid, proceed
            return await call_next(request)

        except HTTPException:
            # Re-raise HTTP exceptions
            raise

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication error"}
            )

    def _should_authenticate(self, path: str) -> bool:
        """Check if path requires authentication."""
        return any(path.startswith(prefix) for prefix in self.required_paths)

    def _verify_signature(
        self,
        body: bytes,
        timestamp: str,
        signature: str
    ) -> bool:
        """
        Verify HMAC signature.

        Args:
            body: Request body bytes
            timestamp: Unix timestamp string
            signature: HMAC signature hex string

        Returns:
            True if signature valid and not expired

        Raises:
            HTTPException: If request expired
        """
        # Validate timestamp format
        try:
            request_time = int(timestamp)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid timestamp format"
            )

        # Check for replay attack
        current_time = int(time.time())
        time_diff = abs(current_time - request_time)

        if time_diff > self.replay_window:
            logger.warning(
                f"Request expired: {time_diff}s old (max: {self.replay_window}s)"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Request expired (age: {time_diff}s)"
            )

        # Compute expected signature
        message = f"{timestamp}.{body.decode('utf-8')}"
        expected_signature = hmac.new(
            self.secret_key,
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)


def create_hmac_middleware(app) -> HMACAuthMiddleware:
    """
    Create and attach HMAC middleware to FastAPI app.

    Args:
        app: FastAPI application instance

    Returns:
        Configured middleware instance

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> middleware = create_hmac_middleware(app)
    """
    secret_key = settings.fdk_signing_secret

    if not secret_key:
        logger.warning(
            "FDK_SIGNING_SECRET not set! HMAC authentication disabled."
        )
        # Return no-op middleware
        return None

    middleware = HMACAuthMiddleware(
        secret_key=secret_key,
        replay_window_seconds=300,
        required_paths=["/api/v1/assist"]
    )

    app.middleware("http")(middleware)

    logger.info("HMAC authentication middleware enabled")
    return middleware


# Helper functions for testing/development

def generate_signature(
    body: str,
    timestamp: int,
    secret_key: str
) -> str:
    """
    Generate HMAC signature for request.

    Args:
        body: Request body JSON string
        timestamp: Unix timestamp
        secret_key: Shared secret

    Returns:
        HMAC-SHA256 hex digest

    Example:
        >>> signature = generate_signature(
        ...     '{"ticket_id": "123"}',
        ...     1234567890,
        ...     'my-secret-key'
        ... )
    """
    message = f"{timestamp}.{body}"
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()


def create_signed_headers(
    body: str,
    secret_key: str,
    tenant_id: str,
    platform: str
) -> dict:
    """
    Create signed request headers for testing.

    Args:
        body: Request body JSON string
        secret_key: Shared secret
        tenant_id: Tenant identifier
        platform: Platform name

    Returns:
        Dictionary of headers with signature

    Example:
        >>> headers = create_signed_headers(
        ...     '{"ticket_id": "123"}',
        ...     'my-secret',
        ...     'demo-tenant',
        ...     'freshdesk'
        ... )
        >>> # Use in requests.post(..., headers=headers)
    """
    timestamp = int(time.time())
    signature = generate_signature(body, timestamp, secret_key)

    return {
        'X-Timestamp': str(timestamp),
        'X-Signature': signature,
        'X-Tenant-ID': tenant_id,
        'X-Platform': platform,
        'Content-Type': 'application/json'
    }


# Quick test
if __name__ == "__main__":
    # Test signature generation
    test_body = '{"ticket_id": "TKT-123", "stream_progress": true}'
    test_secret = "test-secret-key-change-in-production"
    test_timestamp = int(time.time())

    signature = generate_signature(test_body, test_timestamp, test_secret)

    print("HMAC Signature Test:")
    print(f"Timestamp: {test_timestamp}")
    print(f"Signature: {signature}")
    print(f"\nHeaders:")
    headers = create_signed_headers(
        test_body,
        test_secret,
        "demo-tenant",
        "freshdesk"
    )
    for key, value in headers.items():
        print(f"  {key}: {value}")
