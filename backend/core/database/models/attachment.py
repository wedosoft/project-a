"""
첨부파일 모델

티켓이나 대화에 첨부된 파일 정보를 저장하는 ORM 모델입니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Attachment(MultiTenantModel):
    """첨부파일 모델"""
    __tablename__ = 'attachments'
    
    # 기본 정보
    original_id = Column(String(100))  # 원본 첨부파일 ID
    name = Column(String(255))  # 파일명
    content_type = Column(String(100))  # MIME 타입
    size = Column(Integer)  # 파일 크기
    
    # 관계 필드
    ticket_id = Column(Integer, ForeignKey('tickets.id'), index=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), index=True)
    
    # 관계 설정
    ticket = relationship("Ticket", back_populates="attachments", lazy="select")
    conversation = relationship("Conversation", back_populates="attachments", lazy="select")
    
    # 통합 정보
    download_url = Column(String(1024))  # 다운로드 URL
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
    
    # 인덱스
    __table_args__ = (
        Index('idx_attachment_original', 'company_id', 'platform', 'original_id', unique=True),
        Index('idx_attachment_tenant', 'company_id', 'platform'),
    )
