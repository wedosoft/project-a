"""
첨부파일 API 엔드포인트

Freshdesk 첨부파일에 대한 동적 URL 발급 및 접근 관리 모듈
pre-signed URL 만료 문제를 해결하기 위해 실시간으로 새로운 URL을 발급받습니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx
from core.database.vectordb import vector_db
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

# .env 파일 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

# Freshdesk 설정
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY")
BASE_URL = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2"

router = APIRouter(prefix="/attachments", tags=["attachments"])


class AttachmentResponse(BaseModel):
    """첨부파일 응답 모델"""
    id: int
    name: str
    content_type: str
    size: int
    download_url: str
    expires_at: str
    ticket_id: Optional[int] = None
    conversation_id: Optional[int] = None


class AttachmentMetadata(BaseModel):
    """첨부파일 메타데이터 모델"""
    id: int
    name: str
    content_type: str
    size: int
    ticket_id: Optional[int] = None
    conversation_id: Optional[int] = None


async def get_freshdesk_attachment_url(
    attachment_id: int,
    ticket_id: Optional[int] = None,
    conversation_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Freshdesk API를 통해 첨부파일의 최신 pre-signed URL을 발급받습니다.
    
    Args:
        attachment_id: 첨부파일 ID
        ticket_id: 티켓 ID (선택사항)
        conversation_id: 대화 ID (선택사항)
        
    Returns:
        Dict: 첨부파일 정보와 다운로드 URL을 포함한 딕셔너리
        
    Raises:
        HTTPException: API 호출 실패 시
    """
    async with httpx.AsyncClient() as client:
        try:
            # Freshdesk API 호출을 위한 Basic Auth 설정
            auth = (FRESHDESK_API_KEY, "X")
            
            # 첨부파일이 티켓에 직접 연결된 경우
            if ticket_id and not conversation_id:
                # 티켓 상세 정보에서 첨부파일 URL 찾기
                ticket_url = f"{BASE_URL}/tickets/{ticket_id}"
                logger.info(f"티켓 {ticket_id}에서 첨부파일 {attachment_id} 정보 조회 중...")
                
                response = await client.get(ticket_url, auth=auth, timeout=30.0)
                response.raise_for_status()
                ticket_data = response.json()
                
                # 티켓 첨부파일에서 해당 ID 찾기
                if "attachments" in ticket_data:
                    for attachment in ticket_data["attachments"]:
                        if attachment["id"] == attachment_id:
                            return {
                                "id": attachment["id"],
                                "name": attachment["name"],
                                "content_type": attachment["content_type"],
                                "size": attachment["size"],
                                "download_url": attachment["attachment_url"],
                                "expires_at": "5분 후 만료",  # Freshdesk 기본값
                                "ticket_id": ticket_id
                            }
            
            # 대화에 첨부된 파일인 경우
            elif conversation_id:
                # 대화 정보에서 첨부파일 URL 찾기
                conv_url = f"{BASE_URL}/conversations/{conversation_id}"
                logger.info(f"대화 {conversation_id}에서 첨부파일 {attachment_id} 정보 조회 중...")
                
                response = await client.get(conv_url, auth=auth, timeout=30.0)
                response.raise_for_status()
                conv_data = response.json()
                
                # 대화 첨부파일에서 해당 ID 찾기
                if "attachments" in conv_data:
                    for attachment in conv_data["attachments"]:
                        if attachment["id"] == attachment_id:
                            return {
                                "id": attachment["id"],
                                "name": attachment["name"],
                                "content_type": attachment["content_type"],
                                "size": attachment["size"],
                                "download_url": attachment["attachment_url"],
                                "expires_at": "5분 후 만료",
                                "conversation_id": conversation_id,
                                "ticket_id": ticket_id
                            }
            
            # 일반적인 접근: 티켓 목록에서 검색 (성능상 비추천, 마지막 수단)
            else:
                logger.warning(f"첨부파일 {attachment_id}에 대한 구체적인 위치 정보가 없어 전체 검색을 시도합니다")
                # 이 경우 벡터 DB에서 메타데이터를 먼저 조회하는 것을 권장
                raise HTTPException(
                    status_code=400,
                    detail="첨부파일 위치 정보(ticket_id 또는 conversation_id)가 필요합니다"
                )
            
            # 첨부파일을 찾지 못한 경우
            raise HTTPException(
                status_code=404,
                detail=f"첨부파일 {attachment_id}를 찾을 수 없습니다"
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Freshdesk API 오류 {e.response.status_code}: {e}")
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="첨부파일을 찾을 수 없습니다")
            elif e.response.status_code == 429:
                raise HTTPException(status_code=429, detail="API 요청 한도 초과")
            else:
                raise HTTPException(status_code=502, detail="Freshdesk 서버 오류")
        except Exception as e:
            logger.error(f"첨부파일 URL 조회 중 오류: {e}")
            raise HTTPException(status_code=500, detail="서버 내부 오류")


@router.get("/{attachment_id}/download-url", response_model=AttachmentResponse)
async def get_attachment_download_url(
    attachment_id: int,
    ticket_id: Optional[int] = Query(None, description="첨부파일이 속한 티켓 ID"),
    conversation_id: Optional[int] = Query(None, description="첨부파일이 속한 대화 ID")
):
    """
    첨부파일의 최신 다운로드 URL을 발급받습니다.
    
    이 엔드포인트는 Freshdesk의 pre-signed URL 만료 문제를 해결하기 위해
    매번 새로운 URL을 동적으로 발급받습니다.
    
    Args:
        attachment_id: 첨부파일 고유 ID
        ticket_id: 첨부파일이 속한 티켓 ID (권장)
        conversation_id: 첨부파일이 속한 대화 ID (권장)
        
    Returns:
        AttachmentResponse: 첨부파일 정보와 유효한 다운로드 URL
        
    Example:
        GET /attachments/12345/download-url?ticket_id=67890
    """
    logger.info(f"첨부파일 {attachment_id} 다운로드 URL 요청 (ticket_id={ticket_id}, conversation_id={conversation_id})")
    
    try:
        # Freshdesk에서 최신 URL 발급
        attachment_data = await get_freshdesk_attachment_url(
            attachment_id=attachment_id,
            ticket_id=ticket_id,
            conversation_id=conversation_id
        )
        
        logger.info(f"첨부파일 {attachment_id} URL 발급 완료: {attachment_data['name']}")
        return AttachmentResponse(**attachment_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"첨부파일 URL 발급 중 예상치 못한 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류")


@router.get("/{attachment_id}/metadata", response_model=AttachmentMetadata)
async def get_attachment_metadata(attachment_id: int):
    """
    벡터 DB에서 첨부파일 메타데이터를 조회합니다.
    
    실제 파일 다운로드 없이 첨부파일의 기본 정보만 조회할 때 사용합니다.
    이 정보는 벡터 DB에 캐시되어 있어 빠르게 응답됩니다.
    
    Args:
        attachment_id: 첨부파일 고유 ID
        
    Returns:
        AttachmentMetadata: 첨부파일의 메타데이터
    """
    try:
        logger.info(f"첨부파일 {attachment_id} 메타데이터 조회 중...")
        
        # 벡터 DB에서 첨부파일 메타데이터 검색
        # 여러 소스에서 검색을 시도합니다 (티켓/KB 문서의 첨부파일 메타데이터)
        attachment_data = None
        
        # 먼저 티켓 문서에서 검색
        try:
            # company_id는 환경변수에서 가져오거나 기본값 사용
            company_id = os.getenv("COMPANY_ID", "default")
            
            # scroll API를 사용하여 모든 문서에서 첨부파일 메타데이터 검색
            # 이는 첨부파일이 어느 티켓/문서에 속하는지 모를 때 사용하는 방법입니다
            offset = 0
            batch_size = 100
            
            while offset < 1000:  # 최대 1000개 문서까지만 검색 (성능 고려)
                # 벡터 DB에서 배치 단위로 문서 검색
                # has_attachments 필드 인덱스 문제를 피하기 위해 기본 필터만 사용
                scroll_result = vector_db.client.scroll(
                    collection_name=vector_db.collection_name,
                    offset=offset,
                    limit=batch_size,
                    with_payload=True,
                    with_vectors=False,
                    filter=Filter(
                        must=[
                            FieldCondition(key="company_id", match=MatchValue(value=company_id))
                        ]
                    )
                )
                
                if not scroll_result or not scroll_result[0]:
                    break
                    
                points, next_offset = scroll_result
                
                # 각 문서에서 첨부파일 메타데이터 검색
                for point in points:
                    payload = point.payload
                    
                    # 문서의 첨부파일 메타데이터에서 해당 ID 찾기
                    attachments = payload.get("attachments", [])
                    if attachments and isinstance(attachments, list):
                        for att in attachments:
                            if isinstance(att, dict) and att.get("id") == attachment_id:
                                attachment_data = {
                                    "id": att.get("id"),
                                    "name": att.get("name", "unknown"),
                                    "content_type": att.get("content_type", "application/octet-stream"),
                                    "size": att.get("size", 0),
                                    "ticket_id": payload.get("original_id") if payload.get("doc_type") == "ticket" else None
                                }
                                logger.info(f"첨부파일 {attachment_id} 메타데이터 발견: {attachment_data['name']}")
                                break
                
                if attachment_data:
                    break
                    
                # 다음 배치로 이동
                if next_offset is None:
                    break
                offset = next_offset
                
        except Exception as db_error:
            logger.error(f"벡터 DB 검색 중 오류: {db_error}")
            # 벡터 DB 검색 실패 시에도 계속 진행
        
        # 첨부파일 메타데이터를 찾은 경우
        if attachment_data:
            return AttachmentMetadata(**attachment_data)
            
        # 벡터 DB에서 찾지 못한 경우, 404 오류 반환
        logger.warning(f"첨부파일 {attachment_id} 메타데이터를 찾을 수 없습니다")
        raise HTTPException(
            status_code=404,
            detail=f"첨부파일 {attachment_id}의 메타데이터를 찾을 수 없습니다. 티켓 ID와 함께 다시 시도해보세요."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"첨부파일 메타데이터 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류")


@router.get("/bulk-urls")
async def get_bulk_attachment_urls(
    attachment_ids: str = Query(..., description="쉼표로 구분된 첨부파일 ID 목록"),
    ticket_id: Optional[int] = Query(None, description="공통 티켓 ID")
):
    """
    여러 첨부파일의 다운로드 URL을 한 번에 발급받습니다.
    
    대화창에서 여러 이미지를 동시에 표시해야 할 때 유용합니다.
    성능 최적화를 위해 동시 요청으로 처리됩니다.
    
    Args:
        attachment_ids: 쉼표로 구분된 첨부파일 ID 목록 (예: "123,456,789")
        ticket_id: 모든 첨부파일이 속한 공통 티켓 ID (있는 경우)
        
    Returns:
        Dict: 각 첨부파일 ID별 URL 정보
        
    Example:
        GET /attachments/bulk-urls?attachment_ids=123,456,789&ticket_id=999
    """
    try:
        # 첨부파일 ID 목록 파싱
        id_list = [int(id.strip()) for id in attachment_ids.split(",")]
        logger.info(f"다중 첨부파일 URL 발급 요청: {len(id_list)}개")
        
        # 동시 요청으로 성능 최적화
        tasks = []
        for attachment_id in id_list:
            task = get_freshdesk_attachment_url(
                attachment_id=attachment_id,
                ticket_id=ticket_id
            )
            tasks.append(task)
        
        # 모든 요청을 동시에 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 결과 정리
        response = {}
        for attachment_id, result in zip(id_list, results):
            if isinstance(result, Exception):
                logger.error(f"첨부파일 {attachment_id} URL 발급 실패: {result}")
                response[str(attachment_id)] = {
                    "success": False,
                    "error": str(result)
                }
            else:
                response[str(attachment_id)] = {
                    "success": True,
                    "data": result
                }
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail="유효하지 않은 첨부파일 ID 형식")
    except Exception as e:
        logger.error(f"다중 첨부파일 URL 발급 중 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류")


# 프록시 다운로드 엔드포인트 (선택사항)
@router.get("/{attachment_id}/download")
async def download_attachment_proxy(
    attachment_id: int,
    ticket_id: Optional[int] = Query(None),
    conversation_id: Optional[int] = Query(None)
):
    """
    첨부파일을 프록시를 통해 다운로드합니다.
    
    클라이언트가 직접 Freshdesk의 pre-signed URL에 접근하지 않고
    백엔드를 통해 파일을 다운로드할 때 사용합니다.
    
    주의: 대용량 파일의 경우 메모리 사용량과 네트워크 대역폭을 고려해야 합니다.
    """
    from fastapi.responses import StreamingResponse
    
    try:
        # 최신 URL 발급
        attachment_data = await get_freshdesk_attachment_url(
            attachment_id=attachment_id,
            ticket_id=ticket_id,
            conversation_id=conversation_id
        )
        
        # 파일 스트리밍 다운로드
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", attachment_data["download_url"]) as response:
                response.raise_for_status()
                
                return StreamingResponse(
                    response.aiter_bytes(),
                    media_type=attachment_data["content_type"],
                    headers={
                        "Content-Disposition": f'attachment; filename="{attachment_data["name"]}"'
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"첨부파일 프록시 다운로드 중 오류: {e}")
        raise HTTPException(status_code=500, detail="파일 다운로드 실패")
