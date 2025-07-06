"""
에이전트 관리 API 라우터

Freshdesk 에이전트(상담원) 정보를 관리하는 API 엔드포인트를 제공합니다.
라이선스 할당/해제 및 에이전트 상태 관리 기능을 포함합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from ..models.responses import (
    AgentResponse, AgentListResponse, LicenseUpdateResponse,
    BulkLicenseUpdateRequest, BulkLicenseUpdateResponse
)
from ..dependencies import get_tenant_id, get_platform, get_api_key, get_domain
from core.database import get_session
from core.repositories.agent_repository import AgentRepository
from core.database.models.agent import Agent

# 라우터 생성
router = APIRouter(prefix="/agents", tags=["에이전트 관리"])

# 동기화 라우터 포함
from .agents_sync import router as sync_router
router.include_router(sync_router)

# 로거 설정
logger = logging.getLogger(__name__)


@router.get("", response_model=AgentListResponse)
async def get_agents(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    license_active: Optional[bool] = Query(None, description="라이선스 활성화 필터"),
    active: Optional[bool] = Query(None, description="에이전트 활성화 필터"),
    search: Optional[str] = Query(None, description="이름/이메일 검색"),
    session: Session = Depends(get_session)
):
    """
    에이전트 목록을 조회합니다.
    
    필터링 옵션:
    - license_active: 라이선스 활성화 상태로 필터
    - active: 에이전트 활성화 상태로 필터
    - search: 이름 또는 이메일로 검색
    """
    try:
        repo = AgentRepository(session)
        
        # 기본 쿼리
        query = session.query(Agent).filter(Agent.tenant_id == tenant_id)
        
        # 필터 적용
        if license_active is not None:
            query = query.filter(Agent.license_active == license_active)
        if active is not None:
            query = query.filter(Agent.active == active)
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Agent.name.ilike(search_pattern)) | 
                (Agent.email.ilike(search_pattern))
            )
        
        # 전체 개수
        total_count = query.count()
        
        # 페이지네이션
        offset = (page - 1) * page_size
        agents = query.offset(offset).limit(page_size).all()
        
        # 라이선스 통계
        license_stats = {
            "total_licenses": session.query(Agent).filter(
                Agent.tenant_id == tenant_id
            ).count(),
            "active_licenses": session.query(Agent).filter(
                Agent.tenant_id == tenant_id,
                Agent.license_active == True
            ).count()
        }
        
        return AgentListResponse(
            agents=[AgentResponse.from_orm(agent) for agent in agents],
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size,
            license_stats=license_stats
        )
        
    except Exception as e:
        logger.error(f"에이전트 목록 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """특정 에이전트 정보를 조회합니다."""
    try:
        repo = AgentRepository(session)
        agent = repo.get_agent_by_id(tenant_id, agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다")
            
        return AgentResponse.from_orm(agent)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"에이전트 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}/license", response_model=LicenseUpdateResponse)
async def update_agent_license(
    agent_id: int,
    license_active: bool,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """에이전트의 라이선스 상태를 변경합니다."""
    try:
        repo = AgentRepository(session)
        
        # 라이선스 상태 업데이트
        success = repo.update_license_status(tenant_id, agent_id, license_active)
        
        if not success:
            raise HTTPException(status_code=404, detail="에이전트를 찾을 수 없습니다")
        
        # 업데이트된 에이전트 정보 조회
        agent = repo.get_agent_by_id(tenant_id, agent_id)
        
        # 현재 라이선스 통계
        active_licenses = session.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).count()
        
        return LicenseUpdateResponse(
            agent_id=agent_id,
            license_active=license_active,
            updated_at=datetime.utcnow(),
            agent_name=agent.name,
            agent_email=agent.email,
            active_licenses_count=active_licenses
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"라이선스 상태 업데이트 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-license", response_model=BulkLicenseUpdateResponse)
async def bulk_update_license(
    request: BulkLicenseUpdateRequest,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """여러 에이전트의 라이선스를 일괄 변경합니다."""
    try:
        repo = AgentRepository(session)
        
        success_count = 0
        failed_ids = []
        
        for agent_id in request.agent_ids:
            success = repo.update_license_status(
                tenant_id, 
                agent_id, 
                request.license_active
            )
            if success:
                success_count += 1
            else:
                failed_ids.append(agent_id)
        
        # 현재 라이선스 통계
        active_licenses = session.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.license_active == True
        ).count()
        
        return BulkLicenseUpdateResponse(
            total_requested=len(request.agent_ids),
            success_count=success_count,
            failed_count=len(failed_ids),
            failed_agent_ids=failed_ids,
            active_licenses_count=active_licenses
        )
        
    except Exception as e:
        logger.error(f"일괄 라이선스 업데이트 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active", response_model=AgentListResponse)
async def get_active_agents(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    session: Session = Depends(get_session)
):
    """라이선스가 활성화된 에이전트만 조회합니다."""
    try:
        repo = AgentRepository(session)
        agents = repo.get_active_agents_by_tenant(tenant_id)
        
        return AgentListResponse(
            agents=[AgentResponse.from_orm(agent) for agent in agents],
            total_count=len(agents),
            page=1,
            page_size=len(agents),
            total_pages=1,
            license_stats={
                "total_licenses": session.query(Agent).filter(
                    Agent.tenant_id == tenant_id
                ).count(),
                "active_licenses": len(agents)
            }
        )
        
    except Exception as e:
        logger.error(f"활성 에이전트 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))