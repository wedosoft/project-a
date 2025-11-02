"""
AI Contact Center OS - Configuration Management
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # FastAPI
    fastapi_env: str = "development"
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    # LLM
    openai_api_key: str = ""
    google_api_key: str = ""

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    qdrant_use_https: bool = False

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_service_role_key: str = ""
    supabase_db_password: str = ""
    supabase_db_host: str = ""
    supabase_db_port: int = 6543
    supabase_db_name: str = "postgres"
    supabase_db_user: str = ""

    # Models
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "jinaai/jina-reranker-v2-base-multilingual"

    # Freshdesk
    freshdesk_domain: str = ""
    freshdesk_api_key: str = ""

    # Authentication
    allowed_api_keys: str = ""  # Comma-separated API keys for authentication

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False
    )

    @property
    def QDRANT_URL(self) -> str:
        """Construct Qdrant URL from host and port"""
        protocol = "https" if self.qdrant_use_https else "http"
        return f"{protocol}://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def QDRANT_API_KEY(self) -> str:
        """Qdrant API key"""
        return self.qdrant_api_key


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
