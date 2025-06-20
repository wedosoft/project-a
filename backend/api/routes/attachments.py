"""
첨부파일 라우터

이 모듈은 첨부파일 관련 엔드포인트를 제공합니다.
기존 main.py의 엔드포인트 로직과 api/attachments.py의 함수들을 재활용하여 구현되었습니다.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse
from typing import Optional
import logging

from ..dependencies import get_company_id, get_platform
from ..attachments import (
    get_freshdesk_attachment_url,
    get_attachment_download_url,
    get_attachment_metadata,
    get_bulk_attachment_urls,
    download_attachment_proxy
)

# 라우터 생성
router = APIRouter(prefix="/attachments", tags=["첨부파일"])

# 로거 설정
logger = logging.getLogger(__name__)

@router.get("/download/{attachment_id}")
async def download_attachment(
    attachment_id: int,
    x_freshdesk_domain: str = Header(..., alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: str = Header(..., alias="X-Freshdesk-API-Key")
):
    """
    첨부파일 다운로드 프록시 엔드포인트
    
    Freshdesk 첨부파일을 프록시를 통해 다운로드합니다.
    """
    try:
        return await download_attachment_proxy(
            attachment_id=attachment_id,
            freshdesk_domain=x_freshdesk_domain,
            api_key=x_freshdesk_api_key
        )
    except Exception as e:
        logger.error(f"첨부파일 다운로드 중 오류 발생 - ID: {attachment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"첨부파일 다운로드 실패: {str(e)}")

@router.get("/url/{attachment_id}")
async def get_attachment_url(
    attachment_id: int,
    x_freshdesk_domain: str = Header(..., alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: str = Header(..., alias="X-Freshdesk-API-Key")
):
    """
    첨부파일 다운로드 URL 조회 엔드포인트
    
    Freshdesk 첨부파일의 다운로드 URL을 조회합니다.
    """
    try:
        url = await get_attachment_download_url(
            attachment_id=attachment_id,
            freshdesk_domain=x_freshdesk_domain,
            api_key=x_freshdesk_api_key
        )
        return {"attachment_id": attachment_id, "download_url": url}
    except Exception as e:
        logger.error(f"첨부파일 URL 조회 중 오류 발생 - ID: {attachment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"첨부파일 URL 조회 실패: {str(e)}")

@router.get("/metadata/{attachment_id}")
async def get_attachment_info(
    attachment_id: int
):
    """
    첨부파일 메타데이터 조회 엔드포인트
    
    첨부파일의 메타데이터 정보를 조회합니다.
    """
    try:
        metadata = await get_attachment_metadata(attachment_id)
        return metadata
    except Exception as e:
        logger.error(f"첨부파일 메타데이터 조회 중 오류 발생 - ID: {attachment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"첨부파일 메타데이터 조회 실패: {str(e)}")

@router.get("/bulk-urls")
async def get_bulk_urls(
    attachment_ids: str,  # 쉼표로 구분된 ID 목록
    x_freshdesk_domain: str = Header(..., alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: str = Header(..., alias="X-Freshdesk-API-Key")
):
    """
    대량 첨부파일 URL 조회 엔드포인트
    
    여러 첨부파일의 다운로드 URL을 한 번에 조회합니다.
    """
    try:
        # 쉼표로 구분된 ID 문자열을 정수 리스트로 변환
        id_list = [int(id_str.strip()) for id_str in attachment_ids.split(",") if id_str.strip()]
        
        urls = await get_bulk_attachment_urls(
            attachment_ids=id_list,
            freshdesk_domain=x_freshdesk_domain,
            api_key=x_freshdesk_api_key
        )
        return {"attachment_urls": urls}
    except Exception as e:
        logger.error(f"대량 첨부파일 URL 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"대량 첨부파일 URL 조회 실패: {str(e)}")

@router.get("/freshdesk-url/{attachment_id}")
async def get_freshdesk_url(
    attachment_id: int,
    ticket_id: int,
    x_freshdesk_domain: str = Header(..., alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: str = Header(..., alias="X-Freshdesk-API-Key")
):
    """
    Freshdesk 첨부파일 URL 조회 엔드포인트
    
    Freshdesk API를 통해 첨부파일 URL을 조회합니다.
    """
    try:
        url = await get_freshdesk_attachment_url(
            attachment_id=attachment_id,
            ticket_id=ticket_id,
            freshdesk_domain=x_freshdesk_domain,
            api_key=x_freshdesk_api_key
        )
        return {"attachment_id": attachment_id, "ticket_id": ticket_id, "freshdesk_url": url}
    except Exception as e:
        logger.error(f"Freshdesk 첨부파일 URL 조회 중 오류 발생 - ID: {attachment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Freshdesk 첨부파일 URL 조회 실패: {str(e)}")
