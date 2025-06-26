"""
더미 모델들 (완전한 ORM 구현 전까지 사용)
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from .base import BaseModel


class Ticket(BaseModel):
    """티켓 정보 (더미)"""
    __tablename__ = 'tickets'
    
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String)
    priority = Column(Integer, default=1)
    
    # 관계
    company = relationship("Company", back_populates="tickets")
    agent = relationship("Agent", back_populates="tickets")
    category = relationship("Category", back_populates="tickets")
    conversations = relationship("Conversation", back_populates="ticket")
    summaries = relationship("Summary", back_populates="ticket")
    
    __table_args__ = (
        Index('idx_tickets_company_freshdesk', 'company_id', 'freshdesk_id', unique=True),
    )


class Conversation(BaseModel):
    """대화 정보 (더미)"""
    __tablename__ = 'conversations'
    
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    body_text = Column(Text, nullable=False)
    from_email = Column(String)
    incoming = Column(Boolean, nullable=False)
    private = Column(Boolean, default=False)
    
    # 관계
    ticket = relationship("Ticket", back_populates="conversations")
    attachments = relationship("Attachment", back_populates="conversation")
    
    __table_args__ = (
        Index('idx_conversations_ticket_freshdesk', 'ticket_id', 'freshdesk_id', unique=True),
    )


class Attachment(BaseModel):
    """첨부파일 정보 (더미)"""
    __tablename__ = 'attachments'
    
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    content_type = Column(String)
    size_bytes = Column(Integer)
    
    # 관계
    conversation = relationship("Conversation", back_populates="attachments")
    
    __table_args__ = (
        Index('idx_attachments_conversation_freshdesk', 'conversation_id', 'freshdesk_id', unique=True),
    )


class Summary(BaseModel):
    """요약 정보 (더미)"""
    __tablename__ = 'summaries'
    
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False)
    summary_text = Column(Text, nullable=False)
    quality_score = Column(Float, default=0.0)
    model_used = Column(String)
    is_active = Column(Boolean, default=True)
    
    # 관계
    ticket = relationship("Ticket", back_populates="summaries")
    
    __table_args__ = (
        Index('idx_summaries_ticket_active_quality', 'ticket_id', 'is_active', 'quality_score'),
    )


class ProcessingLog(BaseModel):
    """처리 로그 (더미)"""
    __tablename__ = 'processing_logs'
    
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    process_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    result_message = Column(Text)
    processing_time_ms = Column(Integer)
    
    __table_args__ = (
        Index('idx_processing_logs_table_record', 'table_name', 'record_id'),
    )
