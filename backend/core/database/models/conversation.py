"""
대화 모델

티켓과 관련된 대화 내용을 저장하는 ORM 모델입니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text, JSON
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Conversation(MultiTenantModel):
    """대화 모델"""
    __tablename__ = 'conversations'
    
    # 기본 정보
    original_id = Column(String(100))  # 원본 대화 ID
    body_text = Column(Text)  # 대화 내용
    from_email = Column(String(255))  # 발신자 이메일
    
    # 관계 필드
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False, index=True)
    
    # 관계 설정
    ticket = relationship("Ticket", back_populates="conversations", lazy="select")
    attachments = relationship("Attachment", back_populates="conversation", lazy="dynamic")
    
    # 통합 정보
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
    
    # 인덱스
    __table_args__ = (
        Index('idx_conversation_original', 'tenant_id', 'platform', 'original_id', unique=True),
        Index('idx_conversation_tenant', 'tenant_id', 'platform'),
    )
