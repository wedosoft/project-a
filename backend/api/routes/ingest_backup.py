"""
멀티플랫폼 데이터 수집 라우터 (통합 모듈)

이 모듈은 데이터 수집 관련 모든 엔드포인트를 통합합니다.
기능별로 분할된 서브 모듈들을 하나로 결합하여 제공합니다.

분할된 모듈들:
- ingest_progress: 진행 상황 모니터링 관련
- ingest_jobs: 작업 관리 관련  
- ingest_core: 핵심 수집 기능
"""

from fastapi import APIRouter

# 분할된 서브 라우터들 임포트
from .ingest_progress import router as progress_router
from .ingest_jobs import router as jobs_router
from .ingest_core import router as core_router

# 메인 라우터 생성
router = APIRouter(prefix="/ingest", tags=["데이터 수집"])

# 서브 라우터들을 메인 라우터에 포함
router.include_router(progress_router)
router.include_router(jobs_router) 
router.include_router(core_router)

@router.post("", response_model=IngestResponse)
async def trigger_data_ingestion(
    request: IngestRequest,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: Optional[str] = Depends(get_api_key),
    domain: Optional[str] = Depends(get_domain)
):
    """
    데이터 수집을 트리거하는 엔드포인트 (멀티플랫폼 지원)
    
    **새로운 표준 헤더 (권장):**
    - X-Tenant-ID: 회사 식별자 (또는 X-Domain에서 자동 추출)
    - X-Platform: 플랫폼 식별자 (freshdesk, zendesk 등)
    - X-Domain: 플랫폼 도메인 (예: company-domain)
    - X-API-Key: 플랫폼 API 키
    
    **레거시 헤더 (하위 호환성):**
    - X-Platform-Domain, X-Platform-API-Key 등
    
    Args:
        request: 데이터 수집 옵션
        tenant_id: 테넌트 ID (헤더에서 자동 추출)
        platform: 플랫폼 식별자 (헤더에서 자동 추출)
        api_key: 플랫폼 API 키 (헤더에서 추출 또는 환경변수)
        domain: 플랫폼 도메인 (헤더에서 추출 또는 환경변수)
        
    Returns:
        IngestResponse: 수집 결과 정보
    """
    start_time = datetime.now()
    logger.info(f"즉시 데이터 수집 시작 - Company: {tenant_id}, Platform: {platform}, Domain: {domain}")
    logger.info(f"[DEBUG] 수신된 파라미터 - max_tickets: {request.max_tickets}, max_articles: {request.max_articles}")
    logger.info(f"[DEBUG] 파라미터 타입 확인 - max_tickets type: {type(request.max_tickets)}, max_articles type: {type(request.max_articles)}")
    logger.info(f"[DEBUG] 수신된 옵션 - include_kb: {request.include_kb}, incremental: {request.incremental}")
    
    # 플랫폼 검증 (보안상 필수)
    from core.platforms.factory import PlatformFactory
    supported_platforms = PlatformFactory.get_supported_platforms()
    
    if platform not in supported_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"지원되지 않는 플랫폼입니다: {platform}. 지원되는 플랫폼: {', '.join(supported_platforms)}"
        )
    
    try:
        # 진행상황 콜백 함수 정의
        def progress_callback(message: str, percentage: float):
            try:
                from core.database.database import get_database
                db = get_database(tenant_id, platform)
                # 임시 job_id 생성
                temp_job_id = f"immediate-{tenant_id}-{int(start_time.timestamp())}"
                db.log_progress(
                    job_id=temp_job_id,
                    tenant_id=tenant_id,
                    message=message,
                    percentage=percentage,
                    step=int(percentage),
                    total_steps=100
                )
                db.disconnect()
            except Exception as e:
                logger.error(f"즉시 실행 진행상황 로그 저장 실패: {e}")
            
            logger.info(f"즉시 실행 진행상황: {message} ({percentage:.1f}%)")
        
        # 멀티플랫폼 데이터 수집 실행
        result = await ingest(
            tenant_id=tenant_id,
            platform=platform,
            incremental=request.incremental,
            purge=request.purge,
            process_attachments=request.process_attachments,
            force_rebuild=request.force_rebuild,
            local_data_dir=None,  # API 호출이므로 로컬 데이터 사용 안함
            include_kb=request.include_kb,
            domain=domain,
            api_key=api_key,
            max_tickets=request.max_tickets,
            max_articles=request.max_articles,
            progress_callback=progress_callback
        )
        
        # 데이터 수집 완료 후 요약 생성
        logger.info("데이터 수집 완료. 요약 생성 시작...")
        progress_callback("요약 생성 중...", 85.0)
        
        try:
            # 요약 생성 단계 추가
            from core.ingest.processor import generate_and_store_summaries
            summary_result = await generate_and_store_summaries(
                tenant_id=tenant_id,
                platform=platform,
                force_update=False
            )
            
            logger.info(f"요약 생성 완료 - 성공: {summary_result.get('success_count', 0)}개, "
                       f"실패: {summary_result.get('failure_count', 0)}개, "
                       f"건너뜀: {summary_result.get('skipped_count', 0)}개")
            progress_callback("요약 생성 완료", 88.0)
            
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            progress_callback("요약 생성 실패", 88.0)
        
        # 벡터 DB 동기화 자동 실행 (같은 DB 연결 재사용)
        logger.info("요약 생성 완료. 벡터 DB 동기화 시작...")
        progress_callback("벡터 DB 동기화 중...", 90.0)
        
        try:
            # sync_summaries 기능 직접 호출
            from core.ingest.processor import sync_summaries_to_vector_db
            sync_result = await sync_summaries_to_vector_db(
                tenant_id=tenant_id,
                platform=platform,
                batch_size=25,
                force_update=False
            )
            
            if sync_result.get("status") == "success":
                logger.info(f"벡터 DB 동기화 완료 - 성공: {sync_result.get('synced_count', 0)}개")
                progress_callback("벡터 DB 동기화 완료", 100.0)
            else:
                errors = sync_result.get('errors', [])
                if errors:
                    logger.error(f"벡터 DB 동기화 실패 - 오류: {errors}")
                else:
                    logger.warning(f"벡터 DB 동기화 완료 - 오류 없음, 처리된 문서: {sync_result.get('synced_count', 0)}개")
                progress_callback("벡터 DB 동기화 실패", 95.0)
        except Exception as e:
            logger.error(f"벡터 DB 동기화 실패: {e}")
            progress_callback("벡터 DB 동기화 실패", 95.0)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"데이터 수집 완료 - Company: {tenant_id}, Platform: {platform}, 소요시간: {duration:.2f}초")
        
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
        
        logger.error(f"데이터 수집 중 오류 발생 - Company: {tenant_id}, Platform: {platform}: {e}", exc_info=True)
        
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


@router.post("/sync-summaries", response_model=IngestResponse)
async def sync_summaries_to_vector_db(
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: Optional[str] = Depends(get_api_key),
    domain: Optional[str] = Depends(get_domain),
    batch_size: int = Query(25, description="배치 처리 크기", ge=1, le=100),
    force_update: bool = Query(False, description="기존 임베딩 강제 업데이트 여부")
):
    """
    SQLite에서 요약 데이터를 읽어서 벡터 DB에 동기화하는 엔드포인트 (멀티플랫폼 지원)
    
    이 엔드포인트는 ingest 프로세스에서 누락된 파이프라인 단계를 실행합니다:
    1. SQLite에서 tickets, kb_articles, conversations의 요약 데이터 조회
    2. 요약 텍스트를 임베딩으로 변환
    3. 3-tuple 보안(tenant_id, platform, original_id)을 유지하면서 Qdrant에 저장
    
    **새로운 표준 헤더 (권장):**
    - X-Tenant-ID: 회사 식별자 (멀티테넌트 보안)
    - X-Platform: 플랫폼 식별자 (멀티플랫폼 보안)
    - X-Domain: 플랫폼 도메인 (선택사항)
    - X-API-Key: 플랫폼 API 키 (선택사항, 추가 검증용)
    
    **레거시 헤더 (하위 호환성):**
    - X-Platform-Domain, X-Platform-API-Key 등
    
    Args:
        tenant_id: 테넌트 ID (X-Tenant-ID 헤더에서 자동 추출)
        platform: 플랫폼 식별자 (X-Platform 헤더에서 자동 추출)
        api_key: 플랫폼 API 키 (X-API-Key 헤더, 선택사항)
        domain: 플랫폼 도메인 (X-Domain 헤더, 선택사항)
        batch_size: 배치 처리 크기 (1-100, 기본값: 25)
        force_update: 기존 임베딩을 강제로 업데이트할지 여부 (기본값: False)
        
    Returns:
        IngestResponse: 동기화 결과 정보
    """
    from core.ingest.processor import sync_summaries_to_vector_db as sync_func
    
    start_time = datetime.now()
    logger.info(f"요약 데이터 벡터 DB 동기화 시작 - Company: {tenant_id}, Platform: {platform}")
    
    # 보안 헤더 검증
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID 헤더가 필요합니다 (멀티테넌트 보안)")
    
    if not platform:
        raise HTTPException(status_code=400, detail="X-Platform 헤더가 필요합니다 (멀티플랫폼 보안)")
    
    # 선택적 보안 검증 (API 키와 도메인이 모두 제공된 경우)
    if api_key and domain:
        logger.info("추가 플랫폼 자격 증명 확인됨")
    elif api_key or domain:
        logger.warning("플랫폼 API 키와 도메인은 둘 다 제공되거나 둘 다 생략되어야 합니다")
    
    try:
        # 요약 데이터 동기화 실행
        result = await sync_func(
            tenant_id=tenant_id,
            platform=platform,
            batch_size=batch_size,
            force_update=force_update
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        success_msg = (
            f"요약 데이터 벡터 DB 동기화 완료 - "
            f"성공: {result.get('success_count', 0)}, "
            f"실패: {result.get('failure_count', 0)}, "
            f"건너뜀: {result.get('skipped_count', 0)}, "
            f"총 처리: {result.get('total_processed', 0)}"
        )
        
        logger.info(success_msg)
        
        return IngestResponse(
            success=True,
            message=success_msg,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            metadata={
                "sync_result": result,
                "tenant_id": tenant_id,
                "platform": platform,
                "batch_size": batch_size,
                "force_update": force_update,
                "has_api_credentials": bool(api_key and domain)
            }
        )
        
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        error_msg = f"요약 데이터 벡터 DB 동기화 실패: {str(e)}"
        
        logger.error(error_msg)
        
        return IngestResponse(
            success=False,
            message=error_msg,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            error=str(e)
        )
