"""
Logging Middleware - Request/Response logging
"""
import time
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests and responses

    Logs:
    - Request method, path, headers
    - Response status code, duration
    - Errors if any
    """

    async def dispatch(self, request: Request, call_next: Callable):
        """Process and log request/response"""

        # Skip logging for health checks (too noisy)
        if request.url.path == "/api/health":
            return await call_next(request)

        # Start timer
        start_time = time.time()

        # Extract request info
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        client_host = request.client.host if request.client else "unknown"

        # Log request
        logger.info(
            f"→ {method} {path}",
            extra={
                "method": method,
                "path": path,
                "query_params": query_params,
                "client": client_host,
                "user_agent": request.headers.get("user-agent", "unknown")
            }
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time
            duration_ms = int(duration * 1000)

            # Log response
            logger.info(
                f"← {method} {path} {response.status_code} ({duration_ms}ms)",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms
                }
            )

            # Add duration header
            response.headers["X-Process-Time"] = str(duration_ms)

            return response

        except Exception as e:
            # Log error
            duration = time.time() - start_time
            duration_ms = int(duration * 1000)

            logger.error(
                f"✗ {method} {path} ERROR ({duration_ms}ms): {str(e)}",
                extra={
                    "method": method,
                    "path": path,
                    "error": str(e),
                    "duration_ms": duration_ms
                },
                exc_info=True
            )

            raise
