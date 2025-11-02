"""
pytest configuration and shared fixtures for E2E tests
"""
import pytest
import os


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "requires_qdrant: mark test as requiring Qdrant service"
    )
    config.addinivalue_line(
        "markers", "requires_postgres: mark test as requiring PostgreSQL service"
    )
    config.addinivalue_line(
        "markers", "requires_supabase: mark test as requiring Supabase service"
    )
    config.addinivalue_line(
        "markers", "requires_external_services: mark test as requiring all external services"
    )


# Simple availability checks based on environment variables
def is_qdrant_configured() -> bool:
    """Check if Qdrant is configured"""
    from backend.config import get_settings
    settings = get_settings()
    # If host is localhost and we're not in a Docker env, likely not available
    return settings.qdrant_host != "localhost" or os.getenv("QDRANT_AVAILABLE") == "true"


def is_postgres_configured() -> bool:
    """Check if PostgreSQL is configured"""
    from backend.config import get_settings
    settings = get_settings()
    # Check if we have valid connection info (not placeholder values)
    has_host = bool(settings.supabase_db_host and 
                    not settings.supabase_db_host.startswith("db.your-"))
    has_password = bool(settings.supabase_db_password and 
                        settings.supabase_db_password != "your_db_password_here")
    return has_host and has_password


def is_supabase_configured() -> bool:
    """Check if Supabase is configured"""
    from backend.config import get_settings
    settings = get_settings()
    # Check if we have valid API keys (not placeholder values)
    has_url = bool(settings.supabase_url and 
                   not settings.supabase_url.startswith("https://your-"))
    has_key = bool(settings.supabase_key and 
                   settings.supabase_key != "your_supabase_key_here")
    return has_url and has_key


# Skip markers using environment-based checks
requires_qdrant = pytest.mark.skipif(
    not is_qdrant_configured(),
    reason="Qdrant service not configured (set QDRANT_HOST or QDRANT_AVAILABLE=true)"
)

requires_postgres = pytest.mark.skipif(
    not is_postgres_configured(),
    reason="PostgreSQL service not configured (set SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD)"
)

requires_supabase = pytest.mark.skipif(
    not is_supabase_configured(),
    reason="Supabase service not configured (set SUPABASE_URL and SUPABASE_KEY)"
)

requires_external_services = pytest.mark.skipif(
    not all([is_qdrant_configured(), is_postgres_configured(), is_supabase_configured()]),
    reason="External services not configured"
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

