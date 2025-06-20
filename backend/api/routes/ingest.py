"""
Freshdesk 데이터 수집 라우터

이 모듈은 Freshdesk API를 통해 티켓과 지식베이스 데이터를 수집하는 엔드포인트를 제공합니다.
기존 main.py의 /ingest 엔드포인트 로직을 재활용하여 구현되었습니다.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from datetime import datetime
from typing import Optional
import logging

from ..models.requests import IngestRequest
from ..models.responses import IngestResponse
from ..dependencies import get_company_id
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
    Freshdesk 데이터 수집을 트리거하는 엔드포인트
    
    헤더로 전달된 동적 Freshdesk 도메인과 API 키를 사용하거나
    환경변수에 설정된 기본값을 사용하여 데이터를 수집합니다.
    
    Args:
        request: 데이터 수집 옵션
        company_id: 회사 ID (헤더에서 자동 추출)
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달, 선택사항)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달, 선택사항)
        
    Returns:
        IngestResponse: 수집 결과 정보
    """
    start_time = datetime.now()
    logger.info(f"데이터 수집 시작 - Company: {company_id}, Domain: {x_freshdesk_domain}")
    
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
