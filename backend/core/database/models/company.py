"""
회사 모델
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import MultiTenantModel


class Company(MultiTenantModel):
    """회사 정보"""
    __tablename__ = 'companies'
    
    # BaseModel의 id 필드를 오버라이드
    id = Column(Integer, primary_key=True, autoincrement=True)  # 내부 시스템 ID
    tenant_id = Column(String(50), nullable=False, unique=True)  # 회사 고유 식별자
    freshdesk_domain = Column(String(255), unique=True, nullable=False)
    company_name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255))
    settings_json = Column(Text)
    timezone = Column(String(50), default='UTC')
    language = Column(String(10), default='ko')
    

    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_company_domain', 'freshdesk_domain', unique=True),
        Index('idx_company_platform', 'tenant_id', 'platform', unique=True),
    )
