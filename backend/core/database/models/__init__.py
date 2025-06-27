"""
SQLAlchemy ORM 모델

Freshdesk 통합을 위한 데이터베이스 ORM 모델들을 정의합니다.
이 모델들은 Freshdesk 데이터를 로컬 데이터베이스에 저장하고 관리하기 위해 사용됩니다.

Usage:
    from core.database.models import Company, Agent, IntegratedObject
"""

from .base import Base
# 핵심 모델들만 로드
from .company import Company
from .agent import Agent
from .integrated_object import IntegratedObject
from .progress_log import ProgressLog

__all__ = [
    # 기본 클래스
    "Base",
    
    # 핵심 엔티티
    "Company",
    "Agent", 
    "IntegratedObject",
    "ProgressLog"
]
