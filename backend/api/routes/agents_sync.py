"""
에이전트 동기화 API 라우터

Freshdesk에서 에이전트 정보를 동기화하는 API 엔드포인트를 제공합니다.
실시간 동기화 및 동기화 상태 모니터링 기능을 포함합니다.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging
import asyncio

from ..models.responses import BaseModel, Field
from ..dependencies import (
    get_tenant_id, get_platform, get_api_key, get_domain,
    get_fetcher, get_tenant_config, get_session
)
from core.repositories.agent_repository import AgentRepository
from core.schemas.agent import normalize_agent_data

# 라우터 생성
router = APIRouter(prefix="/agents/sync", tags=["에이전트 동기화"])

# 로거 설정
logger = logging.getLogger(__name__)

# 동기화 상태 저장 (메모리 캐시)
sync_status: Dict[str, Dict[str, Any]] = {}


class AgentSyncRequest(BaseModel):
    """에이전트 동기화 요청 모델"""
    force_refresh: bool = Field(
        default=False, 
        description="캐시를 무시하고 강제로 새로고침"
    )


class AgentSyncResponse(BaseModel):
    """에이전트 동기화 응답 모델"""
    
    job_id: str = Field(description="동기화 작업 ID")
    status: str = Field(description="동기화 상태 (started, in_progress, completed, failed)")
    message: str = Field(description="상태 메시지")
    started_at: datetime = Field(description="시작 시간")
    completed_at: Optional[datetime] = Field(default=None, description="완료 시간")
    total_agents: Optional[int] = Field(default=None, description="전체 에이전트 수")
    synced_agents: Optional[int] = Field(default=None, description="동기화된 에이전트 수")
    failed_agents: Optional[int] = Field(default=None, description="실패한 에이전트 수")
    error: Optional[str] = Field(default=None, description="오류 메시지")


class AgentSyncStatusResponse(BaseModel):
    """에이전트 동기화 상태 응답 모델"""
    
    job_id: str = Field(description="동기화 작업 ID")
    status: str = Field(description="동기화 상태")
    progress_percent: float = Field(description="진행률 (%)")
    message: str = Field(description="상태 메시지")
    started_at: datetime = Field(description="시작 시간")
    updated_at: datetime = Field(description="마지막 업데이트 시간")
    completed_at: Optional[datetime] = Field(default=None, description="완료 시간")
    duration_seconds: Optional[float] = Field(default=None, description="소요 시간 (초)")
    details: Dict[str, Any] = Field(default_factory=dict, description="상세 정보")


async def sync_agents_task(
    job_id: str,
    tenant_id: str,
    platform: str,
    fetcher,
    session: Session
):
    """백그라운드에서 에이전트 동기화를 수행하는 태스크"""
    try:
        # 상태 업데이트
        sync_status[job_id] = {
            "status": "in_progress",
            "message": "에이전트 정보를 가져오는 중...",
            "progress_percent": 10.0,
            "started_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "total_agents": 0,
            "synced_agents": 0,
            "failed_agents": 0
        }
        
        # Freshdesk에서 에이전트 목록 가져오기
        logger.info(f"[{job_id}] Freshdesk에서 에이전트 목록 가져오기 시작")
        agents = await fetcher.get_agents()
        
        total_agents = len(agents)
        logger.info(f"[{job_id}] 총 {total_agents}명의 에이전트 발견")
        
        sync_status[job_id].update({
            "total_agents": total_agents,
            "message": f"{total_agents}명의 에이전트를 동기화하는 중...",
            "progress_percent": 20.0,
            "updated_at": datetime.utcnow()
        })
        
        # 에이전트 저장
        repo = AgentRepository(session)
        synced_count = 0
        failed_count = 0
        
        for i, agent in enumerate(agents):
            try:
                # 진행률 업데이트
                progress = 20 + (70 * (i / total_agents))
                sync_status[job_id].update({
                    "progress_percent": progress,
                    "message": f"에이전트 {i+1}/{total_agents} 처리 중: {agent.get('contact', {}).get('name', 'Unknown')}",
                    "updated_at": datetime.utcnow()
                })
                
                # 에이전트 데이터 정규화
                normalized_agent = normalize_agent_data(agent, tenant_id, platform)
                
                # 데이터베이스에 저장
                repo.upsert_agent(normalized_agent)
                synced_count += 1
                
            except Exception as e:
                logger.error(f"[{job_id}] 에이전트 저장 실패 (ID: {agent.get('id')}): {e}")
                failed_count += 1
        
        # 동기화 완료
        completed_at = datetime.utcnow()
        duration = (completed_at - sync_status[job_id]["started_at"]).total_seconds()
        
        sync_status[job_id].update({
            "status": "completed",
            "message": f"동기화 완료: {synced_count}명 성공, {failed_count}명 실패",
            "progress_percent": 100.0,
            "completed_at": completed_at,
            "updated_at": completed_at,
            "synced_agents": synced_count,
            "failed_agents": failed_count,
            "duration_seconds": duration
        })
        
        logger.info(f"[{job_id}] 에이전트 동기화 완료: {synced_count}/{total_agents} 성공")
        
    except Exception as e:
        logger.error(f"[{job_id}] 에이전트 동기화 중 오류 발생: {e}")
        sync_status[job_id].update({
            "status": "failed",
            "message": "동기화 중 오류가 발생했습니다",
            "error": str(e),
            "progress_percent": sync_status[job_id].get("progress_percent", 0),
            "updated_at": datetime.utcnow(),
            "completed_at": datetime.utcnow()
        })


@router.post("", response_model=AgentSyncResponse)
async def sync_agents(
    request: AgentSyncRequest,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    tenant_config = Depends(get_tenant_config),
    fetcher = Depends(get_fetcher),
    session: Session = Depends(get_session)
):
    """
    Freshdesk에서 에이전트 정보를 동기화합니다.
    
    백그라운드 작업으로 실행되며, 작업 ID를 반환합니다.
    작업 상태는 /agents/sync/status/{job_id} 엔드포인트에서 확인할 수 있습니다.
    """
    try:
        # 작업 ID 생성
        job_id = f"agent_sync_{tenant_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # 초기 상태 설정
        sync_status[job_id] = {
            "status": "started",
            "message": "에이전트 동기화를 시작합니다",
            "progress_percent": 0.0,
            "started_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # 백그라운드 태스크 시작
        background_tasks.add_task(
            sync_agents_task,
            job_id=job_id,
            tenant_id=tenant_id,
            platform=platform,
            fetcher=fetcher,
            session=session
        )
        
        return AgentSyncResponse(
            job_id=job_id,
            status="started",
            message="에이전트 동기화 작업이 시작되었습니다",
            started_at=sync_status[job_id]["started_at"]
        )
        
    except Exception as e:
        logger.error(f"에이전트 동기화 시작 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}", response_model=AgentSyncStatusResponse)
async def get_sync_status(
    job_id: str,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain)
):
    """특정 동기화 작업의 상태를 조회합니다."""
    
    # 작업 ID가 해당 테넌트의 것인지 확인
    if not job_id.startswith(f"agent_sync_{tenant_id}_"):
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    
    # 작업 상태 조회
    if job_id not in sync_status:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    status_data = sync_status[job_id]
    
    # 응답 생성
    response = AgentSyncStatusResponse(
        job_id=job_id,
        status=status_data["status"],
        progress_percent=status_data.get("progress_percent", 0),
        message=status_data.get("message", ""),
        started_at=status_data["started_at"],
        updated_at=status_data["updated_at"],
        completed_at=status_data.get("completed_at"),
        duration_seconds=status_data.get("duration_seconds"),
        details={
            "total_agents": status_data.get("total_agents", 0),
            "synced_agents": status_data.get("synced_agents", 0),
            "failed_agents": status_data.get("failed_agents", 0),
            "error": status_data.get("error")
        }
    )
    
    return response


@router.get("/latest", response_model=AgentSyncStatusResponse)
async def get_latest_sync_status(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain)
):
    """가장 최근의 동기화 작업 상태를 조회합니다."""
    
    # 해당 테넌트의 작업만 필터링
    tenant_jobs = [
        (job_id, data) for job_id, data in sync_status.items()
        if job_id.startswith(f"agent_sync_{tenant_id}_")
    ]
    
    if not tenant_jobs:
        raise HTTPException(status_code=404, detail="동기화 작업 기록이 없습니다")
    
    # 가장 최근 작업 찾기
    latest_job = max(tenant_jobs, key=lambda x: x[1]["started_at"])
    job_id, status_data = latest_job
    
    # 응답 생성
    response = AgentSyncStatusResponse(
        job_id=job_id,
        status=status_data["status"],
        progress_percent=status_data.get("progress_percent", 0),
        message=status_data.get("message", ""),
        started_at=status_data["started_at"],
        updated_at=status_data["updated_at"],
        completed_at=status_data.get("completed_at"),
        duration_seconds=status_data.get("duration_seconds"),
        details={
            "total_agents": status_data.get("total_agents", 0),
            "synced_agents": status_data.get("synced_agents", 0),
            "failed_agents": status_data.get("failed_agents", 0),
            "error": status_data.get("error")
        }
    )
    
    return response