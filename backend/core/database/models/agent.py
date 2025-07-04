"""
에이전트(상담원) 모델

멀티테넌트를 지원하는 에이전트 모델을 정의합니다.
각 플랫폼의 상담원 정보를 통합하여 관리합니다.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index, JSON, DateTime
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Agent(MultiTenantModel):
    """상담원 정보"""
    __tablename__ = 'agents'
    
    # 기본 정보
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    external_id = Column(String(100))  # 외부 플랫폼의 상담원 ID
    
    # 권한 정보
    role = Column(String(50))  # admin, agent, viewer
    department = Column(String(100))
    permissions = Column(JSON)  # 세부 권한 설정
    
    # 상태 정보
    is_active = Column(Boolean, default=True)
    last_active_at = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime)  # 계정 잠금 시간
    
    # 관계 필드
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # 관계 설정 (Company와의 관계만 유지)
    company = relationship("Company", back_populates="agents")
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_agent_email_company', 'email', 'company_id', unique=True),
        Index('idx_agent_external_company', 'external_id', 'company_id', 'platform', unique=True),
        Index('idx_agent_active_role', 'is_active', 'role'),
        Index('idx_agent_tenant', 'tenant_id', 'platform'),
    )
