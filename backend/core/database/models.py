"""
통합 객체 중심 ORM 모델

SQLAlchemy ORM을 사용하여 통합 객체 스키마를 구현
기존 SQLite 구조와 PostgreSQL 구조 모두 지원
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index, DECIMAL, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
import os

# 환경별 Base 클래스
Base = declarative_base()

# 데이터베이스 타입에 따른 JSON 타입 선택
def get_json_type():
    """데이터베이스 타입에 따른 JSON 컬럼 타입 반환"""
    database_url = os.getenv('DATABASE_URL', '')
    if 'postgresql' in database_url:
        return JSONB
    else:
        return Text  # SQLite의 경우 TEXT로 JSON 저장


# =====================================================
# 📊 SaaS 라이선스 관리 모델
# =====================================================

class SubscriptionPlan(Base):
    """구독 플랜"""
    __tablename__ = 'subscription_plans'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    
    # 기본 포함 사항
    base_seats = Column(Integer, nullable=False)
    base_monthly_cost = Column(DECIMAL(10, 2), nullable=False)
    additional_seat_cost = Column(DECIMAL(10, 2), nullable=False)
    
    # 제한사항
    max_seats = Column(Integer, nullable=True)
    max_tickets_per_month = Column(Integer, nullable=True)
    max_api_calls_per_day = Column(Integer, nullable=True)
    
    # 기능 플래그
    features = Column(get_json_type(), nullable=False)
    
    # 메타데이터
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    companies = relationship("Company", back_populates="subscription_plan")


class Company(Base):
    """고객사 정보"""
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 기본 정보
    company_name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True, nullable=False)
    contact_email = Column(String(255), nullable=False)
    
    # 구독 정보
    subscription_plan_id = Column(Integer, ForeignKey('subscription_plans.id'), nullable=False)
    purchased_seats = Column(Integer, nullable=False)
    used_seats = Column(Integer, default=0)
    
    # 결제 정보
    billing_status = Column(String(20), default='active')
    billing_cycle = Column(String(20), default='monthly')
    monthly_cost = Column(DECIMAL(10, 2), nullable=False)
    
    # 시간 정보
    subscription_start_date = Column(DateTime, nullable=False)
    subscription_end_date = Column(DateTime, nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # 관계
    subscription_plan = relationship("SubscriptionPlan", back_populates="companies")
    agents = relationship("Agent", back_populates="company")
    usage_logs = relationship("UsageLog", back_populates="company")


class Agent(Base):
    """에이전트 정보"""
    __tablename__ = 'agents'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # 기본 정보
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    freshdesk_agent_id = Column(Integer, nullable=True)
    
    # 역할 정보
    role = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    
    # 시트 관리
    seat_assigned = Column(Boolean, default=False)
    assigned_by = Column(Integer, ForeignKey('agents.id'), nullable=True)
    assigned_at = Column(DateTime, nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # 관계
    company = relationship("Company", back_populates="agents")
    assigned_by_agent = relationship("Agent", remote_side=[id])
    usage_logs = relationship("UsageLog", back_populates="agent")
    
    # 제약 조건
    __table_args__ = (
        Index('idx_agents_company_email', 'tenant_id', 'email', unique=True),
        Index('idx_agents_company_freshdesk', 'tenant_id', 'freshdesk_agent_id', unique=True),
    )


class UsageLog(Base):
    """사용량 추적 로그"""
    __tablename__ = 'usage_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    agent_id = Column(Integer, ForeignKey('agents.id'), nullable=True)
    
    # 사용량 정보
    usage_type = Column(String(50), nullable=False)
    usage_count = Column(Integer, default=1)
    
    # 세부 정보
    resource_id = Column(String(255), nullable=True)
    metadata = Column(get_json_type(), nullable=True)
    
    # 시간 정보
    usage_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    company = relationship("Company", back_populates="usage_logs")
    agent = relationship("Agent", back_populates="usage_logs")


# =====================================================
# 🗂️ [DEPRECATED] 통합 객체 모델 - Vector DB 단독 모드로 전환됨
# =====================================================

# IntegratedObject 모델 제거됨 - 모든 데이터는 Vector DB에 저장
# 하위 호환성을 위해 빈 클래스만 유지
class IntegratedObject(Base):
    """[DEPRECATED] 통합 객체 모델 - Vector DB 단독 모드로 전환됨"""
    __tablename__ = 'integrated_objects_deprecated'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # 모든 필드 제거됨 - Vector DB 사용


class AIProcessingLog(Base):
    """[DEPRECATED] AI 처리 로그 - Vector DB 단독 모드로 전환됨"""
    __tablename__ = 'ai_processing_logs_deprecated'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # integrated_object_id 제거됨 - Vector DB 사용
    
    # 처리 정보
    processing_type = Column(String(50), nullable=False)
    model_used = Column(String(100), nullable=False)
    
    # 성능 정보
    processing_time_ms = Column(Integer, nullable=True)
    token_usage = Column(get_json_type(), nullable=True)
    cost_estimate = Column(DECIMAL(10, 4), nullable=True)
    
    # 품질 정보
    quality_score = Column(DECIMAL(3, 2), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 시간 정보
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    integrated_object = relationship("IntegratedObject", back_populates="ai_processing_logs")


# =====================================================
# 🔧 시스템 설정 모델
# =====================================================

class SystemSetting(Base):
    """시스템 전체 설정"""
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False)
    setting_value = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CompanySetting(Base):
    """회사별 개별 설정"""
    __tablename__ = 'company_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    # 제약 조건
    __table_args__ = (
        Index('idx_company_settings_unique', 'tenant_id', 'setting_key', unique=True),
    )


class CollectionLog(Base):
    """수집 로그 (통합 객체 기반)"""
    __tablename__ = 'collection_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    platform = Column(String(50), nullable=False, default='freshdesk')
    
    # 수집 정보
    collection_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    
    # 통계 (통합 객체 기반)
    total_items = Column(Integer, default=0)
    successful_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    integrated_objects_created = Column(Integer, default=0)
    
    # 메시지
    message = Column(Text, nullable=True)
    error_details = Column(get_json_type(), nullable=True)
    
    # 시간 정보
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# =====================================================
# 💰 결제 관리 모델
# =====================================================

class BillingHistory(Base):
    """결제 이력"""
    __tablename__ = 'billing_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    
    # 결제 정보
    billing_period_start = Column(DateTime, nullable=False)
    billing_period_end = Column(DateTime, nullable=False)
    
    # 요금 계산
    base_cost = Column(DECIMAL(10, 2), nullable=False)
    additional_seats = Column(Integer, default=0)
    additional_seat_cost = Column(DECIMAL(10, 2), default=0)
    total_cost = Column(DECIMAL(10, 2), nullable=False)
    
    # 결제 상태
    status = Column(String(20), default='pending')
    paid_at = Column(DateTime, nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
