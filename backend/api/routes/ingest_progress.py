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

from ..dependencies import get_company_id
from core.database.database import SQLiteDatabase

# 라우터 생성 (prefix 제거 - 메인 라우터에서 설정)
router = APIRouter(tags=["진행 상황 모니터링"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.get("/progress/{job_id}")
async def get_job_progress(
    job_id: str,
    company_id: str = Depends(get_company_id)
):
    """
    특정 작업의 실시간 진행 상황을 조회합니다.
    
    Args:
        job_id: 작업 ID
        company_id: 회사 ID (헤더에서 자동 추출)
        
    Returns:
        작업 진행 상황 정보
    """
    try:
        # 데이터베이스에서 진행 상황 로그 조회
        db = SQLiteDatabase()
        cursor = db.connection.cursor()
        
        # 최신 진행 상황 조회
        cursor.execute("""
            SELECT 
                job_id,
                company_id,
                message,
                percentage,
                step,
                total_steps,
                created_at
            FROM progress_logs 
            WHERE job_id = ? AND company_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (job_id, company_id))
        
        progress_row = cursor.fetchone()
        
        if not progress_row:
            raise HTTPException(status_code=404, detail=f"진행 상황을 찾을 수 없습니다: {job_id}")
        
        # 수집 작업 로그도 조회 (전체 상태 정보)
        cursor.execute("""
            SELECT 
                status,
                start_time,
                end_time,
                tickets_collected,
                conversations_collected,
                articles_collected,
                attachments_collected,
                errors_count,
                error_message
            FROM collection_logs
            WHERE job_id = ? AND company_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (job_id, company_id))
        
        job_row = cursor.fetchone()
        
        # 응답 데이터 구성
        response = {
            "job_id": job_id,
            "company_id": company_id,
            "current_step": progress_row[4],  # step
            "total_steps": progress_row[5],   # total_steps
            "progress_percentage": progress_row[3],  # percentage
            "current_message": progress_row[2],      # message
            "last_updated": progress_row[6],         # created_at
            "status": "in_progress",
            "details": {}
        }
        
        if job_row:
            response.update({
                "status": job_row[0] or "in_progress",  # status
                "start_time": job_row[1],               # start_time
                "end_time": job_row[2],                 # end_time
                "details": {
                    "tickets_collected": job_row[3] or 0,      # tickets_collected
                    "conversations_collected": job_row[4] or 0, # conversations_collected
                    "articles_collected": job_row[5] or 0,      # articles_collected
                    "attachments_collected": job_row[6] or 0,   # attachments_collected
                    "errors_count": job_row[7] or 0,           # errors_count
                    "error_message": job_row[8]                # error_message
                }
            })
        
        return response
        
    except Exception as e:
        logger.error(f"진행 상황 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"진행 상황 조회 실패: {str(e)}")
