"""
카테고리 모델
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from .base import MultiTenantModel


class Category(MultiTenantModel):
    """카테고리 정보"""
    __tablename__ = 'categories'
    
    external_id = Column(String(100))  # 외부 플랫폼의 카테고리 ID
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    parent_id = Column(Integer, ForeignKey('categories.id'))
    level = Column(Integer, default=0)
    path = Column(String)  # 계층 경로
    
    # 관계 설정
    company = relationship("Company", back_populates="categories")
    parent = relationship("Category", remote_side='Category.id', backref='children')
    tickets = relationship("Ticket", back_populates="category")
    
    # 추가 설정
    settings = Column(JSON)  # 카테고리별 설정
    
    # 인덱스 및 제약조건
    __table_args__ = (
        Index('idx_category_external', 'company_id', 'platform', 'external_id', unique=True),
        Index('idx_category_parent', 'parent_id'),
        Index('idx_category_tenant', 'company_id', 'platform'),
    )
