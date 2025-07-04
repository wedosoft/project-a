"""
이전 버전과의 호환성을 위한 연결 모듈

@deprecated: 새로운 코드에서는 manager.py의 DatabaseManager를 사용하세요.
"""

from .manager import get_db_manager as get_database_manager
from .manager import DatabaseManager, DatabaseConfig, db_config

__all__ = [
    'get_database_manager',
    'DatabaseManager',
    'DatabaseConfig',
    'db_config'
]
