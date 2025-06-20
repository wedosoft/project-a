"""
Freshdesk 데이터 수집 라우터

이 모듈은 Freshdesk API를 통해 티켓과 지식베이스 데이터를 수집하는 엔드포인트를 제공합니다.
기존 main.py의 /ingest 엔드포인트 로직을 재활용하면서 작업 상태 관리 기능을 추가합니다.

주요 기능:
- 데이터 수집 작업 생성 및 시작
- 작업 일시정지/재개/취소
- 작업 상태 및 진행상황 모니터링
- 작업 목록 및 메트릭스 조회
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from datetime import datetime
from typing import Optional, List
import logging

from ..models.requests import IngestRequest
from ..models.responses import IngestResponse
from ..models.ingest_job import (
    IngestJobConfig, 
    JobControlRequest, 
    JobListResponse, 
    JobStatusResponse,
    JobMetrics,
    JobStatus,
    JobType
)
from ..dependencies import get_company_id
from ..services.job_manager import job_manager
from ..ingest import ingest

# 라우터 생성
router = APIRouter(prefix="/ingest", tags=["데이터 수집"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.post("", response_model=IngestResponse)
async def trigger_data_ingestion(
    request: IngestRequest,
    company_id: str = Depends(get_company_id),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    Freshdesk 데이터 수집을 트리거하는 엔드포인트 (기존 방식 - 즉시 실행)
    
    헤더로 전달된 동적 Freshdesk 도메인과 API 키를 사용하거나
    환경변수에 설정된 기본값을 사용하여 데이터를 수집합니다.
    
    이 엔드포인트는 하위 호환성을 위해 유지되며, 즉시 실행됩니다.
    장시간 작업의 경우 /jobs 엔드포인트 사용을 권장합니다.
    
    Args:
        request: 데이터 수집 옵션
        company_id: 회사 ID (헤더에서 자동 추출)
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달, 선택사항)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달, 선택사항)
        
    Returns:
        IngestResponse: 수집 결과 정보
    """
    start_time = datetime.now()
    logger.info(f"즉시 데이터 수집 시작 - Company: {company_id}, Domain: {x_freshdesk_domain}")
    
    try:
        # 동적 Freshdesk 구성을 사용하여 데이터 수집 실행
        await ingest(
            incremental=request.incremental,
            purge=request.purge,
            process_attachments=request.process_attachments,
            force_rebuild=request.force_rebuild,
            local_data_dir=None,  # API 호출이므로 로컬 데이터 사용 안함
            include_kb=request.include_kb,
            domain=x_freshdesk_domain,
            api_key=x_freshdesk_api_key
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"데이터 수집 완료 - Company: {company_id}, 소요시간: {duration:.2f}초")
        
        return IngestResponse(
            success=True,
            message="데이터 수집이 성공적으로 완료되었습니다.",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.error(f"데이터 수집 중 오류 발생 - Company: {company_id}: {e}", exc_info=True)
        
        return IngestResponse(
            success=False,
            message=f"데이터 수집 중 오류가 발생했습니다: {str(e)}",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            error=str(e)
        )


@router.post("/jobs", response_model=JobStatusResponse)
async def create_ingest_job(
    request: IngestRequest,
    company_id: str = Depends(get_company_id),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    새로운 데이터 수집 작업을 생성합니다 (비동기 실행)
    
    이 엔드포인트는 작업을 백그라운드에서 실행하며,
    일시정지/재개/취소 등의 제어가 가능합니다.
    
    Args:
        request: 데이터 수집 옵션
        company_id: 회사 ID
        x_freshdesk_domain: Freshdesk 도메인
        x_freshdesk_api_key: Freshdesk API 키
        
    Returns:
        JobStatusResponse: 생성된 작업 정보
    """
    logger.info(f"새 데이터 수집 작업 생성 요청 - Company: {company_id}")
    
    # 작업 설정 생성
    config = IngestJobConfig(
        incremental=request.incremental,
        purge=request.purge,
        process_attachments=request.process_attachments,
        force_rebuild=request.force_rebuild,
        include_kb=request.include_kb,
        domain=x_freshdesk_domain,
        api_key=x_freshdesk_api_key
    )
    
    # 작업 생성
    job = job_manager.create_job(company_id, config)
    
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
    company_id: str = Depends(get_company_id),
    status: Optional[JobStatus] = Query(None, description="작업 상태 필터"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(20, ge=1, le=100, description="페이지당 항목 수")
):
    """
    데이터 수집 작업 목록을 조회합니다
    
    Args:
        company_id: 회사 ID
        status: 작업 상태 필터 (선택사항)
        page: 페이지 번호
        per_page: 페이지당 항목 수
        
    Returns:
        JobListResponse: 작업 목록
    """
    offset = (page - 1) * per_page
    jobs = job_manager.list_jobs(
        company_id=company_id,
        status=status,
        limit=per_page,
        offset=offset
    )
    
    # 전체 개수 계산 (실제로는 DB 쿼리에서 COUNT를 사용해야 함)
    all_jobs = job_manager.list_jobs(company_id=company_id, status=status, limit=1000)
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
    company_id: str = Depends(get_company_id)
):
    """
    특정 데이터 수집 작업의 상태를 조회합니다
    
    Args:
        job_id: 작업 ID
        company_id: 회사 ID
        
    Returns:
        JobStatusResponse: 작업 상태 정보
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    if job.company_id != company_id:
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
    company_id: str = Depends(get_company_id)
):
    """
    데이터 수집 작업을 제어합니다 (일시정지/재개/취소)
    
    Args:
        job_id: 작업 ID
        request: 제어 요청 (action: pause, resume, cancel)
        company_id: 회사 ID
        
    Returns:
        작업 제어 결과
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    if job.company_id != company_id:
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
    company_id: str = Depends(get_company_id)
):
    """
    데이터 수집 작업 메트릭스를 조회합니다
    
    Args:
        company_id: 회사 ID
        
    Returns:
        JobMetrics: 작업 메트릭스
    """
    return job_manager.get_job_metrics(company_id)
