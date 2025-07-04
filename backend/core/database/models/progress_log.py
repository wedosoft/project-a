"""
진행상황 로그 모델

데이터 수집 진행상황을 실시간으로 추적하는 ORM 모델입니다.
고객이 관리화면에서 진행상황을 볼 수 있도록 합니다.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from datetime import datetime
from .base import BaseModel


class ProgressLog(BaseModel):
    """진행상황 로그 모델"""
    __tablename__ = 'progress_logs'
    
    # 기본 정보
    job_id = Column(String(100), nullable=False)  # 작업 고유 ID
    tenant_id = Column(String(50), nullable=False)  # 회사 ID (company_id 대신)
    message = Column(String(500), nullable=False)  # 사용자 친화적 메시지
    percentage = Column(Float, nullable=False)  # 진행률 (0-100)
    step = Column(Integer, nullable=False)  # 현재 단계
    total_steps = Column(Integer, nullable=False)  # 전체 단계 수
    
    # 인덱스 설정 (UNIQUE 제약조건 제거)
    __table_args__ = (
        Index('idx_progress_job_id', 'job_id'),
        Index('idx_progress_tenant_id', 'tenant_id'),
        Index('idx_progress_created_at', 'created_at'),
        Index('idx_progress_composite', 'job_id', 'tenant_id', 'step'),  # 검색 성능용
    )
