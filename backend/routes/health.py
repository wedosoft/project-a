"""
Health check endpoints with comprehensive dependency monitoring

Provides two endpoints:
- GET /api/v1/health - Basic health check
- GET /api/v1/health/dependencies - Detailed dependency status check
"""
import time
from datetime import datetime
from typing import Dict, Optional
from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from supabase import create_client
import httpx
import asyncio

from backend.config import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["health"])

# Application start time for uptime calculation
APP_START_TIME = time.time()

# Cache for dependency check results (30 seconds TTL)
_dependency_cache: Optional[Dict] = None
_cache_timestamp: float = 0.0
CACHE_TTL_SECONDS = 30.0


# ============================================================================
# Pydantic Models
# ============================================================================

class HealthResponse(BaseModel):
    """Basic health check response"""
    status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(..., description="Application uptime in seconds")


class DependencyStatus(BaseModel):
    """Status of a single dependency"""
    name: str = Field(..., description="Dependency name")
    status: str = Field(..., description="Status: healthy, degraded, unhealthy")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")


class DependencyHealth(BaseModel):
    """Comprehensive dependency health check response"""
    overall_status: str = Field(..., description="Overall status: healthy, degraded, unhealthy")
    dependencies: Dict[str, DependencyStatus] = Field(..., description="Individual dependency statuses")
    checked_at: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")


# ============================================================================
# Dependency Check Functions
# ============================================================================

async def check_supabase() -> DependencyStatus:
    """
    Check Supabase database connectivity

    Returns:
        DependencyStatus with health information
    """
    try:
        start = time.time()

        # Create client
        client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

        # Try a simple query with timeout
        result = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: client.table("approval_logs").select("id").limit(1).execute()
            ),
            timeout=5.0
        )

        latency = (time.time() - start) * 1000

        return DependencyStatus(
            name="supabase",
            status="healthy",
            latency_ms=round(latency, 2)
        )

    except asyncio.TimeoutError:
        logger.error("Supabase health check timed out")
        return DependencyStatus(
            name="supabase",
            status="unhealthy",
            error_message="Request timed out after 5 seconds"
        )
    except Exception as e:
        logger.error(f"Supabase health check failed: {e}")
        return DependencyStatus(
            name="supabase",
            status="unhealthy",
            error_message=str(e)
        )


async def check_google_api() -> DependencyStatus:
    """
    Check Google Gemini API connectivity

    Returns:
        DependencyStatus with health information
    """
    try:
        if not settings.gemini_api_key:
            return DependencyStatus(
                name="google_api",
                status="degraded",
                error_message="API key not configured"
            )

        start = time.time()

        # Use httpx for async HTTP request
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1/models",
                params={"key": settings.gemini_api_key}
            )
            response.raise_for_status()

        latency = (time.time() - start) * 1000

        return DependencyStatus(
            name="google_api",
            status="healthy",
            latency_ms=round(latency, 2)
        )

    except httpx.TimeoutException:
        logger.error("Google API health check timed out")
        return DependencyStatus(
            name="google_api",
            status="unhealthy",
            error_message="Request timed out after 5 seconds"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Google API health check failed: {e}")
        return DependencyStatus(
            name="google_api",
            status="unhealthy",
            error_message=f"HTTP {e.response.status_code}: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Google API health check failed: {e}")
        return DependencyStatus(
            name="google_api",
            status="unhealthy",
            error_message=str(e)
        )


async def check_openai_api() -> DependencyStatus:
    """
    Check OpenAI API connectivity

    Returns:
        DependencyStatus with health information
    """
    try:
        if not settings.openai_api_key:
            return DependencyStatus(
                name="openai_api",
                status="degraded",
                error_message="API key not configured"
            )

        start = time.time()

        # Use httpx for async HTTP request
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"}
            )
            response.raise_for_status()

        latency = (time.time() - start) * 1000

        return DependencyStatus(
            name="openai_api",
            status="healthy",
            latency_ms=round(latency, 2)
        )

    except httpx.TimeoutException:
        logger.error("OpenAI API health check timed out")
        return DependencyStatus(
            name="openai_api",
            status="unhealthy",
            error_message="Request timed out after 5 seconds"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI API health check failed: {e}")
        return DependencyStatus(
            name="openai_api",
            status="unhealthy",
            error_message=f"HTTP {e.response.status_code}: {str(e)}"
        )
    except Exception as e:
        logger.error(f"OpenAI API health check failed: {e}")
        return DependencyStatus(
            name="openai_api",
            status="unhealthy",
            error_message=str(e)
        )


async def check_freshdesk_api() -> DependencyStatus:
    """
    Check Freshdesk API connectivity

    Returns:
        DependencyStatus with health information
    """
    try:
        if not settings.freshdesk_domain or not settings.freshdesk_api_key:
            return DependencyStatus(
                name="freshdesk_api",
                status="degraded",
                error_message="API credentials not configured"
            )

        start = time.time()

        # Use httpx for async HTTP request
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"https://{settings.freshdesk_domain}/api/v2/tickets",
                auth=(settings.freshdesk_api_key, "X"),
                params={"per_page": 1}
            )
            response.raise_for_status()

        latency = (time.time() - start) * 1000

        return DependencyStatus(
            name="freshdesk_api",
            status="healthy",
            latency_ms=round(latency, 2)
        )

    except httpx.TimeoutException:
        logger.error("Freshdesk API health check timed out")
        return DependencyStatus(
            name="freshdesk_api",
            status="unhealthy",
            error_message="Request timed out after 5 seconds"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Freshdesk API health check failed: {e}")
        return DependencyStatus(
            name="freshdesk_api",
            status="unhealthy",
            error_message=f"HTTP {e.response.status_code}: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Freshdesk API health check failed: {e}")
        return DependencyStatus(
            name="freshdesk_api",
            status="unhealthy",
            error_message=str(e)
        )


async def check_all_dependencies() -> Dict[str, DependencyStatus]:
    """
    Check all external dependencies in parallel

    Returns:
        Dictionary mapping dependency names to their status
    """
    # Run all checks in parallel
    results = await asyncio.gather(
        check_supabase(),
        check_google_api(),
        check_openai_api(),
        check_freshdesk_api(),
        return_exceptions=True
    )

    # Map results to dependency names
    dependencies = {}
    dep_names = ["supabase", "google_api", "openai_api", "freshdesk_api"]

    for name, result in zip(dep_names, results):
        if isinstance(result, Exception):
            # Handle unexpected exceptions
            logger.error(f"Unexpected error checking {name}: {result}")
            dependencies[name] = DependencyStatus(
                name=name,
                status="unhealthy",
                error_message=f"Unexpected error: {str(result)}"
            )
        else:
            dependencies[name] = result

    return dependencies


def determine_overall_status(dependencies: Dict[str, DependencyStatus]) -> str:
    """
    Determine overall system status based on dependency health

    Critical services: Supabase
    Non-critical services: Google API, OpenAI API, Freshdesk API

    Rules:
    - Any critical service unhealthy → "unhealthy"
    - 1-2 non-critical degraded → "degraded"
    - All healthy → "healthy"

    Args:
        dependencies: Dictionary of dependency statuses

    Returns:
        Overall status string
    """
    critical_services = ["supabase"]

    # Check critical services
    for service in critical_services:
        if service in dependencies:
            if dependencies[service].status == "unhealthy":
                return "unhealthy"

    # Count degraded/unhealthy services
    degraded_count = sum(
        1 for dep in dependencies.values()
        if dep.status in ["degraded", "unhealthy"]
    )

    if degraded_count >= 1:
        return "degraded"

    return "healthy"


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Returns basic application health status and uptime"
)
async def basic_health_check() -> HealthResponse:
    """
    Basic health check endpoint

    Always returns 200 OK with current status.
    Does not check external dependencies.

    Returns:
        HealthResponse with status, timestamp, version, and uptime
    """
    uptime = time.time() - APP_START_TIME

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime_seconds=round(uptime, 2)
    )


@router.get(
    "/dependencies",
    response_model=DependencyHealth,
    status_code=status.HTTP_200_OK,
    summary="Dependency health check",
    description="Checks all external dependencies and returns detailed status"
)
async def dependency_health_check() -> DependencyHealth:
    """
    Comprehensive dependency health check endpoint

    Checks:
    - Supabase database
    - Google Gemini API
    - OpenAI API
    - Freshdesk API

    Results are cached for 30 seconds to avoid overwhelming external services.
    Always returns 200 OK with detailed status information.

    Returns:
        DependencyHealth with overall status and individual dependency details
    """
    global _dependency_cache, _cache_timestamp

    # Check cache
    current_time = time.time()
    if _dependency_cache and (current_time - _cache_timestamp) < CACHE_TTL_SECONDS:
        logger.debug("Returning cached dependency health check results")
        return _dependency_cache

    # Perform fresh health checks
    logger.info("Performing dependency health checks")
    dependencies = await check_all_dependencies()

    # Determine overall status
    overall_status = determine_overall_status(dependencies)

    # Create response
    response = DependencyHealth(
        overall_status=overall_status,
        dependencies=dependencies,
        checked_at=datetime.utcnow()
    )

    # Update cache
    _dependency_cache = response
    _cache_timestamp = current_time

    # Log failures (not successful checks - too noisy)
    unhealthy_deps = [
        name for name, dep in dependencies.items()
        if dep.status == "unhealthy"
    ]
    if unhealthy_deps:
        logger.warning(f"Unhealthy dependencies: {', '.join(unhealthy_deps)}")

    return response
