"""
데이터베이스 모듈 (Freshdesk 전용)

데이터베이스 연결, 벡터 데이터베이스, 마이그레이션 등을 관리합니다.
Freshdesk 플랫폼만 지원합니다.
"""

from .database import DatabaseManager
from .postgresql_database import PostgreSQLDatabase
from .vectordb import VectorDBFactory, VectorDBInterface, QdrantAdapter, vector_db
from .factory import DatabaseFactory, TenantDataManager, DatabaseType, get_database
from .tenant_config import TenantConfigManager

__all__ = [
    # Core database managers
    'DatabaseManager',
    'PostgreSQLDatabase',
    
    # Vector database (Freshdesk 전용)
    'VectorDBFactory',
    'VectorDBInterface', 
    'QdrantAdapter',
    'vector_db',
    
    # Factory and utilities
    'DatabaseFactory',
    'TenantDataManager', 
    'DatabaseType',
    'get_database',
    
    # Configuration
    'TenantConfigManager',
]
