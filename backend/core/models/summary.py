"""
요약 모델

LLM으로 생성된 요약 정보를 저장하는 ORM 모델입니다.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, Text, JSON
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Summary(MultiTenantModel):
    """요약 정보 모델"""
    __tablename__ = 'summaries'
    
    # 기본 정보
    original_object_id = Column(String(100), nullable=False)  # 원본 객체 ID
    object_type = Column(String(50), nullable=False)  # ticket, article 등
    summary_text = Column(Text)  # LLM 생성 요약
    
    # 요약 메타데이터
    token_count = Column(Integer)  # 토큰 수
    model_version = Column(String(100))  # 사용된 모델 버전
    prompt_template = Column(String(255))  # 사용된 프롬프트 템플릿
    confidence_score = Column(Integer)  # 신뢰도 점수
    
    # 관계 필드
    ticket_id = Column(Integer, ForeignKey('tickets.id'), index=True)
    
    # 관계 설정
    ticket = relationship("Ticket", backref="summaries", lazy="select")
    
    # 통합 정보
    tenant_metadata = Column(JSON)  # 테넌트별 메타데이터
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_summary_original', 'company_id', 'platform', 'object_type', 'original_object_id'),
        Index('idx_summary_tenant', 'company_id', 'platform'),
    )
