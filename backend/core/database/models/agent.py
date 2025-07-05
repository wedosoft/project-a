"""
에이전트(상담원) 모델

멀티테넌트를 지원하는 에이전트 모델을 정의합니다.
각 플랫폼의 상담원 정보를 통합하여 관리합니다.
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index, JSON, DateTime
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Agent(MultiTenantModel):
    """상담원 정보 - Freshdesk API 원본 구조 그대로 사용"""
    __tablename__ = 'agents'
    
    # Freshdesk API 원본 필드들 (이미지 응답 구조 그대로) - id는 MultiTenantModel에서 상속받음
    available = Column(Boolean, default=True)
    occasional = Column(Boolean, default=False) 
    signature = Column(String(2000))  # 서명이 길 수 있음
    ticket_scope = Column(Integer, default=1)
    available_since = Column(String(50))  # 원본은 문자열 형태
    type = Column(String(50))  # support_agent 등
    focus_mode = Column(Boolean, default=True)
    
    # contact 정보 (nested object를 평면화)
    active = Column(Boolean, default=True)  # contact.active -> active
    email = Column(String(255), nullable=False)
    job_title = Column(String(255))
    language = Column(String(10))
    last_login_at = Column(String(50))  # 원본은 문자열 형태
    mobile = Column(String(50))
    name = Column(String(255), nullable=False)
    phone = Column(String(50))
    time_zone = Column(String(100))
    contact_created_at = Column(String(50))  # contact의 created_at
    contact_updated_at = Column(String(50))  # contact의 updated_at
    
    # 라이선스 관리 (추가 필드)
    license_active = Column(Boolean, default=True)  # 라이선스 활성화/비활성화
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_agent_tenant_id', 'tenant_id', 'id', unique=True),  # 중복 체크 핵심 인덱스
        Index('idx_agent_email_tenant', 'email', 'tenant_id', unique=True),
        Index('idx_agent_tenant', 'tenant_id', 'platform'),
        Index('idx_agent_license', 'license_active', 'tenant_id'),  # 라이선스 관리용 인덱스
        Index('idx_agent_active', 'active', 'available'),  # 활성 상태 조회용
    )
