"""
SQLAlchemy ORM 모델

통합 객체 기반 데이터베이스 모델들을 정의합니다.
"""

from .base import Base
# 먼저 기본 모델들을 로드
from .ticket import Ticket
from .conversation import Conversation
from .attachment import Attachment
from .summary import Summary
from .processing_log import ProcessingLog
from .assignment import Assignment
# 그 다음 관계를 가진 모델들을 로드
from .company import Company
from .category import Category
from .agent import Agent
from .integrated_object import IntegratedObject

__all__ = [
    "Base",
    "Company",
    "Agent", 
    "Category",
    "IntegratedObject",
    "Ticket",
    "Conversation",
    "Attachment",
    "Summary",
    "ProcessingLog"
]
