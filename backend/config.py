"""
AI Contact Center OS - Configuration Management
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # FastAPI
    fastapi_env: str = "development"
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    # LLM
    openai_api_key: str = ""

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Freshdesk
    freshdesk_domain: str = ""
    freshdesk_api_key: str = ""

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
