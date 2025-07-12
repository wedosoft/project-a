"""
데이터베이스 모듈 (Freshdesk 전용)

데이터베이스 연결, 벡터 데이터베이스, 마이그레이션 등을 관리합니다.
Freshdesk 플랫폼만 지원합니다.
"""

from .database import DatabaseManager, get_session
from .vectordb import VectorDBFactory, VectorDBInterface, QdrantAdapter, vector_db, search_vector_db
from .factory import DatabaseFactory, TenantDataManager, DatabaseType, get_database
from .tenant_config import TenantConfigManager

# ORM Models (핵심 모델만)
from .models import (
    Base, Company, Agent, IntegratedObject, ProgressLog
)

__all__ = [
    # Core database managers
    'DatabaseManager',
    
    # Vector database (Freshdesk 전용)
    'VectorDBFactory',
    'VectorDBInterface', 
    'QdrantAdapter',
    'vector_db',
    'search_vector_db',
    
    # Factory and utilities
    'DatabaseFactory',
    'TenantDataManager', 
    'DatabaseType',
    'get_database',
    'get_session',
    
    # Configuration
    'TenantConfigManager',
    
    # ORM Models (핵심 모델만)
    'Base',
    'Company', 'Agent', 'IntegratedObject', 'ProgressLog',
]
