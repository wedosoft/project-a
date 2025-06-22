"""
멀티플랫폼 첨부파일 API 엔드포인트
기존 attachments.py를 멀티플랫폼/멀티테넌트 구조로 리팩토링

S3 pre-signed URL 만료 문제를 해결하기 위한 실시간 URL 발급 및 상담사 검색 지원
표준 4개 헤더(X-Company-ID, X-Platform, X-Domain, X-API-Key) 사용
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional, List

import httpx
from core.database.vectordb import vector_db
from core.platforms.factory import PlatformFactory
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

# 표준 헤더 의존성 import (절대경로)
from api.dependencies import get_company_id, get_platform, get_api_key, get_domain

# .env 파일 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attachments", tags=["attachments"])


class AttachmentResponse(BaseModel):
    """첨부파일 응답 모델 - 멀티플랫폼 지원"""
    id: str
    name: str
    content_type: str
    size: int
    download_url: str
    expires_at: str
    ticket_id: Optional[str] = None
    conversation_id: Optional[str] = None
    platform: str
    company_id: str


class AttachmentMetadata(BaseModel):
    """첨부파일 메타데이터 모델 - 멀티플랫폼 지원"""
    id: str
    name: str
    content_type: str
    size: int
    ticket_id: Optional[str] = None
    conversation_id: Optional[str] = None
    platform: str
    company_id: str


def get_platform_adapter(platform: str, company_id: str, domain: str, api_key: str):
    """
    플랫폼별 어댑터 생성 - 표준 헤더 기반
    """
    config = {
        "platform": platform,
        "company_id": company_id,
        "domain": domain,
        "api_key": api_key
    }
    return PlatformFactory.create_adapter(platform, config)


async def get_attachment_download_url_multi_platform(
    attachment_id: str,
    platform: str,
    company_id: str,
    domain: str,
    api_key: str,
    ticket_id: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    멀티플랫폼 첨부파일의 최신 pre-signed URL을 발급받습니다.
    
    Args:
        attachment_id: 첨부파일 ID
        platform: 플랫폼 이름 (freshdesk, zendesk 등)
        company_id: 테넌트 식별자
        domain: 플랫폼 도메인
        api_key: 플랫폼 API 키
        ticket_id: 티켓 ID (선택사항)
        conversation_id: 대화 ID (선택사항)
        
    Returns:
        Dict: 첨부파일 정보와 다운로드 URL을 포함한 딕셔너리
        
    Raises:
        HTTPException: API 호출 실패 시
    """
    try:
        # 플랫폼별 어댑터 생성
        adapter = get_platform_adapter(platform, company_id, domain, api_key)
        
        async with adapter:
            # 어댑터를 통해 첨부파일 URL 발급
            attachment_data = await adapter.get_attachment_download_url(
                attachment_id=attachment_id,
                ticket_id=ticket_id,
                conversation_id=conversation_id
            )
            
            logger.info(f"첨부파일 {attachment_id} URL 발급 완료 (platform={platform}, company_id={company_id}): {attachment_data.get('name', 'Unknown')}")
            return attachment_data
            
    except Exception as e:
        logger.error(f"첨부파일 URL 발급 중 오류 (platform={platform}, company_id={company_id}): {e}")
        raise HTTPException(status_code=500, detail=f"첨부파일 URL 발급 실패: {str(e)}")


@router.get("/{attachment_id}/download-url", response_model=AttachmentResponse)
async def get_attachment_download_url(
    attachment_id: str,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    domain: str = Depends(get_domain),
    api_key: str = Depends(get_api_key),
    ticket_id: Optional[str] = None,
    conversation_id: Optional[str] = None
):
    """
    멀티플랫폼 첨부파일의 최신 다운로드 URL을 발급받습니다.
    
    이 엔드포인트는 플랫폼별 pre-signed URL 만료 문제를 해결하기 위해
    매번 새로운 URL을 동적으로 발급받습니다.
    
    표준 4개 헤더(X-Company-ID, X-Platform, X-Domain, X-API-Key)를 통해
    플랫폼 정보를 받습니다.
    
    Args:
        attachment_id: 첨부파일 고유 ID
        company_id: 회사 ID (헤더)
        platform: 플랫폼 이름 (헤더)
        domain: 플랫폼 도메인 (헤더)
        api_key: API 키 (헤더)
        ticket_id: 첨부파일이 속한 티켓 ID (선택사항)
        conversation_id: 첨부파일이 속한 대화 ID (선택사항)
        
    Returns:
        AttachmentResponse: 첨부파일 정보와 유효한 다운로드 URL
    """
    logger.info(f"첨부파일 {attachment_id} 다운로드 URL 요청 (platform={platform}, company_id={company_id}, ticket_id={ticket_id}, conversation_id={conversation_id})")
    
    try:
        # 멀티플랫폼 URL 발급
        attachment_data = await get_attachment_download_url_multi_platform(
            attachment_id=attachment_id,
            platform=platform,
            company_id=company_id,
            domain=domain,
            api_key=api_key,
            ticket_id=ticket_id,
            conversation_id=conversation_id
        )
        
        # 응답 모델에 맞게 변환
        response = AttachmentResponse(
            id=str(attachment_data["id"]),
            name=attachment_data["name"],
            content_type=attachment_data["content_type"],
            size=attachment_data["size"],
            download_url=attachment_data["download_url"],
            expires_at=attachment_data["expires_at"],
            ticket_id=attachment_data.get("ticket_id"),
            conversation_id=attachment_data.get("conversation_id"),
            platform=attachment_data["platform"],
            company_id=attachment_data["company_id"]
        )
        
        logger.info(f"첨부파일 {attachment_id} URL 발급 완료: {attachment_data['name']}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"첨부파일 URL 발급 중 예상치 못한 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류")


@router.get("/{attachment_id}/metadata", response_model=AttachmentMetadata)
async def get_attachment_metadata(
    attachment_id: str,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform)
):
    """
    벡터 DB에서 첨부파일 메타데이터를 조회합니다.
    
    실제 파일 다운로드 없이 첨부파일의 기본 정보만 조회할 때 사용합니다.
    이 정보는 벡터 DB에 캐시되어 있어 빠르게 응답됩니다.
    
    표준 4개 헤더를 통해 멀티플랫폼/멀티테넌트 보안이 적용됩니다.
    
    Args:
        attachment_id: 첨부파일 고유 ID
        company_id: 회사 ID (헤더, 필수)
        platform: 플랫폼 이름 (헤더, 필수)
        
    Returns:
        AttachmentMetadata: 첨부파일의 메타데이터
    """
    try:
        logger.info(f"첨부파일 {attachment_id} 메타데이터 조회 중 (platform={platform}, company_id={company_id})...")
        
        # 벡터 DB에서 첨부파일 메타데이터 검색
        attachment_data = None
        
        # 벡터 DB 검색 필터 구성 - 멀티테넌트 보안 적용
        search_filters = []
        
        # 필수 헤더로 전달된 platform과 company_id 필터 추가
        search_filters.append(FieldCondition(key="platform", match=MatchValue(value=platform)))
        search_filters.append(FieldCondition(key="company_id", match=MatchValue(value=company_id)))
        
        # scroll API를 사용하여 문서에서 첨부파일 메타데이터 검색
        offset = 0
        batch_size = 100
        
        while offset < 1000:  # 최대 1000개 문서까지만 검색 (성능 고려)
            # 벡터 DB에서 배치 단위로 문서 검색
            scroll_result = vector_db.client.scroll(
                collection_name=vector_db.collection_name,
                offset=offset,
                limit=batch_size,
                with_payload=True,
                with_vectors=False,
                filter=Filter(must=search_filters) if search_filters else None
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
                        if isinstance(att, dict) and str(att.get("id")) == str(attachment_id):
                            attachment_data = {
                                "id": str(att.get("id")),
                                "name": att.get("name", "unknown"),
                                "content_type": att.get("content_type", "application/octet-stream"),
                                "size": att.get("size", 0),
                                "ticket_id": str(payload.get("original_id", "")) if payload.get("doc_type") == "ticket" else None,
                                "platform": payload.get("platform", "unknown"),
                                "company_id": payload.get("company_id", "unknown")
                            }
                            logger.info(f"첨부파일 {attachment_id} 메타데이터 발견: {attachment_data['name']} (platform={attachment_data['platform']}, company_id={attachment_data['company_id']})")
                            break
            
            if attachment_data:
                break
                
            # 다음 배치로 이동
            if next_offset is None:
                break
            offset = next_offset
        
        # 첨부파일 메타데이터를 찾은 경우
        if attachment_data:
            return AttachmentMetadata(**attachment_data)
            
        # 벡터 DB에서 찾지 못한 경우, 404 오류 반환
        logger.warning(f"첨부파일 {attachment_id} 메타데이터를 찾을 수 없습니다 (platform={platform}, company_id={company_id})")
        raise HTTPException(
            status_code=404,
            detail=f"첨부파일 {attachment_id}의 메타데이터를 찾을 수 없습니다. 플랫폼과 테넌트 정보를 확인하거나 티켓 ID와 함께 다시 시도해보세요."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"첨부파일 메타데이터 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류")


@router.get("/bulk-urls")
async def get_bulk_attachment_urls(
    attachment_ids: str,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    domain: str = Depends(get_domain),
    api_key: str = Depends(get_api_key),
    ticket_id: Optional[str] = None
):
    """
    여러 첨부파일의 다운로드 URL을 한 번에 발급받습니다.
    
    대화창에서 여러 이미지를 동시에 표시해야 할 때 유용합니다.
    성능 최적화를 위해 동시 요청으로 처리됩니다.
    
    표준 4개 헤더(X-Company-ID, X-Platform, X-Domain, X-API-Key)를 통해
    플랫폼 정보를 받습니다.
    
    Args:
        attachment_ids: 쉼표로 구분된 첨부파일 ID 목록 (예: "123,456,789")
        company_id: 회사 ID (헤더)
        platform: 플랫폼 이름 (헤더)
        domain: 플랫폼 도메인 (헤더)
        api_key: API 키 (헤더)
        ticket_id: 모든 첨부파일이 속한 공통 티켓 ID (있는 경우)
        
    Returns:
        Dict: 각 첨부파일 ID별 URL 정보
    """
    try:
        # 첨부파일 ID 목록 파싱
        id_list = [id.strip() for id in attachment_ids.split(",")]
        logger.info(f"다중 첨부파일 URL 발급 요청: {len(id_list)}개 (platform={platform}, company_id={company_id})")
        
        # 동시 요청으로 성능 최적화
        tasks = []
        for attachment_id in id_list:
            task = get_attachment_download_url_multi_platform(
                attachment_id=attachment_id,
                platform=platform,
                company_id=company_id,
                domain=domain,
                api_key=api_key,
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


# 프록시 다운로드 엔드포인트 (선택사항) - 멀티플랫폼 지원
@router.get("/{attachment_id}/download")
async def download_attachment_proxy(
    attachment_id: str,
    platform: str = Query(..., description="플랫폼 이름 (freshdesk, zendesk 등)"),
    company_id: str = Query(..., description="테넌트 식별자"),
    ticket_id: Optional[str] = Query(None),
    conversation_id: Optional[str] = Query(None)
):
    """
    첨부파일을 프록시를 통해 다운로드합니다.
    
    클라이언트가 직접 플랫폼의 pre-signed URL에 접근하지 않고
    백엔드를 통해 파일을 다운로드할 때 사용합니다.
    
    주의: 대용량 파일의 경우 메모리 사용량과 네트워크 대역폭을 고려해야 합니다.
    """
    from fastapi.responses import StreamingResponse
    
    try:
        # 최신 URL 발급
        attachment_data = await get_attachment_download_url_multi_platform(
            attachment_id=attachment_id,
            platform=platform,
            company_id=company_id,
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


# 헤더 기반 API (하위 호환성 지원)
@router.get("/legacy/{attachment_id}/download-url", response_model=AttachmentResponse)
async def get_attachment_download_url_legacy(
    attachment_id: str,
    x_platform: str = Header(..., alias="X-Platform", description="플랫폼 이름"),
    x_company_id: str = Header(..., alias="X-Company-ID", description="테넌트 식별자"),
    ticket_id: Optional[str] = Query(None, description="첨부파일이 속한 티켓 ID"),
    conversation_id: Optional[str] = Query(None, description="첨부파일이 속한 대화 ID")
):
    """
    헤더 기반 첨부파일 URL 발급 (하위 호환성 지원)
    
    기존 클라이언트가 헤더로 플랫폼 정보를 전송하는 경우를 위한 엔드포인트
    """
    return await get_attachment_download_url(
        attachment_id=attachment_id,
        platform=x_platform,
        company_id=x_company_id,
        ticket_id=ticket_id,
        conversation_id=conversation_id
    )
