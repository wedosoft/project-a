"""
기본 모델 정의

SQLAlchemy ORM 기본 모델과 멀티테넌트 모델을 정의합니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class BaseModel(Base):
    """기본 모델 클래스"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MultiTenantModel(BaseModel):
    """멀티테넌트 지원을 위한 기본 모델"""
    __abstract__ = True
    
    company_id = Column(String(50), nullable=False, index=True)
    platform = Column(String(20), default='freshdesk', nullable=False, index=True)
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
