"""
Test configuration management
"""
from backend.config import get_settings


def test_settings_singleton():
    """Test settings returns same instance"""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2


def test_settings_defaults():
    """Test default values"""
    settings = get_settings()
    assert settings.fastapi_env in ["development", "production"]
    assert settings.fastapi_port == 8000
    assert settings.log_level == "INFO"
