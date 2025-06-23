"""
요약 API 엔드포인트

최적화된 스키마와 서비스를 사용하는 FastAPI 엔드포인트
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging

from ..services.summary_service import (
    get_summary_service, get_progress_tracker,
    OptimizedSummaryService, ProgressTracker,
    SummaryRequest, SummaryResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summaries", tags=["summaries"])


# ==================
# Pydantic 모델들
# ==================

class SummaryCreateRequest(BaseModel):
    """요약 생성 요청"""
    ticket_id: int = Field(..., description="티켓 ID")
    force_regenerate: bool = Field(False, description="기존 요약 무시하고 재생성")


class BatchSummaryRequest(BaseModel):
    """배치 요약 요청"""
    ticket_ids: List[int] = Field(..., description="티켓 ID 목록", max_items=1000)
    company_id: Optional[int] = Field(None, description="회사 ID 필터")


class SummaryResponseModel(BaseModel):
    """요약 응답 모델"""
    ticket_id: int
    summary: str
    quality_score: float
    processing_time_ms: int
    cost_estimate: float
    created_at: datetime
    model_used: str
    error: Optional[str] = None

    class Config:
        from_attributes = True


class BatchProgressResponse(BaseModel):
    """배치 진행 상황 응답"""
    batch_id: str
    progress: float
    total_processed: int
    successful: int
    failed: int
    estimated_cost: float
    timestamp: str


class StatisticsResponse(BaseModel):
    """통계 응답"""
    total_summaries: int
    average_quality: float
    total_tokens: int
    total_cost: float
    high_quality_count: int
    high_quality_rate: float


class QualityInsightsResponse(BaseModel):
    """품질 인사이트 응답"""
    total_summaries: int
    quality_distribution: Dict[str, int]
    model_performance: Dict[str, Dict[str, Any]]
    average_quality: float
    total_cost: float


# ==================
# 의존성 주입
# ==================

def get_summary_service_dep() -> OptimizedSummaryService:
    """요약 서비스 의존성"""
    return get_summary_service()


def get_progress_tracker_dep() -> ProgressTracker:
    """진행 상황 추적기 의존성"""
    return get_progress_tracker()


# ==================
# API 엔드포인트들
# ==================

@router.get("/{ticket_id}", response_model=SummaryResponseModel)
async def get_summary(
    ticket_id: int,
    service: OptimizedSummaryService = Depends(get_summary_service_dep)
):
    """
    티켓 요약 조회
    
    - **ticket_id**: 조회할 티켓 ID
    - 기존 요약이 있으면 반환, 없으면 404 오류
    """
    
    try:
        summary = await service.get_summary(ticket_id)
        
        if not summary:
            raise HTTPException(
                status_code=404, 
                detail=f"티켓 {ticket_id}의 요약을 찾을 수 없습니다"
            )
        
        return summary
        
    except Exception as e:
        logger.error(f"요약 조회 실패: {ticket_id} - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=SummaryResponseModel)
async def create_summary(
    request: SummaryCreateRequest,
    service: OptimizedSummaryService = Depends(get_summary_service_dep)
):
    """
    단일 티켓 요약 생성
    
    - **ticket_id**: 요약할 티켓 ID
    - **force_regenerate**: 기존 요약 무시하고 재생성 여부
    - 높은 품질의 요약을 생성하여 반환
    """
    
    try:
        summary = await service.create_summary(
            ticket_id=request.ticket_id,
            force_regenerate=request.force_regenerate
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"요약 생성 실패: {request.ticket_id} - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=Dict[str, Any])
async def create_batch_summaries(
    request: BatchSummaryRequest,
    background_tasks: BackgroundTasks,
    service: OptimizedSummaryService = Depends(get_summary_service_dep),
    tracker: ProgressTracker = Depends(get_progress_tracker_dep)
):
    """
    배치 요약 생성 (백그라운드 처리)
    
    - **ticket_ids**: 요약할 티켓 ID 목록 (최대 1000개)
    - **company_id**: 회사 ID 필터 (선택사항)
    - 백그라운드에서 처리되며, batch_id로 진행 상황 추적 가능
    """
    
    if not request.ticket_ids:
        raise HTTPException(status_code=400, detail="티켓 ID 목록이 비어있습니다")
    
    # 배치 ID 생성
    batch_id = str(uuid.uuid4())
    
    # 백그라운드 작업 등록
    background_tasks.add_task(
        _process_batch_summaries,
        batch_id,
        request.ticket_ids,
        service,
        tracker
    )
    
    return {
        "batch_id": batch_id,
        "message": f"{len(request.ticket_ids)}개 티켓의 배치 요약 처리를 시작했습니다",
        "total_tickets": len(request.ticket_ids),
        "progress_url": f"/api/summaries/batch/{batch_id}/progress"
    }


@router.get("/batch/{batch_id}/progress", response_model=Dict[str, Any])
async def get_batch_progress(
    batch_id: str,
    tracker: ProgressTracker = Depends(get_progress_tracker_dep)
):
    """
    배치 처리 진행 상황 조회
    
    - **batch_id**: 배치 처리 ID
    - 실시간 진행 상황과 통계 반환
    """
    
    progress = tracker.get_progress(batch_id)
    
    if not progress:
        raise HTTPException(
            status_code=404, 
            detail=f"배치 {batch_id}를 찾을 수 없습니다"
        )
    
    return progress


@router.get("/pending", response_model=List[int])
async def get_pending_summaries(
    company_id: Optional[int] = Query(None, description="회사 ID 필터"),
    limit: int = Query(100, description="최대 반환 개수", le=1000),
    service: OptimizedSummaryService = Depends(get_summary_service_dep)
):
    """
    요약 대기 중인 티켓 목록
    
    - **company_id**: 특정 회사의 티켓만 조회 (선택사항)
    - **limit**: 최대 반환 개수 (기본 100, 최대 1000)
    - 요약이 아직 생성되지 않은 티켓 ID 목록 반환
    """
    
    try:
        ticket_ids = await service.get_pending_summaries(
            company_id=company_id,
            limit=limit
        )
        
        return ticket_ids
        
    except Exception as e:
        logger.error(f"대기 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=StatisticsResponse)
async def get_summary_statistics(
    company_id: Optional[int] = Query(None, description="회사 ID 필터"),
    days: int = Query(30, description="조회 기간 (일)", ge=1, le=365),
    service: OptimizedSummaryService = Depends(get_summary_service_dep)
):
    """
    요약 통계 조회
    
    - **company_id**: 특정 회사 통계만 조회 (선택사항)
    - **days**: 조회 기간 (기본 30일, 최대 365일)
    - 요약 개수, 품질, 비용 등의 통계 반환
    """
    
    try:
        stats = await service.get_summary_statistics(
            company_id=company_id,
            days=days
        )
        
        return StatisticsResponse(**stats)
        
    except Exception as e:
        logger.error(f"통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights/quality", response_model=QualityInsightsResponse)
async def get_quality_insights(
    company_id: Optional[int] = Query(None, description="회사 ID 필터"),
    min_quality: float = Query(0.5, description="최소 품질 점수", ge=0.0, le=1.0),
    service: OptimizedSummaryService = Depends(get_summary_service_dep)
):
    """
    품질 인사이트 조회
    
    - **company_id**: 특정 회사 인사이트 조회 (선택사항)
    - **min_quality**: 분석 대상 최소 품질 점수
    - 품질 분포, 모델별 성능 등의 인사이트 반환
    """
    
    try:
        insights = await service.get_quality_insights(
            company_id=company_id,
            min_quality=min_quality
        )
        
        return QualityInsightsResponse(**insights)
        
    except Exception as e:
        logger.error(f"품질 인사이트 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/auto", response_model=Dict[str, Any])
async def auto_batch_summaries(
    company_id: Optional[int] = Query(None, description="회사 ID 필터"),
    limit: int = Query(100, description="처리할 최대 티켓 수", le=1000),
    background_tasks: BackgroundTasks,
    service: OptimizedSummaryService = Depends(get_summary_service_dep),
    tracker: ProgressTracker = Depends(get_progress_tracker_dep)
):
    """
    자동 배치 요약 처리
    
    - **company_id**: 특정 회사 티켓만 처리 (선택사항)
    - **limit**: 처리할 최대 티켓 수 (기본 100, 최대 1000)
    - 요약이 없는 티켓들을 자동으로 찾아서 배치 처리
    """
    
    try:
        # 대기 중인 티켓 조회
        ticket_ids = await service.get_pending_summaries(
            company_id=company_id,
            limit=limit
        )
        
        if not ticket_ids:
            return {
                "message": "처리할 티켓이 없습니다",
                "total_tickets": 0
            }
        
        # 배치 ID 생성
        batch_id = str(uuid.uuid4())
        
        # 백그라운드 작업 등록
        background_tasks.add_task(
            _process_batch_summaries,
            batch_id,
            ticket_ids,
            service,
            tracker
        )
        
        return {
            "batch_id": batch_id,
            "message": f"{len(ticket_ids)}개 티켓의 자동 배치 요약 처리를 시작했습니다",
            "total_tickets": len(ticket_ids),
            "progress_url": f"/api/summaries/batch/{batch_id}/progress"
        }
        
    except Exception as e:
        logger.error(f"자동 배치 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================
# 백그라운드 작업
# ==================

async def _process_batch_summaries(
    batch_id: str,
    ticket_ids: List[int],
    service: OptimizedSummaryService,
    tracker: ProgressTracker
):
    """배치 요약 백그라운드 처리"""
    
    try:
        logger.info(f"배치 요약 시작: {batch_id} ({len(ticket_ids)}개 티켓)")
        
        # 진행 상황 콜백
        async def progress_callback(progress: float, stats):
            await tracker.update_progress(batch_id, progress, {
                'total_processed': getattr(stats, 'completed', 0) + getattr(stats, 'failed', 0),
                'successful': getattr(stats, 'completed', 0),
                'failed': getattr(stats, 'failed', 0),
                'estimated_cost': getattr(stats, 'total_cost_estimate', 0.0),
                'high_quality_count': getattr(stats, 'high_quality_count', 0)
            })
        
        # 배치 처리 실행
        responses, batch_stats = await service.create_batch_summaries(
            ticket_ids=ticket_ids,
            progress_callback=progress_callback
        )
        
        # 최종 결과 업데이트
        await tracker.update_progress(batch_id, 1.0, {
            **batch_stats,
            'status': 'completed',
            'results': [
                {
                    'ticket_id': r.ticket_id,
                    'quality_score': r.quality_score,
                    'cost_estimate': r.cost_estimate,
                    'error': r.error
                } for r in responses[:100]  # 최대 100개 결과만 저장
            ]
        })
        
        logger.info(f"배치 요약 완료: {batch_id} (성공: {batch_stats.get('successful', 0)}, 실패: {batch_stats.get('failed', 0)})")
        
    except Exception as e:
        logger.error(f"배치 요약 실패: {batch_id} - {e}")
        await tracker.update_progress(batch_id, 0.0, {
            'status': 'failed',
            'error': str(e),
            'total_processed': 0,
            'successful': 0,
            'failed': len(ticket_ids)
        })


# ==================
# 헬스 체크
# ==================

@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    service: OptimizedSummaryService = Depends(get_summary_service_dep)
):
    """
    요약 서비스 헬스 체크
    
    - 데이터베이스 연결 상태
    - 요약 서비스 상태
    - 기본 통계 정보
    """
    
    try:
        # 기본 통계 조회 (연결 테스트)
        stats = await service.get_summary_statistics(days=1)
        
        return {
            "status": "healthy",
            "database": "connected",
            "service": "available",
            "today_summaries": stats.get('total_summaries', 0),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "service": "unavailable",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
