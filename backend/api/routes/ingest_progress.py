"""
데이터 수집 진행 상황 모니터링 라우터

이 모듈은 데이터 수집 작업의 실시간 진행 상황을 모니터링하는 엔드포인트를 제공합니다.

주요 기능:
- 특정 작업의 실시간 진행 상황 조회
- 최근 작업들의 진행 상황 목록 조회
- 데이터 수집 통계 및 분석
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging
import os

from ..dependencies import get_tenant_id
from core.database.manager import DatabaseManager
from core.database.models.progress_log import ProgressLog

# 라우터 생성 (prefix 제거 - 메인 라우터에서 설정)
router = APIRouter(tags=["진행 상황 모니터링"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.get("/progress/{job_id}")
async def get_job_progress(
    job_id: str,
    tenant_id: str = Depends(get_tenant_id)
):
    """
    특정 작업의 실시간 진행 상황을 조회합니다.
    
    Args:
        job_id: 작업 ID
        tenant_id: 테넌트 ID (헤더에서 자동 추출)
        
    Returns:
        작업 진행 상황 정보
    """
    try:
        # 환경변수에서 데이터베이스 URL 가져오기
        database_url = os.getenv("DATABASE_URL", f"sqlite:///backend/core/data/{tenant_id}_data.db")
        db_manager = DatabaseManager(database_url)
        
        with db_manager.get_session() as session:
            # progress_logs 테이블에서 최신 진행 상황 조회
            progress_log = session.query(ProgressLog).filter(
                ProgressLog.job_id == job_id,
                ProgressLog.tenant_id == tenant_id
            ).order_by(ProgressLog.created_at.desc()).first()
            
            if not progress_log:
                raise HTTPException(status_code=404, detail=f"진행 상황을 찾을 수 없습니다: {job_id}")
            
            # 응답 데이터 구성 (progress_logs 테이블만 사용)
            response = {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "current_step": progress_log.step,
                "total_steps": progress_log.total_steps,
                "progress_percentage": progress_log.percentage,
                "current_message": progress_log.message,
                "last_updated": progress_log.created_at.isoformat() if progress_log.created_at else None,
                "status": "in_progress",
                "details": {
                    "message": progress_log.message,
                    "step": progress_log.step,
                    "total_steps": progress_log.total_steps,
                    "percentage": progress_log.percentage
                }
            }
        
        return response
        
    except Exception as e:
        logger.error(f"진행 상황 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"진행 상황 조회 실패: {str(e)}")
