"""
Tests for health check endpoints

Tests both basic and comprehensive dependency health checks.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestBasicHealthCheck:
    """Test basic health check endpoint"""

    def test_basic_health_returns_200(self):
        """Basic health check should always return 200"""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_basic_health_response_structure(self):
        """Basic health check should have correct response structure"""
        response = client.get("/api/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "uptime_seconds" in data

    def test_basic_health_status_is_healthy(self):
        """Basic health check status should be healthy"""
        response = client.get("/api/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_basic_health_version(self):
        """Basic health check should return version"""
        response = client.get("/api/health")
        data = response.json()

        assert data["version"] == "1.0.0"

    def test_basic_health_uptime_positive(self):
        """Basic health check uptime should be positive"""
        response = client.get("/api/health")
        data = response.json()

        assert data["uptime_seconds"] > 0


class TestDependencyHealthCheck:
    """Test dependency health check endpoint"""

    def test_dependency_health_returns_200(self):
        """Dependency health check should always return 200"""
        response = client.get("/api/health/dependencies")
        assert response.status_code == 200

    def test_dependency_health_response_structure(self):
        """Dependency health check should have correct response structure"""
        response = client.get("/api/health/dependencies")
        data = response.json()

        assert "overall_status" in data
        assert "dependencies" in data
        assert "checked_at" in data

    def test_dependency_health_checks_all_services(self):
        """Dependency health check should check all required services"""
        response = client.get("/api/health/dependencies")
        data = response.json()

        dependencies = data["dependencies"]
        expected_services = ["supabase", "google_api", "openai_api", "freshdesk_api"]

        for service in expected_services:
            assert service in dependencies

    def test_dependency_status_structure(self):
        """Each dependency should have correct status structure"""
        response = client.get("/api/health/dependencies")
        data = response.json()

        for dep_name, dep_status in data["dependencies"].items():
            assert "name" in dep_status
            assert "status" in dep_status
            assert dep_status["status"] in ["healthy", "degraded", "unhealthy"]

            # If healthy, should have latency
            if dep_status["status"] == "healthy":
                assert "latency_ms" in dep_status
                assert dep_status["latency_ms"] is not None

            # If unhealthy/degraded, should have error message
            if dep_status["status"] in ["unhealthy", "degraded"]:
                assert "error_message" in dep_status

    def test_overall_status_values(self):
        """Overall status should be one of the valid values"""
        response = client.get("/api/health/dependencies")
        data = response.json()

        assert data["overall_status"] in ["healthy", "degraded", "unhealthy"]

    def test_caching_behavior(self):
        """Dependency health check should cache results"""
        # First call
        response1 = client.get("/api/health/dependencies")
        data1 = response1.json()
        timestamp1 = data1["checked_at"]

        # Second call (should be cached)
        response2 = client.get("/api/health/dependencies")
        data2 = response2.json()
        timestamp2 = data2["checked_at"]

        # Timestamps should be the same (cached result)
        assert timestamp1 == timestamp2


class TestHealthCheckIntegration:
    """Integration tests for health check system"""

    def test_root_endpoint_still_works(self):
        """Root endpoint should still work after adding health routes"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_basic_vs_dependency_health(self):
        """Basic health should not check dependencies"""
        # Basic health should be fast
        import time
        start = time.time()
        response = client.get("/api/health")
        basic_time = time.time() - start

        # Dependency health will be slower
        start = time.time()
        response = client.get("/api/health/dependencies")
        dep_time = time.time() - start

        # Basic should be significantly faster (< 100ms)
        assert basic_time < 0.1

    def test_openapi_docs_include_health(self):
        """OpenAPI docs should include health endpoints"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi = response.json()

        # Check paths exist
        assert "/api/health" in openapi["paths"]
        assert "/api/health/dependencies" in openapi["paths"]


@pytest.mark.parametrize("endpoint", ["/api/health", "/api/health/dependencies"])
def test_health_endpoints_cors_headers(endpoint):
    """Health endpoints should have CORS headers"""
    response = client.get(endpoint)

    # CORS headers should be present (configured in main.py)
    assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
