"""
할당 모델

에이전트에게 할당된 작업을 추적하는 ORM 모델입니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import MultiTenantModel


class Assignment(MultiTenantModel):
    """작업 할당 정보"""
    __tablename__ = 'assignments'
    
    # 기본 정보
    status = Column(String(50), nullable=False, default='pending')  # pending, accepted, completed, rejected
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # 관계 필드
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=False)
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey('agents.id'))  # 할당한 관리자
    
    # 관계 설정
    agent = relationship("Agent", back_populates="assignments", foreign_keys=[agent_id])
    ticket = relationship("Ticket", back_populates="assignments")
    assigned_by = relationship("Agent", foreign_keys=[assigned_by_id], post_update=True)
    
    # 통합 정보
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_assignment_agent', 'agent_id', 'status'),
        Index('idx_assignment_ticket', 'ticket_id', 'status'),
        Index('idx_assignment_tenant', 'tenant_id', 'platform'),
    )
