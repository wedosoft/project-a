"""
통합 객체 모델 (핵심)
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from .base import MultiTenantModel


class IntegratedObject(MultiTenantModel):
    """통합 객체 - 모든 플랫폼 데이터의 통합 저장소"""
    __tablename__ = 'integrated_objects'
    
    # 기본 식별자 
    original_id = Column(String(100), nullable=False)  # 원본 플랫폼의 ID
    object_type = Column(String(50), nullable=False, default='integrated_ticket')
    
    # 핵심 컨텐츠
    integrated_content = Column(Text)  # 통합된 텍스트 컨텐츠
    summary = Column(Text)  # LLM 생성 요약
    
    # 원본 데이터 및 메타데이터
    original_data = Column(JSON)  # 원본 플랫폼 데이터 (JSON)
    tenant_metadata = Column(JSON)  # 구조화된 메타데이터
    
    # 처리 정보
    processed_at = Column(DateTime)
    summary_generated_at = Column(DateTime)
    
    # 인덱스
    __table_args__ = (
        Index('idx_integrated_unique', 'tenant_id', 'platform', 'object_type', 'original_id', unique=True),
        Index('idx_integrated_type_created', 'object_type', 'created_at'),
        Index('idx_integrated_summary_status', 'summary_generated_at'),
        Index('idx_integrated_tenant', 'tenant_id', 'platform'),
    )
