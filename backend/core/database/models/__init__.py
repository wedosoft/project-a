"""
SQLAlchemy ORM 모델

Freshdesk 통합을 위한 데이터베이스 ORM 모델들을 정의합니다.
이 모델들은 Freshdesk 데이터를 로컬 데이터베이스에 저장하고 관리하기 위해 사용됩니다.

Usage:
    from core.database.models import Ticket, Attachment, Company
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
    # 기본 클래스
    "Base",
    
    # 주요 엔티티
    "Ticket",
    "Attachment", 
    "Conversation",
    "Summary",
    
    # 조직 및 사용자
    "Company",
    "Agent",
    "Assignment",
    
    # 분류 및 메타데이터
    "Category",
    "IntegratedObject",
    "ProcessingLog"
]
