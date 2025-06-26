"""
데이터베이스 팩토리 - SQLite와 PostgreSQL 백엔드 선택
"""

import os
import logging
from typing import Optional, Union
from enum import Enum

from .database import DatabaseManager
from .postgresql_database import PostgreSQLDatabase
from .tenant_config import TenantConfigManager

logger = logging.getLogger(__name__)

class DatabaseType(Enum):
    """지원되는 데이터베이스 타입"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"

class DatabaseFactory:
    """
    데이터베이스 백엔드 선택을 위한 팩토리 클래스
    환경변수나 설정에 따라 적절한 데이터베이스 매니저를 반환
    """
    
    @staticmethod
    def get_database_type() -> DatabaseType:
        """환경변수에서 데이터베이스 타입 결정"""
        db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
        
        if db_type == "postgresql":
            return DatabaseType.POSTGRESQL
        else:
            return DatabaseType.SQLITE
    
    @staticmethod
    def create_database_manager(
        tenant_id: Optional[str] = None,
        platform: Optional[str] = None,
        db_type: Optional[DatabaseType] = None
    ) -> Union[DatabaseManager, PostgreSQLDatabase]:
        """
        적절한 데이터베이스 매니저 인스턴스 생성
        
        Args:
            tenant_id: 테넌트 ID (멀티테넌트 환경에서)
            platform: 플랫폼 (현재는 Freshdesk만 지원)
            db_type: 강제로 지정할 데이터베이스 타입
        
        Returns:
            적절한 데이터베이스 매니저 인스턴스
        """
        if db_type is None:
            db_type = DatabaseFactory.get_database_type()
        
        if db_type == DatabaseType.POSTGRESQL:
            logger.info(f"PostgreSQL 데이터베이스 매니저 생성 - tenant: {tenant_id}, platform: {platform}")
            return PostgreSQLDatabase(tenant_id, platform or "freshdesk")
        else:
            logger.info(f"SQLite 데이터베이스 매니저 생성 - tenant: {tenant_id}, platform: {platform}")
            return DatabaseManager(tenant_id, platform or "freshdesk")
    
    @staticmethod
    def validate_environment() -> bool:
        """
        현재 환경의 데이터베이스 설정이 유효한지 검증
        
        Returns:
            True if valid, False otherwise
        """
        db_type = DatabaseFactory.get_database_type()
        
        if db_type == DatabaseType.POSTGRESQL:
            required_vars = [
                "POSTGRES_HOST",
                "POSTGRES_PORT", 
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD"
            ]
            
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                logger.error(f"PostgreSQL 환경변수 누락: {missing_vars}")
                return False
                
        elif db_type == DatabaseType.SQLITE:
            # SQLite는 별도 환경변수 불필요 (파일 기반)
            pass
        
        return True

class TenantDataManager:
    """
    멀티테넌트 데이터 관리를 위한 유틸리티 클래스
    """
    
    def __init__(self, db_type: Optional[DatabaseType] = None):
        self.db_type = db_type or DatabaseFactory.get_database_type()
    
    def get_tenant_database(self, tenant_id: str, platform: str = "freshdesk"):
        """특정 테넌트의 데이터베이스 매니저 반환"""
        return DatabaseFactory.create_database_manager(
            tenant_id=tenant_id,
            platform=platform,
            db_type=self.db_type
        )
    
    def migrate_tenant(self, tenant_id: str, platform: str = "freshdesk") -> bool:
        """특정 테넌트의 스키마 마이그레이션 실행"""
        try:
            db = self.get_tenant_database(tenant_id, platform)
            db.create_tables()
            logger.info(f"테넌트 {tenant_id} ({platform}) 마이그레이션 완료")
            return True
        except Exception as e:
            logger.error(f"테넌트 {tenant_id} 마이그레이션 실패: {e}")
            return False
    
    def get_tenant_statistics(self, tenant_id: str, platform: str = "freshdesk") -> dict:
        """특정 테넌트의 데이터 통계 반환"""
        try:
            db = self.get_tenant_database(tenant_id, platform)
            
            # 통합 객체 수 조회
            total_objects = db.count_integrated_objects()
            
            # 타입별 객체 수 조회
            type_counts = {}
            for obj_type in ['ticket', 'conversation', 'attachment', 'knowledge_base']:
                count = db.count_integrated_objects_by_type(obj_type)
                type_counts[obj_type] = count
            
            return {
                'tenant_id': tenant_id,
                'platform': platform,
                'total_objects': total_objects,
                'type_counts': type_counts,
                'database_type': self.db_type.value
            }
        except Exception as e:
            logger.error(f"테넌트 {tenant_id} 통계 조회 실패: {e}")
            return {}

def get_database(tenant_id: Optional[str] = None, platform: str = "freshdesk"):
    """
    기본 데이터베이스 인스턴스 반환 (기존 코드 호환성 유지)
    
    Args:
        tenant_id: 테넌트 ID
        platform: 플랫폼 이름
    
    Returns:
        적절한 데이터베이스 매니저 인스턴스
    """
    return DatabaseFactory.create_database_manager(tenant_id=tenant_id, platform=platform)
