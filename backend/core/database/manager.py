"""
데이터베이스 연결 관리

SQLAlchemy를 사용한 데이터베이스 연결 및 세션 관리.
"""

import os
from typing import Optional, Generator
from contextlib import contextmanager
import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from .models.base import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 연결 관리자"""
    
    def __init__(self, database_url: str, is_async: bool = False, echo: bool = False):
        """
        DatabaseManager 초기화
        
        Args:
            database_url: 데이터베이스 연결 URL
            is_async: 비동기 모드 사용 여부
            echo: SQL 로깅 활성화 여부
        """
        self.database_url = database_url
        self.is_async = is_async
        self.echo = echo
        self._setup_engine()
    
    def _setup_engine(self):
        """데이터베이스 엔진 설정"""
        if self.is_async:
            self.engine = create_async_engine(
                self.database_url,
                echo=self.echo,
                pool_pre_ping=True
            )
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        else:
            # SQLite 특별 설정
            if self.database_url.startswith('sqlite:'):
                # SQLite 연결 인수 설정
                connect_args = {
                    "check_same_thread": False,
                    "isolation_level": None,  # autocommit 모드
                    "timeout": 20,  # 20초 타임아웃
                }
                
                self.engine = create_engine(
                    self.database_url,
                    echo=self.echo,
                    pool_pre_ping=True,
                    pool_recycle=3600,  # 1시간마다 연결 재활용
                    connect_args=connect_args
                )
                
                # SQLite 최적화 설정 실행
                @event.listens_for(self.engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    # WAL 모드 활성화 (동시성 개선)
                    cursor.execute("PRAGMA journal_mode=WAL")
                    # 동기화 모드 설정 (데이터 안전성)
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    # 외래키 제약조건 활성화
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
                    
            else:
                self.engine = create_engine(
                    self.database_url,
                    echo=self.echo,
                    pool_pre_ping=True
                )
            
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
    
    def create_database(self):
        """데이터베이스 생성"""
        if not self.is_async:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ 데이터베이스 스키마 생성 완료")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        데이터베이스 세션 컨텍스트 매니저
        
        Example:
            with db.get_session() as session:
                result = session.query(User).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"⚠️ 데이터베이스 세션 오류: {str(e)}")
            raise
        finally:
            session.close()
    
    async def get_async_session(self) -> AsyncSession:
        """비동기 세션 반환"""
        if not self.is_async:
            raise RuntimeError("비동기 세션은 is_async=True로 초기화된 경우에만 사용 가능합니다")
        return self.SessionLocal()


class DatabaseConfig:
    """데이터베이스 설정 관리"""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
    
    def get_database_url(self, tenant_id: Optional[str] = None) -> str:
        """
        환경에 따른 데이터베이스 URL 반환
        
        Args:
            tenant_id: 테넌트 ID (개발 환경에서 SQLite DB 파일명에 사용)
            
        Returns:
            str: 데이터베이스 연결 URL
        """
        if self.environment == 'development':
            # SQLite 사용 (개발 환경)
            if tenant_id:
                db_path = f"./data/{tenant_id}_freshdesk_data.db"
                os.makedirs(os.path.dirname(db_path), exist_ok=True)
                return f"sqlite:///{db_path}"
            return "sqlite:///./data/main.db"
        
        elif self.environment in ['staging', 'production']:
            # PostgreSQL 사용 (스테이징/운영 환경)
            db_url = os.getenv('DATABASE_URL')
            if not db_url:
                raise ValueError(f"{self.environment} 환경에서는 DATABASE_URL 환경변수가 필요합니다")
            return db_url
        
        else:
            raise ValueError(f"알 수 없는 환경: {self.environment}")
    
    def get_manager(
        self, 
        tenant_id: Optional[str] = None,
        is_async: bool = False,
        echo: bool = False
    ) -> DatabaseManager:
        """
        DatabaseManager 인스턴스 생성
        
        Args:
            tenant_id: 테넌트 ID
            is_async: 비동기 모드 사용 여부
            echo: SQL 로깅 활성화 여부
            
        Returns:
            DatabaseManager: 데이터베이스 매니저 인스턴스
        """
        database_url = self.get_database_url(tenant_id)
        return DatabaseManager(database_url, is_async=is_async, echo=echo)


# 전역 설정 인스턴스
db_config = DatabaseConfig()


def get_db_manager(
    tenant_id: Optional[str] = None,
    is_async: bool = False,
    echo: bool = False
) -> DatabaseManager:
    """
    데이터베이스 매니저 팩토리 함수
    
    Args:
        tenant_id: 테넌트 ID
        is_async: 비동기 모드 사용 여부
        echo: SQL 로깅 활성화 여부
        
    Returns:
        DatabaseManager: 데이터베이스 매니저 인스턴스
    """
    return db_config.get_manager(tenant_id, is_async, echo)
