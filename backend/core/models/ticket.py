"""
티켓 모델

통합 티켓 정보를 담는 ORM 모델입니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text, JSON
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Ticket(MultiTenantModel):
    """티켓 모델"""
    __tablename__ = 'tickets'
    
    # 기본 정보
    original_id = Column(String(100), nullable=False)  # 원본 시스템의 티켓 ID
    subject = Column(String(255))
    description = Column(Text)
    status = Column(String(50))
    priority = Column(Integer)
    
    # 관계 필드
    agent_id = Column(Integer, ForeignKey('agents.id'), index=True)
    category_id = Column(Integer, ForeignKey('categories.id'), index=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # 관계 설정
    agent = relationship("Agent", back_populates="tickets", lazy="select")
    company = relationship("Company", back_populates="tickets", lazy="select")
    category = relationship("Category", back_populates="tickets", lazy="select")
    conversations = relationship("Conversation", back_populates="ticket", lazy="dynamic")
    attachments = relationship("Attachment", back_populates="ticket", lazy="dynamic")
    assignments = relationship("Assignment", back_populates="ticket", lazy="dynamic")
    
    # 통합 정보
    integrated_content = Column(Text)  # 통합된 텍스트 컨텐츠
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_ticket_original', 'company_id', 'platform', 'original_id', unique=True),
        Index('idx_ticket_status', 'status'),
        Index('idx_ticket_priority', 'priority'),
        Index('idx_ticket_tenant', 'company_id', 'platform'),
    )
