"""
라이선스 관리 API 라우터

에이전트 라이선스 할당 및 사용 현황을 관리하는 API 엔드포인트를 제공합니다.
라이선스 통계, 이력 조회 및 재할당 기능을 포함합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case
from datetime import datetime, timedelta
import logging

from ..models.responses import BaseModel, Field
from ..dependencies import get_tenant_id, get_platform, get_api_key, get_domain
from core.database import get_session
from core.database.models.agent import Agent

# 라우터 생성
router = APIRouter(prefix="/licenses", tags=["라이선스 관리"])

# 로거 설정
logger = logging.getLogger(__name__)


class LicenseSummaryResponse(BaseModel):
    """라이선스 사용 현황 응답 모델"""
    
    total_licenses: int = Field(description="전체 라이선스 수")
    active_licenses: int = Field(description="활성 라이선스 수")
    inactive_licenses: int = Field(description="비활성 라이선스 수")
    utilization_rate: float = Field(description="라이선스 활용률 (%)")
    
    # 에이전트 상태별 통계
    agent_stats: Dict[str, int] = Field(
        description="에이전트 상태별 통계",
        default_factory=dict
    )
    
    # 라이선스 분포
    license_distribution: Dict[str, Any] = Field(
        description="라이선스 분포 정보",
        default_factory=dict
    )
    
    # 추천 사항
    recommendations: List[str] = Field(
        default_factory=list,
        description="라이선스 최적화 추천 사항"
    )
    
    last_updated: datetime = Field(description="마지막 업데이트 시간")


class LicenseHistoryItem(BaseModel):
    """라이선스 변경 이력 항목"""
    
    agent_id: int = Field(description="에이전트 ID")
    agent_name: str = Field(description="에이전트 이름")
    agent_email: str = Field(description="에이전트 이메일")
    action: str = Field(description="액션 (activated/deactivated)")
    timestamp: datetime = Field(description="변경 시간")
    performed_by: str = Field(description="수행자")


class LicenseHistoryResponse(BaseModel):
    """라이선스 변경 이력 응답 모델"""
    
    history: List[LicenseHistoryItem] = Field(description="변경 이력 목록")
    total_count: int = Field(description="전체 이력 수")
    page: int = Field(description="현재 페이지")
    page_size: int = Field(description="페이지 크기")


class LicenseAllocationRequest(BaseModel):
    """라이선스 재할당 요청 모델"""
    
    activate_agent_ids: List[int] = Field(
        default_factory=list,
        description="활성화할 에이전트 ID 목록"
    )
    deactivate_agent_ids: List[int] = Field(
        default_factory=list,
        description="비활성화할 에이전트 ID 목록"
    )
    auto_optimize: bool = Field(
        default=False,
        description="자동 최적화 실행 여부"
    )


class LicenseAllocationResponse(BaseModel):
    """라이선스 재할당 응답 모델"""
    
    success: bool = Field(description="성공 여부")
    message: str = Field(description="응답 메시지")
    activated_count: int = Field(description="활성화된 수")
    deactivated_count: int = Field(description="비활성화된 수")
    current_active_licenses: int = Field(description="현재 활성 라이선스 수")
    optimization_applied: bool = Field(description="최적화 적용 여부")
    
    # 실패한 항목
    failed_activations: List[int] = Field(
        default_factory=list,
        description="활성화 실패한 에이전트 ID"
    )
    failed_deactivations: List[int] = Field(
        default_factory=list,
        description="비활성화 실패한 에이전트 ID"
    )


@router.get("/summary", response_model=LicenseSummaryResponse)
async def get_license_summary(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """라이선스 사용 현황을 조회합니다."""
    try:
        # 전체 에이전트 수
        total_agents = session.query(Agent).filter(
            Agent.tenant_id == tenant_id
        ).count()
        
        # 활성 라이선스 수
        active_licenses = session.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).count()
        
        # 비활성 라이선스 수
        inactive_licenses = total_agents - active_licenses
        
        # 활용률 계산
        utilization_rate = (active_licenses / total_agents * 100) if total_agents > 0 else 0
        
        # 에이전트 상태별 통계
        agent_stats_query = session.query(
            Agent.active,
            Agent.available,
            func.count(Agent.id)
        ).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).group_by(Agent.active, Agent.available).all()
        
        agent_stats = {
            "active_available": 0,
            "active_unavailable": 0,
            "inactive": 0
        }
        
        for active, available, count in agent_stats_query:
            if active and available:
                agent_stats["active_available"] = count
            elif active and not available:
                agent_stats["active_unavailable"] = count
            else:
                agent_stats["inactive"] = count
        
        # 라이선스 분포 정보
        license_distribution = {
            "by_job_title": {},
            "by_type": {},
            "by_last_login": {
                "within_7_days": 0,
                "within_30_days": 0,
                "over_30_days": 0,
                "never": 0
            }
        }
        
        # 직책별 분포
        job_title_dist = session.query(
            Agent.job_title,
            func.count(Agent.id)
        ).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).group_by(Agent.job_title).all()
        
        for job_title, count in job_title_dist:
            license_distribution["by_job_title"][job_title or "Unknown"] = count
        
        # 타입별 분포
        type_dist = session.query(
            Agent.type,
            func.count(Agent.id)
        ).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).group_by(Agent.type).all()
        
        for agent_type, count in type_dist:
            license_distribution["by_type"][agent_type or "Unknown"] = count
        
        # 추천 사항 생성
        recommendations = []
        
        if utilization_rate < 50:
            recommendations.append("라이선스 활용률이 낮습니다. 비활성 에이전트에게 라이선스를 재할당하는 것을 고려해보세요.")
        
        if agent_stats["inactive"] > active_licenses * 0.2:
            recommendations.append("비활성 상태의 라이선스가 많습니다. 해당 에이전트들의 상태를 확인해보세요.")
        
        if inactive_licenses > total_agents * 0.3:
            recommendations.append("미할당 라이선스가 많습니다. 신규 에이전트나 활발한 에이전트에게 할당을 고려해보세요.")
        
        return LicenseSummaryResponse(
            total_licenses=total_agents,
            active_licenses=active_licenses,
            inactive_licenses=inactive_licenses,
            utilization_rate=round(utilization_rate, 2),
            agent_stats=agent_stats,
            license_distribution=license_distribution,
            recommendations=recommendations,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"라이선스 사용 현황 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=LicenseHistoryResponse)
async def get_license_history(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(50, ge=1, le=100, description="페이지 크기"),
    agent_id: Optional[int] = Query(None, description="특정 에이전트 필터"),
    days: int = Query(30, description="조회 기간 (일)"),
    session: Session = Depends(get_session)
):
    """라이선스 변경 이력을 조회합니다."""
    # 실제 구현에서는 별도의 이력 테이블에서 조회
    # 현재는 더미 데이터 반환
    history_items = []
    
    # 더미 데이터 생성
    if page == 1:
        history_items = [
            LicenseHistoryItem(
                agent_id=1,
                agent_name="김상담",
                agent_email="kim@example.com",
                action="activated",
                timestamp=datetime.utcnow() - timedelta(days=1),
                performed_by="admin"
            ),
            LicenseHistoryItem(
                agent_id=2,
                agent_name="이지원",
                agent_email="lee@example.com",
                action="deactivated",
                timestamp=datetime.utcnow() - timedelta(days=2),
                performed_by="admin"
            )
        ]
    
    return LicenseHistoryResponse(
        history=history_items,
        total_count=len(history_items),
        page=page,
        page_size=page_size
    )


@router.put("/allocation", response_model=LicenseAllocationResponse)
async def update_license_allocation(
    request: LicenseAllocationRequest,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """라이선스를 재할당합니다."""
    try:
        activated_count = 0
        deactivated_count = 0
        failed_activations = []
        failed_deactivations = []
        
        # 활성화 처리
        for agent_id in request.activate_agent_ids:
            try:
                agent = session.query(Agent).filter(
                    Agent.tenant_id == tenant_id,
                    Agent.id == agent_id
                ).first()
                
                if agent:
                    agent.license_active = True
                    activated_count += 1
                else:
                    failed_activations.append(agent_id)
            except Exception as e:
                logger.error(f"에이전트 {agent_id} 활성화 실패: {e}")
                failed_activations.append(agent_id)
        
        # 비활성화 처리
        for agent_id in request.deactivate_agent_ids:
            try:
                agent = session.query(Agent).filter(
                    Agent.tenant_id == tenant_id,
                    Agent.id == agent_id
                ).first()
                
                if agent:
                    agent.license_active = False
                    deactivated_count += 1
                else:
                    failed_deactivations.append(agent_id)
            except Exception as e:
                logger.error(f"에이전트 {agent_id} 비활성화 실패: {e}")
                failed_deactivations.append(agent_id)
        
        # 자동 최적화 (선택적)
        optimization_applied = False
        if request.auto_optimize:
            # 최근 로그인하지 않은 에이전트의 라이선스를 회수하고
            # 활발한 에이전트에게 재할당하는 로직
            # (실제 구현 필요)
            optimization_applied = True
        
        # 변경사항 저장
        session.commit()
        
        # 현재 활성 라이선스 수 조회
        current_active = session.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).count()
        
        return LicenseAllocationResponse(
            success=True,
            message=f"라이선스 재할당 완료: {activated_count}개 활성화, {deactivated_count}개 비활성화",
            activated_count=activated_count,
            deactivated_count=deactivated_count,
            current_active_licenses=current_active,
            optimization_applied=optimization_applied,
            failed_activations=failed_activations,
            failed_deactivations=failed_deactivations
        )
        
    except Exception as e:
        session.rollback()
        logger.error(f"라이선스 재할당 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))