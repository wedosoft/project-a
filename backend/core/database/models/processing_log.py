"""
처리 로그 모델

데이터 처리 이력을 저장하는 ORM 모델입니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import MultiTenantModel


class ProcessingLog(MultiTenantModel):
    """처리 이력 모델"""
    __tablename__ = 'processing_logs'
    
    # 기본 정보
    process_type = Column(String(50), nullable=False)  # 처리 유형 (summarization, embedding 등)
    status = Column(String(20), nullable=False)  # success, failure, pending
    original_object_id = Column(String(100))  # 처리된 객체 ID
    object_type = Column(String(50))  # ticket, article 등
    
    # 처리 상세
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    execution_time = Column(Integer)  # 밀리초 단위
    
    # 처리 메타데이터
    processor_version = Column(String(50))  # 프로세서 버전
    model_version = Column(String(100))  # 사용된 모델 버전
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_log_process_type', 'process_type', 'status'),
        Index('idx_log_object', 'object_type', 'original_object_id'),
        Index('idx_log_tenant', 'company_id', 'platform'),
    )
