"""
데이터 수집 작업 관리 라우터

이 모듈은 데이터 수집 작업의 생성, 제어, 모니터링을 담당하는 엔드포인트를 제공합니다.

주요 기능:
- 백그라운드 작업 생성 및 시작
- 작업 일시정지/재개/취소 제어
- 작업 목록 및 상태 조회
- 작업 메트릭스 및 성능 지표
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import Optional
import logging

from ..models.requests import IngestRequest
from ..models.ingest_job import (
    IngestJobConfig, 
    JobControlRequest, 
    JobListResponse, 
    JobStatusResponse,
    JobMetrics,
    JobStatus
)
from ..dependencies import get_tenant_id, get_platform, get_api_key, get_domain
from ..services.job_manager import job_manager

# 라우터 생성 (prefix 제거 - 메인 라우터에서 설정)
router = APIRouter(tags=["작업 관리 & 메트릭스"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.post("/jobs", response_model=JobStatusResponse)
async def create_ingest_job(
    request: IngestRequest,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: Optional[str] = Depends(get_api_key),
    domain: Optional[str] = Depends(get_domain)
):
    """
    새로운 데이터 수집 작업을 생성합니다 (비동기 실행, 멀티플랫폼 지원)
    
    이 엔드포인트는 작업을 백그라운드에서 실행하며,
    일시정지/재개/취소 등의 제어가 가능합니다.
    
    **새로운 표준 헤더 (권장):**
    - X-Tenant-ID, X-Platform, X-Domain, X-API-Key
    
    **레거시 헤더 (하위 호환성):**
    - X-Platform-Domain, X-Platform-API-Key 등
    
    Args:
        request: 데이터 수집 옵션
        tenant_id: 테넌트 ID
        platform: 플랫폼 식별자
        api_key: 플랫폼 API 키
        domain: 플랫폼 도메인
        
    Returns:
        JobStatusResponse: 생성된 작업 정보
    """
    logger.info(f"새 데이터 수집 작업 생성 요청 - Company: {tenant_id}, Platform: {platform}")
    
    # 작업 설정 생성
    config = IngestJobConfig(
        incremental=request.incremental,
        purge=request.purge,
        process_attachments=request.process_attachments,
        force_rebuild=request.force_rebuild,
        include_kb=request.include_kb,
        start_date=request.start_date,  # 시작 날짜 추가
        domain=domain,
        api_key=api_key
    )
    
    # 작업 생성
    job = job_manager.create_job(tenant_id, config)
    
    # 즉시 시작
    success = job_manager.start_job(job.job_id)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="작업을 시작할 수 없습니다. 최대 동시 실행 수를 초과했을 수 있습니다."
        )
    
    logger.info(f"데이터 수집 작업 시작됨: {job.job_id}")
    
    return JobStatusResponse(
        job=job,
        is_active=True,
        can_pause=True,
        can_resume=False,
        can_cancel=True
    )

@router.get("/jobs", response_model=JobListResponse)
async def list_ingest_jobs(
    tenant_id: str = Depends(get_tenant_id),
    status: Optional[JobStatus] = Query(None, description="작업 상태 필터"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 항목 수")
):
    """
    데이터 수집 작업 목록을 조회합니다
    
    Args:
        tenant_id: 테넌트 ID
        status: 작업 상태 필터 (선택사항)
        page: 페이지 번호
        per_page: 페이지당 항목 수
        
    Returns:
        JobListResponse: 작업 목록
    """
    offset = (page - 1) * per_page
    jobs = job_manager.list_jobs(
        tenant_id=tenant_id,
        status=status,
        limit=per_page,
        offset=offset
    )
    
    # 전체 개수 계산 (실제로는 DB 쿼리에서 COUNT를 사용해야 함)
    all_jobs = job_manager.list_jobs(tenant_id=tenant_id, status=status, limit=1000)
    total = len(all_jobs)
    
    return JobListResponse(
        jobs=jobs,
        total=total,
        page=page,
        per_page=per_page
    )

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_ingest_job_status(
    job_id: str,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    특정 데이터 수집 작업의 상태를 조회합니다
    
    Args:
        job_id: 작업 ID
        tenant_id: 테넌트 ID
        
    Returns:
        JobStatusResponse: 작업 상태 정보
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    if job.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    
    # 제어 가능 여부 판단
    is_active = job.status in [JobStatus.RUNNING, JobStatus.PAUSED]
    can_pause = job.status == JobStatus.RUNNING
    can_resume = job.status == JobStatus.PAUSED
    can_cancel = job.status in [JobStatus.RUNNING, JobStatus.PAUSED, JobStatus.PENDING]
    
    return JobStatusResponse(
        job=job,
        is_active=is_active,
        can_pause=can_pause,
        can_resume=can_resume,
        can_cancel=can_cancel
    )

@router.post("/jobs/{job_id}/control")
async def control_ingest_job(
    job_id: str,
    request: JobControlRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    데이터 수집 작업을 제어합니다 (일시정지/재개/취소)
    
    Args:
        job_id: 작업 ID
        request: 제어 요청 (action: pause, resume, cancel)
        tenant_id: 테넌트 ID
        
    Returns:
        작업 제어 결과
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    if job.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다")
    
    success = False
    message = ""
    
    if request.action == "pause":
        success = job_manager.pause_job(job_id)
        message = "작업이 일시정지되었습니다" if success else "작업을 일시정지할 수 없습니다"
        
    elif request.action == "resume":
        success = job_manager.resume_job(job_id)
        message = "작업이 재개되었습니다" if success else "작업을 재개할 수 없습니다"
        
    elif request.action == "cancel":
        success = job_manager.cancel_job(job_id)
        message = "작업이 취소되었습니다" if success else "작업을 취소할 수 없습니다"
        
    else:
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 액션입니다. (pause, resume, cancel 중 선택)"
        )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # 사유 로깅
    if request.reason:
        job.logs.append(f"{datetime.now().isoformat()} - {request.action}: {request.reason}")
    
    logger.info(f"작업 제어: {job_id}, 액션: {request.action}, 사유: {request.reason}")
    
    return {
        "success": True,
        "message": message,
        "job_id": job_id,
        "action": request.action
    }

@router.get("/metrics", response_model=JobMetrics)
async def get_ingest_job_metrics(
    tenant_id: str = Depends(get_tenant_id)
):
    """
    데이터 수집 작업 메트릭스를 조회합니다
    
    Args:
        tenant_id: 테넌트 ID
        
    Returns:
        JobMetrics: 작업 메트릭스
    """
    return job_manager.get_job_metrics(tenant_id)
