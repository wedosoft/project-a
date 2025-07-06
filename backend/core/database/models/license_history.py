"""
라이선스 히스토리 모델

에이전트 라이선스 변경 이력을 추적하는 모델을 정의합니다.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class LicenseHistory(MultiTenantModel):
    """라이선스 변경 이력"""
    __tablename__ = 'license_history'
    
    # 에이전트 정보
    agent_id = Column(Integer, nullable=False)
    agent_name = Column(String(255), nullable=False)
    agent_email = Column(String(255), nullable=False)
    
    # 변경 정보
    action = Column(String(20), nullable=False)  # activated, deactivated, transferred
    previous_status = Column(Boolean, nullable=False)
    new_status = Column(Boolean, nullable=False)
    
    # 수행자 정보
    performed_by = Column(String(255), nullable=False, default='system')
    performed_at = Column(DateTime, nullable=False)
    
    # 추가 정보
    reason = Column(String(500))  # 변경 사유
    ip_address = Column(String(50))  # 요청 IP 주소
    user_agent = Column(String(500))  # 요청 User-Agent
    
    # 인덱스
    __table_args__ = (
        Index('idx_license_history_tenant', 'tenant_id', 'performed_at'),
        Index('idx_license_history_agent', 'tenant_id', 'agent_id'),
        Index('idx_license_history_action', 'action', 'performed_at'),
    )