"""
Pytest configuration and fixtures
"""
import pytest
from typing import Dict, Any


@pytest.fixture
def sample_ticket_context() -> Dict[str, Any]:
    """Sample ticket context for testing"""
    return {
        "ticket_id": "12345",
        "ticket_content": "User unable to login after password reset",
        "ticket_meta": {
            "product": "Web App",
            "priority": "high",
            "status": "open",
            "tenant_id": "tenant-001",
        }
    }


@pytest.fixture
def sample_similar_cases() -> list:
    """Sample similar cases for testing"""
    return [
        {
            "ticket_id": "11111",
            "summary": "Login issue after password change",
            "similarity_score": 0.92,
            "resolution": "Clear browser cache and retry",
        },
        {
            "ticket_id": "22222",
            "summary": "Authentication failure post-reset",
            "similarity_score": 0.85,
            "resolution": "Reset session tokens",
        }
    ]


@pytest.fixture
def sample_kb_procedures() -> list:
    """Sample KB procedures for testing"""
    return [
        {
            "doc_id": "KB-AUTH-001",
            "title": "Password Reset Troubleshooting",
            "steps": [
                "Clear browser cookies",
                "Verify email confirmation",
                "Check password complexity",
            ]
        }
    ]
