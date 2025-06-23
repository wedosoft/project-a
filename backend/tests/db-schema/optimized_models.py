"""
최적화된 데이터베이스 모델

SQLAlchemy ORM을 사용하여 최적화된 스키마를 백엔드 API에 통합
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()


class Company(Base):
    """회사 정보"""
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    freshdesk_domain = Column(String, unique=True, nullable=False)
    company_name = Column(String, nullable=False)
    api_key_hash = Column(String)
    settings_json = Column(Text)
    timezone = Column(String, default='UTC')
    language = Column(String, default='ko')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    tickets = relationship("Ticket", back_populates="company")
    agents = relationship("Agent", back_populates="company")
    categories = relationship("Category", back_populates="company")


class Agent(Base):
    """상담원 정보"""
    __tablename__ = 'agents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    email = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String)
    department = Column(String)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    company = relationship("Company", back_populates="agents")
    tickets = relationship("Ticket", back_populates="agent")
    
    # 유니크 제약조건
    __table_args__ = (
        Index('idx_agents_company_freshdesk', 'company_id', 'freshdesk_id', unique=True),
    )


class Category(Base):
    """카테고리 정보"""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    level = Column(Integer, default=0)
    path = Column(String)  # 계층 경로
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    company = relationship("Company", back_populates="categories")
    parent = relationship("Category", remote_side=[id])
    tickets = relationship("Ticket", back_populates="category")
    
    # 유니크 제약조건
    __table_args__ = (
        Index('idx_categories_company_freshdesk', 'company_id', 'freshdesk_id', unique=True),
    )


class Ticket(Base):
    """티켓 정보 (최적화)"""
    __tablename__ = 'tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    
    # 기본 정보
    subject = Column(String, nullable=False)
    description_text = Column(Text)
    description_html = Column(Text)
    
    # 분류 정보
    status_id = Column(Integer, nullable=False)
    priority_id = Column(Integer, nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    sub_category_id = Column(Integer)
    type_id = Column(Integer)
    source_id = Column(Integer)
    
    # 담당자 정보
    requester_id = Column(Integer)
    agent_id = Column(Integer, ForeignKey('agents.id'))
    group_id = Column(Integer)
    
    # 메타데이터
    due_by = Column(DateTime)
    fr_due_by = Column(DateTime)
    is_escalated = Column(Boolean, default=False)
    spam = Column(Boolean, default=False)
    
    # JSON 압축 필드
    tags_json = Column(Text)
    custom_fields_json = Column(Text)
    
    # 시간 정보
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    
    # 통계 정보 (비정규화)
    conversation_count = Column(Integer, default=0)
    attachment_count = Column(Integer, default=0)
    resolution_time_hours = Column(Integer)
    first_response_time_hours = Column(Integer)
    
    # 관계
    company = relationship("Company", back_populates="tickets")
    agent = relationship("Agent", back_populates="tickets")
    category = relationship("Category", back_populates="tickets")
    conversations = relationship("Conversation", back_populates="ticket", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="ticket", cascade="all, delete-orphan")
    
    # 인덱스
    __table_args__ = (
        Index('idx_tickets_company_freshdesk', 'company_id', 'freshdesk_id', unique=True),
        Index('idx_tickets_status_priority', 'status_id', 'priority_id'),
        Index('idx_tickets_created_at', 'created_at'),
        Index('idx_tickets_updated_at', 'updated_at'),
        Index('idx_tickets_company_status_created', 'company_id', 'status_id', 'created_at'),
    )
    
    @property
    def tags(self):
        """태그 리스트 반환"""
        if self.tags_json:
            return json.loads(self.tags_json)
        return []
    
    @tags.setter
    def tags(self, value):
        """태그 리스트 설정"""
        self.tags_json = json.dumps(value) if value else None
    
    @property
    def custom_fields(self):
        """커스텀 필드 딕셔너리 반환"""
        if self.custom_fields_json:
            return json.loads(self.custom_fields_json)
        return {}
    
    @custom_fields.setter
    def custom_fields(self, value):
        """커스텀 필드 딕셔너리 설정"""
        self.custom_fields_json = json.dumps(value) if value else None


class Conversation(Base):
    """대화 정보"""
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    
    # 메시지 내용
    body_text = Column(Text, nullable=False)
    body_html = Column(Text)
    
    # 발신자 정보
    user_id = Column(Integer)
    from_email = Column(String)
    
    # 메시지 유형
    incoming = Column(Boolean, nullable=False)
    private = Column(Boolean, default=False)
    source_id = Column(Integer)
    
    # 시간 정보
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime)
    
    # 통계
    attachment_count = Column(Integer, default=0)
    
    # 관계
    ticket = relationship("Ticket", back_populates="conversations")
    attachments = relationship("Attachment", back_populates="conversation", cascade="all, delete-orphan")
    
    # 인덱스
    __table_args__ = (
        Index('idx_conversations_ticket_freshdesk', 'ticket_id', 'freshdesk_id', unique=True),
        Index('idx_conversations_ticket_created', 'ticket_id', 'created_at'),
    )


class Attachment(Base):
    """첨부파일 정보"""
    __tablename__ = 'attachments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    freshdesk_id = Column(Integer, nullable=False)
    
    # 파일 정보
    name = Column(String, nullable=False)
    content_type = Column(String)
    size_bytes = Column(Integer)
    
    # 다운로드 정보
    attachment_url = Column(String)
    download_url = Column(String)
    
    # 처리 상태
    downloaded = Column(Boolean, default=False)
    local_path = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    conversation = relationship("Conversation", back_populates="attachments")
    
    # 인덱스
    __table_args__ = (
        Index('idx_attachments_conversation_freshdesk', 'conversation_id', 'freshdesk_id', unique=True),
    )


class Summary(Base):
    """요약 정보"""
    __tablename__ = 'summaries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id'), nullable=False)
    
    # 요약 내용
    summary_text = Column(Text, nullable=False)
    summary_type = Column(String, default='ticket')
    
    # 품질 관리
    quality_score = Column(Float, nullable=False, default=0.0)
    structure_score = Column(Float, default=0.0)
    completion_score = Column(Float, default=0.0)
    language_score = Column(Float, default=0.0)
    
    # 생성 정보
    model_used = Column(String)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    processing_time_ms = Column(Integer, default=0)
    cost_estimate = Column(Float, default=0.0)
    
    # 메타데이터
    ui_language = Column(String, default='ko')
    content_language = Column(String, default='ko')
    retry_count = Column(Integer, default=0)
    
    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 버전 관리
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    
    # 관계
    ticket = relationship("Ticket", back_populates="summaries")
    
    # 인덱스
    __table_args__ = (
        Index('idx_summaries_ticket_active_quality', 'ticket_id', 'is_active', 'quality_score'),
        Index('idx_summaries_created_at', 'created_at'),
    )


class ProcessingLog(Base):
    """처리 로그"""
    __tablename__ = 'processing_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 처리 대상
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    
    # 처리 유형
    process_type = Column(String, nullable=False)  # 'summary', 'sync', 'cleanup'
    status = Column(String, nullable=False)        # 'pending', 'processing', 'completed', 'failed'
    
    # 처리 결과
    result_message = Column(Text)
    error_message = Column(Text)
    
    # 성능 메트릭
    processing_time_ms = Column(Integer)
    memory_usage_mb = Column(Float)
    
    # 배치 정보
    batch_id = Column(String)
    batch_size = Column(Integer)
    
    # 시간 정보
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # 재시도 정보
    attempt_count = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)
    
    # 인덱스
    __table_args__ = (
        Index('idx_processing_logs_table_record', 'table_name', 'record_id'),
        Index('idx_processing_logs_status', 'status'),
        Index('idx_processing_logs_batch', 'batch_id'),
    )
